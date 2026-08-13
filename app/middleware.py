"""ASGI middleware for request tracing and access logging.

- RequestContextMiddleware assigns/forwards an X-Request-ID and publishes it to
  the request-id contextvar so all log records for a request are correlated.
- RequestLogMiddleware emits a structured access-log line per request with
  method, path, status, and duration.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging import get_logger, set_request_id

logger = get_logger("app.middleware")

_HEADER_REQUEST_ID = "X-Request-ID"


def _new_request_id() -> str:
    return uuid.uuid4().hex


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Generate or accept a request ID and propagate it via contextvars."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = request.headers.get(_HEADER_REQUEST_ID) or _new_request_id()
        set_request_id(request_id)
        response: Response = await call_next(request)
        response.headers[_HEADER_REQUEST_ID] = request_id
        return response


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Emit a structured access log line per request."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "request_failed",
                extra={"method": request.method, "path": request.url.path},
            )
            raise exc
        duration_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "access",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response
