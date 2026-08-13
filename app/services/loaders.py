"""Document loaders (LangChain 1.x) with a uniform normalized output.

Returns `LoadedSegment` objects: normalized text plus page metadata where the
format is page-oriented (PDF). Everything downstream chunks a segment and tags
chunks with its metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.ingestion.normalizer import normalize_text

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".html", ".htm", ".pdf"}


@dataclass
class LoadedSegment:
    text: str
    page: int | None = None
    title: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class UnsupportedFormatError(ValueError):
    pass


def load_document(path: Path) -> list[LoadedSegment]:
    """Load a supported document into normalized text segments."""
    extension = path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(f"unsupported format: {extension}")

    if extension in {".md", ".markdown", ".txt"}:
        return [
            LoadedSegment(text=normalize_text(path.read_text(encoding="utf-8")), title=path.stem)
        ]

    if extension in {".html", ".htm"}:
        return [_load_html(path)]

    if extension == ".pdf":
        return _load_pdf(path)

    raise UnsupportedFormatError(f"no loader for: {extension}")


def _load_html(path: Path) -> LoadedSegment:
    from langchain_community.document_loaders import BSHTMLLoader

    loader = BSHTMLLoader(str(path))
    docs = loader.load()
    title = docs[0].metadata.get("title") if docs else None
    text = normalize_text("\n\n".join(doc.page_content for doc in docs))
    return LoadedSegment(text=text, title=title)


def _load_pdf(path: Path) -> list[LoadedSegment]:
    from langchain_community.document_loaders import PyPDFLoader

    loader = PyPDFLoader(str(path))
    docs = loader.load()
    segments: list[LoadedSegment] = []
    for doc in docs:
        page = doc.metadata.get("page")
        text = normalize_text(doc.page_content)
        if text:
            segments.append(LoadedSegment(text=text, page=page, title=path.stem))
    return segments


def detect_format(path: Path) -> str:
    extension = path.suffix.lower().lstrip(".")
    return {"markdown": "md"}.get(extension, extension)
