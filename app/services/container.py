"""Application service container.

Single wiring point for the API: resolves the active index collection (plain
collection until the first versioned reindex), builds the retriever, generator,
query log, and rate limiter, and exposes zero-downtime reindex.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient

from app.config import Settings, get_settings
from app.core.retrieval.rerank import CrossEncoderReranker
from app.core.retrieval.sparse import SparseIndex
from app.services.embeddings import EmbeddingService
from app.services.generation import GenerationService
from app.services.llm import LLMClient
from app.services.retrieval import HybridRetriever
from app.store.base import VectorPoint
from app.store.index import IndexManager
from app.store.qdrant import QdrantStore
from app.store.querylog import QueryLog


def resolve_active_collection(settings: Settings) -> str:
    """Resolve the collection currently behind the versioned alias.

    Falls back to the plain configured collection name before the first
    versioned reindex (or if no alias exists yet).
    """
    client = QdrantClient(url=settings.qdrant_url)
    index = IndexManager(
        client,
        base_collection=settings.qdrant_collection,
        alias=f"{settings.qdrant_collection}-active",
    )
    return index.active_collection() or settings.qdrant_collection


class AppServices:
    """Holds the long-lived service instances the API depends on."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = QdrantClient(url=self.settings.qdrant_url)
        self.index = IndexManager(
            self.client,
            base_collection=self.settings.qdrant_collection,
            alias=f"{self.settings.qdrant_collection}-active",
        )
        self.embedder = EmbeddingService(model_id=self.settings.models.embedding_model_id)
        self.querylog = QueryLog(self.settings.querylog_path)
        self._model_ready: bool | None = None

        self._active = self._resolve_active()
        self.store = self._make_store(self._active)
        self.sparse = SparseIndex()
        self.sparse.build(self.store.all_points())
        self.retriever = HybridRetriever(
            store=self.store,
            embedder=self.embedder,
            sparse=self.sparse,
            reranker=self._make_reranker(),
            reranker_name="cross_encoder",
            dense_k=self.settings.retrieval_dense_k,
            sparse_k=self.settings.retrieval_sparse_k,
            fused_k=self.settings.retrieval_fused_k,
            rrf_k=self.settings.fusion_rrf_k,
            dense_weight=self.settings.fusion_dense_weight,
            sparse_weight=self.settings.fusion_sparse_weight,
        )
        self.generation = GenerationService(
            llm=LLMClient(
                api_keys=self.settings.effective_groq_keys,
                model=self.settings.models.llm_model,
                temperature=self.settings.generation_temperature,
                max_tokens=self.settings.generation_max_tokens,
            ),
            verify_llm=LLMClient(
                api_keys=self.settings.effective_groq_keys,
                model=self.settings.models.judge_model,
                temperature=0.0,
                max_tokens=512,
            ),
            context_k=self.settings.generation_context_k,
        )

    def _resolve_active(self) -> str:
        active = self.index.active_collection()
        return active or self.settings.qdrant_collection

    def _make_store(self, collection: str) -> QdrantStore:
        store = QdrantStore(
            collection=collection,
            vector_size=self.settings.models.embedding_dim,
            client=self.client,
        )
        store.ensure_collection()
        return store

    @staticmethod
    def _make_reranker() -> CrossEncoderReranker:
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        return CrossEncoderReranker(get_settings().models.reranker_cross_encoder_id, device=device)

    def refresh_sparse(self) -> None:
        """Rebuild the BM25 index from the current store and rewire the retriever."""
        self.sparse.build(self.store.all_points())
        self.retriever.sparse = self.sparse
        self.retriever.store = self.store

    def active_collection(self) -> str:
        return self._active

    def model_ready(self) -> bool:
        """Lazily probe embedding model readiness (checked once, then cached)."""
        if self._model_ready is None:
            try:
                self.embedder.embed_queries(["ping"])
                self._model_ready = True
            except Exception:  # noqa: BLE001
                self._model_ready = False
        return self._model_ready

    def seed_samples(self) -> list[dict[str, Any]]:
        """Ingest the sample corpus when the index is empty (one-command startup)."""
        from app.core.ingestion.dedup import Deduplicator
        from app.services.ingestion import IngestionPipeline

        settings = self.settings
        pipeline = IngestionPipeline(
            embedder=self.embedder,
            store=self.store,
            chunk_size=settings.ingestion_chunk_size,
            overlap=settings.ingestion_overlap,
            default_strategy=settings.ingestion_default_strategy,
            dedup=Deduplicator(
                store=self.store,
                threshold=settings.dedup_threshold,
                mode=settings.dedup_mode,
                scope=settings.dedup_scope,
                top_k=settings.dedup_top_k,
            ),
        )
        reports = pipeline.ingest_directory(Path(settings.seed_samples_dir))
        self.refresh_sparse()
        return [r.model_dump(mode="json") for r in reports]

    def documents(self) -> list[dict[str, Any]]:
        counts: dict[str, dict[str, Any]] = {}
        for point in self.store.all_points():
            document_id = point.payload.get("document_id", "unknown")
            entry = counts.setdefault(
                document_id,
                {
                    "document_id": document_id,
                    "format": point.payload.get("format", "?"),
                    "chunk_count": 0,
                },
            )
            entry["chunk_count"] += 1
        return sorted(counts.values(), key=lambda d: d["document_id"])

    def delete_document(self, document_id: str) -> bool:
        deleted = self.store.delete_by_document(document_id)
        if deleted:
            self.refresh_sparse()
        return deleted

    def reindex(self) -> dict[str, Any]:
        """Zero-downtime reindex: build a new version, re-embed, atomic swap."""
        start = time.perf_counter()
        previous = self._active
        new_collection = self.index.begin_reindex(vector_size=self.settings.models.embedding_dim)
        new_store = self._make_store(new_collection)

        points = self.store.all_points()
        if points:
            texts = [p.payload.get("text", "") for p in points]
            vectors = self.embedder.embed_documents(texts)
            new_store.upsert(
                [
                    VectorPoint(id=point.id, vector=vector, payload=point.payload)
                    for point, vector in zip(points, vectors, strict=True)
                ]
            )

        self.index.activate(new_collection)
        self._active = new_collection
        self.store = new_store
        self.refresh_sparse()

        if previous and previous != new_collection:
            self.index.drop_version(previous)

        return {
            "previous_collection": previous,
            "current_collection": new_collection,
            "chunks_reindexed": len(points),
            "duration_ms": round((time.perf_counter() - start) * 1000.0, 2),
        }
