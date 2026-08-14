# GroundedDocs API Contract — v1

Frozen response/request schemas for the GroundedDocs HTTP API. Consumers (the
Phase 8 dashboard) depend on these shapes. **Any schema change requires a
version bump and a dated note here BEFORE the code change.** The authoritative
OpenAPI spec is generated at `/openapi.json`; this document pins the stable
contract semantics.

Version: **1** (frozen Phase 5). Last change: initial freeze.

## Conventions

- Base path: `/`. JSON bodies. Errors use a single envelope:
  ```json
  {"error": {"code": "unauthorized", "message": "a valid API key is required", "request_id": "..."}}
  ```
- Error codes: `unauthorized` (401), `rate_limited` (429), `not_found` (404),
  `method_not_allowed` (405), `service_unavailable` (503), `internal_error` (500).
- Auth: `X-API-Key: <key>` header, required only when `GROUNDEDDOCS_API_KEY` is
  set. `/health` is always unauthenticated (liveness probes).
- Every response carries `X-Request-ID`; `/ask` echoes it in the body.
- Rate limiting: token bucket per client IP
  (`api_rate_limit_max` per `api_rate_limit_window_seconds`). 429 when exceeded.

## Endpoints

| Method | Path | Auth | Summary |
|--------|------|------|---------|
| GET | `/health` | no | Liveness + readiness (Qdrant + index) |
| POST | `/ask` | yes | Grounded question answering |
| POST | `/ingest` | yes | Upload document(s), multipart `files` |
| GET | `/documents` | yes | List ingested documents |
| DELETE | `/documents/{document_id}` | yes | Delete a document's chunks (204) |
| POST | `/reindex` | yes | Zero-downtime re-embed index rebuild |
| GET | `/metrics` | yes | Aggregated observability + recent queries |

## POST /ask

Request:
```json
{"question": "string (1..2000)", "retrieval_method": "hybrid|dense_only|sparse_only", "top_k": 6}
```

Response `200`:
```json
{
  "question": "...",
  "answer": "...",
  "insufficient": false,
  "confidence": 0.974,
  "citations": [{"index": 1, "chunk_id": "uuid", "supported": true, "reason": "..."}],
  "sentences": [{"sentence": "...", "checks": [{"index": 1, "chunk_id": "uuid", "supported": true, "reason": "..."}]}],
  "breakdown": {
    "embed_ms": 12.3, "dense_ms": 4.2, "sparse_ms": 0.8, "fusion_ms": 0.1,
    "rerank_ms": 51.0, "generate_ms": 380.0, "verify_ms": 220.0, "total_ms": 690.0
  },
  "tokens": {
    "input_tokens": 514, "output_tokens": 36,
    "verify_input_tokens": 210, "verify_output_tokens": 24,
    "total_tokens": 784, "cost_usd": 0.000404
  },
  "models": {"llm_model": "llama-3.3-70b-versatile", "embedding_model": "intfloat/multilingual-e5-large", "reranker": "cross_encoder"},
  "request_id": "..."
}
```

Semantics:
- `insufficient=true` → `answer` is `""`, `confidence` is `0.0`; no citations.
- `confidence` is the composite confidence (retrieval + verification + coverage + completeness).
- `supported=false` on a citation means the verifier flagged it; consumers should
  render it as a caveat, not drop the answer.
- `breakdown.*` stage latencies are `null` when a stage did not run (e.g.
  `sparse_ms` is null for `retrieval_method=dense_only`).

## POST /ingest

Multipart form field `files` (one or more). Supported extensions:
`.md`, `.markdown`, `.txt`, `.html`, `.htm`, `.pdf`.

Response `200`:
```json
{
  "documents": [
    {"file": "doc.md", "document_id": "doc", "format": "md", "segments": 1,
     "chunks_total": 14, "inserted": 14, "skipped": 0, "flagged": 0,
     "strategy_counts": {"structure": 14}, "duration_ms": 1459.24}
  ],
  "total_inserted": 14,
  "index_chunks": 47
}
```

## GET /documents

Response `200`:
```json
{"documents": [{"document_id": "employee-handbook", "format": "md", "chunk_count": 14}], "total_chunks": 33}
```

## DELETE /documents/{document_id}

`204` on success; `404` + error envelope when the document has no chunks.

## POST /reindex

Builds a new index version, re-embeds all chunks, atomically swaps the alias,
drops the old version. Response `200`:
```json
{"previous_collection": "groundeddocs_chunks", "current_collection": "groundeddocs_chunks-v2",
 "chunks_reindexed": 33, "duration_ms": 1240.5}
```

## GET /metrics

Response `200`:
```json
{
  "request_count": 12, "success_count": 12, "error_count": 0, "error_rate": 0.0,
  "total_input_tokens": 5000, "total_output_tokens": 400, "total_cost_usd": 0.003,
  "total_citations": 24, "total_supported_citations": 22, "citation_accuracy": 0.9167,
  "latency": {"p50": 680.0, "p95": 1200.0, "p99": 1500.0, "count": 12},
  "stage_latency": {"embed_ms": {...}, "dense_ms": {...}, "sparse_ms": {...},
                    "fusion_ms": {...}, "rerank_ms": {...}, "generate_ms": {...}, "verify_ms": {...}},
  "model_versions": {"llm": "...", "judge": "...", "embedding": "...", "reranker": "..."},
  "recent_queries": [{"request_id": "...", "question": "...", "answer": "...", "ts": 123.0, "...": "..."}]
}
```

## GET /health

Response `200` (always):
```json
{"status": "ok|degraded", "service": "GroundedDocs", "version": "0.1.0", "qdrant": true, "index_chunks": 33}
```

## Revision log

- **2026-08-13** — v1 frozen (Phase 5).
