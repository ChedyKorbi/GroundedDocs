# GroundedDocs

Production-grade hybrid Retrieval-Augmented Generation (RAG) system for enterprise
internal documentation, with hybrid retrieval (dense + sparse), fusion, reranking,
grounded answers with verified citations, and full performance / cost / quality
observability.

> **Status:** Phases 0–8 complete. Full README lands in Phase 9.

## Quick start

```bash
cp .env.example .env          # set GROQ_API_KEY (required for generation)
docker compose up --build     # API + Qdrant, seeds the sample corpus on first boot
curl http://localhost:8000/health
```

Without Docker (Qdrant already running): `uv run uvicorn app.main:app --port 8000`.

**Dashboard (Next.js):**

```bash
cd frontend
npm install
npm run dev                   # http://localhost:3000
```

API docs (Swagger): http://localhost:8000/docs

## Layout

```
app/            FastAPI service (config, logging, middleware, API)
app/core/       pure-Python logic (ingestion, retrieval, generation, evaluation)
app/services/   LangChain 1.x orchestration wiring + service container
frontend/       Next.js dashboard (Ask / Documents / Performance)
scripts/        seed + evaluation entrypoints
docs/           API contract + per-phase engineering documentation
tests/          unit + integration tests
data/           sample corpus + golden evaluation sets
```

## Reference

- `GroundedDocs_PRD_v2.1.docx` — authoritative product specification (Sections 1–11)
- `docs/README.md` — phase-by-phase build narrative
- `docs/API_CONTRACT.md` — frozen API contract v1

## License

MIT — see `LICENSE`.
