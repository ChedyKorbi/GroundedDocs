"""LLM client wrapper (Groq).

Thin wrapper over the Groq SDK exposing completion with token accounting,
optional JSON mode, and a single retry on transient failures. Model-agnostic by
design — the provider is selected in config.
"""

from __future__ import annotations

import json
import time
from typing import Any

from pydantic import BaseModel

from app.logging import get_logger

logger = get_logger("app.services.llm")


class LLMResponse(BaseModel):
    text: str
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMClient:
    """Groq-backed chat completion client."""

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        max_retries: int = 1,
    ) -> None:
        from groq import Groq

        if not api_key:
            raise ValueError("Groq API key required")
        self.client = Groq(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries

    def complete(
        self,
        system: str,
        user: str,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Run a chat completion; returns text + token usage."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                message = response.choices[0].message
                usage = response.usage
                return LLMResponse(
                    text=message.content or "",
                    input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(2.0 * (attempt + 1))
        logger.error("llm_completion_failed", extra={"model": self.model, "error": str(last_error)})
        raise RuntimeError(f"LLM completion failed: {last_error}") from last_error

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        """Run a completion in JSON mode and parse the response object."""
        response = self.complete(system, user, json_mode=True)
        try:
            parsed = json.loads(response.text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as exc:
            logger.warning(
                "llm_json_parse_failed",
                extra={"model": self.model, "raw": response.text[:200]},
            )
            raise ValueError("LLM returned malformed JSON") from exc
        raise ValueError("LLM returned non-object JSON")
