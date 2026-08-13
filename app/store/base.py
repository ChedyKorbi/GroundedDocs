"""Vector store abstraction.

The store interface keeps ingestion, deduplication, and retrieval independent of
the concrete backend (Qdrant in production, in-memory in tests). Phase 2 extends
this with named-collection + alias-swap semantics for zero-downtime re-indexing.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class VectorPoint(BaseModel):
    id: str
    vector: list[float]
    payload: dict[str, Any] = Field(default_factory=dict)


class SearchHit(BaseModel):
    id: str
    score: float
    payload: dict[str, Any] = Field(default_factory=dict)


class VectorStore(Protocol):
    def ensure_collection(self) -> None: ...

    def upsert(self, points: list[VectorPoint]) -> None: ...

    def search(
        self,
        vector: list[float],
        limit: int = 10,
        filter_payload: dict[str, Any] | None = None,
    ) -> list[SearchHit]: ...

    def count(self) -> int: ...

    def all_points(self) -> list[VectorPoint]: ...

    def delete_by_document(self, document_id: str) -> bool: ...
