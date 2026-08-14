"""API key authentication.

Enforced when `GROUNDEDDOCS_API_KEY` is set. Comparison is constant-time. The
`/health` probe stays unauthenticated for container liveness checks.
"""

from __future__ import annotations

import hmac

from fastapi import Header

from app.api.errors import AppError
from app.config import get_settings


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency: 401 unless a valid API key is supplied."""
    settings = get_settings()
    expected = settings.api_key
    if not expected:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise AppError(401, "unauthorized", "a valid API key is required")
