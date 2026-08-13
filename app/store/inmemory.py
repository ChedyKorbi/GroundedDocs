"""In-memory vector store used by unit tests and fast local demos.

Cosine similarity over a normalized numpy matrix with optional payload filtering.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.store.base import SearchHit, VectorPoint


class InMemoryVectorStore:
    """Naive numpy-backed store; not for production scale."""

    def __init__(self) -> None:
        self._vectors: list[np.ndarray] = []
        self._points: list[VectorPoint] = []
        self._index: dict[str, int] = {}

    def ensure_collection(self) -> None:
        pass

    def upsert(self, points: list[VectorPoint]) -> None:
        for point in points:
            if point.id in self._index:
                i = self._index[point.id]
                self._points[i] = point
                self._vectors[i] = self._normalize(np.asarray(point.vector, dtype=np.float32))
                continue
            self._index[point.id] = len(self._points)
            self._points.append(point)
            self._vectors.append(self._normalize(np.asarray(point.vector, dtype=np.float32)))

    def search(
        self,
        vector: list[float],
        limit: int = 10,
        filter_payload: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        query = self._normalize(np.asarray(vector, dtype=np.float32))
        scores: list[SearchHit] = []
        for i, point in enumerate(self._points):
            if filter_payload and not all(
                point.payload.get(key) == value for key, value in filter_payload.items()
            ):
                continue
            score = float(np.dot(self._vectors[i], query))
            scores.append(SearchHit(id=point.id, score=score, payload=point.payload))
        scores.sort(key=lambda hit: hit.score, reverse=True)
        return scores[:limit]

    def count(self) -> int:
        return len(self._points)

    def items(self) -> list[VectorPoint]:
        """Return all stored points (test/diagnostic accessor)."""
        return list(self._points)

    def all_points(self) -> list[VectorPoint]:
        return list(self._points)

    def delete_by_document(self, document_id: str) -> bool:
        before = len(self._points)
        pairs = [
            (v, p)
            for v, p in zip(self._vectors, self._points, strict=True)
            if p.payload.get("document_id") != document_id
        ]
        self._vectors = [v for v, _ in pairs]
        self._points = [p for _, p in pairs]
        self._index = {p.id: i for i, p in enumerate(self._points)}
        return len(self._points) < before

    @staticmethod
    def _normalize(vector: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(vector))
        return vector / norm if norm > 0 else vector
