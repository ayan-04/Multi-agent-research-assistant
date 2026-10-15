"""Writer: draft and revise a report from retrieved chunks."""

from __future__ import annotations

from src.agent.steps import StepGuard
from src.config import Settings
from src.llm.client import LLMClient
from src.llm.prompts import build_report_prompt, build_revise_prompt
from src.llm.schemas import Critique, Finding, Report, ResearchPlan
from src.rag.retrieve import VectorStore, retrieve_for_report


def write_report(
    topic: str,
    plan: ResearchPlan,
    findings: list[Finding],
    *,
    llm: LLMClient,
    store: VectorStore,
    settings: Settings,
    steps: StepGuard,
) -> Report:
    steps.tick("write")
    chunks = _chunks(topic, plan, store, settings)
    return llm.complete_model(build_report_prompt(topic, plan, findings, chunks), Report)


def revise_report(
    topic: str,
    plan: ResearchPlan,
    findings: list[Finding],
    report: Report,
    critique: Critique,
    *,
    llm: LLMClient,
    store: VectorStore,
    settings: Settings,
    steps: StepGuard,
) -> Report:
    steps.tick("revise")
    chunks = _chunks(topic, plan, store, settings)
    return llm.complete_model(
        build_revise_prompt(topic, plan, findings, chunks, report, critique),
        Report,
    )


def _chunks(topic: str, plan: ResearchPlan, store: VectorStore, settings: Settings):
    questions = [item.question for item in plan.sub_questions]
    return retrieve_for_report(store, topic, questions, settings.top_k)
