"""Core data models for the ingestion pipeline."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

ChunkStrategy = Literal["fixed", "structure", "semantic"]
DedupDecision = Literal["insert", "skip", "flag"]


class SourceDocument(BaseModel):
    """A raw document loaded from disk or an upload, before chunking."""

    id: str
    source: str
    format: str
    title: str | None = None
    language: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DedupInfo(BaseModel):
    """Result of the duplicate check for a single chunk."""

    decision: DedupDecision
    score: float
    match_chunk_id: str | None = None
    checked_against: int = 0


class Chunk(BaseModel):
    """A unit of retrieval: normalized text + metadata + strategy tag."""

    id: str
    document_id: str
    index: int
    text: str
    strategy: ChunkStrategy
    language: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)
    dedup: DedupInfo | None = None

    @classmethod
    def new(
        cls,
        document_id: str,
        index: int,
        text: str,
        strategy: ChunkStrategy,
        language: str = "en",
        metadata: dict[str, Any] | None = None,
    ) -> Chunk:
        """Build a chunk with a stable, content-addressed id (valid UUID)."""
        digest = hashlib.sha1(f"{document_id}:{index}:{strategy}".encode()).hexdigest()
        chunk_id = str(uuid.UUID(int=int(digest[:16], 16)))
        return cls(
            id=chunk_id,
            document_id=document_id,
            index=index,
            text=text,
            strategy=strategy,
            language=language,
            metadata=metadata or {},
        )
