"""Judge tests (faithfulness, relevance) with a scripted fake LLM."""

from __future__ import annotations

from app.core.evaluation.judges import FaithfulnessJudge, RelevanceJudge


class _FakeLLM:
    def __init__(self, json_result=None, fail=False) -> None:
        self._json = json_result or {}
        self._fail = fail

    def complete_json(self, system: str, user: str) -> dict:
        if self._fail:
            raise ValueError("boom")
        return self._json


class TestFaithfulnessJudge:
    def test_all_supported(self) -> None:
        llm = _FakeLLM(
            {
                "claims": [
                    {"claim": "a", "supported": True, "reason": "ok"},
                    {"claim": "b", "supported": True, "reason": "ok"},
                ]
            }
        )
        result = FaithfulnessJudge(llm).score("q", "a. b.", ["ctx"])
        assert result.score == 1.0
        assert len(result.claims) == 2

    def test_partial(self) -> None:
        llm = _FakeLLM(
            {
                "claims": [
                    {"claim": "a", "supported": True, "reason": "ok"},
                    {"claim": "b", "supported": False, "reason": "not in context"},
                ]
            }
        )
        result = FaithfulnessJudge(llm).score("q", "a. b.", ["ctx"])
        assert result.score == 0.5

    def test_empty_answer_is_trivially_faithful(self) -> None:
        result = FaithfulnessJudge(_FakeLLM()).score("q", "  ", [])
        assert result.score == 1.0

    def test_judge_failure_is_zero(self) -> None:
        result = FaithfulnessJudge(_FakeLLM(fail=True)).score("q", "a claim.", ["ctx"])
        assert result.score == 0.0

    def test_empty_claims_is_zero(self) -> None:
        result = FaithfulnessJudge(_FakeLLM({"claims": []})).score("q", "a claim.", ["ctx"])
        assert result.score == 0.0


class TestRelevanceJudge:
    def test_score_normalization(self) -> None:
        llm = _FakeLLM({"relevance": 8, "reason": "good"})
        result = RelevanceJudge(llm).score("q", "an answer")
        assert result.score == 0.8

    def test_clamped(self) -> None:
        llm = _FakeLLM({"relevance": 12, "reason": "over"})
        assert RelevanceJudge(llm).score("q", "a").score == 1.0

    def test_empty_answer(self) -> None:
        result = RelevanceJudge(_FakeLLM()).score("q", "")
        assert result.score == 0.0

    def test_judge_failure(self) -> None:
        result = RelevanceJudge(_FakeLLM(fail=True)).score("q", "an answer")
        assert result.score == 0.0
