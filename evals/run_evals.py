"""Run the research loop and record deterministic citation checks.

This module is intentionally not executed during unit tests. It calls the live
stack only from `main`.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from evals.checks import quote_in_source, url_resolves
from src.llm.schemas import Finding
from src.tools.fetch import PageFetcher


class EvalTopic(BaseModel):
    id: str
    topic: str
    notes: str = ""


class FindingCheck(BaseModel):
    topic_id: str
    url: str = ""
    url_resolves: bool = False
    quote_in_source: bool = False
    claim: str = ""
    note: str = ""


def load_topics(path: Path | None = None) -> list[EvalTopic]:
    topic_path = path or Path(__file__).with_name("topics.jsonl")
    topics: list[EvalTopic] = []
    for line in topic_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        topics.append(EvalTopic.model_validate_json(line))
    return topics


def check_finding(topic_id: str, finding: Finding, fetch: PageFetcher) -> FindingCheck:
    page = fetch.fetch(finding.source_url)
    resolves = url_resolves(page)
    return FindingCheck(
        topic_id=topic_id,
        url=finding.source_url,
        url_resolves=resolves,
        quote_in_source=resolves and quote_in_source(finding.quote, page.text),
        claim=finding.claim,
    )


def evaluate_topic(topic: EvalTopic, findings: list[Finding], fetch: PageFetcher) -> list[FindingCheck]:
    if not findings:
        return [
            FindingCheck(
                topic_id=topic.id,
                note="no findings",
            )
        ]
    return [check_finding(topic.id, finding, fetch) for finding in findings]


def main() -> int:
    from src.agent.loop import run_research
    from src.config import load_settings
    from src.runtime import build_runtime

    settings = load_settings()
    runtime = build_runtime(settings)
    rows: list[dict] = []
    for topic in load_topics():
        result = run_research(
            topic.topic,
            settings=settings,
            llm=runtime.llm,
            search=runtime.search,
            fetch=runtime.fetch,
            store=runtime.store,
            budget=runtime.budget,
        )
        checks = evaluate_topic(topic, result.findings, runtime.fetch)
        for item in checks:
            row = item.model_dump()
            row["stopped_reason"] = result.stopped_reason
            rows.append(row)
    out = Path("data/eval_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"results": rows}, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
