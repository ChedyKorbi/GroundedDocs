"""Dedup tests: nearest-neighbor duplicate detection against the store."""

import pytest

from app.core.ingestion.dedup import Deduplicator
from app.store.base import VectorPoint

SAME = [1.0, 0.0, 0.0]
OTHER = [0.0, 1.0, 0.0]
NEAR = [0.95, 0.30, 0.0]


def _add(store, vector: list[float], document_id: str = "doc-a", index: int = 0) -> str:
    point = VectorPoint(
        id=f"c-{document_id}-{index}",
        vector=vector,
        payload={"document_id": document_id},
    )
    store.upsert([point])
    return point.id


def test_exact_match_is_skipped(store) -> None:
    _add(store, SAME)
    result = Deduplicator(store=store, threshold=0.95).check(SAME, "doc-a")
    assert result.decision == "skip"
    assert result.score >= 0.95
    assert result.match_chunk_id == "c-doc-a-0"


def test_dissimilar_chunk_is_inserted(store) -> None:
    _add(store, OTHER)
    result = Deduplicator(store=store, threshold=0.95).check(SAME, "doc-a")
    assert result.decision == "insert"
    assert result.checked_against == 1


def test_flag_mode_marks_instead_of_skip(store) -> None:
    _add(store, SAME)
    result = Deduplicator(store=store, threshold=0.95, mode="flag").check(SAME, "doc-a")
    assert result.decision == "flag"


def test_high_threshold_lets_near_duplicates_through(store) -> None:
    _add(store, SAME)
    result = Deduplicator(store=store, threshold=0.999).check(NEAR, "doc-a")
    assert result.decision == "insert"


def test_same_document_scope_excludes_other_documents(store) -> None:
    _add(store, SAME, document_id="doc-a")
    assert (
        Deduplicator(store=store, threshold=0.95, scope="all").check(SAME, "doc-b").decision
        == "skip"
    )
    assert (
        Deduplicator(store=store, threshold=0.95, scope="same_document")
        .check(SAME, "doc-b")
        .decision
        == "insert"
    )


def test_validation_rules(store) -> None:
    with pytest.raises(ValueError):
        Deduplicator(store=store, threshold=1.5)
    with pytest.raises(ValueError):
        Deduplicator(store=store, mode="delete")
    with pytest.raises(ValueError):
        Deduplicator(store=store, scope="everywhere")


def test_top_k_limits_search(store) -> None:
    for i in range(10):
        _add(store, OTHER, index=i)
    result = Deduplicator(store=store, threshold=0.1, top_k=3).check(SAME, "doc-a")
    assert result.checked_against == 3
