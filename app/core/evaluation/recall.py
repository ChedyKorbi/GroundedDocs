"""Retrieval metrics (pure functions)."""

from __future__ import annotations

from collections.abc import Sequence


def recall_at_k(retrieved: Sequence[str], gold: set[str], k: int) -> float:
    """Fraction of gold chunk ids present in the top-k retrieved ids."""
    if not gold:
        return 0.0
    top_k = set(retrieved[:k])
    hits = len(top_k & gold)
    return hits / len(gold)


def mrr(retrieved: Sequence[str], gold: set[str]) -> float:
    """Reciprocal rank of the first gold hit in the retrieved list."""
    for rank, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in gold:
            return 1.0 / rank
    return 0.0


def precision_at_k(retrieved: Sequence[str], gold: set[str], k: int) -> float:
    """Precision of the top-k retrieved ids against gold."""
    if k == 0:
        return 0.0
    top_k = set(retrieved[:k])
    return len(top_k & gold) / k
