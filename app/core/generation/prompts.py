"""Grounded generation and judge prompts."""

from __future__ import annotations

INSUFFICIENT_SENTINEL = "INSUFFICIENT_INFORMATION"

GROUNDED_SYSTEM_PROMPT = (
    "You are GroundedDocs, a precise assistant for enterprise internal documentation.\n"
    "Answer the user's question using ONLY the numbered context passages provided below.\n"
    "\n"
    "Rules:\n"
    "1. Base every statement on one or more context passages, and cite them immediately"
    " with [n], where n is the passage number.\n"
    "2. Use the exact numbers and wording from the context; do not add outside knowledge"
    " or assumptions.\n"
    f"3. If the context passages do not contain enough information to answer, respond"
    f" with exactly {INSUFFICIENT_SENTINEL} and nothing else.\n"
    "4. If you cannot fully answer, answer what the context supports and explicitly say"
    " what is not covered.\n"
    "5. Answer in the same language as the question, concisely."
)


def build_grounded_user_prompt(query: str, contexts: list[tuple[str, str]]) -> str:
    """Build the user prompt with numbered context blocks.

    Args:
        query: the user question.
        contexts: (chunk_id, chunk_text) pairs, best-ranked first.
    """
    blocks = []
    for index, (_chunk_id, text) in enumerate(contexts, start=1):
        blocks.append(f"[{index}]\n{text}")
    return f"Question: {query}\n\nContext:\n" + "\n\n".join(blocks)


VERIFY_SYSTEM_PROMPT = (
    "You are a strict citation verifier for a grounded QA system.\n"
    "You are given ONE claim sentence from an answer and a set of numbered passages that"
    " the answer cites.\n"
    "For each cited passage, decide whether the claim is FULLY SUPPORTED by that passage"
    " alone.\n"
    "A passage supports the claim only if the claim's facts appear in it or follow"
    " directly from it.\n"
    "If the passage is silent on the claim or contradicts it, it does NOT support it.\n"
    "\n"
    "Respond with JSON only, in this exact shape:\n"
    '{{"checks": [{{"index": <int>, "supported": <bool>, "reason": "<brief why>"}}]}}\n'
    "Include one check per cited passage index."
)


def build_verify_prompt(claim: str, passages: dict[int, str]) -> str:
    """Build the judge user prompt for a claim and its cited passages."""
    blocks = []
    for index in sorted(passages):
        blocks.append(f"[{index}]\n{passages[index]}")
    return f"Claim: {claim}\n\nCited passages:\n" + "\n\n".join(blocks)
