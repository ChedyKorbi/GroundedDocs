# GroundedDocs

Production-grade hybrid Retrieval-Augmented Generation (RAG) system for enterprise
internal documentation, with hybrid retrieval (dense + sparse), fusion, reranking,
grounded answers with verified citations, and full performance / cost / quality
observability.

> **Status:** Phase 0 (Foundations) — scaffold in progress. Full README lands in Phase 9.

## Quick start (Phase 0)

```bash
cp .env.example .env          # set GROQ_API_KEY when generation work begins (Phase 3)
docker compose up --build
curl http://localhost:8000/health
```

## Layout

```
app/            FastAPI service (config, logging, middleware, API)
core/           pure-Python logic (ingestion, retrieval, generation, evaluation)
services/       LangChain 1.x orchestration wiring
frontend/       Next.js dashboard (Phase 8)
scripts/        seed + evaluation entrypoints
docs/phases/    per-phase engineering documentation
tests/          unit + integration tests
```

## Reference

- `GroundedDocs_PRD_v2.1.docx` — authoritative product specification (Sections 1–11)
- `docs/README.md` — phase-by-phase build narrative

## License

MIT — see `LICENSE`.
