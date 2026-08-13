# Phase 1 — Ingestion & Chunking Pipeline

## 1. Phase Intro

Phase 1 turns raw documents into clean, deduplicated, metadata-rich chunks that
Phase 2 retrieves against. It is the read-path upstream of everything else:
loaders normalize input, three strategy-tagged chunkers produce retrievable
units, and a nearest-neighbor deduplicator keeps the index free of copies. Scope
for this pass is English-only by explicit decision; Arabic normalization and
Arabic edge-case testing are deferred to the v1.1 pass, but every interface is
language-agnostic (`language` field already present and set to `"en"`).

## 2. Goal

- Multi-format loading (PDF, MD, TXT, HTML) via LangChain 1.x document loaders.
- Three chunking strategies (fixed-size, structure-aware, semantic), each
  tagged per chunk, with metadata preservation (source, title, section, page).
- Deduplication via the vector index itself — top-k nearest-neighbor per new
  chunk, not an O(n^2) pairwise pass.
- Definition of Done: chunkers unit-tested; integration flow ingests sample
  docs into real Qdrant with dedup applied; measured numbers reported.

## 3. Description

### Architecture

```
services/loaders.py   LangChain loaders -> LoadedSegment (normalized text + meta)
core/ingestion/       pure chunkers + dedup + normalizer (framework-free, testable)
services/embeddings.py e5 embedding service (query:/passage: prefixes)
store/qdrant.py       VectorStore protocol impl (Qdrant, cosine, dim=1024)
services/ingestion.py orchestration: load -> normalize -> chunk -> embed -> dedup -> upsert
```

The `core/ingestion` modules are pure Python + numpy with injected callables
(an embedding function for semantic chunking, a store for dedup), so they are
unit-testable offline. LangChain is confined to the loaders (PyPDFLoader,
BSHTMLLoader) and the overall chain wiring — honoring "use LangChain 1.3.x but
keep the architecture clean and modular."

### Design decisions

- **Dedup is index-assisted, not all-pairs** (gap-closure #3). For each new
  chunk: embed once → `store.search(top_k=5)` → any neighbor at cosine ≥ 0.95
  marks a duplicate. Cost is one index query per chunk, not O(n²). Three knobs:
  `threshold` (default 0.95), `mode` (skip | flag), `scope` (all |
  same_document). Exact re-ingest measured at score ≈ 1.0 → reliably skipped.
- **Strategy selection is format-aware.** `structure` acts as *auto*: Markdown
  → structure-aware; TXT/HTML/PDF → fixed-size (PDF per page for page
  metadata). Explicit `fixed` or `semantic` strategies override all formats,
  so the CLI `--strategy` flag behaves predictably.
- **Fixed-size chunks are token-window based** (whitespace token approximation),
  so sizes are uniform in tokens, not characters, and overlap is exact.
- **Structure-aware chunker keeps the heading path** (`"Handbook / Employment /
  Probation Period"`) as `section` metadata and includes the heading in the
  chunk text so chunks are self-contained. Long sections are split into
  `section_part`s while keeping the structure tag. Documents without headings
  fall back to fixed-size and are tagged `fixed` (honest tagging).
- **Semantic chunker breaks at similarity valleys** (adjacent-sentence cosine
  below mean − k·std), merging small groups into a minimum sentence count.
  Embedding failures or too-few sentences fall back to fixed-size.
- **e5 prefixes.** Documents are embedded with `passage:`, queries with
  `query:` — the documented protocol for intfloat/e5 models.
- **Normalizer is English-scope but language-agnostic by construction**: NFKC,
  CRLF→LF, whitespace collapsing, line-leading/trailing space removal. Arabic
  steps (diacritics, tatweel, alef variants, RTL) land in v1.1.

### Alternatives considered

- LangChain's `RecursiveCharacterTextSplitter` / `MarkdownHeaderTextSplitter`
  as the chunkers — rejected: three bespoke strategies with exact tagging and
  injection points were cleaner to test and explain, and keep `core/` free of
  framework coupling.
- Embedding each candidate against a sample batch for threshold calibration —
  deferred; the corpus is small and exact duplicates dominate, so 0.95 holds
  (see Results). Real near-duplicate tuning happens alongside Phase 4 eval.

## 4. Work Done, Step by Step

1. Added deps `pypdf`, `beautifulsoup4`, `langchain-community`; added ingestion
   settings (chunk size, overlap, default strategy, dedup threshold/mode/scope/top_k)
   to `app/config.py` + `.env.example`.
2. `app/core/ingestion/models.py` — `SourceDocument`, `Chunk` (strategy-tagged,
   UUID-form id from sha1 of `document_id:index:strategy`), `DedupInfo`.
3. `app/core/ingestion/normalizer.py` — `normalize_text`, `collapse_whitespace`.
4. `app/core/ingestion/chunking.py` — `BaseChunker` + `FixedSizeChunker`,
   `StructureAwareChunker`, `SemanticChunker` (injected `EmbedFn`).
5. `app/core/ingestion/dedup.py` — `Deduplicator` (top-k nearest-neighbor,
   threshold/mode/scope, validation).
6. `app/store/base.py` — `VectorStore` protocol + `VectorPoint`/`SearchHit`.
   `app/store/qdrant.py` — Qdrant adapter (ensure_collection, upsert, search
   with payload filters, count, delete_by_document). `app/store/inmemory.py` —
   numpy-backed store for tests.
7. `app/services/embeddings.py` — lazy `SentenceTransformer` load, device probe,
   `embed_documents`/`embed_queries` with e5 prefixes.
8. `app/services/loaders.py` — LangChain loaders → `LoadedSegment` with page
   metadata for PDF; `SUPPORTED_EXTENSIONS` + `detect_format`.
9. `app/services/ingestion.py` — `IngestionPipeline` + `IngestReport`
   (segments, chunks_total, inserted/skipped/flagged, strategy_counts, duration).
10. `scripts/ingest.py` — CLI: `uv run python scripts/ingest.py <paths...>`.
11. `data/samples/` — three enterprise Markdown docs (handbook, incident
    playbook, security policy) + corpus README.
12. `docker-compose.yml` — added Qdrant service (healthcheck, volume); aligned
    server to v1.19.0 to match the 1.19.0 client.
13. Tests: normalizer, chunkers, dedup, pipeline (with `FakeEmbedder` +
    `InMemoryVectorStore` in `tests/conftest.py`).
14. Smoke run against real Qdrant + real `multilingual-e5-large`: ingest → 33
    chunks inserted; re-ingest → 33 skipped (dedup); retrieval sanity queries
    verified. Qdrant upgraded in place to v1.19.0, data preserved.

## 5. Files to Review

| File | Purpose |
|------|---------|
| `app/core/ingestion/models.py` | Chunk/SourceDocument/DedupInfo models |
| `app/core/ingestion/normalizer.py` | English-scope text normalization |
| `app/core/ingestion/chunking.py` | Three strategy-tagged chunkers |
| `app/core/ingestion/dedup.py` | Index-assisted nearest-neighbor dedup |
| `app/store/base.py` | `VectorStore` protocol |
| `app/store/qdrant.py` | Qdrant adapter (write + search + filters) |
| `app/store/inmemory.py` | Test/diagnostic in-memory store |
| `app/services/embeddings.py` | e5 embedding service with prefixes |
| `app/services/loaders.py` | LangChain loaders (PDF/MD/TXT/HTML) |
| `app/services/ingestion.py` | Ingestion orchestration + report |
| `scripts/ingest.py` | Ingest CLI |
| `data/samples/` | Seed corpus (3 enterprise Markdown docs) |
| `tests/test_normalizer.py` | Normalizer unit tests |
| `tests/test_chunking.py` | Chunker unit tests (incl. edge cases) |
| `tests/test_dedup.py` | Dedup behavior tests |
| `tests/test_ingestion.py` | Pipeline integration tests (fakes) |
| `tests/conftest.py` | `FakeEmbedder` + in-memory store fixtures |

## 6. Testing

- **Unit (pytest):** 39 tests pass (Phase 0's 6 + 33 new). Covers normalizer
  (CRLF, NFKC ligatures/fullwidth, whitespace), fixed-size (window/overlap/
  bounds/validation), structure-aware (section paths, nesting, fallback to
  fixed, long-section split), semantic (similar-sentence grouping, small-group
  merge, fallback, mismatched-vector error), dedup (skip/flag/insert, threshold
  edges, scope filtering, top-k, validation), pipeline (markdown→structure,
  txt→fixed fallback, re-ingest full skip, flag mode, directory skip of
  unsupported files, semantic default strategy).
- **Lint / type / security:** `ruff check` clean, `ruff format --check` clean,
  `mypy app` strict clean (19 files), `pip-audit` clean. Full suite mirrors the
  CI jobs.
- **Real integration smoke** (not in CI — requires Docker + model download):
  - Qdrant `v1.19.0` healthy; collection `groundeddocs_chunks` (cosine, 1024d).
  - `scripts/ingest.py data/samples` → 33 structure chunks inserted.
  - Re-run same command → 33 skipped, 0 inserted; index count stayed 33
    (dedup proven end-to-end against real embeddings).
  - Retrieval sanity: "How many days per week can an employee work remotely?"
    → top hit `Remote Work Policy` at cosine 0.8901; probation query → top hit
    `Probation Period` at 0.8916.

## 7. Results

- **Chunk counts (real model, real store):** handbook 14, incident playbook 9,
  security policy 10 → **33 chunks**, all `structure`, all inserted.
- **Dedup:** re-ingest produced 0 inserted / 33 skipped; index held at 33.
- **Latency:** after model warm-up, per-file ingest (9–14 chunks, structure) was
  ≈1.4–1.6 s each. The first file took 167 s because it includes the one-time
  `multilingual-e5-large` model download; steady-state embedding is the
  dominant cost, not chunking (<10 ms/chunk).
- **Retrieval sanity (Phase 2 preview, dense-only):** top-1 relevant hits at
  cosine ≥ 0.83–0.89 on three probes. This is the baseline that Phase 2's
  hybrid + reranking must beat — evidence to come from the Phase 4 harness, not
  asserted here.

## 8. Deliverables

Matched against the Phase 1 Definition of Done:

- [x] Multi-format loaders (PDF/MD/TXT/HTML) — LangChain 1.x
- [x] Three chunking strategies, strategy-tagged per chunk, metadata-rich
- [x] Dedup via top-k vector-index lookup (skip/flag, scope, threshold)
- [x] Unit tests per strategy + dedup + pipeline (39 passing)
- [x] Integration: sample corpus ingested into real Qdrant with dedup applied
- [x] Measured numbers: chunk counts, dedup behavior, latency
- [x] English-first scope honored; language-agnostic interfaces
- [x] `docs/phases/phase-1-ingestion.md`

## 9. Known Limitations / Follow-ups

- **HTML/PDF loaders not smoke-tested on real files.** Unit tests exercise MD
  and TXT; LangChain's HTML/PDF loaders are wired but unverified against a real
  sample. Add a sample `.pdf` + `.html` to the corpus and verify when the
  `/ingest` endpoint lands in Phase 5.
- **Dedup threshold (0.95) is untuned for near-duplicates.** Only exact
  duplicates (~1.0) were measured. Real near-duplicate distributions and
  threshold sensitivity are measured in Phase 4, where the evaluation harness
  compares chunking strategies anyway.
- **Retrieval quality is dense-only here** by design; hybrid + reranking
  (Phase 2) and the eval harness (Phase 4) will quantify the improvement.
- **Embeddings ran on CPU** in this phase (project venv resolved the CPU torch
  wheel). CUDA torch install for the project venv is a tracked follow-up; not
  blocking at corpus scale.
- **Normalizer strips line-leading whitespace**, flattening indented code
  blocks in documents. Acceptable for retrieval-focused ingestion; revisit if
  source code is indexed.
- **Arabic fully deferred** to the v1.1 pass per the explicit scope decision.
