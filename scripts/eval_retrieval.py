"""Retrieval-only evaluation: hybrid vs dense-only vs sparse-only.

Usage:
    uv run python scripts/eval_retrieval.py [--top-k 5] [--no-rerank]

Connects to the Qdrant index, builds the sparse index, and computes recall@1/3/5
and MRR for four methods: dense-only, sparse-only, hybrid, hybrid+rerank.
Results are printed and saved to data/eval/reports/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import QdrantClient

from app.config import get_settings
from app.core.evaluation.recall import mrr, recall_at_k
from app.core.evaluation.retrieval_eval import (
    resolve_gold_chunks,
)
from app.core.retrieval.rerank import CrossEncoderReranker
from app.core.retrieval.sparse import SparseIndex
from app.services.embeddings import EmbeddingService
from app.services.retrieval import HybridRetriever
from app.store.qdrant import QdrantStore

GOLDEN_PATH = Path("data/eval/retrieval_golden.json")
REPORT_DIR = Path("data/eval/reports")


def run_method(
    retriever: HybridRetriever,
    questions: list[dict[str, Any]],
    gold_map: dict[str, set[str]],
    top_k: int,
    method: str,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for entry in questions:
        result = retriever.retrieve(
            entry["question"],
            top_k=max(top_k, 5),
            dense_only=method == "dense_only",
            sparse_only=method == "sparse_only",
        )
        ids = [c.chunk_id for c in result.chunks]
        gold = gold_map.get(entry["id"], set())
        results.append(
            {
                "id": entry["id"],
                "recall_1": recall_at_k(ids, gold, 1),
                "recall_3": recall_at_k(ids, gold, 3),
                "recall_5": recall_at_k(ids, gold, 5),
                "mrr": mrr(ids, gold),
            }
        )
    n = len(results)
    averages = {
        "recall@1": round(sum(r["recall_1"] for r in results) / n, 4),
        "recall@3": round(sum(r["recall_3"] for r in results) / n, 4),
        "recall@5": round(sum(r["recall_5"] for r in results) / n, 4),
        "mrr": round(sum(r["mrr"] for r in results) / n, 4),
    }
    return {"results": results, "averages": averages}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--no-rerank", action="store_true", help="skip the cross-encoder rerank method"
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    store = QdrantStore(
        collection=settings.qdrant_collection,
        vector_size=settings.models.embedding_dim,
        client=client,
    )
    store.ensure_collection()
    embedder = EmbeddingService(model_id=settings.models.embedding_model_id)
    sparse = SparseIndex()
    sparse.build(store.all_points())
    print(f"index chunks: {store.count()}, sparse built: {sparse.size}", file=sys.stderr)

    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    gold_map = resolve_gold_chunks(store, golden)
    unresolved = [qid for qid, gold in gold_map.items() if not gold]
    if unresolved:
        print(f"WARNING: no gold chunks resolved for: {unresolved}", file=sys.stderr)

    questions = golden["questions"]

    def make_retriever(reranker: Any = None) -> HybridRetriever:
        return HybridRetriever(
            store=store,
            embedder=embedder,
            sparse=sparse,
            reranker=reranker,
            reranker_name="cross_encoder" if reranker else None,
            dense_k=settings.retrieval_dense_k,
            sparse_k=settings.retrieval_sparse_k,
            fused_k=settings.retrieval_fused_k,
            rrf_k=settings.fusion_rrf_k,
            dense_weight=settings.fusion_dense_weight,
            sparse_weight=settings.fusion_sparse_weight,
        )

    start = time.perf_counter()
    base = make_retriever()
    methods: dict[str, dict[str, Any]] = {
        "dense_only": run_method(base, questions, gold_map, args.top_k, "dense_only"),
        "sparse_only": run_method(base, questions, gold_map, args.top_k, "sparse_only"),
        "hybrid": run_method(base, questions, gold_map, args.top_k, "hybrid"),
    }
    if not args.no_rerank:
        reranker = CrossEncoderReranker(settings.models.reranker_cross_encoder_id)
        methods["hybrid_rerank"] = run_method(
            make_retriever(reranker), questions, gold_map, args.top_k, "hybrid"
        )
    elapsed = time.perf_counter() - start

    print("\n=== Retrieval evaluation ===")
    print(f"questions: {len(questions)}   chunks: {store.count()}   elapsed: {elapsed:.1f}s\n")
    header = f"{'method':<16} {'recall@1':>9} {'recall@3':>9} {'recall@5':>9} {'mrr':>6}"
    print(header)
    print("-" * len(header))
    for name, data in methods.items():
        a = data["averages"]
        print(
            f"{name:<16} {a['recall@1']:>9.4f} {a['recall@3']:>9.4f} "
            f"{a['recall@5']:>9.4f} {a['mrr']:>6.4f}"
        )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"retrieval_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "chunks": store.count(),
                "questions": len(questions),
                "model": {
                    "embedding": settings.models.embedding_model_id,
                    "reranker": settings.models.reranker_cross_encoder_id,
                },
                "methods": {name: data["averages"] for name, data in methods.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nreport saved: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
