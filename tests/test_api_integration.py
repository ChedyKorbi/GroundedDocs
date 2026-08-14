"""Integration test: the real HTTP API against live Qdrant + Groq.

Requires RUN_INTEGRATION=1, a seeded Qdrant index, and GROQ_API_KEY.
Covers the frozen contract shape of /ask, /documents, /metrics, /reindex.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _ask(client: TestClient, question: str) -> dict:
    response = client.post("/ask", json={"question": question})
    assert response.status_code == 200, response.text
    return response.json()


def test_health_ready(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["qdrant"] is True
    assert body["index_chunks"] and body["index_chunks"] > 0


def test_ask_grounded_response_shape(client: TestClient) -> None:
    body = _ask(client, "How many days of annual leave do employees accrue per year?")
    assert not body["insufficient"]
    assert body["answer"]
    assert "25" in body["answer"]
    assert 0 <= body["confidence"] <= 1
    assert body["citations"], "expected at least one citation"
    assert body["models"]["llm_model"] == get_settings().models.llm_model
    assert body["breakdown"]["total_ms"] > 0
    assert body["breakdown"]["generate_ms"] > 0
    assert body["tokens"]["total_tokens"] > 0
    assert body["tokens"]["cost_usd"] >= 0
    assert body["request_id"]
    # breakdown covers the stage contract keys
    for stage in ("embed_ms", "dense_ms", "sparse_ms", "fusion_ms", "rerank_ms", "verify_ms"):
        assert stage in body["breakdown"]


def test_ask_insufficient_path(client: TestClient) -> None:
    body = _ask(client, "What is the capital of France?")
    if body["insufficient"]:
        assert body["answer"] == ""
        assert body["confidence"] == 0.0


def test_documents_roundtrip(client: TestClient) -> None:
    body = client.get("/documents").json()
    assert body["total_chunks"] > 0
    assert any(d["document_id"] for d in body["documents"])


def test_metrics_and_recent_queries(client: TestClient) -> None:
    _ask(client, "What is required to access the corporate network remotely?")
    body = client.get("/metrics").json()
    assert body["request_count"] >= 1
    assert body["latency"]["count"] >= 1
    assert body["model_versions"]["embedding"] == get_settings().models.embedding_model_id
    assert body["recent_queries"], "expected at least one logged query"
    assert body["recent_queries"][0]["question"]


def test_reindex_zero_downtime(client: TestClient) -> None:
    before = client.get("/health").json()["index_chunks"]
    body = client.post("/reindex").json()
    assert body["chunks_reindexed"] == before
    assert body["current_collection"]
    assert body["previous_collection"] != body["current_collection"]
    after = client.get("/health").json()["index_chunks"]
    assert after == before  # data intact after the swap
