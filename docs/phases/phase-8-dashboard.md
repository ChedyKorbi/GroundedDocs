# Phase 8 — Dashboard (Next.js)

## 1. Phase Intro

Phase 8 is the product's face: a Next.js dashboard that makes the system's
behavior and health visible to a non-engineer reviewer. It implements the three
PRD views — Chat/Ask with citations + confidence + method toggle, Documents
management, and a Performance/Info page — as a single, premium, editorial
interface ("the Instrument Panel") consuming the frozen v1 API contract so the
frontend can never force API rework.

## 2. Goal

- Chat/Ask view: grounded answers, inline citations with source snippets,
  confidence meter, claim verification, hybrid/dense/sparse toggle, diagnostics.
- Documents view: ingest (drop/browse), list with chunk counts, delete.
- Performance view: latency chart (p50/p95), stage-latency bars, KPIs
  (requests, success, cost, tokens, citations), health + model versions,
  evaluation summary, recent queries with expandable breakdown.
- Premium, professional, elegant — explicitly not a "test frontend": warm
  neutrals, one verdant accent, editorial serif + grotesque + mono type system,
  light + dark, real live data everywhere.

## 3. Description

### Design direction — "The Instrument Panel"

GroundedDocs is a *document-intelligence instrument*, not a chat toy. The UI
reads like a precision tool: quiet, data-dense, confident. **Hierarchy:** one
primary action per view (Ask). **Color:** 80% neutrals (warm paper in light,
near-black green-tint in dark) + one accent (deep verdant — "grounded",
provenance). **Type:** Instrument Serif (display) × Inter (UI) × JetBrains Mono
(every number — tabular figures). **Layout:** left rail + asymmetric grid,
generous spacing. **Motion:** 150–250 ms ease-out, only where it clarifies.
**Refused:** purple gradients, glassmorphism, emoji icons, drop-shadow piles,
centered-hero-with-cards, fake metrics. Icons are Lucide (consistent stroke).

### Architecture

```
frontend/
  app/globals.css             design tokens (CSS variables → Tailwind @theme)
  app/layout.tsx              fonts, Providers, rail + mobile nav shell
  app/page.tsx                Ask view (hero)
  app/documents/page.tsx      Documents view
  app/performance/page.tsx    Performance view
  components/Sidebar.tsx, MobileNav.tsx, ThemeToggle.tsx, Providers.tsx
  components/ask/AskClient.tsx          question → answer + sources + diagnostics
  components/documents/DocumentsClient.tsx  upload/list/delete
  components/performance/PerformanceClient.tsx  telemetry + eval + recent queries
  lib/api.ts                 typed client for the frozen v1 contract
  .env.example               NEXT_PUBLIC_GROUNDEDDOCS_API / API_KEY
```

### Contract-driven (frozen v1)

`lib/api.ts` mirrors `docs/API_CONTRACT.md` exactly. Two small contract revisions
were made for the dashboard and documented as revs 3–4:
- **rev 3**: `/ask` citations + sentence checks carry `text` (the source chunk
  snippet) so the UI can render provenance inline.
- **rev 4**: new `GET /eval` endpoint serving the latest published evaluation
  summary (faithfulness, relevance, citation accuracy, recall, calibration).

### Design decisions

- **Citations are first-class.** The answer renders `[n]` as superscript links
  to numbered source cards showing the actual passage, a verified/unverified
  dot, and the verifier's reason. Every claim sentence is listed with its
  verification status. This is the anti-hallucination story made visible.
- **The method toggle is a real product control** (hybrid / dense / sparse)
  wired to the API, not a demo gimmick — reviewers can feel hybrid vs dense.
- **Diagnostics on every answer**: confidence bar, per-stage latency, tokens,
  cost, model versions, request id — observability the PRD demands, surfaced
  where the reviewer looks.
- **Performance page is live telemetry**, not mockups: KPIs + a real latency
  chart (recharts, p50/p95 reference lines) over the actual query log, stage
  latency bars, health strip (Qdrant/model/index), the evaluation summary, and
  a recent-queries table with an expandable per-query breakdown.
- **Dark mode is designed, not inverted**: surfaces get lighter as elevation
  rises (opposite of light), accent brightens on dark.
- **CORS** added to the backend for the dashboard origin; verified by unit
  tests (preflight + simple request) and live.
- **Accessibility**: 4.5:1 body contrast, visible focus rings, semantic
  structure, keyboard navigation (e.g. `/` focuses the prompt, Enter submits).

## 4. Work Done, Step by Step

1. Backend: CORS middleware (`cors_origins` setting) + `tests/test_cors.py`.
2. Contract rev 3: `CitationSchema.text` (source snippet) populated in `/ask`;
   rev 4: `GET /eval` endpoint + `EvalSummaryResponse`.
3. Scaffolded Next.js 16 (App Router, TS, Tailwind v4) in `frontend/`; added
   `next-themes`, `recharts`, `lucide-react`.
4. Design system in `globals.css`: token ramp, semantic primitives
   (`.card`, `.btn`, `.input`, `.eyebrow`), light + dark via `@custom-variant`.
5. Typed API client (`lib/api.ts`) mirroring the contract.
6. Shell: `Sidebar` (rail), `MobileNav`, `ThemeToggle`, `Providers`.
7. Ask view: prompt hero, method toggle, AnswerBody (citation-aware renderer),
   SourcesRail, claim-verification list, Diagnostics, insufficient state.
8. Documents view: drag-drop ingest, table, delete, inline notices.
9. Performance view: KPI grid, health strip, recharts latency chart, stage
   bars, evaluation summary, expandable recent-queries table.
10. `frontend/.env.example`; root README quick-start updated.
11. Verified: `npm run lint` clean, `npm run build` clean (3 static routes),
    live stack (backend + frontend + CORS preflight) all green.

## 5. Files to Review

| File | Purpose |
|------|---------|
| `frontend/app/globals.css` | Design tokens + semantic primitives |
| `frontend/app/layout.tsx` | Fonts, providers, shell |
| `frontend/components/ask/AskClient.tsx` | Ask hero view |
| `frontend/components/documents/DocumentsClient.tsx` | Documents view |
| `frontend/components/performance/PerformanceClient.tsx` | Performance view |
| `frontend/lib/api.ts` | Typed client for the frozen contract |
| `frontend/.env.example` | Frontend env |
| `app/api/routes.py` | CORS + `/eval` endpoint + citation `text` |
| `app/api/schemas.py` | `EvalSummaryResponse`, `CitationSchema.text` |
| `app/config.py` | `cors_origins` |
| `docs/API_CONTRACT.md` | revs 3–4 |
| `tests/test_cors.py` | CORS regression tests |

## 6. Testing

- **Backend (pytest):** 107 passed, 9 integration-marked skipped by default —
  new CORS preflight/simple-request tests.
- **Frontend:** `npm run lint` clean; `npm run build` clean (TypeScript passes,
  3 routes prerendered: `/`, `/documents`, `/performance`).
- **Live smoke:** backend `/health` = `ok` (Qdrant + model + 33 chunks);
  frontend `http://localhost:3000` → 200; CORS preflight `OPTIONS /ask` → 200
  with `access-control-allow-origin: http://localhost:3000`.
- **CI:** the existing workflows cover the backend; the frontend build/lint can
  be added to a frontend job in Phase 9 (documented follow-up).

## 7. Results

- Full stack verified live: API (8000) + Next.js (3000), CORS green.
- Frontend production build: 3 routes, TypeScript + ESLint clean.
- Contract stays frozen and consumed verbatim by `lib/api.ts`; revs 3–4 are the
  only changes and are documented with dates.
- The dashboard surfaces real data end to end: citations with source snippets
  and verification, per-query stage latency, tokens/cost, model versions,
  health, and the published evaluation summary.

## 8. Deliverables

Matched against the Phase 8 Definition of Done:

- [x] Chat/Ask view with citations, confidence, hybrid-vs-dense toggle
- [x] Documents management view (upload/list/delete)
- [x] Performance/Info page: latency charts, token/cost, query volume, success
      rate, recent queries with breakdown, health, model versions, eval summary
- [x] Premium editorial design system (light + dark), no generic AI aesthetics
- [x] Consumes the frozen v1 contract; revs 3–4 documented
- [x] CORS wired + tested; live stack verified
- [x] `docs/phases/phase-8-dashboard.md`

## 9. Known Limitations / Follow-ups

- **Frontend CI job** (lint + build in GitHub Actions) not yet added — listed
  for Phase 7 extension; backend CI already green.
- **Charts are lightweight (recharts);** a time-series store for historical
  latency beyond the last 10 queries is a follow-up (query log already has the
  data).
- **Docker for the frontend** (multi-stage Node build in compose) deferred
  with the rest of the Docker workstream.
- **Arabic UI copy + RTL** deferred to the v1.1 Arabic pass.
- **Manual screenshot / visual review** — recommended before the demo; the
  design system is tokenized so refinements are quick.
