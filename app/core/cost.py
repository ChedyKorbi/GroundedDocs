"""Token cost estimation per model (USD).

Costs are recorded even when the provider tier is free so dashboards and
evaluation reports show what the system *would* cost. Prices are per 1M tokens
(input / output). Local embedding is billed at $0 (runs on our own hardware).
"""

from __future__ import annotations

# USD per 1M tokens (input, output) — Groq on-demand list prices.
PRICING: dict[str, tuple[float, float]] = {
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
}
# Unknown models default to the most expensive known rate (conservative).
_DEFAULT_PRICE = (0.59, 0.79)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimated USD cost for a completion."""
    price_in, price_out = PRICING.get(model, _DEFAULT_PRICE)
    cost = (input_tokens / 1_000_000) * price_in + (output_tokens / 1_000_000) * price_out
    return round(cost, 8)


def estimate_embedding_cost(chunks: int, dim: int = 1024) -> float:
    """Embedding is local hardware: always zero. Kept for explicit reporting."""
    return 0.0
