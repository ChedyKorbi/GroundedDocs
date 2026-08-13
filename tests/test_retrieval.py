"""Sparse BM25, RRF fusion, and rerank tests."""

import pytest

from app.core.retrieval.fusion import rrf_fuse
from app.core.retrieval.rerank import CrossEncoderReranker, LlmJudgeReranker, build_reranker
from app.core.retrieval.sparse import SparseIndex, tokenize
from app.store.base import VectorPoint


class TestSparseIndex:
    def test_tokenize(self) -> None:
        assert tokenize("Hello, WORLD 123!") == ["hello", "world", "123"]

    def test_build_and_search_ranks_relevant_first(self) -> None:
        points = [
            VectorPoint(
                id="a",
                vector=[],
                payload={"text": "Remote work policy allows three days per week."},
            ),
            VectorPoint(
                id="b", vector=[], payload={"text": "Annual leave accrual is twenty five days."}
            ),
            VectorPoint(
                id="c", vector=[], payload={"text": "Remote access requires the approved VPN."}
            ),
        ]
        index = SparseIndex()
        index.build(points)
        hits = index.search("remote work days", limit=5)
        assert hits[0].id == "a"
        assert hits[1].id == "c"
        assert all(hit.score > 0 for hit in hits)

    def test_search_before_build_returns_empty(self) -> None:
        index = SparseIndex()
        assert index.search("anything") == []

    def test_unmatched_query_returns_empty(self) -> None:
        index = SparseIndex()
        index.build([VectorPoint(id="a", vector=[], payload={"text": "cats and dogs"})])
        assert index.search("quantum physics") == []

    def test_limit_respected(self) -> None:
        points = [
            VectorPoint(id=f"c{i}", vector=[], payload={"text": f"shared keyword unique{i}"})
            for i in range(10)
        ]
        index = SparseIndex()
        index.build(points)
        hits = index.search("shared keyword", limit=3)
        assert len(hits) == 3


class TestRrfFusion:
    def test_union_and_weighted_ranking(self) -> None:
        dense = [("a", 0.9), ("b", 0.8), ("c", 0.7)]
        sparse = [("c", 12.0), ("d", 10.0), ("e", 9.0), ("a", 8.0)]
        fused = rrf_fuse(dense, sparse, k=10)
        ids = [hit.id for hit in fused]
        assert set(ids) == {"a", "b", "c", "d", "e"}
        # c: sparse rank 1 (1/11) + dense rank 3 (1/13) > a: sparse rank 4
        # (1/14) + dense rank 1 (1/11); asymmetric ranks -> no tie.
        assert ids[0] == "c"

    def test_missing_in_one_list_contributes_zero(self) -> None:
        dense = [("a", 0.9)]
        sparse = [("b", 5.0)]
        fused = rrf_fuse(dense, sparse, k=10)
        assert len(fused) == 2
        a = next(h for h in fused if h.id == "a")
        b = next(h for h in fused if h.id == "b")
        assert a.sparse_rank is None
        assert b.dense_rank is None

    def test_weights_change_ordering(self) -> None:
        dense = [("a", 0.9), ("b", 0.8)]
        sparse = [("c", 5.0), ("a", 4.0)]
        equal = rrf_fuse(dense, sparse, k=10)
        assert equal[0].id == "a"
        sparse_heavy = rrf_fuse(dense, sparse, k=10, dense_weight=0.1, sparse_weight=10.0)
        assert sparse_heavy[0].id == "c"

    def test_empty_lists(self) -> None:
        assert rrf_fuse([], [], k=10) == []
        assert [h.id for h in rrf_fuse([("a", 0.9)], [], k=10)] == ["a"]


class TestRerank:
    def test_llm_judge_requires_api_key(self) -> None:
        with pytest.raises(ValueError, match="Groq API key"):
            LlmJudgeReranker(api_key=None)

    def test_build_reranker_llm_judge_mode(self, monkeypatch) -> None:
        monkeypatch.setattr("app.core.retrieval.rerank.get_settings", _fake_settings)
        reranker, name = build_reranker()
        assert isinstance(reranker, LlmJudgeReranker)
        assert name == "llm_judge"


def _fake_settings():
    from app.config import ModelRegistry, Settings

    settings = Settings(reranker_mode="llm_judge", groq_api_key="sk-fake")
    settings.models = ModelRegistry(reranker_llm_judge_model="llama-test")
    return settings


@pytest.mark.integration
def test_cross_encoder_smoke() -> None:
    """Verify cross-encoder scores monotonic with relevance (tiny local model)."""
    model_id = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    try:
        reranker = CrossEncoderReranker(model_id)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"model unavailable: {exc}")
    from app.store.base import SearchHit

    candidates = [
        VectorPoint(id="a", vector=[], payload={"text": "Remote work policy allows three days."}),
        VectorPoint(id="b", vector=[], payload={"text": "The bakery sells sourdough bread."}),
    ]
    hits = [SearchHit(id=p.id, score=0.0, payload=p.payload) for p in candidates]
    scores = reranker.rerank("How many remote work days are allowed?", hits)
    assert len(scores) == 2
    assert scores[0] > scores[1]
