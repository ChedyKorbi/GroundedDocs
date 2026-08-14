"""Structured query log persisted to SQLite.

Every /ask request records the full breakdown (question, answer, confidence,
citations, tokens, per-stage latency, estimated cost, model versions) so
/metrics and the dashboard can aggregate without re-running inference.
"""

from __future__ import annotations

import sqlite3
import statistics
import time
from pathlib import Path
from typing import Any

from app.logging import get_logger

logger = get_logger("app.store.querylog")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS query_log (
    request_id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    question TEXT NOT NULL,
    answer TEXT,
    insufficient INTEGER NOT NULL DEFAULT 0,
    confidence REAL,
    citation_count INTEGER NOT NULL DEFAULT 0,
    supported_citations INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    embed_ms REAL, dense_ms REAL, sparse_ms REAL, fusion_ms REAL, rerank_ms REAL,
    generate_ms REAL, verify_ms REAL, total_ms REAL,
    retrieval_method TEXT,
    llm_model TEXT,
    embedding_model TEXT,
    reranker TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_querylog_ts ON query_log(ts);
"""


class QueryLog:
    """SQLite-backed query log."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def insert(self, record: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO query_log (
                request_id, ts, question, answer, insufficient, confidence,
                citation_count, supported_citations, input_tokens, output_tokens,
                cost_usd, embed_ms, dense_ms, sparse_ms, fusion_ms, rerank_ms,
                generate_ms, verify_ms, total_ms, retrieval_method,
                llm_model, embedding_model, reranker, error
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                record.get("request_id"),
                record.get("ts", time.time()),
                record.get("question", ""),
                record.get("answer"),
                int(bool(record.get("insufficient"))),
                record.get("confidence"),
                int(record.get("citation_count", 0)),
                int(record.get("supported_citations", 0)),
                int(record.get("input_tokens", 0)),
                int(record.get("output_tokens", 0)),
                float(record.get("cost_usd", 0.0)),
                record.get("embed_ms"),
                record.get("dense_ms"),
                record.get("sparse_ms"),
                record.get("fusion_ms"),
                record.get("rerank_ms"),
                record.get("generate_ms"),
                record.get("verify_ms"),
                record.get("total_ms"),
                record.get("retrieval_method"),
                record.get("llm_model"),
                record.get("embedding_model"),
                record.get("reranker"),
                record.get("error"),
            ),
        )
        self._conn.commit()

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM query_log ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        columns = [c[0] for c in self._conn.execute("SELECT * FROM query_log LIMIT 0").description]
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def metrics(self) -> dict[str, Any]:
        total = self._conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
        errors = self._conn.execute(
            "SELECT COUNT(*) FROM query_log WHERE error IS NOT NULL"
        ).fetchone()[0]
        success = total - errors
        totals = self._conn.execute(
            "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0),"
            " COALESCE(SUM(cost_usd),0), COALESCE(SUM(citation_count),0),"
            " COALESCE(SUM(supported_citations),0)"
            " FROM query_log"
        ).fetchone()
        return {
            "request_count": total,
            "success_count": success,
            "error_count": errors,
            "error_rate": round(errors / total, 4) if total else 0.0,
            "total_input_tokens": int(totals[0]),
            "total_output_tokens": int(totals[1]),
            "total_cost_usd": round(float(totals[2]), 6),
            "total_citations": int(totals[3]),
            "total_supported_citations": int(totals[4]),
            "citation_accuracy": round(totals[4] / totals[3], 4) if totals[3] else None,
            "latency": self._percentiles("total_ms"),
            "stage_latency": {
                "embed_ms": self._percentiles("embed_ms"),
                "dense_ms": self._percentiles("dense_ms"),
                "sparse_ms": self._percentiles("sparse_ms"),
                "fusion_ms": self._percentiles("fusion_ms"),
                "rerank_ms": self._percentiles("rerank_ms"),
                "generate_ms": self._percentiles("generate_ms"),
                "verify_ms": self._percentiles("verify_ms"),
            },
        }

    def _percentiles(self, column: str) -> dict[str, float | None]:
        rows = self._conn.execute(
            f"SELECT {column} FROM query_log WHERE {column} IS NOT NULL AND error IS NULL"
        ).fetchall()
        values = [float(r[0]) for r in rows]
        if not values:
            return {"p50": None, "p95": None, "p99": None, "count": 0}
        values.sort()
        return {
            "p50": round(statistics.median(values), 2),
            "p95": round(_percentile(values, 0.95), 2),
            "p99": round(_percentile(values, 0.99), 2),
            "count": len(values),
        }

    def close(self) -> None:
        self._conn.close()


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * q
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if c == f:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)
