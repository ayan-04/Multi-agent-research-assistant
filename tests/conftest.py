"""Shared fakes. None of these call Gemini, DuckDuckGo, or the network."""

from __future__ import annotations

import json
import uuid

from src.budget import Budget
from src.cache import NullCache
from src.config import Settings
from src.errors import TransientLLMError
from src.llm.client import LLMClient
from src.llm.schemas import ResearchPlan, ResearchRun
from src.rag.embeddings import HashingEmbedder
from src.rag.store import MemoryStore
from src.tools.fetch import FetchResult
from src.tools.search import SearchHit


class ScriptedBackend:
    def __init__(self, outputs: list[str] | None = None) -> None:
        self.outputs = list(outputs or [])
        self.prompts: list[str] = []
        self.calls = 0

    def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        if not self.outputs:
            raise AssertionError("scripted backend ran out of replies")
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FlakyBackend:
    def __init__(self, failures: int, success: str) -> None:
        self.failures = failures
        self.success = success
        self.calls = 0

    def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise TransientLLMError("429 rate limit")
        return self.success


class FakeSearch:
    def __init__(self, hits: list[SearchHit] | None = None) -> None:
        self.hits = list(hits or [])
        self.queries: list[str] = []

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        self.queries.append(query)
        return self.hits[:max_results]


class FakeFetch:
    def __init__(self, result: FetchResult) -> None:
        self.result = result
        self.urls: list[str] = []

    def fetch(self, url: str) -> FetchResult:
        self.urls.append(url)
        return self.result.model_copy(update={"url": url})


def make_settings(**overrides) -> Settings:
    base = dict(
        gemini_api_key="",
        max_llm_calls=20,
        max_searches=10,
        max_fetches=10,
        max_embed_calls=20,
        max_steps=40,
        max_retries=3,
        retry_base_seconds=0.5,
        validation_repairs=1,
        critic_max_iterations=2,
        chunk_size=800,
        chunk_overlap=120,
        top_k=4,
        search_results_per_query=2,
        max_subquestions=3,
    )
    base.update(overrides)
    return Settings(**base).trimmed()


def make_llm(settings: Settings, backend, budget: Budget | None = None, sleeper=None) -> LLMClient:
    return LLMClient(
        settings,
        backend=backend,
        cache=NullCache(),
        budget=budget if budget is not None else Budget(settings),
        sleeper=sleeper or (lambda _seconds: None),
    )


def make_store() -> MemoryStore:
    return MemoryStore(
        embedder=HashingEmbedder(),
        collection_name=f"t_{uuid.uuid4().hex[:16]}",
    )


def plan_json(question: str = "How do solid-state batteries replace liquid electrolytes?") -> str:
    return json.dumps(
        {
            "topic": "ignored by planner",
            "sub_questions": [{"question": question, "rationale": "core mechanism"}],
        }
    )


def findings_json(url: str, quote: str) -> str:
    return json.dumps(
        {
            "items": [
                {
                    "sub_question": "",
                    "claim": "They use solid electrolytes.",
                    "source_url": url,
                    "quote": quote,
                    "title": "SSB",
                }
            ]
        }
    )


def report_json(summary: str = "They replace liquid electrolytes.") -> str:
    return json.dumps(
        {
            "title": "Solid-state batteries",
            "summary": summary,
            "sections": [
                {
                    "heading": "Mechanism",
                    "body": "Solid-state batteries replace liquid electrolytes with solid ones.",
                    "citations": ["https://example.com/ssb"],
                }
            ],
            "sources": ["https://example.com/ssb"],
        }
    )


def critique_json(approved: bool, issue: str = "") -> str:
    return json.dumps(
        {
            "approved": approved,
            "issues": [issue] if issue else [],
            "unsupported_claims": [],
        }
    )


def sample_run() -> ResearchRun:
    plan = ResearchPlan.model_validate(json.loads(plan_json()))
    return ResearchRun(
        topic=plan.topic,
        plan=plan,
        findings=[],
        report=None,
        stopped_reason="completed",
    )
