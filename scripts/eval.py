"""GroundedDocs evaluation harness.

Usage:
    uv run python scripts/eval.py                 # full golden-set eval on hybrid
    uv run python scripts/eval.py --method dense_only
    uv run python scripts/eval.py --limit 5       # quick subset
    uv run python scripts/eval.py compare         # hybrid vs dense vs sparse
    uv run python scripts/eval.py calibration     # judge vs human agreement
    uv run python scripts/eval.py chunking        # chunking strategy shootout

Requires a running Qdrant index seeded with data/samples and GROQ_API_KEY set.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import QdrantClient

from app.config import Settings
from app.core.evaluation.judges import FaithfulnessJudge, RelevanceJudge
from app.core.evaluation.recall import mrr, recall_at_k
from app.core.evaluation.retrieval_eval import (
    average_metrics,
    load_golden,
    resolve_gold_chunks,
)
from app.core.retrieval.rerank import CrossEncoderReranker
from app.core.retrieval.sparse import SparseIndex
from app.services.container import AppServices
from app.services.embeddings import EmbeddingService
from app.services.generation import GenerationResult, GenerationService
from app.services.ingestion import IngestionPipeline
from app.services.llm import LLMClient
from app.services.retrieval import HybridRetriever
from app.store.qdrant import QdrantStore

GOLDEN_PATH = Path("data/eval/golden.json")
CALIBRATION_PATH = Path("data/eval/calibration_labels.json")
REPORT_DIR = Path("data/eval/reports")
SAMPLES_DIR = Path("data/samples")

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _token_set(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 4)


class EvalContext:
    """Bundled services shared across a single evaluation run."""

    def __init__(
        self,
        settings: Settings,
        store: QdrantStore,
        embedder: EmbeddingService,
        sparse: SparseIndex,
        llm: LLMClient,
        judge_llm: LLMClient,
        generation: GenerationService,
    ) -> None:
        self.settings = settings
        self.store = store
        self.embedder = embedder
        self.sparse = sparse
        self.llm = llm
        self.judge_llm = judge_llm
        self.generation = generation

    def retriever(self, reranker: Any = None, reranker_name: str | None = None) -> HybridRetriever:
        return HybridRetriever(
            store=self.store,
            embedder=self.embedder,
            sparse=self.sparse,
            reranker=reranker,
            reranker_name=reranker_name,
            dense_k=self.settings.retrieval_dense_k,
            sparse_k=self.settings.retrieval_sparse_k,
            fused_k=self.settings.retrieval_fused_k,
            rrf_k=self.settings.fusion_rrf_k,
            dense_weight=self.settings.fusion_dense_weight,
            sparse_weight=self.settings.fusion_sparse_weight,
        )


def build_context() -> EvalContext:
    services = AppServices()
    judge_llm = LLMClient(
        api_keys=services.settings.effective_groq_keys,
        model=services.settings.models.judge_model,
        temperature=0.0,
        max_tokens=512,
    )
    return EvalContext(
        settings=services.settings,
        store=services.store,
        embedder=services.embedder,
        sparse=services.sparse,
        llm=services.generation.llm,
        judge_llm=judge_llm,
        generation=services.generation,
    )


def evaluate_question(
    entry: dict[str, Any],
    retriever: HybridRetriever,
    ctx: EvalContext,
    faithful: FaithfulnessJudge,
    relevant: RelevanceJudge,
    gold_map: dict[str, set[str]],
    top_k: int,
    method: str,
) -> tuple[dict[str, Any], GenerationResult]:
    qid = entry["id"]
    question = entry["question"]
    retrieval = retriever.retrieve(
        question,
        top_k=max(top_k, 5),
        dense_only=method == "dense_only",
        sparse_only=method == "sparse_only",
    )
    ids = [c.chunk_id for c in retrieval.chunks]
    gold = gold_map.get(qid, set())
    result = ctx.generation.generate(question, retrieval)

    row: dict[str, Any] = {
        "id": qid,
        "category": entry["category"],
        "question": question,
        "recall_1": recall_at_k(ids, gold, 1),
        "recall_3": recall_at_k(ids, gold, 3),
        "recall_5": recall_at_k(ids, gold, 5),
        "mrr": mrr(ids, gold),
        "expected_insufficient": entry.get("expected_insufficient", False),
        "insufficient": result.insufficient,
        "answer": result.answer,
        "confidence": result.confidence.composite,
        "num_citations": len(result.citations),
        "supported_citations": sum(1 for c in result.citations if c.supported),
        "citation_accuracy": None,
    }
    if row["num_citations"]:
        row["citation_accuracy"] = round(row["supported_citations"] / row["num_citations"], 4)

    if not result.insufficient and result.answer:
        # Faithfulness judge gets a trimmed context budget (top-3, 600 chars
        # each) to keep eval token cost within free-tier daily caps.
        contexts = [c.text[:600] for c in retrieval.chunks[:3]]
        f = faithful.score(question, result.answer, contexts)
        r = relevant.score(question, result.answer)
        row["faithfulness"] = round(f.score, 4)
        row["relevance"] = round(r.score, 4)
    else:
        row["faithfulness"] = None
        row["relevance"] = None
    return row, result


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [r for r in results if not r["expected_insufficient"]]
    answered = [r for r in results if not r["insufficient"] and r.get("answer")]
    unanswerable = [r for r in results if r["expected_insufficient"]]

    return {
        "questions": len(results),
        "retrieval": average_metrics(answerable),
        "faithfulness": _mean([r["faithfulness"] for r in answered]),
        "relevance": _mean([r["relevance"] for r in answered]),
        "citation_accuracy": _mean([r["citation_accuracy"] for r in answered]),
        "correct_refusal_rate": round(
            sum(1 for r in unanswerable if r["insufficient"]) / len(unanswerable), 4
        )
        if unanswerable
        else None,
        "hallucination_on_unanswerable": round(
            sum(1 for r in unanswerable if not r["insufficient"]) / len(unanswerable), 4
        )
        if unanswerable
        else None,
        "false_refusal_rate": round(
            sum(1 for r in answerable if r["insufficient"]) / len(answerable), 4
        )
        if answerable
        else None,
    }


def failure_analysis(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for r in results:
        if r["expected_insufficient"]:
            if not r["insufficient"]:
                failures.append(
                    {
                        "id": r["id"],
                        "type": "hallucination_on_unanswerable",
                        "root_cause": "model answered despite no supporting evidence in the corpus",
                        "question": r["question"],
                        "answer": r["answer"][:200],
                        "confidence": r["confidence"],
                    }
                )
            continue
        if r["recall_1"] == 0:
            failures.append(
                {
                    "id": r["id"],
                    "type": "retrieval_miss",
                    "root_cause": "gold chunk not ranked first (retrieval stage)",
                    "question": r["question"],
                    "recall_1": r["recall_1"],
                    "recall_3": r["recall_3"],
                }
            )
        if r["insufficient"]:
            failures.append(
                {
                    "id": r["id"],
                    "type": "false_refusal",
                    "root_cause": "model refused despite the corpus containing the answer",
                    "question": r["question"],
                    "confidence": r["confidence"],
                }
            )
        if r["faithfulness"] is not None and r["faithfulness"] < 0.7:
            failures.append(
                {
                    "id": r["id"],
                    "type": "unsupported_content",
                    "root_cause": "faithfulness below 0.7: claims not entailed by context",
                    "question": r["question"],
                    "answer": (r["answer"] or "")[:200],
                    "faithfulness": r["faithfulness"],
                }
            )
        if r.get("num_citations", 0) and r.get("supported_citations", 0) < r["num_citations"]:
            failures.append(
                {
                    "id": r["id"],
                    "type": "unsupported_citation",
                    "root_cause": "citation verification flagged unsupported reference(s)",
                    "question": r["question"],
                    "unsupported": r["num_citations"] - r["supported_citations"],
                    "of": r["num_citations"],
                }
            )
    return failures


def run_calibration(store: QdrantStore, llm: LLMClient, golden: dict[str, Any]) -> dict[str, Any]:
    labels = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))["labels"]
    faithful = FaithfulnessJudge(llm)
    relevant = RelevanceJudge(llm)
    rows: list[dict[str, Any]] = []
    for label in labels:
        contexts: list[str] = []
        for gold_entry in label["gold"]:
            for point in store.all_points():
                payload = point.payload
                if payload.get("document_id") != gold_entry["document_id"]:
                    continue
                leaf = ((payload.get("metadata") or {}).get("section") or "").split(" / ")[-1]
                if leaf == gold_entry["section"]:
                    contexts.append(payload.get("text", ""))
        f = faithful.score(label["question"], label["reference_answer"], contexts)
        r = relevant.score(label["question"], label["reference_answer"])
        judge_faithful = f.score >= 0.5
        judge_relevant = r.score >= 0.5
        rows.append(
            {
                "id": label["id"],
                "human_faithful": label["human_faithful"],
                "judge_faithful": judge_faithful,
                "faithful_score": round(f.score, 3),
                "faithful_agree": judge_faithful == label["human_faithful"],
                "human_relevant": label["human_relevance"] >= 0.5,
                "judge_relevant": judge_relevant,
                "relevance_score": round(r.score, 3),
                "relevance_agree": judge_relevant == (label["human_relevance"] >= 0.5),
            }
        )
    n = len(rows)
    fabricated = [x for x in rows if x["id"].startswith("f")]
    real = [x for x in rows if not x["id"].startswith("f")]
    return {
        "items": rows,
        "faithful_agreement": round(sum(1 for x in rows if x["faithful_agree"]) / n, 4),
        "relevance_agreement": round(sum(1 for x in rows if x["relevance_agree"]) / n, 4),
        "faithful_agreement_real": round(sum(1 for x in real if x["faithful_agree"]) / len(real), 4)
        if real
        else None,
        "faithful_agreement_fabricated": round(
            sum(1 for x in fabricated if x["faithful_agree"]) / len(fabricated), 4
        )
        if fabricated
        else None,
    }


def run_full(method: str, limit: int | None, save: bool = True) -> dict[str, Any]:
    ctx = build_context()
    reranker = CrossEncoderReranker(ctx.settings.models.reranker_cross_encoder_id)
    retriever = ctx.retriever(reranker, "cross_encoder")
    faithful = FaithfulnessJudge(ctx.judge_llm)
    relevant = RelevanceJudge(ctx.judge_llm)

    golden = load_golden(GOLDEN_PATH)
    gold_map = resolve_gold_chunks(ctx.store, golden)
    questions = golden["questions"][:limit] if limit else golden["questions"]

    results: list[dict[str, Any]] = []
    for entry in questions:
        row, _result = evaluate_question(
            entry, retriever, ctx, faithful, relevant, gold_map, 5, method
        )
        results.append(row)
        print(
            f"  {row['id']:>4} [{row['category']:<12}] rec@1={row['recall_1']:.2f} "
            f"insuf={row['insufficient']} faith={row['faithfulness']}",
            file=sys.stderr,
        )

    agg = aggregate(results)
    failures = failure_analysis(results)
    calibration = run_calibration(ctx.store, ctx.judge_llm, golden)

    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "method": method,
        "questions": len(results),
        "models": {
            "embedding": ctx.settings.models.embedding_model_id,
            "llm": ctx.settings.models.llm_model,
            "judge": ctx.settings.models.judge_model,
            "reranker": ctx.settings.models.reranker_cross_encoder_id,
        },
        "aggregates": agg,
        "calibration": calibration,
        "failures": failures,
        "results": results,
    }
    if save:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORT_DIR / f"eval_{method}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["report_path"] = str(path)
    return report


def print_report(report: dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print(f"EVALUATION — method: {report['method']}  ({report['questions']} questions)")
    print("=" * 60)
    a = report["aggregates"]
    r = a["retrieval"]
    print(
        f"retrieval:            recall@1={r['recall@1']:.4f}  recall@3={r['recall@3']:.4f}  "
        f"recall@5={r['recall@5']:.4f}  mrr={r['mrr']:.4f}"
    )
    print(f"faithfulness:         {a['faithfulness']}")
    print(f"answer relevance:     {a['relevance']}")
    print(f"citation accuracy:    {a['citation_accuracy']}")
    print(f"correct refusal rate: {a['correct_refusal_rate']}")
    print(f"false refusal rate:   {a['false_refusal_rate']}")
    print(f"hallucination on unanswerable: {a['hallucination_on_unanswerable']}")
    c = report["calibration"]
    print("\n-- judge calibration (human vs judge agreement) --")
    print(
        f"faithfulness agreement: {c['faithful_agreement']}  "
        f"(real={c['faithful_agreement_real']}, fabricated={c['faithful_agreement_fabricated']})"
    )
    print(f"relevance agreement:    {c['relevance_agreement']}")
    print(f"\nfailures: {len(report['failures'])}")
    for f in report["failures"]:
        print(f"  [{f['type']}] {f['id']}: {f['root_cause']}")
    if "report_path" in report:
        print(f"\nreport saved: {report['report_path']}")


def translate_gold_terms(
    source_points: list[Any], target_points: list[Any], gold_entries: list[dict[str, Any]]
) -> set[str]:
    """Resolve gold chunk ids in a target index via token overlap with source texts."""
    gold_ids: set[str] = set()
    for gold_entry in gold_entries:
        src_tokens: set[str] = set()
        for p in source_points:
            payload = p.payload
            if payload.get("document_id") != gold_entry["document_id"]:
                continue
            leaf = ((payload.get("metadata") or {}).get("section") or "").split(" / ")[-1]
            if leaf == gold_entry["section"]:
                src_tokens |= _token_set(payload.get("text", ""))
        if not src_tokens:
            continue
        for p in target_points:
            target_tokens = _token_set(p.payload.get("text", ""))
            overlap = len(target_tokens & src_tokens) / len(src_tokens)
            if overlap >= 0.5:
                gold_ids.add(p.id)
    return gold_ids


def run_chunking() -> dict[str, Any]:
    ctx = build_context()
    client = QdrantClient(url=ctx.settings.qdrant_url)
    source = QdrantStore(
        collection=ctx.store.collection,
        vector_size=ctx.settings.models.embedding_dim,
        client=client,
    )
    source_points = source.all_points()
    golden = load_golden(GOLDEN_PATH)
    questions = golden["questions"]
    comparison: dict[str, dict[str, Any]] = {}
    created: list[str] = []
    try:
        for strategy in ("structure", "fixed", "semantic"):
            collection = f"eval-{strategy}"
            created.append(collection)
            store = QdrantStore(
                collection=collection,
                vector_size=ctx.settings.models.embedding_dim,
                client=client,
            )
            store.ensure_collection()
            pipeline = IngestionPipeline(
                embedder=ctx.embedder,
                store=store,
                chunk_size=ctx.settings.ingestion_chunk_size,
                overlap=ctx.settings.ingestion_overlap,
                default_strategy=strategy,
                dedup=None,
            )
            pipeline.ingest_directory(SAMPLES_DIR)
            sparse = SparseIndex()
            sparse.build(store.all_points())
            target_points = store.all_points()
            retriever = HybridRetriever(
                store=store,
                embedder=ctx.embedder,
                sparse=sparse,
                dense_k=ctx.settings.retrieval_dense_k,
                sparse_k=ctx.settings.retrieval_sparse_k,
                fused_k=ctx.settings.retrieval_fused_k,
                rrf_k=ctx.settings.fusion_rrf_k,
                dense_weight=ctx.settings.fusion_dense_weight,
                sparse_weight=ctx.settings.fusion_sparse_weight,
            )

            rows: list[dict[str, Any]] = []
            for entry in questions:
                if entry["expected_insufficient"] or not entry.get("gold"):
                    continue
                gold = translate_gold_terms(source_points, target_points, entry["gold"])
                result = retriever.retrieve(entry["question"], top_k=5)
                ids = [c.chunk_id for c in result.chunks]
                rows.append(
                    {
                        "id": entry["id"],
                        "recall_1": recall_at_k(ids, gold, 1),
                        "recall_3": recall_at_k(ids, gold, 3),
                        "recall_5": recall_at_k(ids, gold, 5),
                        "mrr": mrr(ids, gold),
                        "gold_size": len(gold),
                    }
                )
            comparison[strategy] = {"chunks": store.count(), "metrics": average_metrics(rows)}
            m = comparison[strategy]["metrics"]
            print(
                f"  {strategy:<10} chunks={store.count():>3}  recall@1={m['recall@1']:.4f} "
                f"recall@3={m['recall@3']:.4f} mrr={m['mrr']:.4f}",
                file=sys.stderr,
            )
    finally:
        for collection in created:
            with contextlib.suppress(Exception):
                client.delete_collection(collection)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"chunking_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    return {"comparison": comparison, "report_path": str(path)}


def cmd_compare(limit: int | None) -> None:
    print("running dense_only ...", file=sys.stderr)
    dense = run_full("dense_only", limit, save=True)
    print("\nrunning sparse_only ...", file=sys.stderr)
    sparse = run_full("sparse_only", limit, save=True)
    print("\nrunning hybrid ...", file=sys.stderr)
    hybrid = run_full("hybrid", limit, save=True)
    methods = {"dense_only": dense, "sparse_only": sparse, "hybrid": hybrid}
    print("\n" + "=" * 70)
    print("COMPARISON")
    print("=" * 70)
    header = (
        f"{'method':<12} {'rec@1':>6} {'rec@3':>6} {'faith':>6} "
        f"{'relev':>6} {'cite':>6} {'refusal':>7}"
    )
    print(header)
    print("-" * len(header))
    for name, rep in methods.items():
        a = rep["aggregates"]
        f_val = f"{a['faithfulness']:.4f}" if a["faithfulness"] is not None else "-"
        r_val = f"{a['relevance']:.4f}" if a["relevance"] is not None else "-"
        c_val = f"{a['citation_accuracy']:.4f}" if a["citation_accuracy"] is not None else "-"
        ref = f"{a['correct_refusal_rate']:.2f}" if a["correct_refusal_rate"] is not None else "-"
        print(
            f"{name:<12} {a['retrieval']['recall@1']:>6.4f} {a['retrieval']['recall@3']:>6.4f} "
            f"{f_val:>6} {r_val:>6} {c_val:>6} {ref:>7}"
        )


def cmd_calibration() -> None:
    ctx = build_context()
    golden = load_golden(GOLDEN_PATH)
    cal = run_calibration(ctx.store, ctx.judge_llm, golden)
    print(
        f"faithfulness agreement: {cal['faithful_agreement']} "
        f"(real={cal['faithful_agreement_real']}, "
        f"fabricated={cal['faithful_agreement_fabricated']})"
    )
    print(f"relevance agreement:    {cal['relevance_agreement']}")
    for row in cal["items"]:
        print(
            f"  {row['id']:>4} human_faithful={row['human_faithful']!s:5} "
            f"judge_faithful={row['judge_faithful']!s:5} score={row['faithful_score']:.2f} "
            f"agree={row['faithful_agree']}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GroundedDocs evaluation harness")
    parser.add_argument(
        "--method", default="hybrid", choices=["hybrid", "dense_only", "sparse_only"]
    )
    parser.add_argument("--limit", type=int, default=None)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("compare", help="hybrid vs dense vs sparse")
    sub.add_parser("calibration", help="judge vs human agreement")
    sub.add_parser("chunking", help="chunking strategy shootout")
    args = parser.parse_args(argv)

    command = args.command or "run"
    if command == "run":
        start = time.perf_counter()
        report = run_full(args.method, args.limit)
        print_report(report)
        print(f"\nfinished in {time.perf_counter() - start:.1f}s")
    elif command == "compare":
        cmd_compare(args.limit)
    elif command == "calibration":
        cmd_calibration()
    elif command == "chunking":
        report = run_chunking()
        for strategy, data in report["comparison"].items():
            m = data["metrics"]
            print(
                f"{strategy:<10} recall@1={m['recall@1']:.4f} "
                f"recall@3={m['recall@3']:.4f} mrr={m['mrr']:.4f}"
            )
        print(f"report saved: {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
