"""HybridRetriever tests with fake embedder + in-memory store + real BM25."""

from __future__ import annotations

from app.core.retrieval.sparse import SparseIndex
from app.services.retrieval import HybridRetriever
from app.store.base import VectorPoint

QUERIES = ["How many remote work days are allowed?", "What is the annual leave allowance?"]

TEXTS = [
    "Remote work policy allows employees to work remotely up to three days per week.",
    "Annual leave accrual is twenty five working days per year.",
    "Remote access to the corporate network requires the approved VPN and MFA.",
    "Probation period for new hires is ninety days.",
]

GOLD_A = "c0"  # remote work text
GOLD_B = "c1"  # annual leave text


def _seed(store, embedder) -> SparseIndex:
    points = [
        VectorPoint(
            id=f"c{i}",
            vector=embedder.embed_documents([text])[0],
            payload={"text": text, "metadata": {"source": "doc"}, "document_id": "doc"},
        )
        for i, text in enumerate(TEXTS)
    ]
    store.upsert(points)
    sparse = SparseIndex()
    sparse.build(points)
    return sparse


def _retriever(store, embedder, sparse, reranker=None, name=None, **kw) -> HybridRetriever:
    return HybridRetriever(
        store=store,
        embedder=embedder,
        sparse=sparse,
        reranker=reranker,
        reranker_name=name,
        dense_k=4,
        sparse_k=4,
        fused_k=4,
        **kw,
    )


def test_dense_only_returns_dense_chunks(store, embedder) -> None:
    sparse = _seed(store, embedder)
    result = _retriever(store, embedder, sparse).retrieve(QUERIES[0], top_k=2, dense_only=True)
    assert result.dense_count > 0
    assert result.sparse_count == 0
    assert all(c.dense_score is not None for c in result.chunks)


def test_sparse_only_returns_sparse_chunks(store, embedder) -> None:
    sparse = _seed(store, embedder)
    result = _retriever(store, embedder, sparse).retrieve(QUERIES[0], top_k=2, sparse_only=True)
    assert result.dense_count == 0
    assert result.sparse_count > 0
    assert all(c.sparse_score is not None for c in result.chunks)


def test_hybrid_combines_and_reranks_with_stub(store, embedder) -> None:
    sparse = _seed(store, embedder)

    class StubReranker:
        def rerank(self, query: str, candidates) -> list[float]:
            return [float(len(candidates) - i) for i in range(len(candidates))]

    result = _retriever(store, embedder, sparse, reranker=StubReranker(), name="stub").retrieve(
        QUERIES[0], top_k=4
    )
    assert result.reranker == "stub"
    assert all(c.rerank_score is not None for c in result.chunks)
    # reranked order: scores descend with index
    assert result.chunks[0].rerank_score >= result.chunks[-1].rerank_score


def test_hybrid_handles_sparse_miss_gracefully(store, embedder) -> None:
    """A query with no lexical overlap returns dense-only results, not an empty list."""
    sparse = _seed(store, embedder)
    query = "Xyzzle quibble brummagem"
    result = _retriever(store, embedder, sparse).retrieve(query, top_k=4)
    assert result.sparse_count == 0
    assert result.dense_count > 0
    assert result.chunks  # dense path carried the query


def test_hybrid_prefers_cross_match(store, embedder) -> None:
    """Hybrid ranks a chunk found by BOTH rankers above a chunk found by one."""
    sparse = _seed(store, embedder)
    result = _retriever(store, embedder, sparse).retrieve(QUERIES[1], top_k=4)
    ids = [c.chunk_id for c in result.chunks]
    assert ids[0] == GOLD_B


def test_retrieval_result_shape(store, embedder) -> None:
    sparse = _seed(store, embedder)
    result = _retriever(store, embedder, sparse).retrieve(QUERIES[0], top_k=3)
    assert result.query == QUERIES[0]
    assert len(result.chunks) <= 3
    first = result.chunks[0]
    assert first.text
    assert first.metadata == {"source": "doc"}
