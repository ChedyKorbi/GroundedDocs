"""Auth + rate-limiting tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.auth import verify_api_key
from app.api.errors import AppError
from app.api.ratelimit import TokenBucket, make_rate_limiter


def test_verify_api_key_ok(monkeypatch) -> None:
    from app.config import Settings

    monkeypatch.setattr("app.api.auth.get_settings", lambda: Settings(api_key="secret"))
    verify_api_key("secret")


def test_verify_api_key_rejects(monkeypatch) -> None:
    from app.config import Settings

    monkeypatch.setattr("app.api.auth.get_settings", lambda: Settings(api_key="secret"))
    with pytest.raises(AppError) as excinfo:
        verify_api_key("wrong")
    assert excinfo.value.status_code == 401


def test_no_key_configured_always_passes() -> None:
    verify_api_key(None)


class TestTokenBucket:
    def test_allows_up_to_capacity(self) -> None:
        bucket = TokenBucket(capacity=2.0, refill_per_second=0.0)
        assert bucket.allow("a") is True
        assert bucket.allow("a") is True
        assert bucket.allow("a") is False

    def test_refills_over_time(self) -> None:
        import time

        bucket = TokenBucket(capacity=1.0, refill_per_second=10.0)
        assert bucket.allow("a") is True
        assert bucket.allow("a") is False
        time.sleep(0.15)
        assert bucket.allow("a") is True

    def test_keys_are_isolated(self) -> None:
        bucket = TokenBucket(capacity=1.0, refill_per_second=0.0)
        assert bucket.allow("a") is True
        assert bucket.allow("b") is True


def test_make_rate_limiter_raises_429() -> None:
    dependency = make_rate_limiter(max_requests=1, window_seconds=60)

    class _FakeRequest:
        client = type("C", (), {"host": "127.0.0.1"})()

    dependency(_FakeRequest())  # first call allowed
    with pytest.raises(AppError) as excinfo:
        dependency(_FakeRequest())
    assert excinfo.value.status_code == 429


def test_api_key_header_enforced(monkeypatch) -> None:
    from app.config import Settings

    monkeypatch.setattr("app.config.get_settings", lambda: Settings(api_key="test-key"))
    monkeypatch.setattr("app.api.auth.get_settings", lambda: Settings(api_key="test-key"))

    from app.main import app

    # No context manager: lifespan is not run, so services stay uninitialized and
    # the auth gate is the only behavior under test.
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"
