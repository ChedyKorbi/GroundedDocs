"""Citation parsing from grounded answer text.

Supports `[1]`, `[2, 3]`, and `[1,3]` bracket forms. Pure functions for unit
testing.
"""

from __future__ import annotations

import re

_CITATION_RE = re.compile(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]")


def extract_citations(text: str) -> list[int]:
    """Return the distinct cited indices in the order they first appear."""
    indices: list[int] = []
    seen: set[int] = set()
    for match in _CITATION_RE.finditer(text):
        for token in match.group(1).split(","):
            index = int(token.strip())
            if index not in seen:
                seen.add(index)
                indices.append(index)
    return indices


def split_sentences(text: str) -> list[str]:
    """Split answer text into sentences (English), preserving citation markers."""
    if not text.strip():
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text.strip())
    return [part.strip() for part in parts if part.strip()]


def sentence_citations(sentence: str) -> list[int]:
    """Citations referenced within a single sentence."""
    return extract_citations(sentence)


def strip_citation_markers(sentence: str) -> str:
    """Remove `[n]` markers, used when feeding a sentence to a judge."""
    return _CITATION_RE.sub("", sentence).strip()
