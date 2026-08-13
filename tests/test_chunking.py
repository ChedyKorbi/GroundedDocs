"""Chunking strategy tests: fixed-size, structure-aware, semantic."""

import hashlib

import numpy as np
import pytest

from app.core.ingestion.chunking import (
    FixedSizeChunker,
    SemanticChunker,
    StructureAwareChunker,
)
from app.core.ingestion.normalizer import normalize_text

DOC_ID = "test-doc"


def _hash_index(word: str) -> int:
    return int(hashlib.md5(word.encode()).hexdigest(), 16) % 16


def _embedder(texts: list[str]) -> list[list[float]]:
    """Deterministic bag-of-words embedder: shared words -> high cosine."""
    vectors = []
    for text in texts:
        vec = np.zeros(16, dtype=np.float32)
        for word in text.lower().split():
            vec[_hash_index(word)] += 1.0
        vectors.append(vec.tolist())
    return vectors


class TestFixedSizeChunker:
    def test_sliding_window_with_overlap(self) -> None:
        text = " ".join(f"token{i}" for i in range(25))
        chunks = FixedSizeChunker(chunk_size=10, overlap=2).chunk_text(text, DOC_ID)
        assert len(chunks) == 3
        assert [c.strategy for c in chunks] == ["fixed", "fixed", "fixed"]
        assert [c.index for c in chunks] == [0, 1, 2]
        assert len(chunks[0].text.split()) == 10
        assert chunks[1].text.startswith("token8")  # overlap = step 8
        assert chunks[0].metadata["chunk_start_token"] == 0
        assert chunks[1].metadata["chunk_start_token"] == 8

    def test_empty_text_returns_no_chunks(self) -> None:
        assert FixedSizeChunker().chunk_text("", DOC_ID) == []

    def test_single_small_text_is_one_chunk(self) -> None:
        chunks = FixedSizeChunker(chunk_size=512).chunk_text("just a few words here", DOC_ID)
        assert len(chunks) == 1

    def test_invalid_overlap_raises(self) -> None:
        with pytest.raises(ValueError):
            FixedSizeChunker(chunk_size=10, overlap=10)


class TestStructureAwareChunker:
    def test_splits_on_headings_with_section_path(self) -> None:
        text = (
            "# Handbook\n\nWelcome text.\n\n"
            "## Employment\n\nEmployment text.\n\n"
            "## Benefits\n\nBenefits text."
        )
        chunks = StructureAwareChunker().chunk_text(text, DOC_ID)
        assert len(chunks) == 3
        assert all(c.strategy == "structure" for c in chunks)
        assert chunks[0].metadata["section"] == "Handbook"
        assert chunks[1].metadata["section"] == "Handbook / Employment"
        assert chunks[2].metadata["section"] == "Handbook / Benefits"
        assert chunks[0].text.startswith("# Handbook")
        assert chunks[1].text.startswith("## Employment")

    def test_nested_heading_path(self) -> None:
        text = "# A\n\nintro\n\n## B\n\nbody\n\n### C\n\ndeep\n\n## D\n\nback to level two"
        chunks = StructureAwareChunker().chunk_text(text, DOC_ID)
        sections = [c.metadata["section"] for c in chunks]
        assert "A / B / C" in sections
        assert "A / D" in sections

    def test_no_headings_falls_back_to_fixed(self) -> None:
        text = "This document has no headings at all. Just a plain paragraph that keeps going."
        chunks = StructureAwareChunker().chunk_text(text, DOC_ID)
        assert all(c.strategy == "fixed" for c in chunks)

    def test_long_section_splits_but_keeps_structure_tag(self) -> None:
        body = " ".join(f"word{i}" for i in range(30))
        text = f"# Big Section\n\n{body}"
        chunks = StructureAwareChunker(chunk_size=10, overlap=2).chunk_text(text, DOC_ID)
        assert len(chunks) > 1
        assert all(c.strategy == "structure" for c in chunks)
        assert all(c.metadata["section"] == "Big Section" for c in chunks)


class TestSemanticChunker:
    def test_groups_similar_sentences(self) -> None:
        text = (
            "The quick brown fox jumps over the lazy dog. "
            "The quick brown fox jumps high again today. "
            "Mountains rise above the quiet forest valley. "
            "Rivers flow gently through the green meadow."
        )
        chunks = SemanticChunker(embed_fn=_embedder).chunk_text(text, DOC_ID)
        assert all(c.strategy == "semantic" for c in chunks)
        assert len(chunks) == 2
        assert "fox" in chunks[0].text and "fox" in chunks[0].text
        assert "mountains" in chunks[1].text.lower()

    def test_merges_small_groups(self) -> None:
        text = "Alpha beta gamma. Delta epsilon zeta."
        chunks = SemanticChunker(embed_fn=_embedder, min_chunk_sentences=2).chunk_text(text, DOC_ID)
        assert len(chunks) == 1

    def test_single_sentence_falls_back_to_fixed(self) -> None:
        chunks = SemanticChunker(embed_fn=_embedder).chunk_text("Only one sentence here.", DOC_ID)
        assert chunks and chunks[0].strategy == "fixed"

    def test_rejects_mismatched_vector_count(self) -> None:
        def bad_embedder(texts: list[str]) -> list[list[float]]:
            return [[0.0] * 4]

        with pytest.raises(RuntimeError, match="mismatched"):
            SemanticChunker(embed_fn=bad_embedder).chunk_text("Sentence one. Sentence two.", DOC_ID)


def test_normalized_text_chunks_have_expected_shape() -> None:
    raw = "  Line one.\r\n\r\n\r\n   Line two.   "
    normalized = normalize_text(raw)
    assert normalized == "Line one.\n\nLine two."
    chunks = FixedSizeChunker().chunk_text(normalized, DOC_ID)
    assert len(chunks) == 1
    assert chunks[0].text == "Line one. Line two."
