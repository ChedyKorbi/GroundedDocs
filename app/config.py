"""Application configuration.

Centralizes all runtime settings behind Pydantic Settings so nothing is
hardcoded and every value is overridable via environment variables or `.env`.
"""

from functools import lru_cache

from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "GROUNDEDDOCS_"


class ModelRegistry(BaseModel):
    """Single source of truth for model identities used by the pipeline.

    Versions are resolved at load time and recorded per-query so every answer
    is traceable to the exact artifacts that produced it (see Phase 5).
    """

    embedding_model_id: str = "intfloat/multilingual-e5-large"
    embedding_dim: int = 1024
    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    reranker_cross_encoder_id: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_llm_judge_model: str = "llama-3.3-70b-versatile"


class Settings(BaseSettings):
    """Runtime settings for the GroundedDocs service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix=ENV_PREFIX,
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "GroundedDocs"
    app_version: str = "0.1.0"
    environment: str = "development"

    # Security: API key auth enforced from Phase 5 onward; when unset the
    # service runs open (local development only).
    api_key: str | None = None

    log_level: str = "INFO"

    groq_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(f"{ENV_PREFIX}GROQ_API_KEY", "GROQ_API_KEY"),
    )

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "groundeddocs_chunks"

    reranker_mode: str = "auto"  # auto | cross_encoder | llm_judge

    # Hybrid retrieval
    retrieval_dense_k: int = 20
    retrieval_sparse_k: int = 20
    retrieval_fused_k: int = 10
    fusion_rrf_k: int = 60
    fusion_dense_weight: float = 1.0
    fusion_sparse_weight: float = 1.0

    # Ingestion pipeline
    ingestion_chunk_size: int = 512
    ingestion_overlap: int = 50
    ingestion_default_strategy: str = "structure"  # fixed | structure | semantic
    dedup_threshold: float = 0.95
    dedup_mode: str = "skip"  # skip | flag
    dedup_scope: str = "all"  # all | same_document
    dedup_top_k: int = 5

    models: ModelRegistry = ModelRegistry()

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton (cached)."""
    return Settings()
