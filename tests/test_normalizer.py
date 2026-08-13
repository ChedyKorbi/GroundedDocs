"""Normalizer tests: unicode, line endings, whitespace."""

from app.core.ingestion.normalizer import collapse_whitespace, normalize_text


def test_normalizes_crlf_and_cr() -> None:
    assert normalize_text("line1\r\nline2\rline3") == "line1\nline2\nline3"


def test_collapses_runs_of_spaces() -> None:
    assert normalize_text("a    b\t\tc") == "a b c"


def test_strips_trailing_spaces_and_outer_whitespace() -> None:
    assert normalize_text("  hello   \n\nworld  ") == "hello\n\nworld"


def test_limits_blank_lines_to_two() -> None:
    assert normalize_text("a\n\n\n\n\nb") == "a\n\nb"


def test_nfkc_normalizes_compat_characters() -> None:
    assert normalize_text("\uff21\uff22\uff23") == "ABC"
    assert normalize_text("\ufb01") == "fi"  # ligature fi -> "fi"


def test_collapse_whitespace_flattens_newlines() -> None:
    assert collapse_whitespace("a\n\nb  c") == "a b c"
