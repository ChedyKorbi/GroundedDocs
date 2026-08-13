"""Duplicate detection at scale.

Dedup queries the vector index itself — a top-k nearest-neighbor lookup per new
chunk — rather than an all-pairs cosine pass. This keeps the cost per chunk at
the index's search complexity instead of O(n^2) in corpus size.

Decisions:
- score >= threshold  -> duplicate candidate.
- mode "skip"         -> chunk is not inserted.
- mode "flag"         -> chunk is inserted but marked as a duplicate.
- scope "all"         -> search across the whole index (cross-document copies).
- scope "same_document" -> search only within the document being ingested.
"""

from __future__ import annotations

from app.core.ingestion.models import DedupInfo
from app.store.base import VectorStore


class Deduplicator:
    """Nearest-neighbor duplicate check backed by a vector store."""

    def __init__(
        self,
        store: VectorStore,
        threshold: float = 0.95,
        mode: str = "skip",
        scope: str = "all",
        top_k: int = 5,
    ) -> None:
        if threshold <= 0 or threshold > 1:
            raise ValueError("dedup threshold must be in (0, 1]")
        if mode not in {"skip", "flag"}:
            raise ValueError("dedup mode must be 'skip' or 'flag'")
        if scope not in {"all", "same_document"}:
            raise ValueError("dedup scope must be 'all' or 'same_document'")
        self.store = store
        self.threshold = threshold
        self.mode = mode
        self.scope = scope
        self.top_k = top_k

    def check(self, vector: list[float], document_id: str) -> DedupInfo:
        """Return the dedup decision for a chunk embedding."""
        filter_payload = None
        if self.scope == "same_document":
            filter_payload = {"document_id": document_id}
        hits = self.store.search(vector, limit=self.top_k, filter_payload=filter_payload)
        for hit in hits:
            if hit.score >= self.threshold:
                decision = "skip" if self.mode == "skip" else "flag"
                return DedupInfo(
                    decision=decision,
                    score=hit.score,
                    match_chunk_id=hit.id,
                    checked_against=len(hits),
                )
        best = hits[0].score if hits else 0.0
        return DedupInfo(decision="insert", score=best, checked_against=len(hits))
