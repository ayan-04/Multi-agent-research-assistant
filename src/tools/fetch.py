"""Fetch a page and reduce it to truncated plain text. Dead links are results."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup
from pydantic import BaseModel

from src.budget import Budget
from src.cache import Cache

logger = logging.getLogger(__name__)

_USER_AGENT = "research-agent/0.1 (educational; local research assistant)"


class FetchResult(BaseModel):
    url: str
    ok: bool
    status_code: int | None = None
    title: str = ""
    text: str = ""
    error: str = ""


class PageFetcher:
    def fetch(self, url: str) -> FetchResult:
        raise NotImplementedError


def html_to_text(html: str) -> tuple[str, str]:
    """Return `(title, text)` with scripts removed so they cannot look like content."""
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    raw = soup.get_text(separator="\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
    text = "\n".join(line for line in lines if line)
    return title, text


def truncate_text(text: str, max_chars: int) -> str:
    """Cap page text before it enters a prompt. The marker tells the model it is partial."""
    if max_chars < 1 or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n[truncated]"


class HttpxFetcher(PageFetcher):
    def __init__(
        self,
        *,
        max_chars: int = 6000,
        timeout_seconds: float = 15.0,
        client=None,
        cache: Cache | None = None,
        budget: Budget | None = None,
    ) -> None:
        self.max_chars = max_chars
        self.timeout_seconds = timeout_seconds
        self._client = client
        self.cache = cache
        self.budget = budget

    def fetch(self, url: str) -> FetchResult:
        if self.cache is not None:
            cached = self.cache.get("fetch", url)
            if cached is not None:
                return FetchResult.model_validate_json(cached)
        if self.budget is not None:
            self.budget.charge("fetch")
        result = self._fetch_live(url)
        # Cache completed HTTP exchanges, including 404s. Timeouts stay uncached.
        if self.cache is not None and result.status_code is not None:
            self.cache.set("fetch", url, result.model_dump_json())
        return result

    def _fetch_live(self, url: str) -> FetchResult:
        import httpx

        try:
            response = self._http().get(
                url,
                timeout=self.timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            )
        except httpx.HTTPError as exc:
            logger.warning("fetch failed for %s: %s", url, exc)
            return FetchResult(url=url, ok=False, error=str(exc))

        status = response.status_code
        if status >= 400:
            return FetchResult(
                url=url,
                ok=False,
                status_code=status,
                error=f"HTTP {status}",
            )
        content_type = response.headers.get("content-type", "")
        if content_type and "html" not in content_type and "text/plain" not in content_type:
            return FetchResult(
                url=url,
                ok=False,
                status_code=status,
                error=f"unsupported content type: {content_type}",
            )
        title, text = html_to_text(response.text)
        text = truncate_text(text, self.max_chars)
        if not text.strip():
            return FetchResult(
                url=url,
                ok=False,
                status_code=status,
                title=title,
                error="empty page text",
            )
        return FetchResult(url=url, ok=True, status_code=status, title=title, text=text)

    def _http(self):
        if self._client is not None:
            return self._client
        import httpx

        self._client = httpx.Client()
        return self._client
