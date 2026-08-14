import Link from "next/link";
import {
  ArrowUpRight,
  BookOpen,
  Check,
  CircuitBoard,
  Container,
  FlaskConical,
  Gauge,
  GitBranch,
  Layers,
  ShieldCheck,
} from "lucide-react";

const RESULTS = [
  { label: "Faithfulness", value: "96.3%", note: "claims entailed by the retrieved context" },
  { label: "Citation accuracy", value: "88.2%", note: "verified supported citations" },
  { label: "Recall@3", value: "93.8%", note: "hybrid retrieval, 48-question golden set" },
  { label: "Correct refusal", value: "100%", note: "on unanswerable questions — 0% hallucinated" },
  { label: "Judge↔human calibration", value: "100%", note: "both fabricated answers caught" },
];

const CHUNKING = [
  { strategy: "Fixed-size", recall1: "81.0%", recall3: "98.1%" },
  { strategy: "Structure-aware", recall1: "74.4%", recall3: "90.6%" },
  { strategy: "Semantic", recall1: "70.4%", recall3: "88.8%" },
];

const STAGES = [
  "Ingest & chunk",
  "Hybrid retrieval",
  "Rerank",
  "Grounded generation",
  "Citation verification",
  "Confidence + eval",
];

function Flow() {
  return (
    <div className="flex flex-wrap items-stretch gap-2">
      {STAGES.map((stage, i) => (
        <div key={stage} className="flex items-center gap-2">
          <div className="rounded-lg border border-line bg-surface px-3.5 py-2.5 text-center">
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-accent">
              {String(i + 1).padStart(2, "0")}
            </p>
            <p className="mt-0.5 text-[0.8125rem] font-medium text-ink">{stage}</p>
          </div>
          {i < STAGES.length - 1 && <ArrowUpRight size={14} className="shrink-0 text-faint" />}
        </div>
      ))}
    </div>
  );
}

export default function AboutPage() {
  const apiBase = process.env.NEXT_PUBLIC_GROUNDEDDOCS_API ?? "http://localhost:8000";
  const links = [
    { href: "https://github.com/ChedyKorbi/GroundedDocs", label: "GitHub repository", sub: "architecture, docs, evaluation reports", external: true },
    { href: `${apiBase}/docs`, label: "API reference (Swagger)", sub: "every endpoint, live", external: true },
    { href: "/performance", label: "Live telemetry", sub: "latency, cost, evaluation summary", external: false },
    { href: "/documents", label: "Documents", sub: "ingest and manage the corpus", external: false },
  ];
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-10 lg:px-12">
      {/* Hero */}
      <header className="mb-14 max-w-2xl">
        <p className="eyebrow">About the project</p>
        <h1 className="mt-3 font-serif text-4xl leading-tight tracking-tight text-ink sm:text-5xl">
          GroundedDocs.
          <br />
          <span className="text-accent">An instrument for trustworthy answers.</span>
        </h1>
        <p className="mt-5 text-[0.9375rem] leading-relaxed text-muted">
          A production-grade hybrid retrieval-augmented generation (RAG) system for
          enterprise documentation. Every answer is drawn only from indexed sources,
          cited claim by claim, and verified — because a RAG system that cannot prove
          where its answers come from is not worth trusting.
        </p>
      </header>

      {/* What it is */}
      <section className="mb-14 grid gap-4 md:grid-cols-3">
        <div className="card p-5">
          <CircuitBoard size={18} className="text-accent" strokeWidth={1.75} />
          <p className="mt-3 font-medium text-ink">Grounded, not generated</p>
          <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-muted">
            A strict grounded prompt forces the model to answer only from numbered
            context passages, with bracketed citations the reader can check.
          </p>
        </div>
        <div className="card p-5">
          <ShieldCheck size={18} className="text-accent" strokeWidth={1.75} />
          <p className="mt-3 font-medium text-ink">Verified, not assumed</p>
          <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-muted">
            Every claim↔citation pair is re-checked by a strict LLM judge; when the
            documentation cannot answer, the system refuses instead of guessing.
          </p>
        </div>
        <div className="card p-5">
          <Gauge size={18} className="text-accent" strokeWidth={1.75} />
          <p className="mt-3 font-medium text-ink">Measured, not claimed</p>
          <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-muted">
            Retrieval, faithfulness, and citation quality are evaluated against a
            48-question golden set with published, reproducible numbers.
          </p>
        </div>
      </section>

      {/* Pipeline */}
      <section className="mb-14">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="font-serif text-2xl tracking-tight text-ink">How it works</h2>
          <span className="eyebrow">End to end</span>
        </div>
        <div className="card p-5">
          <Flow />
        </div>
        <div className="mt-4 grid gap-3 text-[0.8125rem] leading-relaxed text-muted md:grid-cols-2">
          <p>
            Documents are loaded (PDF, Markdown, TXT, HTML), normalized, and chunked
            with one of three strategies — fixed-size, structure-aware, semantic —
            then deduplicated against the index itself. Dense vectors (multilingual
            e5-large) and sparse BM25 are retrieved independently and merged with
            reciprocal rank fusion, then re-ranked.
          </p>
          <p>
            The answer is generated under a strict grounded prompt, citations are
            verified per claim by a judge model, and a composite confidence score
            summarizes groundedness. Failures are collected and root-caused in an
            automated evaluation harness.
          </p>
        </div>
      </section>

      {/* Results */}
      <section className="mb-14">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="font-serif text-2xl tracking-tight text-ink">Measured results</h2>
          <Link href="/performance" className="text-[0.8125rem] text-accent hover:underline">
            View live telemetry →
          </Link>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {RESULTS.map((r) => (
            <div key={r.label} className="card p-4">
              <p className="font-mono text-[1.7rem] leading-none tnum text-ok">{r.value}</p>
              <p className="mt-2 text-[0.8125rem] font-medium text-ink">{r.label}</p>
              <p className="mt-1 text-[0.6875rem] leading-snug text-faint">{r.note}</p>
            </div>
          ))}
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <div className="card p-5">
            <p className="eyebrow mb-3">Chunking strategy comparison</p>
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-line">
                  <th className="py-2 font-mono text-[0.6875rem] font-normal uppercase tracking-wider text-faint">Strategy</th>
                  <th className="py-2 text-right font-mono text-[0.6875rem] font-normal uppercase tracking-wider text-faint">recall@1</th>
                  <th className="py-2 text-right font-mono text-[0.6875rem] font-normal uppercase tracking-wider text-faint">recall@3</th>
                </tr>
              </thead>
              <tbody>
                {CHUNKING.map((c) => (
                  <tr key={c.strategy} className="border-b border-line last:border-0">
                    <td className="py-2.5 text-sm text-ink">{c.strategy}</td>
                    <td className="py-2.5 text-right font-mono text-sm tnum text-ink">{c.recall1}</td>
                    <td className="py-2.5 text-right font-mono text-sm tnum text-ink">{c.recall3}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-[0.6875rem] leading-snug text-faint">
              Measured, not assumed — fixed-size wins on this short, keyword-dense
              corpus; the trade-off is documented rather than hidden.
            </p>
          </div>

          <div className="card p-5">
            <p className="eyebrow mb-3">Latency & cost (live, CPU)</p>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
              <div>
                <dt className="text-[0.6875rem] text-faint">Total p50 / p95</dt>
                <dd className="font-mono text-sm tnum text-ink">1.4s / 8.5s</dd>
              </div>
              <div>
                <dt className="text-[0.6875rem] text-faint">Generation p50</dt>
                <dd className="font-mono text-sm tnum text-ink">501 ms</dd>
              </div>
              <div>
                <dt className="text-[0.6875rem] text-faint">Tokens / query</dt>
                <dd className="font-mono text-sm tnum text-ink">≈1,150</dd>
              </div>
              <div>
                <dt className="text-[0.6875rem] text-faint">Cost / query (est.)</dt>
                <dd className="font-mono text-sm tnum text-ok">$0.000355</dd>
              </div>
            </dl>
            <p className="mt-3 text-[0.6875rem] leading-snug text-faint">
              Per-stage timing (embed / dense / sparse / fusion / rerank / generate /
              verify) is recorded for every query and surfaced on the Performance page.
            </p>
          </div>
        </div>
      </section>

      {/* Production */}
      <section className="mb-14">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="font-serif text-2xl tracking-tight text-ink">Production engineering</h2>
          <span className="eyebrow">Not a demo</span>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="card p-5">
            <Container size={18} className="text-accent" strokeWidth={1.75} />
            <p className="mt-3 font-medium text-ink">One-command stack</p>
            <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-muted">
              Multi-stage Dockerfile, API + Qdrant compose stack, sample corpus seeded
              on first boot, health checks verifying DB + model readiness.
            </p>
          </div>
          <div className="card p-5">
            <GitBranch size={18} className="text-accent" strokeWidth={1.75} />
            <p className="mt-3 font-medium text-ink">CI with an eval gate</p>
            <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-muted">
              Lint, strict typing, 107 unit tests, dependency audit, Docker build —
              plus a real-stack suite that fails if faithfulness or citation accuracy
              regresses.
            </p>
          </div>
          <div className="card p-5">
            <Layers size={18} className="text-accent" strokeWidth={1.75} />
            <p className="mt-3 font-medium text-ink">Zero-downtime reindex</p>
            <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-muted">
              Versioned Qdrant collections with atomic alias swap — re-index without
              dropping in-flight queries.
            </p>
          </div>
          <div className="card p-5">
            <FlaskConical size={18} className="text-accent" strokeWidth={1.75} />
            <p className="mt-3 font-medium text-ink">Observability built-in</p>
            <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-muted">
              Structured logs with request IDs, SQLite query log, p50/p95/p99 latency,
              token + cost tracking, model-version registry per answer.
            </p>
          </div>
        </div>
      </section>

      {/* Stack + links */}
      <section className="grid gap-4 lg:grid-cols-2">
        <div className="card p-6">
          <p className="eyebrow mb-3">Stack</p>
          <div className="flex flex-wrap gap-2">
            {[
              "Python 3.12", "FastAPI", "Qdrant", "LangChain 1.3", "Groq",
              "multilingual-e5-large", "BM25 (rank-bm25)", "sentence-transformers",
              "Next.js 16", "Tailwind", "Docker", "GitHub Actions",
            ].map((t) => (
              <span key={t} className="rounded border border-line bg-paper px-2.5 py-1 font-mono text-[0.6875rem] text-muted">
                {t}
              </span>
            ))}
          </div>
          <div className="mt-5 flex flex-wrap items-center gap-2 text-[0.8125rem] text-muted">
            <Check size={14} className="text-ok" strokeWidth={2} />
            107 unit tests passing · 6 real-stack integration tests · mypy strict clean
          </div>
        </div>

        <div className="card flex flex-col justify-between p-6">
          <div>
            <p className="eyebrow mb-3">Explore</p>
            <ul className="space-y-2.5 text-[0.875rem]">
              {links.map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="group flex items-baseline justify-between gap-4 border-b border-line pb-2.5 last:border-0">
                    <span>
                      <span className="block font-medium text-ink group-hover:text-accent">{l.label}</span>
                      <span className="block text-[0.6875rem] text-faint">{l.sub}</span>
                    </span>
                    <ArrowUpRight size={14} className="shrink-0 text-faint transition-colors group-hover:text-accent" />
                  </Link>
                </li>
              ))}
            </ul>
          </div>
          <div className="mt-6 flex items-center gap-2 text-[0.6875rem] text-faint">
            <BookOpen size={13} />
            Built phase by phase with a documented engineering narrative in docs/phases/.
          </div>
        </div>
      </section>
    </div>
  );
}
