"""Grounded generation service.

Pipeline: retrieval result -> grounded prompt -> LLM answer -> sentence/citation
parsing -> per claim-citation verification (LLM judge) -> composite confidence.
The insufficient-information path returns a structured, honest result instead of
a hallucinated guess. Model versions are stamped on every result for traceability.
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.generation.citations import (
    sentence_citations,
    split_sentences,
    strip_citation_markers,
)
from app.core.generation.confidence import ConfidenceBreakdown, score_confidence
from app.core.generation.prompts import (
    GROUNDED_SYSTEM_PROMPT,
    INSUFFICIENT_SENTINEL,
    VERIFY_SYSTEM_PROMPT,
    build_grounded_user_prompt,
    build_verify_prompt,
)
from app.logging import get_logger
from app.services.llm import LLMClient
from app.services.retrieval import RetrievalResult

logger = get_logger("app.services.generation")


class CitationCheck(BaseModel):
    index: int
    chunk_id: str
    supported: bool
    reason: str = ""


class SentenceCheck(BaseModel):
    sentence: str
    checks: list[CitationCheck] = Field(default_factory=list)


class GenerationResult(BaseModel):
    question: str
    answer: str
    insufficient: bool
    citations: list[CitationCheck] = Field(default_factory=list)
    sentences: list[SentenceCheck] = Field(default_factory=list)
    confidence: ConfidenceBreakdown = Field(default_factory=ConfidenceBreakdown)
    llm_model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    model_versions: dict[str, str] = Field(default_factory=dict)


class GenerationService:
    """Produce grounded, verified answers from retrieved chunks."""

    def __init__(
        self,
        llm: LLMClient,
        context_k: int = 6,
        insufficient_sentinel: str = INSUFFICIENT_SENTINEL,
    ) -> None:
        self.llm = llm
        self.context_k = context_k
        self.sentinel = insufficient_sentinel

    def generate(self, question: str, retrieval: RetrievalResult) -> GenerationResult:
        start = time.perf_counter()

        contexts = [(c.chunk_id, c.text) for c in retrieval.chunks[: self.context_k]]
        user_prompt = build_grounded_user_prompt(question, contexts)
        response = self.llm.complete(GROUNDED_SYSTEM_PROMPT, user_prompt)
        answer = response.text.strip()
        latency_ms = (time.perf_counter() - start) * 1000.0

        if (
            not answer
            or answer.upper() == self.sentinel
            or answer.upper().startswith(self.sentinel)
        ):
            return GenerationResult(
                question=question,
                answer="",
                insufficient=True,
                llm_model=self.llm.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                latency_ms=round(latency_ms, 2),
                model_versions=_model_versions(),
            )

        chunks_by_index: dict[int, dict[str, Any]] = {
            idx + 1: {"chunk_id": c.chunk_id, "dense_score": c.dense_score or 0.0}
            for idx, c in enumerate(retrieval.chunks[: self.context_k])
        }

        sentences = split_sentences(answer)
        sentence_checks: list[SentenceCheck] = []
        sentence_citations_map: dict[int, list[int]] = {}
        citation_to_sentence: dict[int, list[int]] = {}
        all_checks: dict[int, list[CitationCheck]] = {}

        for sentence_index, sentence in enumerate(sentences):
            cited = sentence_citations(sentence)
            checks: list[CitationCheck] = []
            valid_cited: list[int] = []
            if cited:
                passages = {idx: contexts[idx - 1][1] for idx in cited if idx in chunks_by_index}
                if passages:
                    checks = self._verify_claim(sentence, passages, chunks_by_index)
                for idx in cited:
                    if idx in chunks_by_index:
                        valid_cited.append(idx)
                        citation_to_sentence.setdefault(idx, []).append(sentence_index)
                        all_checks.setdefault(idx, []).extend([c for c in checks if c.index == idx])
            if valid_cited:
                sentence_citations_map[sentence_index] = valid_cited
            sentence_checks.append(
                SentenceCheck(sentence=strip_citation_markers(sentence), checks=checks)
            )

        supported_indices = {
            idx for idx, checks in all_checks.items() if checks and all(c.supported for c in checks)
        }
        dense_scores = {idx: float(chunks_by_index[idx]["dense_score"]) for idx in chunks_by_index}

        confidence = score_confidence(
            answer_sentences=[strip_citation_markers(s) for s in sentences],
            supported_indices=supported_indices,
            sentence_citations_map=sentence_citations_map,
            dense_scores=dense_scores,
            insufficient=False,
        )

        flat_citations = []
        for idx in sorted(all_checks):
            checks = all_checks[idx]
            flat_citations.append(
                CitationCheck(
                    index=idx,
                    chunk_id=chunks_by_index[idx]["chunk_id"],
                    supported=all(c.supported for c in checks),
                    reason="; ".join(c.reason for c in checks if c.reason),
                )
            )

        result = GenerationResult(
            question=question,
            answer=answer,
            insufficient=False,
            citations=flat_citations,
            sentences=sentence_checks,
            confidence=confidence,
            llm_model=self.llm.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=round(latency_ms, 2),
            model_versions=_model_versions(),
        )
        logger.info(
            "generation",
            extra={
                "insufficient": False,
                "sentences": len(sentences),
                "citations": len(flat_citations),
                "supported": sum(1 for c in flat_citations if c.supported),
                "confidence": confidence.composite,
                "latency_ms": result.latency_ms,
                "tokens": response.total_tokens,
            },
        )
        return result

    def _verify_claim(
        self,
        sentence: str,
        passages: dict[int, str],
        chunks_by_index: dict[int, dict[str, Any]],
    ) -> list[CitationCheck]:
        claim = strip_citation_markers(sentence)
        try:
            verdict = self.llm.complete_json(
                VERIFY_SYSTEM_PROMPT, build_verify_prompt(claim, passages)
            )
            raw_checks = verdict.get("checks", [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("verification_failed", extra={"error": str(exc)})
            return [
                CitationCheck(
                    index=idx,
                    chunk_id=chunks_by_index[idx]["chunk_id"],
                    supported=False,
                    reason="verification call failed",
                )
                for idx in passages
            ]
        checks: list[CitationCheck] = []
        for raw in raw_checks:
            index = raw.get("index")
            if index is None or index not in chunks_by_index:
                continue
            checks.append(
                CitationCheck(
                    index=index,
                    chunk_id=chunks_by_index[index]["chunk_id"],
                    supported=bool(raw.get("supported", False)),
                    reason=str(raw.get("reason", "")),
                )
            )
        return checks


def _model_versions() -> dict[str, str]:
    settings = get_settings()
    return {
        "llm_provider": settings.models.llm_provider,
        "llm_model": settings.models.llm_model,
        "embedding_model": settings.models.embedding_model_id,
        "reranker": settings.models.reranker_cross_encoder_id,
    }


def build_generation_service() -> GenerationService:
    """Construct the generation service from settings (single wiring point)."""
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY required for generation")
    llm = LLMClient(
        api_key=settings.groq_api_key,
        model=settings.models.llm_model,
        temperature=settings.generation_temperature,
        max_tokens=settings.generation_max_tokens,
    )
    return GenerationService(llm=llm, context_k=settings.generation_context_k)
