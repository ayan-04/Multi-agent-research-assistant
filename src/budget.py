"""Per-run counters. Checked before a paid or rate-limited call is made."""

from __future__ import annotations

from src.config import Settings
from src.errors import BudgetExceededError


class Budget:
    def __init__(self, settings: Settings) -> None:
        self.max_llm_calls = settings.max_llm_calls
        self.max_searches = settings.max_searches
        self.max_fetches = settings.max_fetches
        self.max_embed_calls = settings.max_embed_calls
        self.llm_calls = 0
        self.search_calls = 0
        self.fetch_calls = 0
        self.embed_calls = 0

    def charge(self, kind: str) -> None:
        if kind == "llm":
            self._charge("llm", self.llm_calls, self.max_llm_calls)
            self.llm_calls += 1
            return
        if kind == "search":
            self._charge("search", self.search_calls, self.max_searches)
            self.search_calls += 1
            return
        if kind == "fetch":
            self._charge("fetch", self.fetch_calls, self.max_fetches)
            self.fetch_calls += 1
            return
        if kind == "embed":
            self._charge("embed", self.embed_calls, self.max_embed_calls)
            self.embed_calls += 1
            return
        raise ValueError(f"unknown budget kind: {kind}")

    @staticmethod
    def _charge(kind: str, used: int, limit: int) -> None:
        if used >= limit:
            raise BudgetExceededError(f"{kind} budget exhausted ({limit})")
