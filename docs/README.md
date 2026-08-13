# GroundedDocs — Build Documentation Index

This index is the single narrative for the entire GroundedDocs build. Every phase
produces a dedicated engineering document (per the top-level directive, Section 5)
that a technical reviewer can read in order without seeing a single diff.

**Scope note (v1):** this build pass is **English-first, end-to-end**. Arabic-specific
work (normalization, diacritics/RTL handling, Arabic eval set) is intentionally
deferred to a dedicated **Arabic pass (v1.1)** that reuses the language-agnostic
interfaces designed here. This trade-off is documented in every phase that touches it.

## Phases

| # | Phase | Doc | Status |
|---|-------|-----|--------|
| 0 | Foundations & Repo Scaffolding | [phase-0-foundations.md](phases/phase-0-foundations.md) | **Complete** |
| 1 | Ingestion & Chunking Pipeline | [phase-1-ingestion.md](phases/phase-1-ingestion.md) | **Complete** |
| 2 | Hybrid Retrieval & Ranking | [phase-2-retrieval.md](phases/phase-2-retrieval.md) | **Complete** |
| 3 | Grounded Generation & Citation Verification | [phase-3-generation.md](phases/phase-3-generation.md) | **Complete** |
| 4 | Evaluation Framework | [phase-4-evaluation.md](phases/phase-4-evaluation.md) | **Complete** |
| 5 | Production API & Observability | phase-5-api.md | Pending |
| 6 | Containerization & One-Command Deployment | phase-6-containerization.md | Pending |
| 7 | CI/CD Quality Gates | phase-7-ci.md | Pending |
| 8 | Dashboard (Next.js) | phase-8-dashboard.md | Pending |
| 9 | Polish, Documentation & Case Study | phase-9-polish.md | Pending |
| — | Arabic pass (v1.1) | phase-arabic-pass.md | Planned |

## How to read this

Each phase doc follows the same nine-part template:

1. **Phase Intro** — what this phase is and where it sits in the system
2. **Goal** — measurable objectives
3. **Description** — approach, design decisions, alternatives considered, trade-offs
4. **Work Done, Step by Step** — reconstructable chronological log
5. **Files to Review** — key files with one-line notes
6. **Testing** — what was tested, how, and outcomes
7. **Results** — concrete numbers; no unmeasured claims
8. **Deliverables** — matched against the phase's Definition of Done
9. **Known Limitations / Follow-ups** — deferred items and where they land

## Reference

- Authoritative spec: `GroundedDocs_PRD_v2.1.docx` (Sections 1–11)
- Top-level directive: pasted as the system prompt for the coding agent
