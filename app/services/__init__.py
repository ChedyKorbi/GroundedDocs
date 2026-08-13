"""Service layer: LangChain wiring + orchestration over the pure core."""

from app.services.embeddings import EmbeddingService
from app.services.ingestion import IngestionPipeline, IngestReport
from app.services.loaders import (
    SUPPORTED_EXTENSIONS,
    LoadedSegment,
    UnsupportedFormatError,
    detect_format,
    load_document,
)

__all__ = [
    "EmbeddingService",
    "IngestionPipeline",
    "IngestReport",
    "SUPPORTED_EXTENSIONS",
    "LoadedSegment",
    "UnsupportedFormatError",
    "detect_format",
    "load_document",
]
