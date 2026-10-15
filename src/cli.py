"""Command line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.agent.loop import run_research
from src.config import load_settings
from src.llm.schemas import Report, ResearchPlan
from src.runtime import build_runtime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research-agent",
        description="Plan, search, and write a cited research report.",
    )
    parser.add_argument("topic", help="Research topic")
    parser.add_argument(
        "--approve-outline",
        action="store_true",
        help="Print the outline and wait for approval before searching.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to write the report markdown.",
    )
    return parser


def render_outline(plan: ResearchPlan) -> str:
    lines = [f"Outline for: {plan.topic}"]
    for index, item in enumerate(plan.sub_questions, start=1):
        lines.append(f"{index}. {item.question}")
        if item.rationale:
            lines.append(f"   {item.rationale}")
    return "\n".join(lines)


def ask_user_to_approve(plan: ResearchPlan) -> bool:
    print(render_outline(plan))
    answer = input("Approve this outline? [Y/n]: ")
    return answer.strip().lower() in {"", "y", "yes"}


def report_to_markdown(report: Report) -> str:
    lines = [f"# {report.title}", "", report.summary, ""]
    for section in report.sections:
        lines.append(f"## {section.heading}")
        lines.append("")
        lines.append(section.body)
        if section.citations:
            lines.append("")
            lines.append("Citations: " + ", ".join(section.citations))
        lines.append("")
    if report.sources:
        lines.append("## Sources")
        lines.append("")
        for source in report.sources:
            lines.append(f"- {source}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    runtime = build_runtime(settings)
    result = run_research(
        args.topic,
        settings=settings,
        llm=runtime.llm,
        search=runtime.search,
        fetch=runtime.fetch,
        store=runtime.store,
        budget=runtime.budget,
        approve_outline=args.approve_outline,
        approver=ask_user_to_approve if args.approve_outline else None,
    )
    if result.report is None:
        print(f"Stopped: {result.stopped_reason}")
        if result.plan is not None and result.stopped_reason == "outline_rejected":
            print(render_outline(result.plan))
        return 1
    markdown = report_to_markdown(result.report)
    print(markdown, end="")
    if result.critiques and not result.critiques[-1].approved:
        print("Critic still has open issues after the revision cap:")
        for issue in result.critiques[-1].issues:
            print(f"- {issue}")
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
