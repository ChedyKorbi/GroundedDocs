"""Query log tests: persistence, percentiles, metrics aggregation."""

from app.store.querylog import QueryLog, _percentile


def test_insert_and_recent(tmp_path) -> None:
    log = QueryLog(tmp_path / "queries.db")
    log.insert({"request_id": "r1", "question": "q1", "answer": "a1", "total_ms": 100.0})
    log.insert({"request_id": "r2", "question": "q2", "answer": "a2", "total_ms": 200.0})
    recent = log.recent(limit=5)
    assert len(recent) == 2
    assert recent[0]["request_id"] == "r2"  # newest first
    assert recent[1]["question"] == "q1"
    log.close()


def test_metrics_percentiles(tmp_path) -> None:
    log = QueryLog(tmp_path / "queries.db")
    for i in range(1, 101):
        log.insert(
            {
                "request_id": f"r{i}",
                "question": f"q{i}",
                "answer": "a",
                "input_tokens": 10,
                "output_tokens": 5,
                "cost_usd": 0.000001,
                "citation_count": 2,
                "supported_citations": 2,
                "embed_ms": 10.0,
                "dense_ms": 20.0,
                "total_ms": float(i),
            }
        )
    metrics = log.metrics()
    assert metrics["request_count"] == 100
    assert metrics["error_rate"] == 0.0
    assert metrics["total_input_tokens"] == 1000
    assert metrics["citation_accuracy"] == 1.0
    assert metrics["latency"]["count"] == 100
    assert metrics["latency"]["p50"] == 50.5
    assert metrics["latency"]["p95"] == 95.05
    assert metrics["latency"]["p99"] == 99.01
    assert metrics["stage_latency"]["dense_ms"]["count"] == 100
    log.close()


def test_error_rows_excluded_from_latency(tmp_path) -> None:
    log = QueryLog(tmp_path / "queries.db")
    log.insert({"request_id": "ok", "question": "q", "total_ms": 10.0})
    log.insert({"request_id": "bad", "question": "q", "total_ms": None, "error": "boom"})
    metrics = log.metrics()
    assert metrics["error_count"] == 1
    assert metrics["error_rate"] == 0.5
    assert metrics["latency"]["count"] == 1
    log.close()


def test_empty_log(tmp_path) -> None:
    log = QueryLog(tmp_path / "queries.db")
    metrics = log.metrics()
    assert metrics["request_count"] == 0
    assert metrics["error_rate"] == 0.0
    assert metrics["latency"]["p50"] is None
    log.close()


def test_percentile_interpolation() -> None:
    assert _percentile([1, 2, 3, 4], 0.5) == 2.5
    assert _percentile([1, 2, 3, 4], 1.0) == 4.0
    assert _percentile([5], 0.9) == 5.0
