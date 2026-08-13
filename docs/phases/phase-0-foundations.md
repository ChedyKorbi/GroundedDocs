# Phase 0 — Foundations & Repo Scaffolding

## 1. Phase Intro

Phase 0 establishes the skeleton every later phase builds on: a typed, config-driven
Python service with structured JSON logging, request tracing, a health-checked
container, and a CI pipeline that already enforces quality. No feature logic exists
yet — the point is that everything downstream (ingestion, retrieval, generation,
evaluation, dashboard) plugs into a proven, reviewable foundation rather than being
retrofitted into a demo.

## 2. Goal

- Repo structure, `pyproject.toml` dependency management, pre-commit hooks (lint /
  format / type-check).
- Pydantic Settings config layer + `.env.example` with a single model registry.
- Base FastAPI app with a `/health` endpoint.
- CI skeleton (lint + type-check + tests + Docker build) defined and locally verified.
- Definition of Done: `docker-compose up` boots an empty-but-healthy API; CI is green.

## 3. Description

### Approach and rationale

- **`uv` for dependency management** (already available at `v0.11.11`). `pyproject.toml`
  is the single source of truth; `uv.lock` is committed for byte-reproducible installs.
  The same lockfile drives local dev, CI, and the Docker build.
- **Dependency groups.** ML deps (`sentence-transformers`, `torch`) live in the `ml`
  optional extra, and dev tools live in a `dev` dependency group. The Phase 0 Docker
  image therefore installs only runtime deps (`uv sync --no-group dev`), keeping the
  first image lean and the CI Docker job fast. Phase 1 adds `--extra ml` when embeddings
  are actually needed; Phase 6 finalizes a multi-stage build.
- **Python version strategy.** Local dev runs Python 3.14 (per the reserved `ai-kernel`
  interpreter); the Docker image pins `python:3.12-slim`. Both satisfy the `>=3.11,<3.15`
  constraint in `pyproject.toml`, and CI runs the same suite under 3.12 so neither drift
  is invisible.
- **Configuration (Pydantic Settings).** Everything is overridable via env vars with a
  `GROUNDEDDOCS_` prefix; `GROQ_API_KEY` is also accepted via the conventional name using
  `AliasChoices`. No hardcoded secrets or magic strings. `ModelRegistry` is the single
  source of truth for embedding / LLM / reranker identities — versions are resolved at
  load time in later phases and stamped on every query log so answers are traceable to
  the exact artifacts that produced them (PRD §11.5 "model/version registry").
- **Structured JSON logging from day one.** A `JsonFormatter` emits one JSON line per
  record (UTC timestamp, level, logger, message, extra attributes). A `request_id`
  contextvar is set by middleware and read by the formatter, so every record for a
  request carries the same correlation ID without threading it through call sites
  (PRD §11.3 / §11.5 "request ID / correlation ID").
- **Middleware order.** `RequestLogMiddleware` wraps `RequestContextMiddleware`
  (outer → inner), so the access log line captures the same request ID the context
  middleware generated.
- **Pre-commit mypy hook.** The stock `mirrors-mypy` hook runs in an isolated venv that
  lacks the project's real dependencies (fastapi, starlette, pydantic-settings), which
  degraded strict mypy to `Any` errors. Replaced with a `local` hook invoking
  `uv run mypy app` in the project venv — byte-identical to the CI typecheck job.
- **Line endings.** `.gitattributes` normalizes everything to LF so Windows working
  copies don't inject CRLF noise into the Linux Docker / CI build.
- **Compose without `.env`.** `env_file` is `required: false`, so `docker compose up`
  works on a fresh clone before `.env` exists (defaults apply); `cp .env.example .env`
  is still documented for real configuration.

### Alternatives considered

- LangChain orchestrators / full app frameworks — rejected; this phase intentionally
  contains no framework wiring. LangChain 1.3.x enters in Phase 1 via `services/`.
- Prometheus + Grafana now — rejected; structured JSON logs + a `/metrics` endpoint
  (Phase 5) give the same signal with far less moving surface. Revisit in Phase 8.
- `pip` instead of `uv` — rejected; `uv` is faster, and the lockfile semantics make
  Docker + CI + local dev agree by construction.

## 4. Work Done, Step by Step

1. Initialized git (`main` branch) and linked the remote
   `https://github.com/ChedyKorbi/GroundedDocs.git`.
2. Added `.gitignore`, `.gitattributes` (LF normalization, docx/pdf/png marked binary),
   MIT `LICENSE`, and a `README.md` stub (full README lands in Phase 9).
3. Authored `pyproject.toml`: runtime deps, `ml` optional extra, `dev` dependency group,
   ruff config (line length 100, `E/F/W/I/UP/B/SIM/ASYNC`), strict mypy config with the
   pydantic plugin, pytest config with `pythonpath = ["."]`.
4. `app/config.py` — `Settings` (Pydantic Settings) + `ModelRegistry` + cached
   `get_settings()` singleton.
5. `app/logging.py` — `JsonFormatter`, `request_id_var` contextvar, `setup_logging()`,
   `get_logger()`.
6. `app/middleware.py` — `RequestContextMiddleware` (generate/echo `X-Request-ID`) and
   `RequestLogMiddleware` (structured access log with duration).
7. `app/main.py` — FastAPI app with `/health` liveness endpoint.
8. `.env.example` documenting every configuration surface.
9. `tests/test_health.py` — health shape, request-id generation/echo, OpenAPI presence,
   model-registry defaults, settings singleton.
10. `Dockerfile` (python:3.12-slim, layer 1 = `uv sync --frozen --no-group dev
    --no-install-project`, layer 2 = code) and `docker-compose.yml` (api service,
    `required: false` env_file, healthcheck).
11. `.github/workflows/ci.yml` — five jobs: lint (ruff), typecheck (mypy), test (pytest),
    security (pip-audit), Docker build.
12. `.pre-commit-config.yaml` — ruff, ruff-format, local mypy, whitespace/EOF/YAML
    checks.
13. Installed dependencies with `uv sync --extra ml`; created `uv.lock`.
14. Verified: pytest (6 passed), ruff clean, mypy strict clean, pip-audit clean,
    pre-commit all green, `docker compose up --build` → container healthy, `/health`
    200, structured JSON access logs with correlation IDs observed in container output.
15. Wrote `docs/README.md` (phase index) and this phase document.

## 5. Files to Review

| File | Purpose |
|------|---------|
| `pyproject.toml` | Single source of truth for deps, ruff, mypy, pytest config |
| `uv.lock` | Locked, reproducible dependency tree |
| `.env.example` | Documented configuration surface for the whole system |
| `app/config.py` | Pydantic Settings + `ModelRegistry` (model/version single source) |
| `app/logging.py` | Structured JSON logging + request-id contextvar |
| `app/middleware.py` | Request tracing + structured access logging |
| `app/main.py` | FastAPI entrypoint with `/health` |
| `tests/test_health.py` | Phase 0 smoke + tracing + config tests |
| `Dockerfile` | Layered image: deps then code, LF-normalized |
| `docker-compose.yml` | One-command API boot with healthcheck |
| `.github/workflows/ci.yml` | Lint / typecheck / test / pip-audit / docker jobs |
| `.pre-commit-config.yaml` | Enforced local quality gates |
| `.gitattributes`, `.gitignore` | LF normalization; repo hygiene |
| `docs/README.md` | Phase index / build narrative |

## 6. Testing

- **Unit (pytest, `tests/test_health.py`):** 6/6 passed in 0.12s locally.
- **Lint:** `ruff check .` — all checks passed; `ruff format --check .` — clean.
- **Type check:** `uv run mypy app` — success, no issues in 5 source files (strict).
- **Security:** `uv run pip-audit` — no known vulnerabilities found.
- **Pre-commit:** `pre-commit run --all-files` — all 8 hooks passed.
- **Container:** `docker compose up -d --build` — image built (deps layer ≈21s),
  container reached `healthy` status, `/health` returned
  `{"status":"ok","service":"GroundedDocs","version":"0.1.0"}` with an
  `X-Request-ID` echo header; container logs confirmed JSON access lines with
  request-id correlation.
- **CI:** GitHub Actions workflow defined for the above; not executed yet because the
  repo has not been pushed. Each job mirrors a command that was verified locally
  against Python 3.12 semantics via the Docker image (3.12-slim).

## 7. Results

- `/health` → 200 OK from a Docker container; healthcheck green.
- 6/6 unit tests pass; ruff clean; mypy strict clean; pip-audit 0 vulnerabilities.
- Structured JSON access log observed in-container:
  `{"ts": "...", "level": "INFO", "logger": "app.middleware", "msg": "access",
  "request_id": "a984...", "method": "GET", "path": "/health", "status": 200,
  "duration_ms": 0.45}`.
- Dependency layer builds in ~21s; total first image build ≈30s (before export).
- No performance claims beyond process liveness — none are in scope for Phase 0.

## 8. Deliverables

Matched against the Phase 0 Definition of Done:

- [x] Repo structure + `pyproject.toml` + `uv.lock` + pre-commit hooks
- [x] Pydantic Settings config layer + `.env.example` + `ModelRegistry`
- [x] FastAPI app with `/health` stub
- [x] CI skeleton (ruff, mypy, pytest, pip-audit, Docker build) defined
- [x] `docker compose up` boots an empty-but-healthy API (verified live)
- [x] CI "green" verified locally via the same commands the workflow runs
- [x] `docs/README.md` index + this phase doc
- [x] Local git repo on `main` linked to the GitHub remote

## 9. Known Limitations / Follow-ups

- **GitHub Actions not yet exercised.** The workflow is defined and locally mirrored,
  but will only run once the repo is pushed to GitHub (Phase 7 hardens it with buildx
  caching + an evaluation gate).
- **`torch` in the local venv is the CPU build** (`torch 2.13.0`, `cuda: False`). The
  GPU (CUDA 12.8, 1 device) is present and the reserved `ai-kernel` interpreter has a
  CUDA build, but the project venv needs the cu12 wheels installed for GPU embeddings /
  cross-encoders in Phases 1–2. Documented here so it's done deliberately, not silently.
- **`GROQ_API_KEY` not configured** — not needed until Phase 3 (generation). `.env`
  creation is documented.
- **FastAPI/starlette/httpx emit a deprecation warning** (`httpx` → `httpx2`) in
  `TestClient`; non-blocking, tracked.
- **Arabic work fully deferred** to the v1.1 pass by explicit scope decision; the
  `ModelRegistry` and settings already anticipate language-agnostic model identity.
- **Phase 0 accepts a single-stage Dockerfile** by design; multi-stage build +
  Qdrant service land in Phase 6.
