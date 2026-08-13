"""Text normalization.

English-first scope: NFKC unicode normalization, line-ending unification, and
whitespace collapsing. Arabic-specific normalization (diacritics, tatweel,
alef variants, RTL handling) is intentionally deferred to the v1.1 Arabic pass.
"""

from __future__ import annotations

import re
import unicodedata

_BLANK_LINES_RE = re.compile(r"\n{3,}")
_TRAILING_SPACE_RE = re.compile(r"[ \t]+(?=\n)")
_LINE_LEAD_RE = re.compile(r"(?m)^[ \t]+")


def normalize_text(text: str) -> str:
    """Normalize unicode + whitespace for indexing.

    - NFKC normalizes compatibility characters (ligatures, fullwidth forms).
    - CRLF/CR line endings become LF.
    - Runs of spaces/tabs collapse to a single space; trailing spaces before
      newlines and leading whitespace on any line are removed; three or more
      blank lines collapse to two.

    Note: leading-whitespace stripping flattens indented code blocks; acceptable
    for retrieval-focused ingestion (revisit if source code is indexed).
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = _LINE_LEAD_RE.sub("", text)
    text = _TRAILING_SPACE_RE.sub("", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def collapse_whitespace(text: str) -> str:
    """Collapse all runs of whitespace (including newlines) to single spaces."""
    return re.sub(r"\s+", " ", text).strip()
