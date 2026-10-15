"""DuckDuckGo search behind a small interface. Live calls stay inside `_raw`."""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field

from src.budget import Budget
from src.cache import Cache

logger = logging.getLogger(__name__)


class SearchHit(BaseModel):
    title: str = ""
    url: str = Field(min_length=1)
    snippet: str = ""


class SearchProvider:
    """Structural stand-in so callers depend on `search`, not on DuckDuckGo."""

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        raise NotImplementedError


def parse_hits(raw: list[dict]) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        url = row.get("href") or row.get("url") or row.get("link") or ""
        url = str(url).strip()
        if not url:
            continue
        hits.append(
            SearchHit(
                title=str(row.get("title") or ""),
                url=url,
                snippet=str(row.get("body") or row.get("snippet") or ""),
            )
        )
    return hits


def _load_ddgs_class():
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS  # type: ignore
    return DDGS


class DuckDuckGoSearch(SearchProvider):
    def __init__(self, cache: Cache | None = None, budget: Budget | None = None) -> None:
        self.cache = cache
        self.budget = budget

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        material = json.dumps({"q": query, "n": max_results}, ensure_ascii=False)
        if self.cache is not None:
            cached = self.cache.get("search", material)
            if cached is not None:
                return [SearchHit.model_validate(item) for item in json.loads(cached)]
        if self.budget is not None:
            self.budget.charge("search")
        try:
            raw = self._raw(query, max_results)
            hits = parse_hits(raw)
        except Exception as exc:
            # Empty is a finished search. Callers move on; the failure is not cached.
            logger.warning("search failed for %r: %s", query, exc)
            return []
        if self.cache is not None:
            payload = json.dumps([hit.model_dump() for hit in hits])
            self.cache.set("search", material, payload)
        return hits

    def _raw(self, query: str, max_results: int) -> list[dict]:
        ddgs_cls = _load_ddgs_class()
        with ddgs_cls() as client:
            results = client.text(query, max_results=max_results)
        return list(results or [])
