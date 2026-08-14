"""API routes: /ask, /ingest, /documents, /metrics, /health, /reindex."""

from __future__ import annotations

import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.api.auth import verify_api_key
from app.api.errors import AppError
from app.api.ratelimit import make_rate_limiter
from app.api.schemas import (
    AskRequest,
    AskResponse,
    CitationSchema,
    DocumentInfo,
    DocumentsResponse,
    HealthResponse,
    IngestResponse,
    IngestResult,
    LatencyBreakdown,
    MetricsResponse,
    ModelVersions,
    ReindexResponse,
    SentenceSchema,
    TokenUsage,
)
from app.config import get_settings
from app.core.cost import estimate_cost
from app.core.ingestion.dedup import Deduplicator
from app.logging import get_logger, get_request_id
from app.services.container import AppServices
from app.services.ingestion import IngestionPipeline

logger = get_logger("app.api.routes")

router = APIRouter(tags=["api"])


def _services(request: Request) -> AppServices:
    """Return the lazily-built service container, or a structured 503."""
    services = getattr(request.app.state, "services", None)
    if isinstance(services, AppServices):
        return services
    error = getattr(request.app.state, "services_error", "not initialized")
    try:
        if error is None:
            built = AppServices()
            request.app.state.services = built
            request.app.state.services_error = None
            return built
    except Exception as exc:  # noqa: BLE001
        request.app.state.services_error = str(exc)
        raise AppError(503, "service_unavailable", f"services failed to initialize: {exc}") from exc
    raise AppError(503, "service_unavailable", f"services unavailable: {error}")


def _auth_dependency(request: Request) -> AppServices:
    """Routes that require an API key authenticate first, then access services."""
    verify_api_key(request.headers.get("x-api-key"))
    return _services(request)


def _rate_limited() -> Callable[[Request], None]:
    settings = get_settings()
    return make_rate_limiter(settings.api_rate_limit_max, settings.api_rate_limit_window_seconds)


ServicesDep = Annotated[AppServices, Depends(_services)]
AuthedServices = Annotated[AppServices, Depends(_auth_dependency)]


@router.post("/ask", response_model=AskResponse, summary="Ask a grounded question")
def ask(
    request: AskRequest, services: AuthedServices, _rl: None = Depends(_rate_limited())
) -> AskResponse:
    total_start = time.perf_counter()
    retrieval = services.retriever.retrieve(
        request.question,
        top_k=request.top_k,
        dense_only=request.retrieval_method == "dense_only",
        sparse_only=request.retrieval_method == "sparse_only",
    )
    result = services.generation.generate(request.question, retrieval)
    total_ms = (time.perf_counter() - total_start) * 1000.0

    citation_schemas = [
        CitationSchema(index=c.index, chunk_id=c.chunk_id, supported=c.supported, reason=c.reason)
        for c in result.citations
    ]
    sentence_schemas = [
        SentenceSchema(
            sentence=s.sentence,
            checks=[
                CitationSchema(
                    index=c.index, chunk_id=c.chunk_id, supported=c.supported, reason=c.reason
                )
                for c in s.checks
            ],
        )
        for s in result.sentences
    ]

    total_tokens = (
        result.input_tokens
        + result.output_tokens
        + result.verify_input_tokens
        + result.verify_output_tokens
    )
    cost = estimate_cost(
        result.llm_model, result.input_tokens, result.output_tokens
    ) + estimate_cost(
        get_settings().models.judge_model,
        result.verify_input_tokens,
        result.verify_output_tokens,
    )

    response = AskResponse(
        question=request.question,
        answer=result.answer,
        insufficient=result.insufficient,
        confidence=result.confidence.composite,
        citations=citation_schemas,
        sentences=sentence_schemas,
        breakdown=LatencyBreakdown(
            **retrieval.latencies,
            generate_ms=result.generate_ms,
            verify_ms=result.verify_ms,
            total_ms=round(total_ms, 2),
        ),
        tokens=TokenUsage(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            verify_input_tokens=result.verify_input_tokens,
            verify_output_tokens=result.verify_output_tokens,
            total_tokens=total_tokens,
            cost_usd=round(cost, 8),
        ),
        models=ModelVersions(
            llm_model=result.llm_model,
            embedding_model=result.model_versions.get("embedding_model", ""),
            reranker=retrieval.reranker,
        ),
        request_id=get_request_id(),
    )

    services.querylog.insert(
        {
            "request_id": get_request_id(),
            "question": request.question,
            "answer": result.answer,
            "insufficient": result.insufficient,
            "confidence": result.confidence.composite,
            "citation_count": len(result.citations),
            "supported_citations": sum(1 for c in result.citations if c.supported),
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": response.tokens.cost_usd,
            **retrieval.latencies,
            "generate_ms": result.generate_ms,
            "verify_ms": result.verify_ms,
            "total_ms": round(total_ms, 2),
            "retrieval_method": request.retrieval_method,
            "llm_model": result.llm_model,
            "embedding_model": result.model_versions.get("embedding_model", ""),
            "reranker": retrieval.reranker,
        }
    )
    logger.info(
        "ask_complete",
        extra={
            "insufficient": result.insufficient,
            "confidence": result.confidence.composite,
            "total_ms": round(total_ms, 2),
            "cost_usd": response.tokens.cost_usd,
        },
    )
    return response


@router.post("/ingest", response_model=IngestResponse, summary="Ingest uploaded documents")
async def ingest(
    services: AuthedServices,
    files: list[UploadFile] = File(...),
    _rl: None = Depends(_rate_limited()),
) -> IngestResponse:
    settings = get_settings()
    pipeline = IngestionPipeline(
        embedder=services.embedder,
        store=services.store,
        chunk_size=settings.ingestion_chunk_size,
        overlap=settings.ingestion_overlap,
        default_strategy=settings.ingestion_default_strategy,
        dedup=Deduplicator(
            store=services.store,
            threshold=settings.dedup_threshold,
            mode=settings.dedup_mode,
            scope=settings.dedup_scope,
            top_k=settings.dedup_top_k,
        ),
    )
    results: list[IngestResult] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for upload in files:
            tmp_path = Path(tmpdir) / (upload.filename or "upload")
            tmp_path.write_bytes(await upload.read())
            report = pipeline.ingest_file(tmp_path)
            results.append(
                IngestResult(
                    file=upload.filename or tmp_path.name,
                    document_id=report.document_id,
                    format=report.format,
                    segments=report.segments,
                    chunks_total=report.chunks_total,
                    inserted=report.inserted,
                    skipped=report.skipped,
                    flagged=report.flagged,
                    strategy_counts=report.strategy_counts,
                    duration_ms=report.duration_ms,
                )
            )
    services.refresh_sparse()
    return IngestResponse(
        documents=results,
        total_inserted=sum(r.inserted for r in results),
        index_chunks=services.store.count(),
    )


@router.get("/documents", response_model=DocumentsResponse, summary="List ingested documents")
def documents(services: AuthedServices) -> DocumentsResponse:
    infos = [DocumentInfo(**d) for d in services.documents()]
    return DocumentsResponse(documents=infos, total_chunks=services.store.count())


@router.delete("/documents/{document_id}", status_code=204, summary="Delete a document's chunks")
def delete_document(document_id: str, services: AuthedServices) -> None:
    if not services.delete_document(document_id):
        raise AppError(404, "not_found", f"document not found: {document_id}")


@router.post("/reindex", response_model=ReindexResponse, summary="Zero-downtime reindex")
def reindex(services: AuthedServices) -> ReindexResponse:
    report = services.reindex()
    return ReindexResponse(**report)


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health(request: Request) -> HealthResponse:
    settings = get_settings()
    services = getattr(request.app.state, "services", None)
    qdrant_ok = False
    model_ready = False
    index_chunks: int | None = None
    if isinstance(services, AppServices):
        try:
            index_chunks = services.store.count()
            qdrant_ok = True
        except Exception:  # noqa: BLE001
            qdrant_ok = False
        model_ready = services.model_ready()
    return HealthResponse(
        status="ok" if qdrant_ok and model_ready else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        qdrant=qdrant_ok,
        model_ready=model_ready,
        index_chunks=index_chunks,
    )


@router.get("/metrics", response_model=MetricsResponse, summary="Observability metrics")
def metrics(services: AuthedServices) -> MetricsResponse:
    data = services.querylog.metrics()
    data["model_versions"] = {
        "llm": get_settings().models.llm_model,
        "judge": get_settings().models.judge_model,
        "embedding": get_settings().models.embedding_model_id,
        "reranker": get_settings().models.reranker_cross_encoder_id,
    }
    recent = services.querylog.recent(limit=10)
    for row in recent:
        row["ts"] = row["ts"]
    data["recent_queries"] = recent
    return MetricsResponse(**data)
