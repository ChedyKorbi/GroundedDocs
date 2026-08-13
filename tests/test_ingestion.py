"""Ingestion pipeline integration tests with fake embedder + in-memory store."""

from __future__ import annotations

from pathlib import Path

from app.core.ingestion.dedup import Deduplicator
from app.services.ingestion import IngestionPipeline
from tests.conftest import FakeEmbedder


def _write(directory: Path, name: str, content: str) -> Path:
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


def _pipeline(
    store, embedder: FakeEmbedder, dedup: Deduplicator | None = None
) -> IngestionPipeline:
    return IngestionPipeline(
        embedder=embedder,
        store=store,
        chunk_size=512,
        overlap=50,
        default_strategy="structure",
        dedup=dedup,
    )


def test_ingest_markdown_structure(tmp_path, store, embedder) -> None:
    path = _write(
        tmp_path,
        "guide.md",
        "# Onboarding\n\nFirst steps.\n\n## Accounts\n\nRequest accounts here.",
    )
    report = _pipeline(store, embedder).ingest_file(path)

    assert report.format == "md"
    assert report.document_id == "guide"
    assert report.chunks_total == 2
    assert report.inserted == 2
    assert report.strategy_counts == {"structure": 2}
    assert store.count() == 2

    payloads = [p.payload for p in store.items()]
    assert all(p["language"] == "en" for p in payloads)
    assert all(p["strategy"] == "structure" for p in payloads)
    assert all(p["metadata"]["format"] == "md" for p in payloads)
    assert all(p["metadata"]["source"] == "guide" for p in payloads)
    assert payloads[0]["metadata"]["section"] == "Onboarding"


def test_txt_falls_back_to_fixed(tmp_path, store, embedder) -> None:
    path = _write(tmp_path, "notes.txt", "Just a plain text file with no structure at all.")
    report = _pipeline(store, embedder).ingest_file(path)
    assert report.strategy_counts == {"fixed": 1}
    assert report.inserted == 1


def test_second_ingest_skips_all_as_duplicates(tmp_path, store, embedder) -> None:
    path = _write(
        tmp_path,
        "doc.md",
        "# Title\n\nThis paragraph contains enough tokens to make several structure chunks.\n\n"
        "## Section\n\nMore body text here for the second chunk.",
    )
    dedup = Deduplicator(store=store, threshold=0.95, mode="skip")
    pipeline = _pipeline(store, embedder, dedup=dedup)
    first = pipeline.ingest_file(path)
    assert first.inserted == first.chunks_total

    second = pipeline.ingest_file(path)
    assert second.skipped == second.chunks_total
    assert second.inserted == 0
    assert store.count() == first.chunks_total


def test_dedup_flag_keeps_duplicates_but_marks_them(tmp_path, store, embedder) -> None:
    path = _write(tmp_path, "doc.md", "# Title\n\nSome body text.\n\n## More\n\nExtra text here.")
    dedup = Deduplicator(store=store, threshold=0.95, mode="flag")
    pipeline = _pipeline(store, embedder, dedup=dedup)
    pipeline.ingest_file(path)
    second = pipeline.ingest_file(path)
    assert second.flagged == second.chunks_total
    assert store.count() == second.chunks_total


def test_directory_ingest_skips_unsupported(tmp_path, store, embedder) -> None:
    _write(tmp_path, "a.md", "# A\n\nBody.")
    _write(tmp_path, "b.txt", "plain text")
    _write(tmp_path, "c.log", "not supported")
    reports = _pipeline(store, embedder).ingest_directory(tmp_path)
    assert [r.document_id for r in reports] == ["a", "b"]


def test_unsupported_format_raises(tmp_path, store, embedder) -> None:
    from app.services.loaders import UnsupportedFormatError

    path = _write(tmp_path, "x.docx", "nope")
    try:
        _pipeline(store, embedder).ingest_file(path)
        raise AssertionError("expected UnsupportedFormatError")
    except UnsupportedFormatError:
        pass


def test_semantic_default_strategy(tmp_path, store, embedder) -> None:
    path = _write(
        tmp_path,
        "s.md",
        "The cat sat on the mat. The cat slept on the mat. "
        "Rockets fly far into deep space. Planets orbit the distant sun.",
    )
    pipeline = IngestionPipeline(
        embedder=embedder,
        store=store,
        chunk_size=512,
        overlap=50,
        default_strategy="semantic",
        dedup=None,
    )
    report = pipeline.ingest_file(path)
    assert report.inserted >= 1
    assert report.strategy_counts.get("semantic", 0) == report.chunks_total
