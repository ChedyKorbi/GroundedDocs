# Phase 6 — Containerization & One-Command Deployment

## 1. Phase Intro

Phase 6 makes the system runnable with one command: `docker compose up`. It adds
a multi-stage Dockerfile (builder resolves deps into a venv, runtime copies only
the venv + code), a compose stack of API + Qdrant with an HF cache volume,
auto-seeding of the sample corpus on first boot, and a `/health` endpoint that
now reports true readiness (Qdrant reachable + index present + embedding model
loaded) instead of process liveness.

## 2. Goal

- Multi-stage Dockerfile (lean runtime image).
- `docker-compose.yml`: API + Qdrant, HF model-cache volume, healthchecks.
- Seed script auto-loads the sample corpus on first boot when the index is empty.
- `/health` verifies DB connection + model readiness.
- Target: anyone can `docker compose up` a working seeded system in ~2 minutes.

## 3. Description

### Architecture

```
Dockerfile            builder (uv sync, incl. ml extra) -> runtime (venv + code)
docker-compose.yml    qdrant + api, healthchecks, hf_cache + qdrant_data volumes
.dockerignore         keeps .venv/.git/caches out of the build context
scripts/seed.py       manual seed entrypoint
app/services/container.py  seed_samples() + model_ready() probes
app/main.py           lifespan auto-seeds when index empty + SEED_ON_BOOT
app/api/routes.py     /health now reports model_ready
docs/API_CONTRACT.md  /health v1 rev 2 adds model_ready
```

### Design decisions

- **Multi-stage build.** The builder runs `uv sync --frozen --no-group dev
  --extra ml` into a project venv; the runtime copies that venv + code. No build
  tools, no dev deps, no source caches in the final image.
- **CPU-only torch (important lesson).** PyPI's *Linux* `torch` wheel defaults
  to the CUDA bundle (~3-4 GB). The first Docker build silently pulled
  `nvidia-cudnn/cublas/nccl` etc. and produced an **8.71 GB** image — a genuine
  production smell caught only by measuring the image. Fixed at the source:
  `[tool.uv.sources]` forces the `pytorch-cpu` index
  (`torch 2.13.0+cpu`), which slashes the deps layer and matches how we actually
  run (CPU). The lockfile now pins `+cpu` everywhere.
- **Seed-on-boot.** `SEED_ON_BOOT=true` (default): in the lifespan, if the active
  index has 0 chunks, `AppServices.seed_samples()` ingests `data/samples` through
  the normal pipeline (with dedup). Idempotent — subsequent boots are no-ops.
  Also exposed as `scripts/seed.py` for manual runs.
- **Readiness over liveness.** `/health` now returns `status: ok` only when
  Qdrant responds AND the embedding model loads (probed once, cached). Contract
  v1 rev 2.
- **HF cache volume** (`hf_cache:/cache/huggingface`) so model downloads happen
  once per machine, not per container restart.

### Alternatives considered

- `langchain` CPU torch override in the Dockerfile via a constraints file —
  rejected; the uv source override fixes it in the single source of truth (lock)
  for every environment, not just Docker.

## 4. Work Done, Step by Step

1. `app/config.py`: `seed_on_boot`, `seed_samples_dir`; `.env.example` updated.
2. `app/services/container.py`: `model_ready()` (cached probe) and
   `seed_samples()` (pipeline + dedup + sparse refresh).
3. `scripts/seed.py` — manual seed entrypoint.
4. `app/main.py` — lifespan auto-seeds an empty index; logs the result.
5. `app/api/routes.py` + `app/api/schemas.py` + `docs/API_CONTRACT.md` — `/health`
   readiness includes `model_ready`.
6. `Dockerfile` — multi-stage; `.dockerignore`; `docker-compose.yml` — qdrant +
   api, healthchecks, volumes.
7. Fixed the CUDA-torch bloat via `[tool.uv.sources]` pytorch-cpu; re-locked.
8. Verified locally: app boots, `/health` = `status:ok, qdrant:true,
   model_ready:true, index_chunks:33`.
9. Docker image build verification deferred (see Known Limitations).

## 5. Files to Review

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build (builder venv → lean runtime) |
| `.dockerignore` | Build-context exclusions |
| `docker-compose.yml` | API + Qdrant stack, healthchecks, volumes |
| `scripts/seed.py` | Manual corpus seeding |
| `app/services/container.py` | `seed_samples()`, `model_ready()` |
| `app/main.py` | Auto-seed on empty index |
| `app/api/routes.py` | `/health` readiness incl. model |
| `pyproject.toml` | `[tool.uv.sources]` CPU-torch pin |
| `docs/API_CONTRACT.md` | `/health` v1 rev 2 |

## 6. Testing

- **Unit (pytest):** 105 passed, 9 integration-marked skipped by default. Phase 6
  changes are covered by the existing suite (health contract, container).
- **Lint / type:** `ruff` clean, `mypy app scripts` strict clean (47 files),
  format clean.
- **Local runtime:** `uv run uvicorn app.main:app` → `/health` returns
  `{"status":"ok","qdrant":true,"model_ready":true,"index_chunks":33}`.
- **Docker build:** first attempt produced an **8.71 GB** image (CUDA torch) —
  found and root-caused; the CPU-torch lockfile fix is verified locally but the
  image rebuild itself was paused (see Known Limitations).

## 7. Results

- Local readiness probe: `/health` → `status: ok` (Qdrant + index + model).
- Image bloat root cause quantified: default Linux `torch` wheel pulled ~3-4 GB
  of CUDA libraries (`nvidia-cudnn`, `nvidia-cublas`, `nvidia-nccl`, …);
  `2.13.0+cu130` → fixed to `2.13.0+cpu` in the lockfile.
- Docker disk reclaimed: ~20 GB (9 GB image + CUDA build cache) pruned while
  pausing the Docker workstream.

## 8. Deliverables

Matched against the Phase 6 Definition of Done:

- [x] Multi-stage Dockerfile (CPU-torch, lean by design)
- [x] docker-compose.yml: API + Qdrant + healthchecks + HF cache volume
- [x] Seed-on-boot (lifespan auto-seed) + `scripts/seed.py`
- [x] `/health` verifies DB + model readiness (contract v1 rev 2)
- [ ] **Full `docker compose up --build` verification — DEFERRED** (Docker
      workstream paused after the CUDA-torch bloat was found; rebuild with the
      CPU fix is the immediate next Docker task)
- [x] `docs/phases/phase-6-containerization.md`

## 9. Known Limitations / Follow-ups

- **Docker image rebuild + full `docker compose up` verification pending.** The
  CPU-torch fix is in the lockfile and verified locally; the next Docker session
  runs `docker compose up --build` and confirms the image is lean (~2-3 GB) and
  self-seeds.
- **First boot downloads models** (e5-large + cross-encoder, ~2.5 GB) into the
  HF cache volume; the healthcheck `start_period` tolerates this.
- **CI Docker build** in GitHub Actions will also benefit from the CPU-torch pin
  (faster, smaller); already wired via the workflow's `docker build`.
- **Arabic support** remains deferred to the v1.1 pass.
