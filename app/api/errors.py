"""Structured error responses.

Every failure returns a consistent envelope:
    {"error": {"code": "...", "message": "...", "request_id": "..."}}
Handlers are registered in main.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.logging import get_request_id


class AppError(Exception):
    """Raised for expected API failures; carries the HTTP status + error code."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _payload(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": get_request_id()}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_payload(exc.code, exc.message))

    @app.exception_handler(status.HTTP_404_NOT_FOUND)
    async def not_found_handler(_request: Request, _exc) -> JSONResponse:  # type: ignore[no-untyped-def]
        return JSONResponse(status_code=404, content=_payload("not_found", "resource not found"))

    @app.exception_handler(status.HTTP_405_METHOD_NOT_ALLOWED)
    async def method_handler(_request: Request, _exc) -> JSONResponse:  # type: ignore[no-untyped-def]
        return JSONResponse(
            status_code=405, content=_payload("method_not_allowed", "method not allowed")
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
        from app.logging import get_logger

        get_logger("app.api.errors").error("unhandled_error", extra={"error": str(exc)})
        return JSONResponse(
            status_code=500, content=_payload("internal_error", "internal server error")
        )
