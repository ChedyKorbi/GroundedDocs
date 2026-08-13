"""Phase 0 smoke tests: app boots, health responds, tracing headers flow."""

from fastapi.testclient import TestClient

from app.config import ModelRegistry, get_settings
from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "GroundedDocs"


def test_request_id_generated() -> None:
    response = client.get("/health")
    assert response.headers.get("X-Request-ID") is not None


def test_request_id_echoed() -> None:
    response = client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
    assert response.headers.get("X-Request-ID") == "trace-abc-123"


def test_openapi_available() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths


def test_model_registry_defaults() -> None:
    registry = ModelRegistry()
    assert registry.embedding_model_id == "intfloat/multilingual-e5-large"
    assert registry.llm_provider == "groq"


def test_settings_singleton() -> None:
    assert get_settings() is get_settings()
