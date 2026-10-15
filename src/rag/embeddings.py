"""Embeddings. Tests and keyless runs use a local hashing embedder."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from src.budget import Budget
from src.config import Settings
from src.errors import TransientLLMError
from src.llm.client import is_transient_message


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


_TOKEN = re.compile(r"[a-z0-9]+")


class HashingEmbedder:
    """Bag-of-words hashed into a fixed vector. Shared words rank nearer."""

    def __init__(self, dim: int = 64) -> None:
        if dim < 4:
            raise ValueError("embedding dimension must be at least 4")
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_embed_one(text, self.dim) for text in texts]


def _embed_one(text: str, dim: int) -> list[float]:
    vector = [0.0] * dim
    tokens = _TOKEN.findall(text.casefold())
    if not tokens:
        vector[0] = 1.0
        return vector
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        vector[0] = 1.0
        return vector
    return [value / norm for value in vector]


class GeminiEmbedder:
    """Gemini embeddings. `embed` is the only method that calls the API."""

    def __init__(self, settings: Settings, budget: Budget | None = None, sleeper=None) -> None:
        self.settings = settings
        self.budget = budget
        self._sleep = sleeper if sleeper is not None else _sleep

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        delay = self.settings.retry_base_seconds
        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries):
            if self.budget is not None:
                self.budget.charge("embed")
            try:
                return self._embed_once(texts)
            except TransientLLMError as exc:
                last_error = exc
                if attempt >= self.settings.max_retries - 1:
                    break
                self._sleep(delay)
                delay *= 2
        assert last_error is not None
        raise last_error

    def _embed_once(self, texts: list[str]) -> list[list[float]]:
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("google-genai is not installed") from exc
        client = genai.Client(api_key=self.settings.gemini_api_key)
        try:
            result = client.models.embed_content(
                model=self.settings.gemini_embed_model,
                contents=texts,
            )
        except Exception as exc:
            if is_transient_message(str(exc)):
                raise TransientLLMError(str(exc)) from exc
            raise
        vectors: list[list[float]] = []
        for item in result.embeddings:
            vectors.append([float(value) for value in item.values])
        if len(vectors) != len(texts):
            raise RuntimeError("embedding response length did not match inputs")
        return vectors


def build_embedder(settings: Settings, budget: Budget | None = None) -> Embedder:
    """Use Gemini when a key is present. Otherwise stay local so tests make no calls."""
    if settings.gemini_api_key:
        return GeminiEmbedder(settings, budget=budget)
    return HashingEmbedder()


def _sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)
