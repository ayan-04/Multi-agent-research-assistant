"""Evaluation helpers that do not call the network by themselves."""

from __future__ import annotations

from src.textutil import quote_in_text
from src.tools.fetch import FetchResult


def quote_in_source(quote: str, page_text: str) -> bool:
    return quote_in_text(quote, page_text)


def url_resolves(page: FetchResult) -> bool:
    return bool(page.ok and page.status_code is not None and 200 <= page.status_code < 400)
