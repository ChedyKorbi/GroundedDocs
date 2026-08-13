"""GroundedDocs FastAPI application entrypoint.

Phase 0 scope: boot an empty-but-healthy API. `/health` reports process
liveness only; database + model readiness checks are added in Phase 6.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import get_settings
from app.logging import get_logger, setup_logging
from app.middleware import RequestContextMiddleware, RequestLogMiddleware

settings = get_settings()
setup_logging(settings.log_level)
logger = get_logger("app.main")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-grade hybrid RAG system with Arabic support.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(RequestLogMiddleware)
app.add_middleware(RequestContextMiddleware)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Process liveness probe. Extended with DB/model checks in Phase 6."""
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}
