"""API request/response schemas.

This file IS the frozen API contract (see docs/API_CONTRACT.md). Changing a
field here requires a contract-version bump and a note in that document before
any code change.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RetrievalMethod = Literal["hybrid", "dense_only", "sparse_only"]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    retrieval_method: RetrievalMethod = "hybrid"
    top_k: int = Field(default=6, ge=1, le=10)


class CitationSchema(BaseModel):
    index: int
    chunk_id: str
    supported: bool
    reason: str = ""
    text: str = ""


class SentenceSchema(BaseModel):
    sentence: str
    checks: list[CitationSchema] = Field(default_factory=list)


class LatencyBreakdown(BaseModel):
    embed_ms: float | None = None
    dense_ms: float | None = None
    sparse_ms: float | None = None
    fusion_ms: float | None = None
    rerank_ms: float | None = None
    generate_ms: float | None = None
    verify_ms: float | None = None
    total_ms: float


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    verify_input_tokens: int = 0
    verify_output_tokens: int = 0
    total_tokens: int
    cost_usd: float


class ModelVersions(BaseModel):
    llm_model: str
    embedding_model: str
    reranker: str | None = None


class AskResponse(BaseModel):
    question: str
    answer: str
    insufficient: bool
    confidence: float
    citations: list[CitationSchema] = Field(default_factory=list)
    sentences: list[SentenceSchema] = Field(default_factory=list)
    breakdown: LatencyBreakdown
    tokens: TokenUsage
    models: ModelVersions
    request_id: str | None = None


class IngestResult(BaseModel):
    file: str
    document_id: str
    format: str
    segments: int
    chunks_total: int
    inserted: int
    skipped: int
    flagged: int
    strategy_counts: dict[str, int] = Field(default_factory=dict)
    duration_ms: float


class IngestResponse(BaseModel):
    documents: list[IngestResult]
    total_inserted: int
    index_chunks: int


class DocumentInfo(BaseModel):
    document_id: str
    format: str
    chunk_count: int


class DocumentsResponse(BaseModel):
    documents: list[DocumentInfo]
    total_chunks: int


class ReindexResponse(BaseModel):
    previous_collection: str | None
    current_collection: str
    chunks_reindexed: int
    duration_ms: float


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    qdrant: bool
    model_ready: bool = False
    index_chunks: int | None = None


class MetricsResponse(BaseModel):
    request_count: int
    success_count: int
    error_count: int
    error_rate: float
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    total_citations: int
    total_supported_citations: int
    citation_accuracy: float | None
    latency: dict[str, Any]
    stage_latency: dict[str, Any]
    model_versions: dict[str, Any]
    recent_queries: list[dict[str, Any]] = Field(default_factory=list)


class EvalSummaryResponse(BaseModel):
    generated_at: str | None = None
    method: str | None = None
    questions: int | None = None
    faithfulness: float | None = None
    relevance: float | None = None
    citation_accuracy: float | None = None
    recall_1: float | None = None
    recall_3: float | None = None
    correct_refusal_rate: float | None = None
    failures: int | None = None
    calibration_faithful_agreement: float | None = None
    report_path: str | None = None
