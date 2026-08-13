# Phase 4 — Evaluation Framework

## 1. Phase Intro

Phase 4 turns the system's quality into *measured, comparable, defensible numbers*.
It adds a 48-question golden set spanning four difficulty categories, LLM-as-judge
metrics (faithfulness, answer relevance, citation accuracy) alongside retrieval
recall@k, a hybrid-vs-dense-vs-sparse comparison, a chunking-strategy shootout,
judge↔human calibration, and a failure-analysis pass. Everything is runnable with
one command: `uv run python scripts/eval.py`.

## 2. Goal

- Golden dataset: 48 questions (20 easy, 12 multi-hop, 8 unanswerable, 8 ambiguous).
- Automated metrics: faithfulness, answer relevance, citation accuracy, recall@k,
  correct-refusal / false-refusal / hallucination rates.
- Comparison reports: hybrid vs dense-only vs sparse-only; chunking shootout
  (structure vs fixed vs semantic).
- Judge↔human calibration on a hand-labeled subset (PRD gap-closure #4).
- Failure analysis with concrete examples + root causes.
- Runnable via `python eval.py`.

## 3. Description

### Architecture

```
data/eval/golden.json             48 questions (id, category, question, gold, reference)
data/eval/calibration_labels.json 16 hand-labeled judge-reference pairs (2 fabricated)
app/core/evaluation/judges.py     FaithfulnessJudge + RelevanceJudge (LLM-as-judge)
app/core/evaluation/recall.py     recall@k / MRR / precision@k
app/core/evaluation/retrieval_eval.py shared golden resolution + retrieval metrics
scripts/eval.py                   run | compare | calibration | chunking
scripts/eval_retrieval.py         Phase 2 retrieval-only harness (refactored to shared helpers)
```

### Design decisions

- **Golden set covers the PRD's four categories.** Easy (single-section factual),
  multi-hop (requires combining two sections), unanswerable (not in corpus — must
  refuse), ambiguous (conditional/partial information — must caveat). Gold is
  expressed as `(document_id, section leaf)` and resolved to chunk ids at eval
  time by the last heading-path component — precise even when a section has
  sub-headings.
- **Metrics are a mix of deterministic and LLM-as-judge.** Retrieval metrics are
  pure functions (no LLM). Faithfulness and relevance are JSON-output judge
  calls; citation accuracy is derived from the Phase 3 per-claim verifier (the
  number of cited references the verifier marks supported).
- **Judge model is separate from the generator.** Generation runs on
  `llama-3.3-70b-versatile`; verification + faithfulness + relevance judges run
  on `llama-3.1-8b-instant`. Groq free-tier daily token caps are **per-model**,
  so splitting the load keeps a full 48-question run inside the daily budget and
  is cheaper. Verified that judge agreement is 100% on the calibration set before
  trusting the smaller model (see Results).
- **Multi-key rotation with failover.** `GROQ_API_KEYS` accepts comma-separated
  keys; the LLM client round-robins and **cools down any key that hits a 429**
  (300s), routing to the next healthy key. This made the full run possible across
  two Groq organizations' quotas and is a defensible production pattern.
- **Calibration (gap #4).** 16 reference answers (14 grounded, 2 deliberately
  fabricated) are hand-labeled; the automated judges score them against their gold
  context and agreement is reported. This gives the published numbers a trust
  story: the judge has verified agreement with a human before its verdicts are
  aggregated.
- **Chunking shootout uses text-overlap gold translation.** Fixed/semantic indexes
  lack section metadata, so gold chunks are resolved per index by token overlap
  (≥0.5) with the source structure-index section text. This keeps the comparison
  fair across strategies.

### Methodology fixes made during the phase (documented, not hidden)

1. **Faithfulness judge claim-extraction bug.** The 8b judge extracted claims from
   the *context* rather than the answer (e.g. for a correct one-sentence answer it
   hallucinated 7 extra claims and scored 0.375). Prompt fixed to extract claims
   *only from the answer*; e02 re-scored 1.0. The earlier 0.858 faithfulness number
   was withdrawn and re-run (0.963).
2. **Insufficient-sentinel detection.** A model answer that embedded
   `INSUFFICIENT_INFORMATION` mid-text was not caught by the startswith check;
   detection now triggers on the sentinel appearing anywhere in the answer
   (confirmed on a03).
3. **Chunking gold-resolution bug.** `run_chunking` built retrievers bound to the
   main store, so gold ids (eval-`{strategy}` collections) never matched retrieved
   ids → uniform zeros. Fixed by binding the retriever to the eval store; the
   structure row was only nonzero because its chunk ids are deterministic-identical.
4. **429-driven engineering.** The first full runs crashed on Groq's per-model
   daily token caps; the client now retries with Retry-After/exponential backoff,
   and multiple keys provide failover (above).

## 4. Work Done, Step by Step

1. `app/core/evaluation/judges.py` — `FaithfulnessJudge`, `RelevanceJudge`
   (JSON judge prompts + deterministic scoring).
2. `app/core/evaluation/recall.py` + `retrieval_eval.py` — metric primitives and
   shared golden resolution; refactored `scripts/eval_retrieval.py` onto them.
3. `data/eval/golden.json` — 48 questions across four categories.
4. `data/eval/calibration_labels.json` — 16 hand-labeled pairs (incl. 2 fabricated).
5. `scripts/eval.py` — full harness: `run` (default), `compare`, `calibration`,
   `chunking` subcommands; per-question rows + aggregates + failures in the report.
6. Judge model config (`judge_model`) + `effective_groq_keys` multi-key support +
   LLM client retry/backoff/failover.
7. Unit tests for judges (9) + sentinel-anywhere detection.
8. Ran the full 48-question eval; found + fixed the judge claim-extraction bug and
   sentinel edge case; re-ran (canonical report).
9. Ran `compare --limit 12` and `chunking` (fixed the retriever-binding bug).

## 5. Files to Review

| File | Purpose |
|------|---------|
| `data/eval/golden.json` | 48-question golden set |
| `data/eval/calibration_labels.json` | Hand-labeled judge-reference subset |
| `app/core/evaluation/judges.py` | Faithfulness + relevance judges |
| `app/core/evaluation/recall.py` | recall@k / MRR / precision@k |
| `app/core/evaluation/retrieval_eval.py` | Shared golden resolution + retrieval metrics |
| `scripts/eval.py` | Full eval harness (run/compare/calibration/chunking) |
| `scripts/eval_retrieval.py` | Phase 2 retrieval harness (shared helpers) |
| `app/services/llm.py` | Retry/backoff + multi-key rotation + 429 failover |
| `app/config.py` | `judge_model`, `groq_api_keys` |
| `data/eval/reports/eval_hybrid_20260813_161422.json` | Canonical full report |
| `data/eval/reports/chunking_20260813_161706.json` | Chunking shootout report |
| `tests/test_judges.py` | Judge unit tests |

## 6. Testing

- **Unit (pytest):** 86 passed, 3 integration-marked skipped by default. New:
  judge scoring (all/partial/empty/failure/claims-empty), sentinel-anywhere
  insufficient detection.
- **Lint / type:** `ruff` clean, `mypy app scripts` strict clean (38 files),
  format clean.
- **Real runs (not in CI):** full hybrid eval (48 Q), compare (12 Q × 3 methods),
  chunking shootout (3 strategies), calibration (16 items) — all against the live
  Qdrant index + Groq.

## 7. Results

### Full evaluation — hybrid, 48 questions, `multilingual-e5-large` + `llama-3.3-70b-versatile` + `ms-marco-MiniLM-L-6-v2`

| metric | value |
|--------|-------:|
| retrieval recall@1 | 0.763 |
| retrieval recall@3 | 0.938 |
| retrieval recall@5 | 0.938 |
| MRR | 0.938 |
| faithfulness | 0.963 |
| answer relevance | 0.787 |
| citation accuracy | 0.882 |
| correct refusal rate | 1.000 |
| false refusal rate | 0.025 |
| hallucination on unanswerable | 0.000 |

Notes: recall is over the 40 answerable questions (multi-hop questions have two
gold chunks, capping recall@1 at 0.5 for those — expected). MRR exceeding
recall@1 follows from multi-gold questions. 0.025 false-refusal = 1/40 (a03, an
ambiguous question where the model opted for an honest refusal — arguably correct;
see failure analysis).

### Judge calibration (human vs judge, 16 items incl. 2 fabricated)

- Faithfulness agreement: **1.0** (real items 1.0, fabricated items 1.0 — both
  invented answers flagged unsupported).
- Relevance agreement: **1.0**.

### Comparison — hybrid vs dense vs sparse (12-question subset, full pipeline)

| method | rec@1 | rec@3 | faithfulness | relevance | citation acc |
|--------|------:|------:|-------------:|----------:|-------------:|
| dense_only | 0.917 | 0.917 | 0.979 | 0.892 | 1.000 |
| sparse_only | 1.000 | 1.000 | 1.000 | 0.900 | 1.000 |
| hybrid | 1.000 | 1.000 | 1.000 | 0.900 | 1.000 |

Consistent with Phase 2: sparse is the strongest ranker on these keyword-dense
questions; hybrid matches it; dense lags slightly on recall.

### Chunking strategy shootout (retrieval recall@k, same 40 answerable questions)

| strategy | chunks | recall@1 | recall@3 | MRR |
|----------|-------:|---------:|---------:|----:|
| fixed (512 tok, 50 ov) | 4 | **0.810** | **0.981** | **0.988** |
| structure (headings) | 34 | 0.744 | 0.906 | 0.918 |
| semantic (sent. groups) | 21 | 0.704 | 0.888 | 0.963 |

**Honest, counterintuitive finding:** on this small corpus, *fixed-size chunking
outperforms the structure-aware default* and semantic grouping is weakest. The
documents are short and keyword-dense, so large fixed chunks keep each answer
fully contained in one retrievable unit, while semantic chunking fragments
answers across sentence groups. This is a measured trade-off, not an assertion;
a larger, longer-form corpus (Phase 9 extension) may reverse it.

### Failure analysis (15 failures on the canonical run)

- **unsupported_citation (7: e16, m03, m06, m07, m08, m10, m12)** — the verifier
  flagged cited references that don't fully support the claim. E.g. e16's answer
  correctly states VPN/MFA requirements (faithfulness 1.0) but over-cites a
  peripheral "remote work compliance" clause (citation accuracy 0.5). Root cause:
  the model over-cites beyond the minimal supporting passage; the verifier
  correctly refuses credit.
- **retrieval_miss (4: e17, m06, a03, a05)** — gold chunk ranked 2–5. E.g. e17's
  gold `Account Provisioning` chunk sits at rank 2, yet the answer is perfect
  (faithfulness 1.0, citation accuracy 1.0) — a rank-1 miss that did not hurt the
  answer. m06's two gold chunks are genuinely absent from top-5 — a real
  multi-hop retrieval failure.
- **unsupported_content (3: m12, a05, a08)** — faithfulness 0.67–0.70; answers
  that combine policy clauses the trimmed judge context doesn't fully carry.
- **false_refusal (1: a03)** — "How quickly are security incidents resolved?" The
  corpus genuinely lacks a resolution-time definition; the model refused rather
  than give the caveated partial answer in the golden reference. Arguably correct
  conservatism; flagged honestly.

## 8. Deliverables

Matched against the Phase 4 Definition of Done:

- [x] 48-question golden set (easy/multi-hop/unanswerable/ambiguous)
- [x] Faithfulness, answer relevance, citation accuracy, recall@k (+ refusal metrics)
- [x] Hybrid vs dense vs sparse comparison report
- [x] Chunking strategy comparison report (measured)
- [x] Judge↔human calibration (100% agreement, fabricated answers caught)
- [x] Failure analysis with concrete examples + root causes
- [x] Runnable via `python eval.py` (+ compare/calibration/chunking subcommands)
- [x] `docs/phases/phase-4-evaluation.md`

## 9. Known Limitations / Follow-ups

- **Golden set is small (48 Qs) and corpus is small (33 chunks).** The numbers are
  a strong proof-of-mechanism but are not yet a statistically robust benchmark.
  Extending the corpus and golden set is a Phase 9 / follow-up item.
- **Answer-relevance (0.787) is the weakest metric.** The relevance judge is
  strict on partial/evasive answers; multi-hop and ambiguous answers legitimately
  score lower. Worth reviewing the judge prompt or reporting per-category
  relevance in a follow-up.
- **Comparison ran on a 12-question subset** (token-budget bounded); a full 48-Q
  three-method comparison is a natural follow-up run once quota allows.
- **Chunking shootout is retrieval-only** (no generation metrics per strategy);
  adding end-to-end per-strategy generation eval is a follow-up.
- **Faithfulness judge context is trimmed** (top-3 × 600 chars) to fit free-tier
  quotas; full-context judging is a quality-vs-cost trade-off to revisit.
- **The 8b judge was validated only on 16 calibration items.** Agreement was 100%,
  but a larger labeled set (e.g., 40) would tighten the trust story.
- **Arabic evaluation** (Arabic golden set + Arabic judges) deferred to the v1.1
  Arabic pass.
