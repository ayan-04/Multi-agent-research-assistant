"""Wire the real Gemini, DuckDuckGo, fetch, and PostgreSQL objects for the CLI."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from src.budget import Budget
from src.cache import DiskCache
from src.config import Settings
from src.llm.client import GeminiBackend, LLMClient
from src.rag.embeddings import build_embedder
from src.rag.store import PostgresStore
from src.tools.fetch import HttpxFetcher
from src.tools.search import DuckDuckGoSearch


@dataclass
class Runtime:
    settings: Settings
    budget: Budget
    llm: LLMClient
    search: DuckDuckGoSearch
    fetch: HttpxFetcher
    store: PostgresStore


def build_runtime(settings: Settings) -> Runtime:
    settings = settings.trimmed()
    budget = Budget(settings)
    cache = DiskCache(settings.cache_dir)
    llm = LLMClient(
        settings,
        backend=GeminiBackend(settings),
        cache=cache,
        budget=budget,
    )
    search = DuckDuckGoSearch(cache=cache, budget=budget)
    fetch = HttpxFetcher(
        max_chars=settings.fetch_max_chars,
        timeout_seconds=settings.fetch_timeout_seconds,
        cache=cache,
        budget=budget,
    )
    # A new collection per process so this run does not retrieve another topic's pages.
    store = PostgresStore(
        embedder=build_embedder(settings, budget=budget),
        database_url=settings.database_url,
        collection_name=f"run_{uuid.uuid4().hex[:12]}",
    )
    return Runtime(
        settings=settings,
        budget=budget,
        llm=llm,
        search=search,
        fetch=fetch,
        store=store,
    )
