"""Shared retrieval-evaluation helpers (golden-set resolution + metrics)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from app.core.evaluation.recall import mrr, recall_at_k
from app.services.retrieval import HybridRetriever
from app.store.base import VectorStore


def load_golden(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def resolve_gold_chunks(store: VectorStore, golden: dict[str, Any]) -> dict[str, set[str]]:
    """Map question id -> set of chunk ids matching (document_id, section leaf).

    The gold `section` is matched against the LAST component of the stored
    heading path (e.g. "Incident Commander" matches ".../Roles/Incident
    Commander"), which is precise when a section contains sub-headings.
    """
    resolved: dict[str, set[str]] = {}
    for entry in golden["questions"]:
        chunk_ids: set[str] = set()
        for gold in entry["gold"]:
            for point in store.all_points():
                payload = point.payload
                if payload.get("document_id") != gold["document_id"]:
                    continue
                section = (payload.get("metadata") or {}).get("section") or ""
                leaf = section.split(" / ")[-1]
                if leaf == gold["section"]:
                    chunk_ids.add(point.id)
        resolved[entry["id"]] = chunk_ids
    return resolved


def run_retrieval_metrics(
    retriever: HybridRetriever,
    questions: list[dict[str, Any]],
    gold_map: dict[str, set[str]],
    top_k: int = 5,
    method: str = "hybrid",
) -> list[dict[str, Any]]:
    """Per-question recall@k / MRR for one retrieval method."""
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
    return results


def average_metrics(results: list[dict[str, Any]]) -> dict[str, float]:
    if not results:
        return {"recall@1": 0.0, "recall@3": 0.0, "recall@5": 0.0, "mrr": 0.0}
    n = len(results)
    return {
        "recall@1": round(sum(r["recall_1"] for r in results) / n, 4),
        "recall@3": round(sum(r["recall_3"] for r in results) / n, 4),
        "recall@5": round(sum(r["recall_5"] for r in results) / n, 4),
        "mrr": round(sum(r["mrr"] for r in results) / n, 4),
    }
