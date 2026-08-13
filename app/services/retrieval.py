"""Hybrid retrieval service: dense + sparse -> RRF fusion -> rerank.

Each stage's outputs are retained so observability can break down latency and
scores per stage (Phase 5). Supports dense-only / sparse-only modes for
side-by-side evaluation and demo toggles.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.retrieval.fusion import rrf_fuse
from app.core.retrieval.rerank import Reranker
from app.core.retrieval.sparse import SparseIndex
from app.logging import get_logger
from app.services.embeddings import EmbeddingService
from app.store.base import SearchHit, VectorStore

logger = get_logger("app.services.retrieval")


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    dense_score: float | None = None
    sparse_score: float | None = None
    fused_score: float | None = None
    rerank_score: float | None = None


class RetrievalResult(BaseModel):
    query: str
    chunks: list[RetrievedChunk]
    dense_count: int
    sparse_count: int
    reranker: str | None = None


class HybridRetriever:
    """Rank chunks via hybrid retrieval with an optional rerank stage."""

    def __init__(
        self,
        store: VectorStore,
        embedder: EmbeddingService,
        sparse: SparseIndex,
        reranker: Reranker | None = None,
        reranker_name: str | None = None,
        dense_k: int = 20,
        sparse_k: int = 20,
        fused_k: int = 10,
        rrf_k: int = 60,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.sparse = sparse
        self.reranker = reranker
        self.reranker_name = reranker_name
        self.dense_k = dense_k
        self.sparse_k = sparse_k
        self.fused_k = fused_k
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        dense_only: bool = False,
        sparse_only: bool = False,
    ) -> RetrievalResult:
        final_k = top_k or self.fused_k

        dense_hits: list[SearchHit] = []
        if not sparse_only:
            query_vector = self.embedder.embed_queries([query])[0]
            dense_hits = self.store.search(query_vector, limit=self.dense_k)

        sparse_hits: list[SearchHit] = []
        if not dense_only:
            sparse_hits = self.sparse.search(query, limit=self.sparse_k)

        if dense_only:
            selected: list[tuple[str, float, dict[str, Any], float | None, float | None]] = [
                (hit.id, hit.score, hit.payload, hit.score, None) for hit in dense_hits[:final_k]
            ]
            sparse_pairs = []
            dense_pairs = [(hit.id, hit.score) for hit in dense_hits]
        elif sparse_only:
            sparse_pairs = [(hit.id, hit.score) for hit in sparse_hits]
            dense_pairs = []
            selected = [
                (hit.id, hit.score, hit.payload, None, hit.score) for hit in sparse_hits[:final_k]
            ]
        else:
            dense_pairs = [(hit.id, hit.score) for hit in dense_hits]
            sparse_pairs = [(hit.id, hit.score) for hit in sparse_hits]
            fused_hits = rrf_fuse(
                dense_pairs,
                sparse_pairs,
                dense_weight=self.dense_weight,
                sparse_weight=self.sparse_weight,
                k=self.rrf_k,
            )[:final_k]
            payloads = {hit.id: hit.payload for hit in dense_hits + sparse_hits}
            selected = [
                (
                    hit.id,
                    hit.score,
                    payloads.get(hit.id, {}),
                    hit.dense_score,
                    hit.sparse_score,
                )
                for hit in fused_hits
            ]

        chunks = [
            RetrievedChunk(
                chunk_id=chunk_id,
                text=payload.get("text", ""),
                metadata=payload.get("metadata", {}),
                fused_score=fused_score,
                dense_score=dense_score,
                sparse_score=sparse_score,
            )
            for chunk_id, fused_score, payload, dense_score, sparse_score in selected
        ]

        if self.reranker is not None and chunks:
            rerank_scores = self.reranker.rerank(
                query,
                [SearchHit(id=c.chunk_id, score=0.0, payload={"text": c.text}) for c in chunks],
            )
            for chunk, score in zip(chunks, rerank_scores, strict=True):
                chunk.rerank_score = score
            chunks.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)

        logger.info(
            "retrieval",
            extra={
                "query": query,
                "dense_hits": len(dense_hits),
                "sparse_hits": len(sparse_hits),
                "returned": len(chunks),
                "reranker": self.reranker_name,
            },
        )
        return RetrievalResult(
            query=query,
            chunks=chunks,
            dense_count=len(dense_hits),
            sparse_count=len(sparse_hits),
            reranker=self.reranker_name,
        )


def build_retriever() -> HybridRetriever:
    """Construct a production retriever from settings (single wiring point)."""
    from qdrant_client import QdrantClient

    from app.core.retrieval.rerank import build_reranker
    from app.store.qdrant import QdrantStore

    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    store = QdrantStore(
        collection=settings.qdrant_collection,
        vector_size=settings.models.embedding_dim,
        client=client,
    )
    store.ensure_collection()
    embedder = EmbeddingService(model_id=settings.models.embedding_model_id)

    sparse = SparseIndex()
    sparse.build(store.all_points())

    reranker, reranker_name = build_reranker()
    return HybridRetriever(
        store=store,
        embedder=embedder,
        sparse=sparse,
        reranker=reranker,
        reranker_name=reranker_name,
        dense_k=settings.retrieval_dense_k,
        sparse_k=settings.retrieval_sparse_k,
        fused_k=settings.retrieval_fused_k,
        rrf_k=settings.fusion_rrf_k,
        dense_weight=settings.fusion_dense_weight,
        sparse_weight=settings.fusion_sparse_weight,
    )
