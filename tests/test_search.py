import json

from src.budget import Budget
from src.cache import DiskCache
from src.config import Settings
from src.tools.search import DuckDuckGoSearch, parse_hits


def test_parse_hits_keeps_rows_with_urls():
    hits = parse_hits(
        [
            {"title": "A", "href": "https://a.example/page", "body": "snip"},
            {"title": "missing"},
            "not-a-dict",
            {"title": "B", "url": "https://b.example", "snippet": "other"},
        ]
    )
    assert [hit.url for hit in hits] == ["https://a.example/page", "https://b.example"]
    assert hits[0].snippet == "snip"
    assert hits[1].snippet == "other"


def test_search_failure_returns_empty_and_is_not_cached(tmp_path):
    search = DuckDuckGoSearch(cache=DiskCache(tmp_path), budget=Budget(Settings(max_searches=5)))
    state = {"fail": True, "calls": 0}

    def raw(query: str, max_results: int):
        state["calls"] += 1
        if state["fail"]:
            raise RuntimeError("search down")
        return [{"title": "A", "href": "https://a.example", "body": "ok"}]

    search._raw = raw  # type: ignore[method-assign]
    assert search.search("batteries") == []
    state["fail"] = False
    hits = search.search("batteries")
    assert state["calls"] == 2
    assert hits[0].url == "https://a.example"
    assert search.budget is not None
    assert search.budget.search_calls == 2


def test_search_cache_does_not_charge_twice(tmp_path):
    budget = Budget(Settings(max_searches=1))
    search = DuckDuckGoSearch(cache=DiskCache(tmp_path), budget=budget)
    calls = {"n": 0}

    def raw(query: str, max_results: int):
        calls["n"] += 1
        return [{"title": "A", "href": "https://a.example", "body": ""}]

    search._raw = raw  # type: ignore[method-assign]
    assert len(search.search("q", max_results=2)) == 1
    assert len(search.search("q", max_results=2)) == 1
    assert calls["n"] == 1
    assert budget.search_calls == 1


def test_empty_search_is_cached(tmp_path):
    search = DuckDuckGoSearch(cache=DiskCache(tmp_path))
    calls = {"n": 0}

    def raw(query: str, max_results: int):
        calls["n"] += 1
        return []

    search._raw = raw  # type: ignore[method-assign]
    assert search.search("nothing") == []
    assert search.search("nothing") == []
    assert calls["n"] == 1
    stored = list((tmp_path / "search").rglob("*"))
    assert any(path.is_file() for path in stored)
    assert json.loads(next(path for path in stored if path.is_file()).read_text(encoding="utf-8")) == []
