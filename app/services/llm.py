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
        api_key: str | None = None,
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 1024,
        max_retries: int = 4,
        api_keys: list[str] | None = None,
        key_cooldown_seconds: float = 300.0,
    ) -> None:
        from groq import Groq

        self._keys = api_keys or ([api_key] if api_key else [])
        if not self._keys:
            raise ValueError("Groq API key required")
        self._round_robin = 0
        self._client_type = Groq
        self._cooldown: dict[int, float] = {}
        self._last_key_index = 0
        self.key_cooldown_seconds = key_cooldown_seconds
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries

    def _client(self) -> Any:
        """Next Groq client, rotating across keys and skipping exhausted ones.

        A key that recently hit a rate limit is cooled down; if all keys are in
        cooldown the one expiring soonest is still attempted.
        """
        now = time.time()
        indices = list(range(len(self._keys)))
        healthy = [i for i in indices if self._cooldown.get(i, 0.0) <= now]
        pool = healthy or sorted(indices, key=lambda i: self._cooldown.get(i, 0.0))
        idx = pool[self._round_robin % len(pool)]
        self._round_robin += 1
        self._last_key_index = idx
        return self._client_type(api_key=self._keys[idx])

    def _note_rate_limit(self, exc: Exception) -> None:
        """Cool down the key that hit a rate limit."""
        if getattr(exc, "status_code", None) == 429:
            self._cooldown[self._last_key_index] = time.time() + self.key_cooldown_seconds

    def complete(
        self,
        system: str,
        user: str,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Run a chat completion; returns text + token usage.

        Retries on transient failures. 429 rate limits honor the server's
        Retry-After header when present, otherwise back off exponentially
        (capped at 60s per attempt) so long eval runs ride out per-minute
        quotas instead of crashing.
        """
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
                response = self._client().chat.completions.create(**kwargs)
                message = response.choices[0].message
                usage = response.usage
                return LLMResponse(
                    text=message.content or "",
                    input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self._note_rate_limit(exc)
                if attempt >= self.max_retries:
                    break
                delay = self._backoff_seconds(exc, attempt)
                logger.warning(
                    "llm_retry",
                    extra={"model": self.model, "attempt": attempt + 1, "delay_s": delay},
                )
                time.sleep(delay)
        logger.error("llm_completion_failed", extra={"model": self.model, "error": str(last_error)})
        raise RuntimeError(f"LLM completion failed: {last_error}") from last_error

    @staticmethod
    def _backoff_seconds(exc: Exception, attempt: int) -> float:
        retry_after = getattr(exc, "response", None)
        if retry_after is not None:
            header = retry_after.headers.get("Retry-After")
            if header and header.isdigit():
                retry_after_seconds = float(header)
                return min(retry_after_seconds, 60.0)
        delay = 4.0 * float(2**attempt)
        return delay if delay <= 60.0 else 60.0

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
