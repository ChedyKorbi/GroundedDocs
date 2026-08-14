# LinkedIn Carousel — Card Specification

Design spec for an 8-card LinkedIn carousel announcing **GroundedDocs**.
Every number below is taken from the repository's evaluation reports and phase
docs (`docs/phases/`, `data/eval/reports/`). Nothing is invented or rounded up.

---

## How to produce the actual images

Recommended (zero new dependencies, pixel control):

1. Open **`docs/marketing/cards.html`** in a browser (it renders all 8 cards at
   exactly 1080×1350 px, laid out vertically).
2. Zoom to 100%, open **DevTools → device toolbar** (Ctrl+Shift+M), set the
   viewport to **1080×1350**, screenshot each card block (or use a full-page
   screenshot and slice).
3. Export each card as PNG and upload to LinkedIn as a carousel (Portrait).

Alternatives:

- **Figma**: recreate the tokens below as styles; ~30 min for one card template
  + 7 duplicates.
- **Python/Pillow script**: `pillow` renders text + boxes programmatically;
  fine for text-heavy cards but slower to iterate than HTML/CSS.

---

## Design system (apply to every card)

| Token | Value |
|---|---|
| Canvas | 1080×1350 px (portrait) |
| Background | `#0A0A0A` (near-black) |
| Card surface | `#141414` with 1px border `#262626` |
| Primary text | `#FAFAFA` |
| Secondary text | `#A1A1AA` |
| Accent (headlines, ONE element per card) | `#6366F1` (indigo) |
| Success / metrics | `#10B981` (emerald) |
| Typography — headlines | Jost, semibold, tight tracking (−0.01em) |
| Typography — body | Inter, regular/medium |
| Typography — numbers | JetBrains Mono / Geist Mono |
| Margins | min 80 px all sides |
| Diagrams | line-art boxes + arrows only, no icons/illustration |
| Brand | small "GroundedDocs" wordmark in a corner of every card |

One idea per card. Max ~40 words of copy per card. Numbers are data, not
decoration: large, mono, emerald.

---

## Card 1 — Hook

**Headline (Jost, ~64px, left-aligned, top third):**
> RAG that has to prove every answer.

**Supporting (Inter, ~30px, `#A1A1AA`):**
> GroundedDocs — hybrid retrieval with verified citations, not vibes.

**Layout:** wordmark top-left; headline block upper-third; a single indigo
rule/underline under "prove." No other accent.

---

## Card 2 — Problem

**Headline:**
> Naive RAG breaks in four predictable ways.

**Body (4 short lines, `#FAFAFA` labels + `#A1A1AA` detail):**
- **Hallucination** — the model answers anyway
- **No citations** — you can't check the source
- **Single-language** — the docs aren't English-only
- **No evaluation** — quality is a feeling, not a number

**Layout:** four stacked rows with small emerald check-dashes on the right;
mono "01"–"04" labels.

---

## Card 3 — Architecture

**Headline:**
> One pipeline, end to end.

**Diagram (line-art boxes + arrows, left→right):**

`Ingest & chunk → Hybrid retrieval → Rerank → Grounded generation → Citation verification → Evaluation`
- "Hybrid retrieval" box labelled *dense + BM25 → RRF fusion*
- "Citation verification" box labelled *claim × passage, judge-checked*

**Layout:** boxes as 6 outlined `#262626` rectangles with `#FAFAFA` text and
thin arrows; sub-labels in mono `#A1A1AA`. Indigo only on the "Citation
verification" box border.

---

## Card 4 — Build phases

**Headline:**
> Built as 10 documented phases — each one tested before the next.

**Timeline (vertical or horizontal mono list):**
Foundations → Ingestion → Hybrid retrieval → Grounded generation → Evaluation →
Production API → Containerization → CI gates → Dashboard → Polish

**Supporting (`#A1A1AA`):**
> Every phase ships a markdown engineering doc. Nothing is asserted; it's measured.

**Layout:** timeline as mono chips connected by a thin line; 80px margins.

---

## Card 5 — Results (real numbers only)

**Headline:**
> Measured, not claimed.

**Metrics block (mono, large, emerald `#10B981`):**

| Metric | Value | Context |
|---|---|---|
| Faithfulness | **96.3%** | 48-question golden set |
| Citation accuracy | **88.2%** | verified supported citations |
| Recall@3 | **100%** vs 88.9% dense-only | 18-question retrieval set |
| Correct refusal | **100%** | unanswerable questions — 0% hallucinated |
| Judge↔human calibration | **100%** | both fabricated answers caught |
| Generation latency | **501 ms** p50 | per answer, live |

**Layout:** 2×3 grid of stat cells; each cell = mono value (emerald, ~64px) +
label + tiny context. One indigo accent: the "100%" under Correct refusal.

---

## Card 6 — Production engineering

**Headline:**
> "Production" means the boring things are done.

**Body (4 bullets):**
- **Docker + Compose** — API + Qdrant, sample corpus seeded on first boot, health
  checks for DB + model readiness (implemented, CI-built)
- **CI with an eval gate** — lint, strict typing, 107 unit tests, dependency
  audit; main fails if faithfulness < 0.85 or citation accuracy < 0.80
- **Observability** — stage-level latency, tokens + estimated cost per query,
  p50/p95/p99, request-id tracing
- **Zero-downtime reindex** — versioned Qdrant collections, atomic alias swap

**Layout:** 4 rows, mono index "01"–"04", body `#FAFAFA`, detail `#A1A1AA`.

---

## Card 7 — Gulf-market relevance

**Headline:**
> Built to the bar GCC enterprise-AI teams actually set.

**Body (3 lines):**
- Evaluation before claims — every capability has a number behind it
- Observability and reliability as first-class features, not polish
- Language-agnostic architecture with multilingual embeddings — ready for
  non-English documentation

**Supporting (`#A1A1AA`):**
> The signals SDAIA / NEOM / Aramco / STC hiring panels look for.

**Layout:** three rows with emerald dashes; indigo accent on the headline word
"bar". No Arabic claims — this card describes engineering rigor and
architecture readiness only.

---

## Card 8 — CTA

**Headline:**
> See the instrument.

**Body:**
> GitHub repo with architecture docs, evaluation reports, and a one-command
> stack · live dashboard with citations, confidence, and telemetry.

**CTA button (indigo fill, white text):**
> github.com/ChedyKorbi/GroundedDocs

**Layout:** centered CTA block lower-third; wordmark corner. Indigo is the one
accent on this card (the button).

---

## Wordmark

Every card carries a small "GroundedDocs" wordmark (Inter semibold, `#FAFAFA`
at ~22px, letter-spaced) with a tiny indigo dot after it, in the top-left
corner (top-right on card 8 for balance).
