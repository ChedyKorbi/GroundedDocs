"""Grounded generation core: prompts, citation parsing, confidence scoring."""

from app.core.generation.citations import (
    extract_citations,
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

__all__ = [
    "extract_citations",
    "sentence_citations",
    "split_sentences",
    "strip_citation_markers",
    "ConfidenceBreakdown",
    "score_confidence",
    "GROUNDED_SYSTEM_PROMPT",
    "INSUFFICIENT_SENTINEL",
    "VERIFY_SYSTEM_PROMPT",
    "build_grounded_user_prompt",
    "build_verify_prompt",
]
