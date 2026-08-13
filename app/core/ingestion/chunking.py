"""Chunking strategies.

Three strategy-tagged chunkers, each implementing a common interface:

- FixedSizeChunker: sliding token window with configurable overlap.
- StructureAwareChunker: splits on markdown heading hierarchy, keeping the
  heading path as metadata; falls back to fixed-size when no structure exists.
- SemanticChunker: embeds sentences and breaks at similarity valleys
  (mean - k*std), producing semantically coherent boundaries.

Chunkers are pure Python + numpy and take an injected embedding callable where
needed, so they are unit-testable without loading a model.
"""

from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from app.core.ingestion.models import Chunk, ChunkStrategy

EmbedFn = Callable[[list[str]], list[list[float]]]


def _tokenize(text: str) -> list[str]:
    """Approximate tokenization: whitespace-separated tokens."""
    return re.findall(r"\S+", text)


class BaseChunker(ABC):
    """Common chunker contract."""

    strategy: ChunkStrategy

    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be in [0, chunk_size)")
        self.chunk_size = chunk_size
        self.overlap = overlap

    @abstractmethod
    def chunk_text(
        self,
        text: str,
        document_id: str,
        language: str = "en",
        metadata: dict[str, Any] | None = None,
        start_index: int = 0,
    ) -> list[Chunk]:
        """Split normalized text into strategy-tagged chunks."""


class FixedSizeChunker(BaseChunker):
    """Sliding token window with overlap; uniform chunk sizes."""

    strategy: ChunkStrategy = "fixed"

    def chunk_text(
        self,
        text: str,
        document_id: str,
        language: str = "en",
        metadata: dict[str, Any] | None = None,
        start_index: int = 0,
    ) -> list[Chunk]:
        tokens = _tokenize(text)
        if not tokens:
            return []
        step = self.chunk_size - self.overlap
        base_meta = metadata or {}
        chunks: list[Chunk] = []
        for i in range(0, len(tokens), step):
            window = tokens[i : i + self.chunk_size]
            if not window:
                break
            chunks.append(
                Chunk.new(
                    document_id=document_id,
                    index=start_index + len(chunks),
                    text=" ".join(window),
                    strategy=self.strategy,
                    language=language,
                    metadata={
                        **base_meta,
                        "chunk_start_token": i,
                        "chunk_end_token": i + len(window),
                    },
                )
            )
            if i + self.chunk_size >= len(tokens):
                break
        return chunks


_HEADER_RE = re.compile(r"^(#{1,4})\s+(.+)$")


class StructureAwareChunker(BaseChunker):
    """Split on markdown headings, carrying the heading path as section metadata."""

    strategy: ChunkStrategy = "structure"

    def chunk_text(
        self,
        text: str,
        document_id: str,
        language: str = "en",
        metadata: dict[str, Any] | None = None,
        start_index: int = 0,
    ) -> list[Chunk]:
        sections = self._extract_sections(text)
        if not sections:
            return FixedSizeChunker(self.chunk_size, self.overlap).chunk_text(
                text, document_id, language, metadata, start_index
            )
        base_meta = metadata or {}
        chunks: list[Chunk] = []
        for section_title, content in sections:
            tokens = _tokenize(content)
            if not tokens:
                continue
            chunk_meta = {**base_meta, "section": section_title}
            if len(tokens) <= self.chunk_size:
                chunks.append(
                    Chunk.new(
                        document_id=document_id,
                        index=start_index + len(chunks),
                        text=content,
                        strategy=self.strategy,
                        language=language,
                        metadata=chunk_meta,
                    )
                )
            else:
                # Long section: split into windows but keep the section tag.
                step = self.chunk_size - self.overlap
                for i in range(0, len(tokens), step):
                    window = tokens[i : i + self.chunk_size]
                    if not window:
                        break
                    chunks.append(
                        Chunk.new(
                            document_id=document_id,
                            index=start_index + len(chunks),
                            text=" ".join(window),
                            strategy=self.strategy,
                            language=language,
                            metadata={**chunk_meta, "section_part": i // step},
                        )
                    )
                    if i + self.chunk_size >= len(tokens):
                        break
        return chunks

    def _extract_sections(self, text: str) -> list[tuple[str, str]]:
        """Return (heading_path, content_including_heading) pairs."""
        sections: list[tuple[str, str]] = []
        path: list[str] = []
        path_levels: list[int] = []
        buffer: list[str] = []

        def flush() -> None:
            nonlocal buffer
            content = "\n".join(buffer).strip()
            if content and path:
                sections.append((" / ".join(path), content))
            buffer = []

        for raw_line in text.split("\n"):
            line = raw_line.strip()
            match = _HEADER_RE.match(line)
            if match:
                flush()
                level = len(match.group(1))
                title = match.group(2).strip()
                while path_levels and path_levels[-1] >= level:
                    path.pop()
                    path_levels.pop()
                path.append(title)
                path_levels.append(level)
                buffer.append(line)
            else:
                buffer.append(raw_line)
        flush()
        return sections


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])|\n{2,}")


class SemanticChunker(BaseChunker):
    """Embedding-based boundary detection at similarity valleys.

    Sentences are embedded with the injected callable; boundaries are placed
    where adjacent-sentence cosine similarity drops below mean - k*std.
    """

    strategy: ChunkStrategy = "semantic"

    def __init__(
        self,
        embed_fn: EmbedFn,
        chunk_size: int = 512,
        overlap: int = 50,
        breakpoint_std: float = 1.0,
        min_chunk_sentences: int = 2,
    ) -> None:
        super().__init__(chunk_size, overlap)
        self.embed_fn = embed_fn
        self.breakpoint_std = breakpoint_std
        self.min_chunk_sentences = min_chunk_sentences

    def chunk_text(
        self,
        text: str,
        document_id: str,
        language: str = "en",
        metadata: dict[str, Any] | None = None,
        start_index: int = 0,
    ) -> list[Chunk]:
        sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
        if len(sentences) < self.min_chunk_sentences:
            return FixedSizeChunker(self.chunk_size, self.overlap).chunk_text(
                text, document_id, language, metadata, start_index
            )
        try:
            vectors = self.embed_fn(sentences)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("semantic chunking failed to embed sentences") from exc
        if len(vectors) != len(sentences):
            raise RuntimeError("embedding callable returned mismatched vector count")
        similarities = self._adjacent_similarities(vectors)
        groups = self._group_sentences(sentences, similarities)
        base_meta = metadata or {}
        chunks: list[Chunk] = []
        for group in groups:
            if not group:
                continue
            chunk_text = " ".join(group)
            chunks.append(
                Chunk.new(
                    document_id=document_id,
                    index=start_index + len(chunks),
                    text=chunk_text,
                    strategy=self.strategy,
                    language=language,
                    metadata={
                        **base_meta,
                        "sentence_count": len(group),
                        "chunk_start_token": 0,
                        "chunk_end_token": len(_tokenize(chunk_text)),
                    },
                )
            )
        if not chunks:
            return FixedSizeChunker(self.chunk_size, self.overlap).chunk_text(
                text, document_id, language, metadata, start_index
            )
        return chunks

    @staticmethod
    def _adjacent_similarities(vectors: list[list[float]]) -> list[float]:
        import numpy as np

        matrix = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        normalized = matrix / norms
        dots = (normalized[:-1] * normalized[1:]).sum(axis=1)
        return [float(v) for v in dots]

    def _group_sentences(self, sentences: list[str], similarities: list[float]) -> list[list[str]]:
        if not similarities:
            return [sentences]
        mean = sum(similarities) / len(similarities)
        variance = sum((s - mean) ** 2 for s in similarities) / len(similarities)
        std = math.sqrt(variance) if variance > 0 else 0.0
        threshold = mean - self.breakpoint_std * std
        groups: list[list[str]] = []
        current: list[str] = [sentences[0]]
        for i in range(1, len(sentences)):
            if similarities[i - 1] < threshold:
                groups.append(current)
                current = []
            current.append(sentences[i])
        groups.append(current)
        return self._merge_small_groups(groups)

    def _merge_small_groups(self, groups: list[list[str]]) -> list[list[str]]:
        merged: list[list[str]] = []
        for group in groups:
            if merged and len(group) < self.min_chunk_sentences:
                merged[-1].extend(group)
            else:
                merged.append(list(group))
        return merged
