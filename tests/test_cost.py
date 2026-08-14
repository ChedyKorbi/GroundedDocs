"""Cost estimation tests."""

from app.core.cost import PRICING, estimate_cost


def test_known_model_pricing() -> None:
    cost = estimate_cost("llama-3.3-70b-versatile", 1_000_000, 1_000_000)
    assert cost == round(0.59 + 0.79, 8)


def test_zero_tokens_zero_cost() -> None:
    assert estimate_cost("llama-3.3-70b-versatile", 0, 0) == 0.0


def test_unknown_model_uses_conservative_rate() -> None:
    cost = estimate_cost("unknown-model", 1_000_000, 0)
    assert cost == PRICING["llama-3.3-70b-versatile"][0]


def test_small_batch() -> None:
    cost = estimate_cost("llama-3.3-70b-versatile", 1000, 100)
    assert 0 < cost < 0.001


def test_judge_model_cheaper() -> None:
    large = estimate_cost("llama-3.3-70b-versatile", 100_000, 0)
    small = estimate_cost("llama-3.1-8b-instant", 100_000, 0)
    assert small < large
