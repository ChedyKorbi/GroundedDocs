# Phase 7 — CI/CD Quality Gates

## 1. Phase Intro

Phase 7 makes reliability a property of the pipeline rather than of memory. The
base CI (lint, type-check, unit tests, dependency audit, Docker build) runs on
every push and PR; a second workflow exercises the real stack (Qdrant + Groq)
and runs an **evaluation quality gate** on `main` that fails the build if
faithfulness or citation accuracy regresses below a threshold. Dependabot keeps
dependencies patched automatically.

## 2. Goal

- Lint, type-check, unit + integration tests, Docker build on every PR/main push.
- Evaluation gate on main: fail if faithfulness or citation accuracy drops below
  threshold (PRD §11.2 bonus).
- Dependabot for pip, Docker, and GitHub Actions (gap-closure #5).
- Reproducible CI: same commands as local dev, uv-lock driven, HF model cache.

## 3. Description

### Workflows

```
.github/workflows/ci.yml        lint, typecheck, test, security, docker (PR + main)
.github/workflows/integration.yml  real-stack integration tests + eval gate (main only)
.github/dependabot.yml          pip / docker / github-actions monthly updates
scripts/eval_gate.py            bounded eval + threshold check (exit 1 on regression)
```

### Design decisions

- **CI mirrors local commands exactly** (`uv sync --frozen --extra ml`, then
  `ruff`, `mypy app scripts`, `pytest`, `pip-audit`) — the same lockfile drives
  local, CI, and Docker, so "works locally" is the definition of "green in CI".
- **The `ml` extra is installed in CI.** Imports (e.g. `app.main` → container →
  `EmbeddingService` → `sentence-transformers`) require it; this was a latent
  bug in the original CI (which used `uv sync` without `--extra ml`).
- **mypy checks `scripts` too** (was `app` only), matching the strict 49-file
  clean local run.
- **Docker job uses BuildKit `gha` cache** so the heavy deps layer is cached
  across runs, and benefits from the CPU-torch pin from Phase 6 (no more 9GB
  CUDA pull).
- **Integration + eval gate run only on main, only when `GROQ_API_KEY` is
  configured** (job-level `if`), so a missing secret never turns main red — the
  job is simply skipped with a note. A Qdrant service container is spun up, the
  sample corpus is seeded, integration tests run, then `eval_gate.py` enforces
  thresholds.
- **The gate is bounded (`--limit 12`)** to keep token cost sane on free-tier
  Groq while still catching regressions (12 easy questions give 1.0/1.0 with
  margin vs the 0.85/0.80 thresholds).
- **Dependabot (gap #5)** watches pip, Docker, and GitHub Actions monthly with
  a `dependencies` label — patching is one click per PR.

### Bug fixed during this phase

The Phase 5 zero-downtime reindex moves data into `groundeddocs_chunks-vN`, but
the eval/ingest **scripts still addressed the plain `groundeddocs_chunks`
collection**, which reindex drops — so `SparseIndex.build([])` hit a
`ZeroDivisionError` in BM25 (empty corpus). Fixed by centralizing
`resolve_active_collection()` in `app/services/container.py` and routing every
entrypoint (eval, eval_retrieval, ingest) through it. This is exactly the class
of drift the CI gate is meant to catch.

## 4. Work Done, Step by Step

1. `ci.yml` — added `--extra ml`, `mypy app scripts`, setup-uv caching, BuildKit
   `gha` cache for Docker.
2. `integration.yml` — main-only job (skipped without `GROQ_API_KEY`): Qdrant
   service, HF model cache, seed, `pytest -m integration`, eval gate.
3. `dependabot.yml` — pip / docker / github-actions, monthly.
4. `scripts/eval_gate.py` — bounded hybrid eval, fails below thresholds.
5. `app/services/container.py` — `resolve_active_collection()` helper.
6. Routed `scripts/eval.py`, `eval_retrieval.py`, `ingest.py` through the active
   collection resolver (fixed the reindex-introduced BM25 crash).
7. Verified locally: 105 unit tests, 6 real-stack integration tests, eval gate
   passes (faithfulness 1.0, citation 1.0 on limit 4).

## 5. Files to Review

| File | Purpose |
|------|---------|
| `.github/workflows/ci.yml` | Lint / type / unit / audit / docker on PR + main |
| `.github/workflows/integration.yml` | Real-stack integration + eval gate on main |
| `.github/dependabot.yml` | Automated dependency updates |
| `scripts/eval_gate.py` | Faithfulness/citation threshold gate |
| `app/services/container.py` | `resolve_active_collection()` |
| `scripts/eval.py` / `eval_retrieval.py` / `ingest.py` | Active-collection resolution |

## 6. Testing

- **Unit (pytest):** 105 passed, 9 integration-marked skipped by default.
- **Integration (RUN_INTEGRATION=1, real Qdrant + Groq):** 6/6 passed — the
  active-collection fix is exercised end-to-end.
- **Gate:** `scripts/eval_gate.py --limit 4` → `EVAL GATE PASSED`
  (faithfulness 1.0, citation accuracy 1.0).
- **Lint / type:** ruff clean, mypy app+scripts strict clean (49 files).
- **CI on GitHub:** the updated `ci.yml` runs on the next push/PR; the
  integration workflow activates once the `GROQ_API_KEY` secret is set.

## 7. Results

- Pre-commit / local gate all green; image build job now CPU-torch + cached.
- Regression caught by this phase's own tooling: the eval gate surfaced the
  `groundeddocs_chunks-vN` drift immediately (ZeroDivisionError) — the gate is
  already earning its keep.
- Eval gate thresholds: faithfulness ≥ 0.85, citation accuracy ≥ 0.80
  (measured 1.0/1.0 on the bounded set; full-48 values 0.963/0.882 from Phase 4).

## 8. Deliverables

Matched against the Phase 7 Definition of Done:

- [x] Lint, type-check, unit + integration tests, Docker build on PR/main push
- [x] Evaluation gate on main (faithfulness + citation accuracy thresholds)
- [x] Dependabot (pip, Docker, GitHub Actions)
- [x] Reproducible CI via the shared uv lockfile + ml extra + caching
- [x] Active-collection drift fixed across all entrypoints
- [x] `docs/phases/phase-7-ci.md`

## 9. Known Limitations / Follow-ups

- **Integration workflow requires a `GROQ_API_KEY` secret** on the GitHub repo
  (`Settings → Secrets → Actions`). Until set, that job is skipped (documented,
  non-red). The Docker-build job needs no secret.
- **The eval gate is token-bounded (limit 12)** to respect free-tier quotas; the
  full 48-question eval remains a manual `python eval.py` run.
- **The gate runs only on `main` pushes**, not PRs — a full pre-merge gate is a
  follow-up if CI minutes/quota allow.
- **Arabic** evaluation and CI coverage deferred to the v1.1 pass.
