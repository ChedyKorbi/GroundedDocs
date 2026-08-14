# Phase 5 — Production API & Observability

## 1. Phase Intro

Phase 5 exposes the whole pipeline as a real HTTP service with production-grade
observability. `/ask` returns grounded answers with a full per-stage latency
breakdown, token usage, estimated cost, and model versions; every query is
persisted to a query log that `/metrics` aggregates into percentiles and
volume/error/cost summaries. The API is protected by API-key auth, rate
limiting, correlation IDs, and structured error responses, and supports
zero-downtime re-indexing via versioned collections.

## 2. Goal

- Endpoints: `/ask`, `/ingest`, `/documents`, `/metrics`, `/health`, plus
  `/reindex` — all OpenAPI-documented.
- Stage-level latency breakdown (embed / dense / sparse / fusion / rerank /
  generate / verify / total) per query.
- Token usage + estimated cost per query; structured query logs.
- API key auth, rate limiting, correlation IDs, structured error responses.
- Zero-downtime `/reindex` (versioned collections + atomic alias swap).
- Frozen API contract (`docs/API_CONTRACT.md`) — gap-closure #6.
- Model/version registry logged per query — gap-closure #2.

## 3. Description

### Architecture

```
app/api/schemas.py      Frozen request/response models (the contract)
app/api/errors.py       AppError + structured error envelope + handlers
app/api/auth.py         Constant-time API-key dependency
app/api/ratelimit.py    Token-bucket rate limiter (per client IP)
app/api/routes.py       /ask /ingest /documents /metrics /health /reindex
app/services/container.py AppServices: index resolution, retriever, generation,
                          query log, sparse refresh, zero-downtime reindex
app/store/querylog.py   SQLite query log + p50/p95/p99 aggregation
app/core/cost.py        Per-model USD cost estimation
docs/API_CONTRACT.md    Frozen v1 contract
```

### Design decisions

- **Lazy service container.** `AppServices` is built in the lifespan; if Qdrant
  or Groq is unavailable the app still boots, `/health` reports `degraded`, and
  protected routes return a structured `503`. This keeps `/health` a real
  readiness signal (Phase 6 hardens it further) rather than a process liveness
  lie.
- **Stage timing is instrumented at the source.** `HybridRetriever.retrieve`
  records `embed_ms/dense_ms/sparse_ms/fusion_ms/rerank_ms`;
  `GenerationService` records `generate_ms`, `verify_ms`, and now also
  verify-token counts. The `/ask` route composes them into
  `LatencyBreakdown.total_ms`.
- **Query log is the metrics source of truth.** Every `/ask` writes one row
  (question, answer, confidence, citations, tokens, cost, all stage latencies,
  method, model versions). `/metrics` computes percentiles and aggregates from
  SQLite — no in-memory drift, survives restarts.
- **Cost is estimated even on the free tier** (`app/core/cost.py`, Groq
  on-demand prices per model). The dashboard can show "what this would cost at
  production scale". Local embedding is $0 (our hardware).
- **Auth + rate limit are dependencies, errors are an envelope.** `verify_api_key`
  uses `hmac.compare_digest` (constant time). The rate limiter is a per-client
  token bucket (in-memory; Redis is the documented production follow-up). Every
  error — expected or unexpected — returns
  `{"error": {"code", "message", "request_id"}}`.
- **Zero-downtime reindex (gap #1).** `POST /reindex` builds a new
  `groundeddocs_chunks-vN` collection, re-embeds all chunk texts, atomically
  swaps the `groundeddocs_chunks-active` alias, then drops the previous version.
  Readers keep resolving the active collection throughout. This surfaced and
  fixed a real design bug: the initial plain collection shared its name with the
  alias, which Qdrant rejects — the alias now uses a distinct `-active` name.
- **Frozen contract (gap #6).** `docs/API_CONTRACT.md` pins the exact shapes;
  `app/api/schemas.py` is the single implementation of the contract, so the
  dashboard (Phase 8) can build against it without renegotiating the API.

### Alternatives considered

- Prometheus + Grafana now — rejected (structured logs + `/metrics` give the
  same signal with far less moving surface; revisit for Phase 8 if needed).
- Redis-backed rate limiting — documented follow-up; token bucket in-memory is
  correct for single-instance demo scale.
- Eager `AppServices` in tests — rejected; lazy build keeps unit tests
  infra-free.

## 4. Work Done, Step by Step

1. Added stage latencies to `RetrievalResult` and `generate_ms/verify_ms` +
   verify-token counts to `GenerationResult`.
2. `app/core/cost.py` — Groq pricing table + `estimate_cost`.
3. `app/store/querylog.py` — SQLite schema, `insert`, `recent`, `metrics`
   (p50/p95/p99 total + per-stage), error rates, citation accuracy.
4. `app/api/errors.py` — `AppError` + `register_exception_handlers`
   (400/404/405/500 + request_id envelope).
5. `app/api/auth.py` — constant-time API-key dependency (off when unset).
6. `app/api/ratelimit.py` — token bucket + `make_rate_limiter`.
7. `app/api/schemas.py` — frozen contract models.
8. `app/services/container.py` — `AppServices` with alias-aware index
   resolution, sparse refresh, document listing, and zero-downtime `reindex`.
9. `app/api/routes.py` — all endpoints; `/ask` composes the full breakdown and
   persists the query log.
10. `app/main.py` — lifespan service build (non-fatal), exception handlers,
    router.
11. `docs/API_CONTRACT.md` — frozen v1 contract.
12. Tests: cost, query log (percentiles, errors, empty), auth + rate limit,
    updated health/contract tests, and a real-stack API integration suite.
13. Fixed the alias/collection name collision (distinct `-active` alias);
    verified zero-downtime reindex leaves exactly one active version.
14. Live smoke: real `/ask` + `/metrics` captured (see Results).

## 5. Files to Review

| File | Purpose |
|------|---------|
| `app/api/routes.py` | All endpoints + `/ask` breakdown/logging |
| `app/api/schemas.py` | Frozen contract models |
| `app/api/errors.py` | Structured error envelope |
| `app/api/auth.py` | API-key auth |
| `app/api/ratelimit.py` | Token-bucket rate limiting |
| `app/services/container.py` | Service wiring + zero-downtime reindex |
| `app/store/querylog.py` | SQLite query log + percentile metrics |
| `app/core/cost.py` | Cost estimation |
| `app/main.py` | Lifespan + middleware + router |
| `docs/API_CONTRACT.md` | Frozen v1 contract |
| `tests/test_cost.py` | Cost tests |
| `tests/test_querylog.py` | Query log tests |
| `tests/test_api_auth_ratelimit.py` | Auth + rate-limit tests |
| `tests/test_api_integration.py` | Real-stack API tests (integration-marked) |

## 6. Testing

- **Unit (pytest):** 105 passed, 9 integration-marked skipped by default.
  New: cost math, query-log insert/percentiles/error-exclusion/empty, token
  bucket allow/refill/isolation, rate-limit 429 dependency, constant-time auth
  (ok/reject/no-key), API contract (all paths in OpenAPI, health degraded path,
  structured 401/503 without infra).
- **Lint / type / security:** `ruff` clean, `mypy app scripts` strict clean (46
  files), `pip-audit` clean.
- **Real-stack integration (`RUN_INTEGRATION=1`):** 6/6 passing —
  health-ready, grounded `/ask` shape (breakdown + tokens + models +
  request_id), insufficient path, documents roundtrip, metrics + recent
  queries, and zero-downtime `/reindex` (data intact after swap, previous
  version dropped).

## 7. Results

Live `/ask` (real hybrid retrieval + Groq, CPU embeddings):

```
Q: How many days of annual leave do employees accrue per year and how many can carry over?
ANSWER: Employees accrue 25 working days of annual leave per year [1]. They can carry over
        up to a maximum of 10 days into the next calendar year [1].
confidence: 0.974
breakdown: embed 6055ms | dense 8ms | sparse 0.3ms | fusion 0.1ms | rerank 57ms
           generate 429ms | verify 515ms | total 7065ms
tokens: 496 in / 36 out (+529/91 verify) = 1152 total | cost $0.000355
models: llama-3.3-70b-versatile + multilingual-e5-large + cross_encoder
request_id: 347410d8... (correlated across every log line)
```

`/metrics` after 7 queries: 0% error, citation accuracy 1.0, total cost $0.0023,
latency p50 1433ms / p95 8464ms / p99 8639ms (dominated by CPU query-embedding
on first requests; generate p50 501ms), 7 recent queries with full breakdown.

**Zero-downtime reindex (verified live):** `groundeddocs_chunks` → v1 → v2 → v3
→ v4, alias `groundeddocs_chunks-active` always pointing at exactly one active
version; old versions dropped after swap; chunk count preserved (33).

## 8. Deliverables

Matched against the Phase 5 Definition of Done:

- [x] `/ask /ingest /documents /metrics /health /reindex`, OpenAPI-documented
- [x] Stage-level latency breakdown per query
- [x] Token usage + estimated cost per query, persisted query logs
- [x] API key auth, rate limiting, correlation IDs, structured errors
- [x] Model/version registry logged per query
- [x] Zero-downtime `/reindex` (verified live)
- [x] Frozen `docs/API_CONTRACT.md` (v1)
- [x] Unit + real-stack integration tests
- [x] `docs/phases/phase-5-api.md`

## 9. Known Limitations / Follow-ups

- **Query-embedding latency on CPU** (~6s first-call) dominates `/ask` total;
  CUDA torch (tracked since Phase 0) brings embed to single-digit ms. The
  stage breakdown makes this explicit and dashboard-visible.
- **Rate limiter is in-memory / single-instance.** Redis-backed limiting is the
  production-scale follow-up.
- **`/ingest` writes to a temp file then ingests** — fine for uploads; a native
  streaming loader is a follow-up. It also refreshes the in-memory BM25 index
  after upload (no restart needed).
- **`/reindex` re-embeds existing chunk texts** rather than re-ingesting from an
  authoritative document store; a document-origin store is the natural Phase 6+
  extension.
- **Costs are estimates** from public Groq list prices; fine for observability,
  not for billing.
- **Arabic support** in the API is deferred to the v1.1 pass (interface already
  language-agnostic).
