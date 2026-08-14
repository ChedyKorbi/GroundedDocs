"""Grounded generation tests: citation parsing, confidence, insufficient path."""

from __future__ import annotations

from app.core.generation.citations import (
    extract_citations,
    sentence_citations,
    split_sentences,
    strip_citation_markers,
)
from app.core.generation.confidence import score_confidence
from app.core.generation.prompts import (
    GROUNDED_SYSTEM_PROMPT,
    build_grounded_user_prompt,
    build_verify_prompt,
)
from app.services.generation import GenerationService
from app.services.llm import LLMResponse
from app.services.retrieval import RetrievalResult, RetrievedChunk


class TestCitationParsing:
    def test_extract_multiple(self) -> None:
        assert extract_citations("See [1] and [2, 3] and [4,5].") == [1, 2, 3, 4, 5]

    def test_extract_deduplicates(self) -> None:
        assert extract_citations("[1] then [1] again") == [1]

    def test_extract_none(self) -> None:
        assert extract_citations("No citations here.") == []

    def test_split_sentences_and_markers(self) -> None:
        text = "First sentence [1]. Second sentence with detail [2]."
        sentences = split_sentences(text)
        assert len(sentences) == 2
        assert sentence_citations(sentences[0]) == [1]
        assert sentence_citations(sentences[1]) == [2]
        assert strip_citation_markers("Claim here. [1]") == "Claim here."


class TestConfidence:
    def test_fully_supported_high_confidence(self) -> None:
        c = score_confidence(
            answer_sentences=["A.", "B."],
            supported_indices={1, 2},
            sentence_citations_map={0: [1], 1: [2]},
            dense_scores={1: 0.9, 2: 0.8},
            insufficient=False,
        )
        assert c.completeness == 1.0
        assert c.verification_rate == 1.0
        assert c.citation_coverage == 1.0
        assert c.retrieval_confidence == 0.9
        assert 0.5 < c.composite <= 1.0

    def test_partial_support_lowers_score(self) -> None:
        c = score_confidence(
            answer_sentences=["A.", "B."],
            supported_indices={1},
            sentence_citations_map={0: [1], 1: [2]},
            dense_scores={1: 0.9, 2: 0.9},
            insufficient=False,
        )
        assert c.verification_rate == 0.5
        assert c.citation_coverage == 0.5

    def test_insufficient_is_zero(self) -> None:
        c = score_confidence([], set(), {}, {}, insufficient=True)
        assert c.composite == 0.0
        assert c.completeness == 0.0


class _FakeLLM:
    def __init__(self, complete_text: str = "Answer with a claim. [1]", json_checks=None) -> None:
        self.model = "fake-model"
        self._complete_text = complete_text
        self._json_checks = (
            json_checks
            if json_checks is not None
            else [{"index": 1, "supported": True, "reason": "matches"}]
        )

    def complete(self, system, user, json_mode=False, max_tokens=None) -> LLMResponse:
        if json_mode:
            import json

            return LLMResponse(
                text=json.dumps({"checks": self._json_checks}), input_tokens=10, output_tokens=15
            )
        return LLMResponse(text=self._complete_text, input_tokens=10, output_tokens=15)

    def complete_json(self, system, user) -> dict:
        return {"checks": self._json_checks}


def _retrieval(
    text: str = "Employees accrue 25 days of annual leave per year.", dense=0.85
) -> RetrievalResult:
    return RetrievalResult(
        query="How many leave days?",
        chunks=[RetrievedChunk(chunk_id="c1", text=text, metadata={}, dense_score=dense)],
        dense_count=1,
        sparse_count=1,
    )


def test_generate_grounded_answer_with_verified_citation() -> None:
    llm = _FakeLLM(complete_text="Employees accrue 25 days of annual leave per year. [1]")
    service = GenerationService(llm=llm)
    result = service.generate("How many leave days?", _retrieval())

    assert not result.insufficient
    assert result.answer.startswith("Employees accrue 25")
    assert len(result.citations) == 1
    assert result.citations[0].index == 1
    assert result.citations[0].chunk_id == "c1"
    assert result.citations[0].supported is True
    assert result.llm_model == "fake-model"
    assert result.model_versions["llm_model"] is not None
    assert result.input_tokens == 10 and result.output_tokens == 15
    assert result.confidence.composite > 0.5


def test_insufficient_information_path() -> None:
    llm = _FakeLLM(complete_text="INSUFFICIENT_INFORMATION")
    result = GenerationService(llm=llm).generate("Unanswerable?", _retrieval())
    assert result.insufficient is True
    assert result.answer == ""
    assert result.citations == []
    assert result.confidence.composite == 0.0


def test_sentinel_embedded_mid_answer_triggers_insufficient() -> None:
    llm = _FakeLLM(complete_text="The context does not cover this. INSUFFICIENT_INFORMATION")
    result = GenerationService(llm=llm).generate("Unanswerable?", _retrieval())
    assert result.insufficient is True
    assert result.answer == ""


def test_unverified_citation_marks_unsupported_and_lowers_confidence() -> None:
    llm = _FakeLLM(
        complete_text="The claim is stated here. [1]",
        json_checks=[{"index": 1, "supported": False, "reason": "not in passage"}],
    )
    result = GenerationService(llm=llm).generate("Q?", _retrieval())
    assert result.citations[0].supported is False
    assert result.confidence.verification_rate == 0.0


def test_verification_failure_is_unsupported_not_crash() -> None:
    class BrokenJSON(_FakeLLM):
        def complete(self, system, user, json_mode=False, max_tokens=None) -> LLMResponse:
            if json_mode:
                raise ValueError("malformed")
            return LLMResponse(text=self._complete_text, input_tokens=10, output_tokens=15)

    result = GenerationService(llm=BrokenJSON(complete_text="Claim. [1]")).generate(
        "Q?", _retrieval()
    )
    assert result.citations[0].supported is False
    assert "verification call failed" in result.citations[0].reason


def test_out_of_range_citation_is_dropped() -> None:
    llm = _FakeLLM(complete_text="Statement citing nothing valid. [9]")
    result = GenerationService(llm=llm).generate("Q?", _retrieval())
    assert result.citations == []
    assert not result.insufficient


def test_prompt_contains_numbered_context() -> None:
    prompt = build_grounded_user_prompt("Q?", [("a", "text a"), ("b", "text b")])
    assert "[1]\ntext a" in prompt
    assert "[2]\ntext b" in prompt
    assert "Question: Q?" in prompt
    assert GROUNDED_SYSTEM_PROMPT


def test_verify_prompt_numbers_passages() -> None:
    prompt = build_verify_prompt("claim here", {1: "passage one", 2: "passage two"})
    assert "[1]\npassage one" in prompt
    assert "[2]\npassage two" in prompt
