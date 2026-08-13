"""Reranking stage.

- CrossEncoderReranker: transformer cross-encoder scoring (query, passage) pairs.
- LlmJudgeReranker: Groq-based judge assigning a relevance score per candidate.
- AutoReranker: probes the GPU + model availability at startup (RERANKER_MODE=auto)
  and selects cross-encoder when viable, otherwise LLM-as-judge. The decision is
  logged and recorded once per process so every query's reranker identity is
  traceable.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.config import get_settings
from app.logging import get_logger
from app.store.base import SearchHit

logger = get_logger("app.core.retrieval.rerank")


class Reranker(ABC):
    """Re-score a candidate list for a query; returns scores aligned to input."""

    @abstractmethod
    def rerank(self, query: str, candidates: list[SearchHit]) -> list[float]:
        """Return a relevance score per candidate, higher is better."""


class CrossEncoderReranker(Reranker):
    """Cross-encoder scoring via sentence-transformers."""

    def __init__(self, model_id: str, device: str | None = None) -> None:
        from sentence_transformers import CrossEncoder

        self.model_id = model_id
        self._model = CrossEncoder(model_id, device=device or "cpu")
        logger.info("cross_encoder_loaded", extra={"model_id": model_id, "device": device or "cpu"})

    def rerank(self, query: str, candidates: list[SearchHit]) -> list[float]:
        if not candidates:
            return []
        pairs = [(query, hit.payload.get("text", "")) for hit in candidates]
        scores = self._model.predict(pairs, show_progress_bar=False)
        return [float(s) for s in scores]


_SCORE_EXTRACT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)")


class LlmJudgeReranker(Reranker):
    """Groq LLM-as-judge: score each candidate 0-10 for relevance to the query."""

    def __init__(self, model: str = "llama-3.3-70b-versatile", api_key: str | None = None) -> None:
        from groq import Groq

        if not api_key:
            raise ValueError("Groq API key required for LLM-as-judge reranker")
        self.model = model
        self.client = Groq(api_key=api_key)

    def rerank(self, query: str, candidates: list[SearchHit]) -> list[float]:
        scores: list[float] = []
        for hit in candidates:
            text = hit.payload.get("text", "")[:1500]
            prompt = (
                "Rate on a scale of 0 to 10 how relevant this passage is to the "
                f"question. Reply with only a number.\nQuestion: {query}\nPassage: {text}"
            )
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=5,
            )
            content = response.choices[0].message.content or ""
            match = _SCORE_EXTRACT_RE.search(content)
            scores.append(min(float(match.group(1)) / 10.0, 1.0) if match else 0.0)
        return scores


def build_reranker() -> tuple[Reranker, str]:
    """Resolve the reranker per RERANKER_MODE; returns (reranker, chosen_mode)."""
    settings = get_settings()
    mode = settings.reranker_mode
    if mode == "auto":
        import torch

        cuda = torch.cuda.is_available()
        model_id = settings.models.reranker_cross_encoder_id
        if cuda:
            logger.info(
                "reranker_auto_gpu_probe",
                extra={"mode": "cross_encoder", "device": "cuda", "model_id": model_id},
            )
            return CrossEncoderReranker(model_id, device="cuda"), "cross_encoder"
        logger.info(
            "reranker_auto_gpu_probe",
            extra={"mode": "llm_judge", "device": "cpu", "reason": "no cuda"},
        )
        if not settings.groq_api_key:
            raise RuntimeError(
                "RERANKER_MODE=auto on CPU requires GROQ_API_KEY for the LLM-as-judge "
                "reranker (or set RERANKER_MODE=cross_encoder)."
            )
        return LlmJudgeReranker(
            model=settings.models.reranker_llm_judge_model, api_key=settings.groq_api_key
        ), "llm_judge"
    if mode == "cross_encoder":
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        return CrossEncoderReranker(settings.models.reranker_cross_encoder_id, device=device), mode
    if mode == "llm_judge":
        if not settings.groq_api_key:
            raise RuntimeError("RERANKER_MODE=llm_judge requires GROQ_API_KEY")
        return (
            LlmJudgeReranker(
                model=settings.models.reranker_llm_judge_model, api_key=settings.groq_api_key
            ),
            mode,
        )
    raise ValueError(f"unknown reranker mode: {mode}")
