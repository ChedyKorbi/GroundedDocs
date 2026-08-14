# GroundedDocs — LinkedIn Post (in-depth)

First person, engineer's voice, no hype. Every number is documented in the repo
(evaluation reports + phase docs); anything I couldn't measure is said so.

---

Most RAG demos will hand you a confident answer and let you discover later that
it came from nowhere. I built the opposite: a system that has to **prove** every
claim.

That system is **GroundedDocs** — a production hybrid RAG for enterprise
documentation. I want to unpack what's actually inside, because the difference
between a demo and a system lives in the details.

**The retrieval isn't one method — it's three decisions measured against each
other.** I implemented three chunking strategies (fixed-size, structure-aware,
semantic) and ran a head-to-head: fixed-size won on recall@1 (81.0% vs 74.4% vs
70.4%). The interesting part isn't the winner — it's that I published the
comparison instead of pretending the default was best.

**Hybrid retrieval means dense + sparse, fused — and I kept the honest finding.**
Dense embeddings (multilingual e5-large) and BM25 are combined with reciprocal
rank fusion, then re-ranked. On a keyword-dense corpus, plain BM25 was the
strongest single ranker and the reranker was net-neutral. So I reported it.
Hybrid's real edge showed up as coverage: recall@3 went from 88.9% (dense-only)
to 100%.

**Every answer is verified, not trusted.** The model answers only from numbered
context passages with bracketed citations; then each claim↔citation pair is
re-checked by a strict LLM judge. Unanswerable questions are refused — 100% of
them, with 0% hallucination — and the composite confidence score tells you how
much the system trusts its own answer.

**Quality is measured, not claimed.** A 48-question golden set spanning easy,
multi-hop, ambiguous, and unanswerable questions. LLM-as-judge metrics for
faithfulness (96.3%) and citation accuracy (88.2%). I hand-labeled a subset and
the judge agreed with me 100% — including catching both fabricated answers I
planted to test it.

**It's observable and it deploys like a product.** Every query records
stage-level latency (embed / dense / sparse / fusion / rerank / generate /
verify), token usage, and estimated cost, surfaced as p50/p95/p99 with
request-id tracing. CI runs lint, strict typing, 107 unit tests, dependency
audits, and a Docker build — plus an evaluation gate that fails the pipeline if
faithfulness drops below 85% or citation accuracy below 80%. Re-indexing is
zero-downtime via versioned Qdrant collections with an atomic alias swap. A
Next.js dashboard makes all of it visible to non-engineers.

The one number that matters most to me: **96.3% faithfulness with 100%
judge↔human calibration** — because an AI system you can't audit is just
confident text.

Repo: github.com/ChedyKorbi/GroundedDocs

#RAG #LLM #AIEngineering #MachineLearning #NLP #FastAPI #Python #AI #GenerativeAI #MLOps
