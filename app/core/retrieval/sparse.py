"""Sparse lexical retrieval with BM25.

An in-memory Okapi BM25 index over chunk texts. English tokenization only for
this pass; Arabic tokenization lands with the v1.1 Arabic pass. The index is
rebuilt from the vector store's payloads when the corpus changes.
"""

from __future__ import annotations

import re
from typing import Any

from rank_bm25 import BM25Okapi

from app.store.base import SearchHit, VectorPoint

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """English tokenization: lowercase alphanumeric runs."""
    return _TOKEN_RE.findall(text.lower())


class SparseIndex:
    """BM25 inverted index over a list of documents."""

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._payloads: dict[str, dict[str, Any]] = {}
        self._bm25: BM25Okapi | None = None
        self.size = 0

    def build(self, points: list[VectorPoint]) -> None:
        tokenized: list[list[str]] = []
        self._ids = []
        self._payloads = {}
        for point in points:
            self._ids.append(point.id)
            self._payloads[point.id] = point.payload
            tokenized.append(tokenize(point.payload.get("text", "")))
        self._bm25 = BM25Okapi(tokenized)
        self.size = len(points)

    def is_built(self) -> bool:
        return self._bm25 is not None

    def search(self, query: str, limit: int = 20) -> list[SearchHit]:
        if self._bm25 is None or not self._bm25.corpus_size:
            return []
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scores = self._bm25.get_scores(query_tokens)
        ranked = sorted(zip(self._ids, scores, strict=True), key=lambda t: t[1], reverse=True)
        hits: list[SearchHit] = []
        for chunk_id, score in ranked:
            if score <= 0:
                continue
            hits.append(
                SearchHit(
                    id=chunk_id,
                    score=float(score),
                    payload=self._payloads.get(chunk_id, {}),
                )
            )
            if len(hits) >= limit:
                break
        return hits
