"""Evaluation core: judges, retrieval metrics, and result models."""

from app.core.evaluation.judges import (
    ClaimVerdict,
    FaithfulnessJudge,
    FaithfulnessResult,
    RelevanceJudge,
    RelevanceResult,
)
from app.core.evaluation.recall import mrr, precision_at_k, recall_at_k
from app.core.evaluation.retrieval_eval import (
    average_metrics,
    load_golden,
    resolve_gold_chunks,
    run_retrieval_metrics,
)

__all__ = [
    "ClaimVerdict",
    "FaithfulnessJudge",
    "FaithfulnessResult",
    "RelevanceJudge",
    "RelevanceResult",
    "mrr",
    "precision_at_k",
    "recall_at_k",
    "average_metrics",
    "load_golden",
    "resolve_gold_chunks",
    "run_retrieval_metrics",
]
