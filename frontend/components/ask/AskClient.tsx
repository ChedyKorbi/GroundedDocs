"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, CircleSlash, Loader2 } from "lucide-react";
import { api, type AskResponse, type RetrievalMethod } from "@/lib/api";

const METHODS: { id: RetrievalMethod; label: string; hint: string }[] = [
  { id: "hybrid", label: "Hybrid", hint: "dense + sparse" },
  { id: "dense_only", label: "Dense", hint: "vectors only" },
  { id: "sparse_only", label: "Sparse", hint: "BM25 only" },
];

function confidenceLabel(v: number): string {
  if (v >= 0.8) return "High";
  if (v >= 0.6) return "Medium";
  return "Low";
}

/** Render the answer, turning [n] markers into superscript source links. */
function AnswerBody({ answer }: { answer: string }) {
  const parts = answer.split(/(\[\d+\])/g);
  return (
    <p className="text-[1.05rem] leading-[1.7] tracking-normal text-ink">
      {parts.map((part, i) => {
        const m = part.match(/^\[(\d+)\]$/);
        if (!m) return part;
        const n = m[1];
        return (
          <a
            key={i}
            href={`#source-${n}`}
            className="mx-0.5 inline-flex h-[1.15em] min-w-[1.15em] items-center justify-center rounded-[3px] bg-accent-soft px-1 align-super font-mono text-[0.55em] leading-none text-accent no-underline transition-colors hover:bg-accent hover:text-white"
            aria-label={`source ${n}`}
          >
            {n}
          </a>
        );
      })}
    </p>
  );
}

function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="eyebrow">Confidence</span>
        <span className="font-mono text-sm tnum text-ink">
          {pct}% <span className="text-faint">· {confidenceLabel(value)}</span>
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
        <div
          className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function LatencyRow({ label, ms }: { label: string; ms: number | null }) {
  return (
    <div className="flex items-baseline justify-between border-b border-line py-1.5 last:border-0">
      <span className="text-[0.8125rem] text-muted">{label}</span>
      <span className="font-mono text-[0.8125rem] tnum text-ink">
        {ms === null ? "—" : `${ms.toFixed(0)} ms`}
      </span>
    </div>
  );
}

function SourcesRail({ result }: { result: AskResponse }) {
  return (
    <div className="space-y-3">
      <p className="eyebrow">Sources · {result.citations.length}</p>
      {result.citations.length === 0 ? (
        <p className="text-sm text-muted">No sources cited.</p>
      ) : (
        result.citations.map((c) => (
          <div
            key={c.index}
            id={`source-${c.index}`}
            className="card p-3.5 scroll-mt-6"
          >
            <div className="mb-2 flex items-center gap-2">
              <span className="grid h-5 w-5 place-items-center rounded bg-ink font-mono text-[0.6875rem] text-paper">
                {c.index}
              </span>
              <span
                className={`inline-flex items-center gap-1.5 font-mono text-[0.6875rem] ${
                  c.supported ? "text-ok" : "text-warn"
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    c.supported ? "bg-ok" : "bg-warn"
                  }`}
                />
                {c.supported ? "verified" : "unverified"}
              </span>
            </div>
            {c.text && (
              <p className="mb-2 line-clamp-4 text-[0.8125rem] leading-relaxed text-muted">
                {c.text}
              </p>
            )}
            {c.reason && (
              <p className="font-mono text-[0.6875rem] leading-relaxed text-faint">
                {c.reason}
              </p>
            )}
          </div>
        ))
      )}
    </div>
  );
}

function Diagnostics({ result }: { result: AskResponse }) {
  const b = result.breakdown;
  const t = result.tokens;
  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="eyebrow">Diagnostics</p>
        <span className="font-mono text-[0.6875rem] text-faint">
          {result.models.llm_model}
        </span>
      </div>

      <ConfidenceMeter value={result.confidence} />

      <div className="mt-4">
        <p className="eyebrow mb-1">Latency · total {b.total_ms.toFixed(0)} ms</p>
        <LatencyRow label="Embed" ms={b.embed_ms} />
        <LatencyRow label="Dense" ms={b.dense_ms} />
        <LatencyRow label="Sparse" ms={b.sparse_ms} />
        <LatencyRow label="Fusion" ms={b.fusion_ms} />
        <LatencyRow label="Rerank" ms={b.rerank_ms} />
        <LatencyRow label="Generate" ms={b.generate_ms} />
        <LatencyRow label="Verify" ms={b.verify_ms} />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3 border-t border-line pt-3">
        <div>
          <p className="eyebrow">Tokens</p>
          <p className="mt-1 font-mono text-sm tnum text-ink">
            {t.total_tokens.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="eyebrow">Cost</p>
          <p className="mt-1 font-mono text-sm tnum text-ink">
            ${t.cost_usd.toFixed(5)}
          </p>
        </div>
        <div>
          <p className="eyebrow">Citations</p>
          <p className="mt-1 font-mono text-sm tnum text-ink">
            {result.citations.filter((c) => c.supported).length}/
            {result.citations.length} ok
          </p>
        </div>
      </div>
    </div>
  );
}

function InsufficientCard() {
  return (
    <div className="card flex items-start gap-3 border-warn/30 p-5">
      <CircleSlash size={18} className="mt-0.5 shrink-0 text-warn" strokeWidth={1.75} />
      <div>
        <p className="font-medium text-ink">Insufficient information</p>
        <p className="mt-1 text-sm leading-relaxed text-muted">
          The indexed documentation does not contain enough evidence to answer
          this question. GroundedDocs refuses to guess rather than fabricate an
          answer.
        </p>
      </div>
    </div>
  );
}

export function AskClient() {
  const [question, setQuestion] = useState("");
  const [method, setMethod] = useState<RetrievalMethod>("hybrid");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  const submit = useCallback(
    async (q: string) => {
      if (!q.trim() || loading) return;
      setLoading(true);
      setError(null);
      setResult(null);
      try {
        const res = await api.ask({ question: q, retrieval_method: method, top_k: 6 });
        setResult(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Request failed");
      } finally {
        setLoading(false);
      }
    },
    [loading, method],
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "/" && !(e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        formRef.current?.querySelector("textarea")?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-10 lg:px-12">
      <header className="mb-10">
        <p className="eyebrow">GroundedDocs · Hybrid retrieval</p>
        <h1 className="mt-2 font-serif text-4xl tracking-tight text-ink sm:text-5xl">
          Ask your documentation.
        </h1>
        <p className="mt-3 max-w-xl text-[0.9375rem] leading-relaxed text-muted">
          Every answer is drawn only from indexed sources, cited, and verified
          claim by claim. Press <kbd className="rounded border border-line bg-surface px-1.5 py-0.5 font-mono text-[0.6875rem] text-ink">/</kbd> to focus the prompt.
        </p>
      </header>

      <form
        ref={formRef}
        className="mb-8"
        onSubmit={(e) => {
          e.preventDefault();
          void submit(question);
        }}
      >
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void submit(question);
            }
          }}
          rows={2}
          placeholder="How many days of annual leave do employees accrue per year?"
          className="w-full resize-none rounded-xl border border-line-strong bg-surface px-5 py-4 font-serif text-xl leading-snug text-ink shadow-none outline-none transition-colors placeholder:text-faint focus:border-accent focus:ring-4 focus:ring-accent-soft"
          aria-label="Your question"
        />

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex overflow-hidden rounded-lg border border-line-strong">
            {METHODS.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setMethod(m.id)}
                aria-pressed={method === m.id}
                className={`px-3.5 py-2 text-left transition-colors duration-150 ${
                  method === m.id
                    ? "bg-accent-soft text-accent"
                    : "bg-surface text-muted hover:text-ink"
                }`}
              >
                <span className="block text-[0.8125rem] font-medium leading-tight">
                  {m.label}
                </span>
                <span className="block font-mono text-[0.625rem] leading-tight opacity-70">
                  {m.hint}
                </span>
              </button>
            ))}
          </div>

          <button
            type="submit"
            disabled={!question.trim() || loading}
            className="btn btn-primary px-5 py-2.5 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <ArrowUp size={15} />
            )}
            {loading ? "Retrieving · verifying" : "Ask"}
          </button>
        </div>
      </form>

      {error && (
        <div className="mb-6 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {loading && (
        <div className="card flex items-center gap-3 p-5 text-sm text-muted">
          <Loader2 size={16} className="animate-spin text-accent" />
          Retrieving candidates, fusing ranks, generating, verifying citations…
        </div>
      )}

      {result && !loading && (
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="min-w-0">
            <div className="mb-3 flex items-baseline justify-between gap-4">
              <p className="eyebrow">{result.insufficient ? "Refused" : "Answer"}</p>
              <p className="truncate font-mono text-[0.6875rem] text-faint">
                {result.insufficient ? "—" : result.request_id}
              </p>
            </div>

            {result.insufficient ? (
              <InsufficientCard />
            ) : (
              <div className="card p-6">
                <AnswerBody answer={result.answer} />
              </div>
            )}

            {!result.insufficient && result.sentences.length > 0 && (
              <div className="mt-6">
                <p className="eyebrow mb-2">Claim verification</p>
                <ul className="space-y-1.5">
                  {result.sentences.map((s, i) => {
                    const ok = s.checks.length > 0 && s.checks.every((c) => c.supported);
                    return (
                      <li key={i} className="flex items-start gap-2.5 text-[0.8125rem] text-muted">
                        <span
                          className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                            ok ? "bg-ok" : s.checks.length ? "bg-warn" : "bg-faint"
                          }`}
                        />
                        <span className="leading-relaxed">{s.sentence}</span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>

          <aside className="min-w-0 space-y-5">
            <SourcesRail result={result} />
            {!result.insufficient && <Diagnostics result={result} />}
          </aside>
        </div>
      )}
    </div>
  );
}
