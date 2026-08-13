"""Ingest one or more documents into the vector index.

Usage:
    uv run python scripts/ingest.py [path_or_directory ...]

Connects to Qdrant (see GROUNDEDDOCS_QDRANT_URL), loads the configured embedding
model, chunks each document, deduplicates, and prints per-file reports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.core.ingestion.dedup import Deduplicator
from app.services.embeddings import EmbeddingService
from app.services.ingestion import IngestionPipeline
from app.store.qdrant import QdrantStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest documents into GroundedDocs.")
    parser.add_argument("paths", nargs="+", type=Path, help="files or directories to ingest")
    parser.add_argument("--no-dedup", action="store_true", help="disable deduplication")
    parser.add_argument("--strategy", default=None, help="override default chunking strategy")
    args = parser.parse_args(argv)

    settings = get_settings()
    store = QdrantStore(
        collection=settings.qdrant_collection,
        vector_size=settings.models.embedding_dim,
        url=settings.qdrant_url,
    )
    store.ensure_collection()

    embedder = EmbeddingService(model_id=settings.models.embedding_model_id)
    print(f"embedding model: {embedder.model_id} on {embedder.device}", file=sys.stderr)

    dedup = (
        None
        if args.no_dedup
        else Deduplicator(
            store=store,
            threshold=settings.dedup_threshold,
            mode=settings.dedup_mode,
            scope=settings.dedup_scope,
            top_k=settings.dedup_top_k,
        )
    )

    pipeline = IngestionPipeline(
        embedder=embedder,
        store=store,
        chunk_size=settings.ingestion_chunk_size,
        overlap=settings.ingestion_overlap,
        default_strategy=args.strategy or settings.ingestion_default_strategy,
        dedup=dedup,
    )

    reports: list = []
    for path in args.paths:
        if path.is_dir():
            reports.extend(pipeline.ingest_directory(path))
        elif path.is_file():
            reports.append(pipeline.ingest_file(path))
        else:
            print(f"skipping missing path: {path}", file=sys.stderr)

    print(json.dumps([r.model_dump(mode="json") for r in reports], indent=2))
    total_inserted = sum(r.inserted for r in reports)
    total_skipped = sum(r.skipped for r in reports)
    print(
        f"\ntotal: {len(reports)} files, {total_inserted} inserted, "
        f"{total_skipped} skipped (dedup), index now has {store.count()} chunks",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
