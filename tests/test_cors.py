"""CORS: the dashboard origin must be able to call the API."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ORIGIN = "http://localhost:3000"


def test_preflight_ask_allows_dashboard_origin() -> None:
    response = client.options(
        "/ask",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ORIGIN


def test_simple_request_echoes_origin() -> None:
    response = client.get("/health", headers={"Origin": ORIGIN})
    assert response.headers.get("access-control-allow-origin") == ORIGIN
