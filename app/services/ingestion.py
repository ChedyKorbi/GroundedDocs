"""Ingestion pipeline: load -> normalize -> chunk -> embed -> dedup -> store.

Orchestrates the pure core (chunkers, deduplicator) with LangChain loaders,
the embedding service, and the vector store. Produces a per-file report with
insert/skip/flag counts and per-strategy tallies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.ingestion.chunking import (
    BaseChunker,
    FixedSizeChunker,
    SemanticChunker,
    StructureAwareChunker,
)
from app.core.ingestion.dedup import Deduplicator
from app.core.ingestion.models import Chunk
from app.logging import get_logger
from app.services.embeddings import EmbeddingService
from app.services.loaders import LoadedSegment, UnsupportedFormatError, detect_format, load_document
from app.store.base import VectorPoint, VectorStore

logger = get_logger("app.services.ingestion")

STRATEGY_BY_FORMAT: dict[str, str] = {
    "md": "structure",
    "txt": "fixed",
    "html": "fixed",
    "htm": "fixed",
    "pdf": "fixed",
}


class IngestReport(BaseModel):
    file: str
    document_id: str
    format: str
    segments: int = 0
    chunks_total: int = 0
    inserted: int = 0
    skipped: int = 0
    flagged: int = 0
    strategy_counts: dict[str, int] = Field(default_factory=dict)
    duration_ms: float = 0.0


class IngestionPipeline:
    """End-to-end ingestion for a single document or directory."""

    def __init__(
        self,
        embedder: EmbeddingService,
        store: VectorStore,
        chunk_size: int = 512,
        overlap: int = 50,
        default_strategy: str = "structure",
        dedup: Deduplicator | None = None,
    ) -> None:
        self.embedder = embedder
        self.store = store
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.default_strategy = default_strategy
        self.dedup = dedup

    def _make_chunker(self, strategy: str, document_id: str) -> BaseChunker:
        if strategy == "semantic":
            return SemanticChunker(self.embedder.embed_documents, self.chunk_size, self.overlap)
        if strategy == "structure":
            return StructureAwareChunker(self.chunk_size, self.overlap)
        if strategy == "fixed":
            return FixedSizeChunker(self.chunk_size, self.overlap)
        raise ValueError(f"unknown chunking strategy: {strategy}")

    def _chunk_segment(
        self,
        segment: LoadedSegment,
        document_id: str,
        format_name: str,
        start_index: int,
    ) -> list[Chunk]:
        # "structure" acts as auto: use format-aware defaults where structure
        # exists (markdown); explicit strategies apply to every format.
        strategy = self.default_strategy
        if strategy == "structure":
            strategy = STRATEGY_BY_FORMAT.get(format_name, strategy)
        chunker = self._make_chunker(strategy, document_id)
        metadata: dict[str, Any] = {}
        if segment.title:
            metadata["title"] = segment.title
        if segment.page is not None:
            metadata["page"] = segment.page
        metadata.update(segment.extra)
        chunks = chunker.chunk_text(
            segment.text,
            document_id=document_id,
            language="en",
            metadata=metadata,
            start_index=start_index,
        )
        for chunk in chunks:
            chunk.metadata["format"] = format_name
            chunk.metadata["source"] = document_id
        return chunks

    def ingest_file(self, path: Path) -> IngestReport:
        import time

        start = time.perf_counter()
        format_name = detect_format(path)
        document_id = path.stem
        segments = load_document(path)

        chunker_seen: dict[str, int] = {}
        all_chunks: list[Chunk] = []
        index = 0
        for segment in segments:
            chunks = self._chunk_segment(segment, document_id, format_name, index)
            all_chunks.extend(chunks)
            index += len(chunks)
            for chunk in chunks:
                chunker_seen[chunk.strategy] = chunker_seen.get(chunk.strategy, 0) + 1

        inserted: list[tuple[Chunk, list[float]]] = []
        skipped = 0
        flagged = 0
        vectors = self.embedder.embed_documents([c.text for c in all_chunks])
        for chunk, vector in zip(all_chunks, vectors, strict=True):
            if self.dedup:
                result = self.dedup.check(vector, document_id)
                chunk.dedup = result
                if result.decision == "skip":
                    skipped += 1
                    continue
                if result.decision == "flag":
                    flagged += 1
            inserted.append((chunk, vector))

        if inserted:
            self.store.upsert(
                [
                    VectorPoint(
                        id=chunk.id,
                        vector=vector,
                        payload=chunk.model_dump(mode="json"),
                    )
                    for chunk, vector in inserted
                ]
            )

        duration_ms = (time.perf_counter() - start) * 1000.0
        report = IngestReport(
            file=str(path),
            document_id=document_id,
            format=format_name,
            segments=len(segments),
            chunks_total=len(all_chunks),
            inserted=len(inserted),
            skipped=skipped,
            flagged=flagged,
            strategy_counts=chunker_seen,
            duration_ms=round(duration_ms, 2),
        )
        logger.info(
            "ingest_report",
            extra=report.model_dump(mode="json"),
        )
        return report

    def ingest_directory(self, path: Path) -> list[IngestReport]:
        if not path.is_dir():
            raise NotADirectoryError(str(path))
        reports: list[IngestReport] = []
        for file_path in sorted(path.iterdir()):
            if file_path.is_file() and file_path.suffix.lower() in {
                ".md",
                ".markdown",
                ".txt",
                ".html",
                ".htm",
                ".pdf",
            }:
                try:
                    reports.append(self.ingest_file(file_path))
                except UnsupportedFormatError as exc:
                    logger.warning(
                        "unsupported_file_skipped",
                        extra={"file": str(file_path), "reason": str(exc)},
                    )
        return reports
