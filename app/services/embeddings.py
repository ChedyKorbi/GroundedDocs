"""Embedding service wrapping sentence-transformers.

Lazy-loads the model on first use and resolves the runtime device at startup so
the chosen device (and model version) can be recorded in the model registry.
e5-style models use `query:` / `passage:` prefixes, applied per caller.
"""

from __future__ import annotations

import hashlib

import numpy as np
from sentence_transformers import SentenceTransformer

from app.logging import get_logger

logger = get_logger("app.services.embeddings")


class EmbeddingService:
    """Multilingual embedding provider with document/query prefixes."""

    def __init__(
        self,
        model_id: str,
        device: str | None = None,
        normalize: bool = True,
    ) -> None:
        import torch

        self.model_id = model_id
        self._model: SentenceTransformer | None = None
        self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.normalize = normalize

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_id, device=self._device)
            logger.info(
                "embedding_model_loaded",
                extra={"model_id": self.model_id, "device": self._device},
            )
        return self._model

    @property
    def device(self) -> str:
        return self._device

    @property
    def model_version(self) -> str:
        """Stable fingerprint of the configured model for version logging.

        Resolved to the actual revision downloaded from the hub in Phase 5
        (model registry); a content-derived digest of the model id is a
        deterministic stand-in until then.
        """
        return hashlib.sha1(self.model_id.encode()).hexdigest()[:8]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, prefix="passage")

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, prefix="query")

    def _embed(self, texts: list[str], prefix: str) -> list[list[float]]:
        if not texts:
            return []
        prefixed = [f"{prefix}: {text}" for text in texts]
        vectors = self.model.encode(
            prefixed,
            batch_size=32,
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
        )
        return [v.tolist() for v in np.asarray(vectors)]
