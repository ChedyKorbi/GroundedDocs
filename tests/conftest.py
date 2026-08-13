"""Shared fixtures: deterministic fake embedder + in-memory store."""

from __future__ import annotations

import hashlib
import re

import pytest

from app.store.inmemory import InMemoryVectorStore

_TOKEN_RE = re.compile(r"[a-z]+")
_DIM = 128


def _hash_index(token: str) -> int:
    return int(hashlib.md5(token.encode()).hexdigest(), 16) % _DIM


class FakeEmbedder:
    """Deterministic fixed-dimension hashed bag-of-words embedder.

    Sentences sharing vocabulary land near each other in cosine space, which is
    enough to exercise semantic chunking and dedup logic deterministically and
    offline (no model download).
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * _DIM
            for token in _TOKEN_RE.findall(text.lower()):
                vector[_hash_index(token)] += 1.0
            vectors.append(vector)
        return vectors


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def store() -> InMemoryVectorStore:
    return InMemoryVectorStore()
