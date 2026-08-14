// Typed client for the GroundedDocs API (frozen contract v1, docs/API_CONTRACT.md).

export const API_BASE =
  process.env.NEXT_PUBLIC_GROUNDEDDOCS_API ?? "http://localhost:8000";

export interface Citation {
  index: number;
  chunk_id: string;
  supported: boolean;
  reason: string;
  text: string;
}

export interface Sentence {
  sentence: string;
  checks: Citation[];
}

export interface LatencyBreakdown {
  embed_ms: number | null;
  dense_ms: number | null;
  sparse_ms: number | null;
  fusion_ms: number | null;
  rerank_ms: number | null;
  generate_ms: number | null;
  verify_ms: number | null;
  total_ms: number;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  verify_input_tokens: number;
  verify_output_tokens: number;
  total_tokens: number;
  cost_usd: number;
}

export interface ModelVersions {
  llm_model: string;
  embedding_model: string;
  reranker: string | null;
}

export interface AskResponse {
  question: string;
  answer: string;
  insufficient: boolean;
  confidence: number;
  citations: Citation[];
  sentences: Sentence[];
  breakdown: LatencyBreakdown;
  tokens: TokenUsage;
  models: ModelVersions;
  request_id: string | null;
}

export interface DocumentInfo {
  document_id: string;
  format: string;
  chunk_count: number;
}

export interface DocumentsResponse {
  documents: DocumentInfo[];
  total_chunks: number;
}

export interface IngestResult {
  file: string;
  document_id: string;
  format: string;
  segments: number;
  chunks_total: number;
  inserted: number;
  skipped: number;
  flagged: number;
  strategy_counts: Record<string, number>;
  duration_ms: number;
}

export interface IngestResponse {
  documents: IngestResult[];
  total_inserted: number;
  index_chunks: number;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  service: string;
  version: string;
  qdrant: boolean;
  model_ready: boolean;
  index_chunks: number | null;
}

export interface QueryRow {
  request_id: string;
  ts: number;
  question: string;
  answer: string | null;
  insufficient: number;
  confidence: number | null;
  citation_count: number;
  supported_citations: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  embed_ms: number | null;
  dense_ms: number | null;
  sparse_ms: number | null;
  fusion_ms: number | null;
  rerank_ms: number | null;
  generate_ms: number | null;
  verify_ms: number | null;
  total_ms: number | null;
  retrieval_method: string | null;
  llm_model: string | null;
  embedding_model: string | null;
  reranker: string | null;
  error: string | null;
}

export interface Percentiles {
  p50: number | null;
  p95: number | null;
  p99: number | null;
  count: number;
}

export interface MetricsResponse {
  request_count: number;
  success_count: number;
  error_count: number;
  error_rate: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  total_citations: number;
  total_supported_citations: number;
  citation_accuracy: number | null;
  latency: Percentiles;
  stage_latency: Record<string, Percentiles>;
  model_versions: Record<string, string>;
  recent_queries: QueryRow[];
}

export interface ReindexResponse {
  previous_collection: string | null;
  current_collection: string;
  chunks_reindexed: number;
  duration_ms: number;
}

export interface EvalSummary {
  generated_at: string | null;
  method: string | null;
  questions: number | null;
  faithfulness: number | null;
  relevance: number | null;
  citation_accuracy: number | null;
  recall_1: number | null;
  recall_3: number | null;
  correct_refusal_rate: number | null;
  failures: number | null;
  calibration_faithful_agreement: number | null;
  report_path: string | null;
}

export type RetrievalMethod = "hybrid" | "dense_only" | "sparse_only";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  const key = process.env.NEXT_PUBLIC_GROUNDEDDOCS_API_KEY;
  if (key) headers["X-API-Key"] = key;

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { error?: { message?: string } };
      if (body?.error?.message) detail = body.error.message;
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => apiFetch<HealthResponse>("/health"),
  ask: (body: { question: string; retrieval_method: RetrievalMethod; top_k?: number }) =>
    apiFetch<AskResponse>("/ask", { method: "POST", body: JSON.stringify(body) }),
  documents: () => apiFetch<DocumentsResponse>("/documents"),
  deleteDocument: (id: string) =>
    fetch(`${API_BASE}/documents/${encodeURIComponent(id)}`, {
      method: "DELETE",
      ...(process.env.NEXT_PUBLIC_GROUNDEDDOCS_API_KEY
        ? { headers: { "X-API-Key": process.env.NEXT_PUBLIC_GROUNDEDDOCS_API_KEY } }
        : {}),
    }),
  metrics: () => apiFetch<MetricsResponse>("/metrics"),
  evalSummary: () => apiFetch<EvalSummary>("/eval"),
  reindex: () => apiFetch<ReindexResponse>("/reindex", { method: "POST" }),
  ingest: async (files: File[]): Promise<IngestResponse> => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    const headers: Record<string, string> = {};
    const key = process.env.NEXT_PUBLIC_GROUNDEDDOCS_API_KEY;
    if (key) headers["X-API-Key"] = key;
    const res = await fetch(`${API_BASE}/ingest`, { method: "POST", body: form, headers });
    if (!res.ok) throw new Error(`Upload failed (${res.status})`);
    return (await res.json()) as IngestResponse;
  },
};
