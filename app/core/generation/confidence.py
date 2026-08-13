"""Composite confidence scoring for grounded answers.

A documented, testable blend of three signals:

- retrieval_confidence: best dense similarity among the chunks the answer cited
  (raw cosine, higher is stronger).
- verification_rate: fraction of claim->citation checks the judge marked as
  supported — the ground-truth groundedness signal.
- citation_coverage: fraction of answer sentences backed by at least one
  supported citation.
- completeness: 1.0 when an answer was produced, 0.0 for the insufficient path.

composite = 0.25*retrieval + 0.35*verification + 0.30*coverage + 0.10*completeness
"""

from __future__ import annotations

from pydantic import BaseModel


class ConfidenceBreakdown(BaseModel):
    retrieval_confidence: float = 0.0
    verification_rate: float = 0.0
    citation_coverage: float = 0.0
    completeness: float = 0.0
    composite: float = 0.0


def score_confidence(
    answer_sentences: list[str],
    supported_indices: set[int],
    sentence_citations_map: dict[int, list[int]],
    dense_scores: dict[int, float],
    insufficient: bool,
) -> ConfidenceBreakdown:
    """Compute the composite confidence score.

    Args:
        answer_sentences: sentences in the final answer (excluding a lone sentinel).
        supported_indices: citation indices whose checks were all supported.
        sentence_citations_map: sentence index -> citation indices it cites.
        dense_scores: citation index -> dense cosine score of its chunk.
        insufficient: whether the answer hit the insufficient-information path.
    """
    if insufficient or not answer_sentences:
        breakdown = ConfidenceBreakdown(completeness=0.0)
        return _clamp(breakdown)

    # verification_rate
    checked = sum(len(v) for v in sentence_citations_map.values())
    supported_checks = sum(
        sum(1 for idx in cited if idx in supported_indices)
        for cited in sentence_citations_map.values()
    )
    verification_rate = (supported_checks / checked) if checked else 0.0

    # citation_coverage
    sentences_with_support = sum(
        1
        for cited in sentence_citations_map.values()
        if any(idx in supported_indices for idx in cited)
    )
    coverage = sentences_with_support / len(answer_sentences) if answer_sentences else 0.0

    # retrieval_confidence
    cited_scores = [dense_scores[idx] for idx in dense_scores if idx in supported_indices]
    retrieval = max(cited_scores) if cited_scores else 0.0

    composite = 0.25 * retrieval + 0.35 * verification_rate + 0.30 * coverage + 0.10 * 1.0
    return _clamp(
        ConfidenceBreakdown(
            retrieval_confidence=retrieval,
            verification_rate=verification_rate,
            citation_coverage=coverage,
            completeness=1.0,
            composite=composite,
        )
    )


def _clamp(breakdown: ConfidenceBreakdown) -> ConfidenceBreakdown:
    breakdown.composite = round(min(max(breakdown.composite, 0.0), 1.0), 3)
    return breakdown
