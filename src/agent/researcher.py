"""Researcher: search, fetch, store, then extract quotes that are actually on the page."""

from __future__ import annotations

import logging

from src.agent.steps import StepGuard
from src.config import Settings
from src.llm.client import LLMClient
from src.llm.prompts import build_findings_prompt
from src.llm.schemas import Finding, FindingBatch, ResearchPlan
from src.rag.chunking import chunk_text
from src.rag.retrieve import VectorStore
from src.textutil import quote_in_text
from src.tools.fetch import FetchResult, PageFetcher
from src.tools.search import SearchProvider

logger = logging.getLogger(__name__)


def research(
    plan: ResearchPlan,
    *,
    llm: LLMClient,
    search: SearchProvider,
    fetch: PageFetcher,
    store: VectorStore,
    settings: Settings,
    steps: StepGuard,
    found: list[Finding] | None = None,
) -> list[Finding]:
    # `found` is the caller's list so a later step-limit still keeps earlier quotes.
    findings = found if found is not None else []
    questions = plan.sub_questions[: settings.max_subquestions]
    for sub_question in questions:
        steps.tick("search")
        hits = search.search(sub_question.question, max_results=settings.search_results_per_query)
        if not hits:
            logger.info("no search hits for %r", sub_question.question)
            continue
        pages: list[FetchResult] = []
        for hit in hits:
            steps.tick("fetch")
            page = fetch.fetch(hit.url)
            if not page.ok or not page.text.strip():
                logger.info("skipping %s: %s", hit.url, page.error or "empty")
                continue
            title = page.title or hit.title
            chunks = chunk_text(page.text, settings.chunk_size, settings.chunk_overlap)
            store.add(page.url, title, chunks)
            pages.append(page.model_copy(update={"title": title}))
        if not pages:
            continue
        steps.tick("extract")
        batch = llm.complete_model(
            build_findings_prompt(sub_question.question, pages),
            FindingBatch,
        )
        findings.extend(_supported(batch.items, pages, sub_question.question))
    return findings


def _supported(items: list[Finding], pages: list[FetchResult], sub_question: str) -> list[Finding]:
    by_url = {page.url: page for page in pages}
    kept: list[Finding] = []
    for item in items:
        page = by_url.get(item.source_url)
        if page is None:
            logger.info("dropping finding with unknown url %s", item.source_url)
            continue
        if not quote_in_text(item.quote, page.text):
            logger.info("dropping finding whose quote is not on the page %s", item.source_url)
            continue
        kept.append(
            item.model_copy(
                update={
                    "sub_question": sub_question,
                    "title": item.title or page.title,
                }
            )
        )
    return kept
