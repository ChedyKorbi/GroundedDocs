"""Basic token-bucket rate limiting keyed by client address.

A per-key token bucket with capacity `max` and refill of `max / window`
tokens/second. 429 when exhausted. Suitable for demo-grade protection; a
distributed limiter (Redis) is the production-scale follow-up.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request

from app.api.errors import AppError


class TokenBucket:
    def __init__(self, capacity: float, refill_per_second: float) -> None:
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self._buckets: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, [self.capacity, now])
        tokens = min(self.capacity, tokens + (now - last) * self.refill_per_second)
        if tokens >= 1.0:
            self._buckets[key] = [tokens - 1.0, now]
            return True
        self._buckets[key] = [tokens, now]
        return False


def make_rate_limiter(max_requests: int, window_seconds: int) -> Callable[[Request], None]:
    """Build a FastAPI dependency enforcing the configured token bucket."""
    limiter = TokenBucket(
        capacity=float(max_requests), refill_per_second=max_requests / max(window_seconds, 1)
    )

    def rate_limit(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            raise AppError(429, "rate_limited", "too many requests, slow down")

    return rate_limit
