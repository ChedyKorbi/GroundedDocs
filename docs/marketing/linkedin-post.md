# GroundedDocs — LinkedIn Post

English, first person, under 200 words. All numbers are documented in the repo
(evaluation reports + phase docs).

---

Most RAG demos will hand you a confident answer and let you discover later that
it came from nowhere. I built the opposite: a system that has to **prove** every
claim.

That's GroundedDocs — a production hybrid RAG for enterprise documentation.
Dense embeddings and BM25 are fused with reciprocal rank fusion, re-ranked,
then every answer is generated only from numbered sources and each
claim↔citation pair is re-checked by a strict LLM judge. If the docs can't
answer, it refuses instead of guessing.

The number that matters most to me: **96.3% faithfulness, with 100% judge↔human
calibration** — I deliberately fed it two fabricated answers and it caught both.

I also measured where it's honest about being average. On a short,
keyword-dense corpus, plain BM25 was the strongest ranker and my reranker was
net-neutral. I published that finding instead of hiding it, because "measured,
not claimed" is the whole point.

Built with evaluation gates in CI, stage-level latency/cost observability,
zero-downtime reindexing, and a Next.js dashboard.

Repo: github.com/ChedyKorbi/GroundedDocs

#RAG #LLM #AIEngineering #MachineLearning #NLP #FastAPI #Python #AI #GenerativeAI
