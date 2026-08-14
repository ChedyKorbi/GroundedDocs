"""GroundedDocs FastAPI application entrypoint.

Wires middleware, structured error handlers, and the API router. Services are
built lazily on first use so /health works even before infrastructure (Qdrant,
Groq) is reachable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.routes import router
from app.config import get_settings
from app.logging import get_logger, setup_logging
from app.middleware import RequestContextMiddleware, RequestLogMiddleware
from app.services.container import AppServices

settings = get_settings()
setup_logging(settings.log_level)
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Build services at startup; failures are non-fatal.

    /health reports degraded and protected routes return 503 with a clear
    message until infrastructure is available.
    """
    try:
        _app.state.services = AppServices()
        _app.state.services_error = None
        logger.info("services_initialized")
    except Exception as exc:  # noqa: BLE001
        _app.state.services = None
        _app.state.services_error = str(exc)
        logger.error("services_init_failed", extra={"error": str(exc)})
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-grade hybrid RAG system with Arabic support.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(RequestLogMiddleware)
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)
app.include_router(router)
