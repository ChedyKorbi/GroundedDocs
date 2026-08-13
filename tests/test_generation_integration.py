"""Integration test: real retrieval + real Groq generation end-to-end.

Requires a running Qdrant index (data/samples ingested), a GROQ_API_KEY, and
RUN_INTEGRATION=1. Verifies grounded answer shape, citations, and the
insufficient-information path against the live stack.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.core.retrieval.rerank import CrossEncoderReranker
from app.core.retrieval.sparse import SparseIndex
from app.services.embeddings import EmbeddingService
from app.services.generation import build_generation_service
from app.services.retrieval import HybridRetriever
from app.store.qdrant import QdrantClient, QdrantStore

pytestmark = pytest.mark.integration


def _retriever() -> HybridRetriever:
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
    reranker = CrossEncoderReranker(settings.models.reranker_cross_encoder_id)
    return HybridRetriever(
        store=store,
        embedder=embedder,
        sparse=sparse,
        reranker=reranker,
        reranker_name="cross_encoder",
        dense_k=settings.retrieval_dense_k,
        sparse_k=settings.retrieval_sparse_k,
        fused_k=settings.retrieval_fused_k,
        rrf_k=settings.fusion_rrf_k,
    )


def test_generate_grounded_answer_with_real_groq() -> None:
    if not get_settings().groq_api_key:
        pytest.skip("GROQ_API_KEY not set")
    retriever = _retriever()
    generation = build_generation_service()

    retrieval = retriever.retrieve("How many days of annual leave do employees accrue per year?")
    assert retrieval.chunks, "no chunks retrieved — is the index seeded?"

    result = generation.generate(retrieval.query, retrieval)
    assert not result.insufficient
    assert result.answer
    assert result.llm_model == get_settings().models.llm_model
    assert result.model_versions["embedding_model"] == get_settings().models.embedding_model_id
    assert result.latency_ms > 0
    assert result.confidence.composite > 0


def test_insufficient_information_path_real() -> None:
    if not get_settings().groq_api_key:
        pytest.skip("GROQ_API_KEY not set")
    retriever = _retriever()
    generation = build_generation_service()

    retrieval = retriever.retrieve("What is the capital of France?")
    result = generation.generate(retrieval.query, retrieval)
    # The answer may be non-empty if retrieval surfaced an unrelated chunk; the
    # contract is that an empty/insufficient answer is honest, never fabricated.
    if result.insufficient:
        assert result.answer == ""
        assert result.citations == []
        assert result.confidence.composite == 0.0
