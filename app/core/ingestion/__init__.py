"""Ingestion core: normalization, chunking, and deduplication primitives."""

from app.core.ingestion.chunking import (
    BaseChunker,
    FixedSizeChunker,
    SemanticChunker,
    StructureAwareChunker,
)
from app.core.ingestion.dedup import Deduplicator
from app.core.ingestion.models import Chunk, ChunkStrategy, DedupInfo, SourceDocument
from app.core.ingestion.normalizer import collapse_whitespace, normalize_text

__all__ = [
    "BaseChunker",
    "FixedSizeChunker",
    "SemanticChunker",
    "StructureAwareChunker",
    "Deduplicator",
    "Chunk",
    "ChunkStrategy",
    "DedupInfo",
    "SourceDocument",
    "collapse_whitespace",
    "normalize_text",
]
