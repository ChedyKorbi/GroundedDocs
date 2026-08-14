"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Loader2 } from "lucide-react";
import {
  api,
  type EvalSummary,
  type HealthResponse,
  type MetricsResponse,
  type QueryRow,
} from "@/lib/api";

function Kpi({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="card p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 font-mono text-[1.6rem] leading-none tnum text-ink">
        {value}
      </p>
      {sub && <p className="mt-1.5 text-[0.6875rem] text-faint">{sub}</p>}
    </div>
  );
}

function StatRow({
  label,
  value,
}: {
  label: string;
  value: string | number | null;
}) {
  return (
    <div className="flex items-baseline justify-between py-1.5">
      <span className="text-[0.8125rem] text-muted">{label}</span>
      <span className="font-mono text-[0.8125rem] tnum text-ink">
        {value === null || value === undefined ? "—" : value}
      </span>
    </div>
  );
}

function fmtTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function latencyMs(r: QueryRow): number | null {
  return r.total_ms ?? null;
}

export function PerformanceClient() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [evalSummary, setEvalSummary] = useState<EvalSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [m, h, e] = await Promise.all([
        api.metrics(),
        api.health(),
        api.evalSummary(),
      ]);
      setMetrics(m);
      setHealth(h);
      setEvalSummary(e);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load metrics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- async data fetch on mount; setState runs after await
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 px-12 py-10 text-sm text-muted">
        <Loader2 size={15} className="animate-spin text-accent" /> Loading
        telemetry…
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div className="px-12 py-10 text-sm text-danger">
        {error ?? "No metrics available."}
      </div>
    );
  }

  const chartData = [...metrics.recent_queries]
    .reverse()
    .map((r) => ({
      label: fmtTime(r.ts),
      total: latencyMs(r),
      generate: r.generate_ms,
    }))
    .filter((d) => d.total !== null);

  const p50 = metrics.latency.p50;
  const p95 = metrics.latency.p95;
  const success = (1 - metrics.error_rate) * 100;
  const tokens = metrics.total_input_tokens + metrics.total_output_tokens;
  const cite = metrics.citation_accuracy;

  const stages = Object.entries(metrics.stage_latency).map(([key, v]) => ({
    key,
    label: key.replace("_ms", ""),
    p50: v.p50,
    p95: v.p95,
  }));
  const maxStage = Math.max(1, ...stages.map((s) => s.p50 ?? 0));

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-10 lg:px-12">
      <header className="mb-8">
        <p className="eyebrow">System telemetry · live</p>
        <h1 className="mt-2 font-serif text-4xl tracking-tight text-ink">
          Performance
        </h1>
      </header>

      {/* Health strip */}
      <div className="mb-8 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-line bg-surface px-4 py-3">
        <span className="flex items-center gap-2 text-sm">
          <span
            className={`h-2 w-2 rounded-full ${
              health?.status === "ok" ? "bg-ok" : "bg-warn"
            }`}
          />
          <span className="font-medium text-ink">
            {health?.status === "ok" ? "Operational" : "Degraded"}
          </span>
        </span>
        <span className="font-mono text-[0.75rem] text-muted">
          Qdrant {health?.qdrant ? "up" : "down"}
        </span>
        <span className="font-mono text-[0.75rem] text-muted">
          Model {health?.model_ready ? "ready" : "loading"}
        </span>
        <span className="font-mono text-[0.75rem] text-muted">
          {health?.index_chunks ?? "—"} chunks indexed
        </span>
        {metrics.model_versions.embedding && (
          <span className="ml-auto hidden font-mono text-[0.6875rem] text-faint md:block">
            {metrics.model_versions.llm}
          </span>
        )}
      </div>

      {/* KPIs */}
      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Kpi label="Requests" value={String(metrics.request_count)} />
        <Kpi
          label="Success"
          value={`${success.toFixed(1)}%`}
          sub={`${metrics.error_count} errors`}
        />
        <Kpi
          label="p95 latency"
          value={p95 === null ? "—" : `${p95.toFixed(0)} ms`}
        />
        <Kpi
          label="Cost"
          value={`$${metrics.total_cost_usd.toFixed(4)}`}
          sub={`${tokens.toLocaleString()} tokens`}
        />
        <Kpi
          label="Citations"
          value={cite === null ? "—" : `${(cite * 100).toFixed(1)}%`}
          sub="verified"
        />
        <Kpi label="Avg tokens" value={Math.round(tokens / Math.max(1, metrics.request_count)).toLocaleString()} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        {/* Latency over time */}
        <div className="card p-5">
          <div className="mb-4 flex items-baseline justify-between">
            <p className="eyebrow">End-to-end latency · recent queries</p>
            <span className="font-mono text-[0.6875rem] text-faint">
              p50 {p50?.toFixed(0)} ms · p95 {p95?.toFixed(0)} ms
            </span>
          </div>
          {chartData.length === 0 ? (
            <p className="py-10 text-center text-sm text-faint">
              No queries logged yet — ask something in the Ask view.
            </p>
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fill: "var(--faint)", fontSize: 10, fontFamily: "var(--mono)" }}
                    tickLine={false}
                    axisLine={{ stroke: "var(--line)" }}
                  />
                  <YAxis
                    tick={{ fill: "var(--faint)", fontSize: 10, fontFamily: "var(--mono)" }}
                    tickLine={false}
                    axisLine={false}
                    width={44}
                    tickFormatter={(v) => `${v}`}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--line)",
                      borderRadius: 8,
                      fontSize: 12,
                      fontFamily: "var(--mono)",
                    }}
                    labelStyle={{ color: "var(--muted)" }}
                    formatter={(value) => [`${Number(value).toFixed(0)} ms`, "total"]}
                  />
                  {p50 !== null && (
                    <ReferenceLine
                      y={p50}
                      stroke="var(--faint)"
                      strokeDasharray="4 4"
                      label={{ value: "p50", fill: "var(--faint)", fontSize: 10, fontFamily: "var(--mono)" }}
                    />
                  )}
                  {p95 !== null && (
                    <ReferenceLine
                      y={p95}
                      stroke="var(--accent)"
                      strokeDasharray="4 4"
                      label={{ value: "p95", fill: "var(--accent)", fontSize: 10, fontFamily: "var(--mono)" }}
                    />
                  )}
                  <Line
                    type="monotone"
                    dataKey="total"
                    stroke="var(--accent)"
                    strokeWidth={1.75}
                    dot={false}
                    activeDot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Stage latency + eval */}
        <div className="space-y-6">
          <div className="card p-5">
            <p className="eyebrow mb-3">Stage latency · p50</p>
            {stages.map((s) => (
              <div key={s.key} className="mb-2.5 last:mb-0">
                <div className="mb-1 flex items-baseline justify-between">
                  <span className="text-[0.75rem] text-muted capitalize">
                    {s.label}
                  </span>
                  <span className="font-mono text-[0.75rem] tnum text-ink">
                    {s.p50 === null ? "—" : `${s.p50.toFixed(0)} ms`}
                  </span>
                </div>
                <div className="h-1 w-full overflow-hidden rounded-full bg-line">
                  <div
                    className="h-full rounded-full bg-accent/70"
                    style={{ width: `${Math.max(2, ((s.p50 ?? 0) / maxStage) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>

          {evalSummary?.questions ? (
            <div className="card p-5">
              <div className="mb-3 flex items-baseline justify-between">
                <p className="eyebrow">Evaluation · golden set</p>
                <span className="font-mono text-[0.6875rem] text-faint">
                  {evalSummary.questions} questions
                </span>
              </div>
              <StatRow label="Faithfulness" value={pct(evalSummary.faithfulness)} />
              <StatRow label="Answer relevance" value={pct(evalSummary.relevance)} />
              <StatRow label="Citation accuracy" value={pct(evalSummary.citation_accuracy)} />
              <StatRow label="Recall@1" value={pct(evalSummary.recall_1)} />
              <StatRow label="Correct refusal" value={pct(evalSummary.correct_refusal_rate)} />
              <StatRow
                label="Judge agreement"
                value={pct(evalSummary.calibration_faithful_agreement)}
              />
              <StatRow label="Failures" value={evalSummary.failures} />
            </div>
          ) : (
            <div className="card p-5">
              <p className="eyebrow mb-2">Evaluation</p>
              <p className="text-sm text-muted">
                No evaluation report yet — run{" "}
                <code className="rounded bg-paper px-1 font-mono text-[0.75rem] text-ink">
                  uv run python scripts/eval.py
                </code>
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Recent queries */}
      <div className="mt-8">
        <p className="eyebrow mb-3">Recent queries</p>
        {metrics.recent_queries.length === 0 ? (
          <p className="text-sm text-faint">None yet.</p>
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-line">
                  {["Time", "Question", "Method", "Confidence", "Citations", "Latency", "Cost"].map(
                    (h) => (
                      <th
                        key={h}
                        className="px-4 py-2.5 font-mono text-[0.6875rem] font-normal uppercase tracking-wider text-faint"
                      >
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {metrics.recent_queries.map((r) => (
                  <Row
                    key={r.request_id}
                    row={r}
                    open={expanded === r.request_id}
                    onToggle={() =>
                      setExpanded(expanded === r.request_id ? null : r.request_id)
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function pct(v: number | null): string | null {
  if (v === null || v === undefined) return null;
  return `${(v * 100).toFixed(1)}%`;
}

function Row({
  row,
  open,
  onToggle,
}: {
  row: QueryRow;
  open: boolean;
  onToggle: () => void;
}) {
  const failed = row.error !== null;
  return (
    <>
      <tr
        className={`cursor-pointer border-b border-line last:border-0 hover:bg-paper ${
          open ? "bg-paper" : ""
        }`}
        onClick={onToggle}
      >
        <td className="whitespace-nowrap px-4 py-3 font-mono text-[0.75rem] tnum text-muted">
          {fmtTime(row.ts)}
        </td>
        <td className="max-w-[260px] truncate px-4 py-3 text-sm text-ink">
          {row.question}
        </td>
        <td className="px-4 py-3">
          <span className="rounded border border-line bg-paper px-1.5 py-0.5 font-mono text-[0.625rem] text-muted">
            {row.retrieval_method ?? "—"}
          </span>
        </td>
        <td className="px-4 py-3 font-mono text-[0.75rem] tnum text-ink">
          {row.confidence === null ? "—" : pct(row.confidence)}
        </td>
        <td className="px-4 py-3 font-mono text-[0.75rem] tnum text-ink">
          {row.supported_citations}/{row.citation_count}
        </td>
        <td className="px-4 py-3 font-mono text-[0.75rem] tnum text-ink">
          {row.total_ms === null ? "—" : `${row.total_ms.toFixed(0)} ms`}
        </td>
        <td className="px-4 py-3 font-mono text-[0.75rem] tnum text-muted">
          ${(row.cost_usd ?? 0).toFixed(5)}
        </td>
      </tr>
      {open && (
        <tr className="bg-paper">
          <td colSpan={7} className="px-4 pb-4">
            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <p className="eyebrow mb-1">Answer</p>
                <p className="text-sm leading-relaxed text-muted">
                  {failed ? (
                    <span className="text-danger">error: {row.error}</span>
                  ) : row.insufficient ? (
                    <em>Insufficient information — refused.</em>
                  ) : (
                    row.answer ?? "—"
                  )}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-x-6">
                <div>
                  <p className="eyebrow mb-1">Stages</p>
                  <StatRow label="Embed" value={ms(row.embed_ms)} />
                  <StatRow label="Dense" value={ms(row.dense_ms)} />
                  <StatRow label="Sparse" value={ms(row.sparse_ms)} />
                  <StatRow label="Fusion" value={ms(row.fusion_ms)} />
                  <StatRow label="Rerank" value={ms(row.rerank_ms)} />
                  <StatRow label="Generate" value={ms(row.generate_ms)} />
                  <StatRow label="Verify" value={ms(row.verify_ms)} />
                </div>
                <div>
                  <p className="eyebrow mb-1">Tokens & models</p>
                  <StatRow label="Input" value={row.input_tokens} />
                  <StatRow label="Output" value={row.output_tokens} />
                  <StatRow label="Total" value={row.input_tokens + row.output_tokens} />
                  <StatRow label="LLM" value={row.llm_model} />
                  <StatRow label="Reranker" value={row.reranker} />
                  <StatRow label="Request" value={shortId(row.request_id)} />
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function ms(v: number | null): string {
  return v === null ? "—" : `${v.toFixed(0)} ms`;
}
function shortId(id: string): string {
  return id ? `${id.slice(0, 8)}…` : "—";
}
