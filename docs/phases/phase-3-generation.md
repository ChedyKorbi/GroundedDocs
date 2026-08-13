# Phase 3 — Grounded Generation & Citation Verification

## 1. Phase Intro

Phase 3 closes the loop the previous phases built toward: it turns ranked chunks
into *trustworthy* answers. A strict grounded prompt forces the LLM to answer
only from numbered context passages with bracketed citations; a second
LLM-as-judge stage verifies every claim↔citation pair; a composite confidence
score summarizes groundedness; and a structured insufficient-information path
guarantees the system says "I don't know" instead of inventing a fact. Every
result is stamped with the exact model versions that produced it.

## 2. Goal

- Strict grounded system prompt with numbered context blocks + bracketed
  citations.
- Post-hoc citation verification: per claim↔citation LLM-as-judge checks.
- Composite confidence scorer (retrieval confidence, verification rate,
  citation coverage, completeness).
- Structured insufficient-information path — no hallucinated guesses.
- Model/version registry stamping per result (PRD gap-closure #2).
- Unit tests for parsing/scoring; real-Groq integration verified.

## 3. Description

### Architecture

```
core/generation/citations.py   extract_citations, split_sentences, strip markers (pure)
core/generation/prompts.py     grounded + verification judge prompts
core/generation/confidence.py  composite confidence scorer (pure)
services/llm.py                Groq client: tokens, JSON mode, retry
services/generation.py         GenerationService orchestration
```

### Pipeline

1. `retrieve` (Phase 2) → top-k chunks become numbered context blocks
   `[1]..[k]` in the grounded user prompt.
2. Groq generates the answer under the strict system prompt; if it emits the
   sentinel `INSUFFICIENT_INFORMATION`, the pipeline returns a structured
   `insufficient=True` result (empty answer, no citations, composite confidence
   0.0) — skipping verification entirely.
3. Otherwise the answer is split into sentences; each sentence's `[n]` markers
   are parsed and its claim (markers stripped) is sent to a strict judge with
   the cited passages; the judge returns per-index `{supported, reason}` JSON.
4. Checks are aggregated per citation index (an index is supported only if all
   its checks are), the composite confidence is computed, and the full
   `GenerationResult` (answer, sentence-level checks, citations, confidence,
   tokens, latency, model versions) is returned for logging and display.

### Design decisions

- **Verification is per claim↔citation pair, batched per sentence.** One judge
  call per *sentence* verifies all of that sentence's citations at once (the
  judge sees the claim plus each cited passage). This gives true per-pair
  granularity (each passage is judged independently in the JSON response) while
  keeping call volume ≈ sentence count rather than citation count.
- **Strict judge prompt.** The judge is told a passage supports a claim only if
  the facts appear in it or follow directly; silence or contradiction ⇒ not
  supported. This is deliberately hallucination-averse (false "supported" is the
  dangerous failure; a verified false-positive would poison the whole point).
- **Unverifiable = unsupported.** If the judge call fails or returns malformed
  JSON, the citation is marked `supported=False` with an explicit reason — never
  silently credited. The system degrades toward lower confidence, not toward
  false grounding.
- **Composite confidence is a documented formula**, not a vibe:
  `0.25·retrieval + 0.35·verification_rate + 0.30·citation_coverage + 0.10·completeness`,
  clamped to [0,1]. Verification — the ground-truth groundedness signal — carries
  the most weight.
- **Model registry stamping (gap #2).** Every result carries
  `model_versions` (llm provider/model, embedding model, reranker) and the LLM
  model id, satisfying PRD §11.5's "log which model + version produced this"
  requirement at the point answers are created. Phase 5 persists these into the
  query log.
- **LLMClient is the single LLM seam.** Token usage is captured from Groq's
  usage object; JSON mode is a per-call flag; a bounded retry handles transient
  failures. Provider-agnostic so the model card can truthfully say "Groq
  (llama-3.3-70b) today, swappable by config".

### Alternatives considered

- Verifying the whole answer against all cited chunks in one call — rejected:
  loses per-pair granularity that the eval metric (citation accuracy) needs.
- Two-pass generation (draft + self-check) — rejected for now; the post-hoc
  judge is cheaper and its failures are exactly the signal confidence scoring
  needs. A second generation pass is a documented Phase 4 experiment if
  citation accuracy lags.
- Rule-based confidence (retrieval score only) — rejected: it cannot detect the
  exact failure mode (grounded-but-wrong retrieval) this phase is built to catch.

## 4. Work Done, Step by Step

1. Added generation settings (max tokens, temperature, context k, sentinel) to
   `app/config.py` + `.env.example`.
2. `core/generation/citations.py` — `extract_citations` (dedup, multi-format),
   `split_sentences`, `sentence_citations`, `strip_citation_markers`.
3. `core/generation/prompts.py` — `GROUNDED_SYSTEM_PROMPT`,
   `build_grounded_user_prompt`, `VERIFY_SYSTEM_PROMPT`, `build_verify_prompt`.
4. `core/generation/confidence.py` — `score_confidence` + `ConfidenceBreakdown`.
5. `services/llm.py` — `LLMClient` (Groq; token accounting; JSON mode;
   bounded retry) + `LLMResponse`.
6. `services/generation.py` — `GenerationService.generate` (grounded prompt →
   parse → verify → score → insufficient path), `CitationCheck`,
   `SentenceCheck`, `GenerationResult`, `build_generation_service()`.
7. Tests: citation parsing, confidence scenarios, generation with a fake LLM
   (grounded answer, insufficient path, unsupported citation, verification
   failure resilience, out-of-range citation, prompt shape).
8. Integration tests (real Groq + real Qdrant): grounded answer end-to-end and
   insufficient path on an out-of-domain question.
9. Verified live: two in-domain queries produced verified, high-confidence
   answers; an out-of-domain query produced `insufficient=True`.

## 5. Files to Review

| File | Purpose |
|------|---------|
| `app/core/generation/citations.py` | Citation/sentence parsing (pure) |
| `app/core/generation/prompts.py` | Grounded + judge prompts |
| `app/core/generation/confidence.py` | Composite confidence formula |
| `app/services/llm.py` | Groq client (tokens, JSON, retry) |
| `app/services/generation.py` | Generation orchestration + result models |
| `app/config.py` | Generation settings + sentinel |
| `tests/test_generation.py` | Parsing/confidence/generation unit tests |
| `tests/test_generation_integration.py` | Real-Groq end-to-end tests |
| `.env` (git-ignored) | `GROQ_API_KEY` |

## 6. Testing

- **Unit (pytest):** 76 passed, 3 integration-marked skipped by default. New
  coverage: multi/dedup citation extraction, sentence splitting + marker
  stripping, confidence (full/partial/insufficient), grounded generation with a
  fake LLM (citations resolved to chunk ids, supported flags, token accounting,
  model-versions stamping), insufficient path, unsupported-citation scoring,
  verification-failure resilience, out-of-range citation dropping, prompt
  shape assertions.
- **Lint / type:** `ruff` clean, `mypy app` strict clean (33 files), format
  clean.
- **Integration (real Groq + real Qdrant, `RUN_INTEGRATION=1`):** 2 passed in
  30.9s — grounded answer with real citations, and the insufficient path.

## 7. Results

Live end-to-end (real hybrid retrieval + `llama-3.3-70b-versatile` on Groq):

**Query 1:** "How many days of annual leave do employees accrue per year and
how many can carry over?"
> Employees accrue 25 working days of annual leave per year [1]. They can carry
> over up to a maximum of 10 days into the next calendar year [1].
> verified: both checks `supported=True` (judge reasons quote the source
> passages); confidence **0.974** (verification_rate 1.0, coverage 1.0,
> retrieval 0.898); tokens 514 in / 36 out; **380 ms** generation.

**Query 2:** "What must be preserved before any remediation action during an
incident?"
> Evidence must be preserved before any remediation action is taken [1].
> verified `supported=True`; confidence **0.943**; 283 ms.

**Query 3 (out of domain):** "What is the recommended tire pressure for a 2024
Toyota Corolla?" → **`insufficient=True`**, empty answer, composite confidence
0.0 — the system refused rather than hallucinated.

These demonstrate the full contract: grounded answers, per-claim verified
citations with machine-readable reasons, quantified confidence, and an honest
refusal path. The citation-accuracy *metric* (aggregated over a golden set) is
measured in Phase 4.

## 8. Deliverables

Matched against the Phase 3 Definition of Done:

- [x] Strict grounded system prompt + numbered contexts + bracketed citations
- [x] Post-hoc per claim↔citation verification (LLM-as-judge)
- [x] Composite confidence scorer with documented weights
- [x] Structured insufficient-information path (verified live)
- [x] Model/version registry stamping per result
- [x] Unit tests (parsing, scoring, generation, resilience)
- [x] Real-Groq integration tests passing
- [x] `docs/phases/phase-3-generation.md`

## 9. Known Limitations / Follow-ups

- **Judge is a second LLM call per sentence** — adds latency (~1–2 judge calls
  per answer ≈ +300–600 ms) and cost. Batching is already per-sentence; a
  single-call whole-answer judge is a possible Phase 4 latency optimization if
  citation accuracy holds.
- **Confidence weights are hand-set, not calibrated.** Phase 4 calibrates the
  composite against human-labeled groundedness if the golden set allows it.
- **Sentence splitter is English-focused** (`.!?` + uppercase). Arabic sentence
  segmentation is part of the v1.1 Arabic pass.
- **Insufficient detection relies on the sentinel.** If the model paraphrases
  the sentinel (e.g., "The context does not contain this information"), it is
  treated as a normal answer. A follow-up heuristics check on empty-citation
  answers is a cheap, tracked improvement.
- **GROQ_API_KEY is now required for generation**; the API layer (Phase 5) will
  surface a structured error if it is missing rather than a bare crash.
