"""LLM-as-judge metrics for the evaluation harness.

- FaithfulnessJudge: is every claim in the answer entailed by the retrieved
  context? Score = fraction of claims supported (RAGAS-style groundedness).
- RelevanceJudge: does the answer actually address the question? Score 0-1.

Both are thin JSON-output completions through `LLMClient`, testable with a fake
client.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.llm import LLMClient

FAITHFULNESS_SYSTEM_PROMPT = (
    "You are a strict faithfulness scorer for a grounded QA system.\n"
    "You are given a QUESTION, an ANSWER, and a set of CONTEXT passages that the"
    " answer was grounded on.\n"
    "Extract claims ONLY from the ANSWER text: exactly one claim per sentence of the"
    " answer, ignoring citation markers like [1].\n"
    "Do NOT list any information from the CONTEXT or from general knowledge that is not"
    " stated in the answer.\n"
    "A claim is supported only if it is entailed by the CONTEXT passages; if the"
    " context is silent or contradicts it, it is NOT supported.\n"
    "\n"
    "Respond with JSON only:\n"
    '{"claims": [{"claim": "<text>", "supported": <bool>, "reason": "<brief>"}]}\n'
    "Include one entry per claim."
)


def build_faithfulness_prompt(question: str, answer: str, contexts: list[str]) -> str:
    blocks = [f"[{i}]\n{text}" for i, text in enumerate(contexts, start=1)]
    return f"Question: {question}\n\nAnswer: {answer}\n\nContext:\n" + "\n\n".join(blocks)


RELEVANCE_SYSTEM_PROMPT = (
    "You are an answer relevance scorer.\n"
    "Given a QUESTION and an ANSWER, rate from 0 to 10 how well the answer directly"
    " addresses the question.\n"
    "A perfect score requires the answer to resolve the question; partial or"
    " evasive answers score lower.\n"
    'Respond with JSON only: {"relevance": <int 0-10>, "reason": "<brief>"}'
)


def build_relevance_prompt(question: str, answer: str) -> str:
    return f"Question: {question}\n\nAnswer: {answer}"


class ClaimVerdict(BaseModel):
    claim: str
    supported: bool
    reason: str = ""


class FaithfulnessResult(BaseModel):
    score: float
    claims: list[ClaimVerdict] = Field(default_factory=list)


class RelevanceResult(BaseModel):
    score: float
    reason: str = ""


class FaithfulnessJudge:
    """Score whether an answer is grounded in the provided context."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def score(self, question: str, answer: str, contexts: list[str]) -> FaithfulnessResult:
        if not answer.strip():
            # An empty (insufficient) answer is trivially faithful.
            return FaithfulnessResult(score=1.0)
        try:
            verdict = self.llm.complete_json(
                FAITHFULNESS_SYSTEM_PROMPT, build_faithfulness_prompt(question, answer, contexts)
            )
            raw_claims = verdict.get("claims", [])
        except Exception:  # noqa: BLE001
            return FaithfulnessResult(score=0.0)
        claims = [
            ClaimVerdict(
                claim=str(c.get("claim", "")),
                supported=bool(c.get("supported", False)),
                reason=str(c.get("reason", "")),
            )
            for c in raw_claims
            if isinstance(c, dict)
        ]
        if not claims:
            return FaithfulnessResult(score=0.0, claims=claims)
        score = sum(1 for c in claims if c.supported) / len(claims)
        return FaithfulnessResult(score=score, claims=claims)


class RelevanceJudge:
    """Score whether an answer addresses the question."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def score(self, question: str, answer: str) -> RelevanceResult:
        if not answer.strip():
            return RelevanceResult(score=0.0, reason="empty answer")
        try:
            verdict = self.llm.complete_json(
                RELEVANCE_SYSTEM_PROMPT, build_relevance_prompt(question, answer)
            )
            score = int(verdict.get("relevance", 0)) / 10.0
            return RelevanceResult(
                score=max(0.0, min(score, 1.0)), reason=str(verdict.get("reason", ""))
            )
        except Exception:  # noqa: BLE001
            return RelevanceResult(score=0.0, reason="judge call failed")
