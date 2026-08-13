# Phase 2 — Hybrid Retrieval & Ranking

## 1. Phase Intro

Phase 2 turns the Phase 1 chunk index into a ranked retrieval system: dense
embeddings and BM25 are each retrieved independently, fused by configurable
Reciprocal Rank Fusion, and re-ranked by a cross-encoder (LLM-as-judge
fallback). It also lays the zero-downtime re-indexing capability via versioned
collections + atomic alias swap. The phase's contract is evidence: hybrid
retrieval must be *measured* against either method alone, and the numbers —
including where hybrid does not win — are reported honestly.

## 2. Goal

- Dense retrieval (Qdrant, e5) + sparse retrieval (BM25) over the same chunks.
- RRF fusion with configurable weights and k.
- Rerank stage with a locked-in auto-probe (GPU → cross-encoder, else
  LLM-as-judge; PRD gap-closure #7).
- IndexManager: named-collection versions + atomic alias swap for
  zero-downtime re-indexing (PRD §11.5 / gap-closure #1).
- Retrieval-only evaluation: recall@k + MRR, hybrid vs dense-only vs
  sparse-only vs hybrid+rerank — numbers required, not assumed.

## 3. Description

### Architecture

```
core/retrieval/sparse.py   SparseIndex (Okapi BM25 over chunk payloads, EN tokenizer)
core/retrieval/fusion.py   rrf_fuse (weighted reciprocal rank fusion)
core/retrieval/rerank.py   CrossEncoderReranker | LlmJudgeReranker + build_reranker probe
services/retrieval.py      HybridRetriever (per-stage scores, dense/sparse/hybrid modes)
store/index.py             IndexManager (versions + alias swap)
core/evaluation/recall.py  recall@k, MRR, precision@k (pure functions)
scripts/eval_retrieval.py  retrieval eval harness + report
```

### Design decisions

- **BM25 is in-memory over chunk payloads.** `SparseIndex` is rebuilt from the
  vector store's `all_points()` payloads. This is O(corpus) memory and rebuild
  time — fine at demo scale, and refreshable after every ingest. The
  refresh-on-ingest hook is wired into the API in Phase 5.
- **Fusion is weighted RRF.** `score(d) = w_d/(k+rank_d) + w_s/(k+rank_s)`,
  ids absent from either list contribute zero (robust to asymmetric recall).
  k and both weights are settings; equal weights are the default after tuning
  experiments (see Results).
- **Reranker auto-probe (gap #7):** `RERANKER_MODE=auto` probes the GPU at
  startup; CUDA available → cross-encoder, else LLM-as-judge (Groq, requires
  `GROQ_API_KEY`). The decision is logged once per process and carried on every
  `RetrievalResult.reranker` field so answers are traceable. Explicit config
  overrides auto-detection; a CPU + no-key machine raises a clear error rather
  than silently degrading.
- **Zero-downtime re-indexing (gap #1):** `IndexManager` keeps the alias
  `groundeddocs_chunks` stable while writers build `<base>-v{n}` collections
  and atomically flip the alias via `update_collection_aliases`. Verified live
  against Qdrant (see Results). The full seed→swap→drop flow is exercised in
  Phase 6; `/reindex` endpoint lands in Phase 5.
- **Per-stage scores retained.** `RetrievedChunk` carries dense/sparse/fused/
  rerank scores independently, which Phase 5 turns into stage-level latency +
  score observability and the dashboard's hybrid-vs-dense toggle.
- **Evaluation methodology is precise.** Gold chunks are resolved by
  `document_id` + the *last component* of the stored heading path, so a parent
  section with sub-headings (e.g. `Roles` → `Roles / Incident Commander`) does
  not inflate the gold set. The first eval run exposed this bug (multi-chunk
  gold sets producing fractional averages); it was fixed and re-run rather than
  left in place.

### Alternatives considered

- LangChain's `BM25Retriever` / vectorstore-backed hybrid — rejected; the
  in-memory `SparseIndex` over our own payloads keeps the store interface as
  the single source of truth and is trivially testable.
- Reranking the full candidate pool vs the fused top-k — the fused top-k (10)
  is reranked; reranking all 40 would cost 4x cross-encoder calls for no
  measured gain here.
- Tuning RRF weights on the 18-question golden set — deliberately avoided
  beyond two sanity experiments; 18 questions is too small to learn weights
  from without overfitting (Phase 4 builds the larger set this needs).

## 4. Work Done, Step by Step

1. Added retrieval settings (dense/sparse/fused k, RRF k, weights) to
   `app/config.py` + `.env.example`.
2. `core/retrieval/sparse.py` — `SparseIndex` (Okapi BM25, EN tokenizer, hit
   search with payloads).
3. `core/retrieval/fusion.py` — `rrf_fuse` (weighted RRF, union of ids).
4. `core/retrieval/rerank.py` — `Reranker` protocol, `CrossEncoderReranker`
   (sentence-transformers), `LlmJudgeReranker` (Groq), `build_reranker()` with
   the auto probe + validation.
5. `store/index.py` — `IndexManager` (ensure_initial, begin_reindex, activate/
   atomic swap, versions, drop). Refactored `QdrantStore` to accept a shared
   client and added `all_points()` (scroll) to the store protocol + both
   implementations.
6. `services/retrieval.py` — `HybridRetriever` (dense/sparse/hybrid modes,
   per-stage scores, optional rerank) + `build_retriever()` production wiring.
7. `core/evaluation/recall.py` — `recall_at_k`, `mrr`, `precision_at_k`.
8. `data/eval/retrieval_golden.json` — 18 retrieval questions over the sample
   corpus with document + section-leaf gold.
9. `scripts/eval_retrieval.py` — eval harness (four methods, recall@1/3/5 +
   MRR, JSON report to `data/eval/reports/`).
10. Tests: sparse, fusion, rerank (mock + integration-marked cross-encoder),
    hybrid retriever (fakes), index manager (fake client + real smoke).
11. Ran the eval against the live index; fixed the gold-resolution bug found on
    the first run; re-ran. Ran two weight-tuning sanity experiments.
12. Ran the IndexManager zero-downtime swap smoke against real Qdrant.

## 5. Files to Review

| File | Purpose |
|------|---------|
| `app/core/retrieval/sparse.py` | In-memory Okapi BM25 index |
| `app/core/retrieval/fusion.py` | Weighted RRF fusion |
| `app/core/retrieval/rerank.py` | Cross-encoder / LLM-judge rerankers + auto probe |
| `app/services/retrieval.py` | HybridRetriever (per-stage scores, modes) |
| `app/store/index.py` | IndexManager: versions + atomic alias swap |
| `app/store/qdrant.py` | Client-shared store + `all_points()` |
| `app/core/evaluation/recall.py` | recall@k / MRR / precision@k |
| `data/eval/retrieval_golden.json` | 18-question retrieval golden set |
| `data/eval/reports/retrieval_20260813_141532.json` | Canonical eval report |
| `scripts/eval_retrieval.py` | Retrieval eval harness |
| `tests/test_retrieval.py` | Sparse/fusion/rerank tests |
| `tests/test_hybrid_retriever.py` | Hybrid pipeline tests (fakes) |
| `tests/test_index_manager.py` | Index version/alias lifecycle tests |

## 6. Testing

- **Unit (pytest):** 62 passed, 1 skipped by default (cross-encoder smoke is
  `integration`-marked: `RUN_INTEGRATION=1` runs it — verified passing in
  8.7s locally). Covers sparse (tokenize, ranking, empty/unmatched, limit),
  fusion (union, weights, empty), rerank (LLM-judge key validation, mode
  selection), hybrid retriever (dense/sparse-only, stub-rerank ordering,
  sparse-miss graceful path, result shape), index manager (init idempotency,
  reindex+swap, versions, drop protection).
- **Lint / type:** `ruff` clean, `mypy app` strict clean (27 files), format
  clean.
- **Real integration smoke (not in CI):**
  - Eval over the live 33-chunk index with real e5 embeddings + real
    cross-encoder (see Results).
  - `IndexManager` zero-downtime swap against real Qdrant: v1 created + aliased,
    v2 built while alias untouched, atomic swap, old version dropped — SMOKE OK,
    temp collections cleaned up; the main index (33 chunks) untouched.

## 7. Results

Retrieval-only evaluation, 18 questions over the 33-chunk sample index,
`multilingual-e5-large` + `ms-marco-MiniLM-L-6-v2`:

| method | recall@1 | recall@3 | recall@5 | MRR |
|--------|---------:|---------:|---------:|----:|
| dense_only | 0.889 | 0.889 | 0.889 | 0.889 |
| sparse_only | 0.944 | 1.000 | 1.000 | 0.972 |
| hybrid | 0.889 | 1.000 | 1.000 | 0.944 |
| hybrid_rerank | 0.889 | 1.000 | 1.000 | 0.944 |

**Measured, honest conclusions (not marketing):**

1. **Sparse (BM25) is the strongest single ranker on this corpus** (recall@1
   0.944 vs dense 0.889). Expected: the sample questions are keyword-exact and
   factual ("how many days…", "which severity…") against synthetic docs, where
   lexical matching is near-perfect.
2. **Hybrid beats dense everywhere and matches sparse's coverage** (recall@3
   1.000) — dense + sparse fail on *disjoint* questions (dense misses r10/r18,
   sparse misses r06), proving genuine complementarity.
3. **Equal-weight RRF dilutes rank-1 on the two complementary cases** (r06, r18):
   hybrid's fused rank-1 lands on a high-scoring chunk from the *other* ranker,
   so hybrid recall@1 (0.889) sits at dense's level, not sparse's. Sparse-heavy
   weights (2.0) changed nothing; dense-heavy (2.0) *dropped* recall@3 to 0.944.
   Conclusion: on 18 questions there is no weight that wins everywhere — a
   larger golden set (Phase 4) is required to learn weights or justify trusting
   the reranker more.
4. **Cross-encoder rerank is net-neutral on recall@1 here** (fixes r06, breaks
   r04; MRR unchanged). The generic MS MARCO cross-encoder adds no signal on
   this tiny, already-well-ranked corpus; it should help most when the fused
   pool is noisier and larger.

**Zero-downtime re-indexing (IndexManager, live):** initial `v1` aliased →
`v2` built with readers still on `v1` → atomic alias swap → old version
dropped. Verified end-to-end against Qdrant v1.19.

## 8. Deliverables

Matched against the Phase 2 Definition of Done:

- [x] Dense + sparse retrieval over the same chunk index
- [x] RRF fusion, configurable weights/k
- [x] Reranker with locked-in auto-probe rule (cross-encoder / LLM-as-judge)
- [x] IndexManager: versioned collections + atomic alias swap (zero-downtime
      re-indexing groundwork)
- [x] Retrieval-only eval with recall@k + MRR for all four methods — measured
- [x] Honest failure analysis (r06/r10/r18 + rerank regressions) documented
- [x] Unit tests (62) + integration smoke (eval + alias swap)
- [x] `docs/phases/phase-2-retrieval.md`

## 9. Known Limitations / Follow-ups

- **BM25 is in-memory and must be refreshed after ingest** — wired as an
  explicit refresh call in the Phase 5 API (post-ingest) and a startup build in
  `build_retriever()`. Not yet automatic per-ingest.
- **Reranker adds no measured value on this corpus** (net-neutral recall@1).
  Re-examined in Phase 4 with a larger, noisier golden set; if it still does
  not help, the model card will say so rather than claim a lift.
- **RRF weights are untuned** (18 questions is too small to learn from).
  Phase 4's golden set enables proper weight selection or a learned fusion.
- **LLM-as-judge reranker is implemented but not exercised** — it requires
  `GROQ_API_KEY`, and the eval used the cross-encoder. Exercised in Phase 3/5
  integration once the key is set.
- **Embeddings + cross-encoder ran on CPU** (project venv resolved CPU torch);
  GPU CUDA install remains a tracked follow-up for latency at scale.
- **Retrieval quality metrics are retrieval-only**; faithfulness/citation
  metrics arrive in Phases 3–4.
- **Arabic retrieval** (Arabic tokenizer for BM25, Arabic eval set) deferred to
  the v1.1 pass.
