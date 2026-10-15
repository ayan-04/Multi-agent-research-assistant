"""Critic: check the report against stored sources."""

from __future__ import annotations

from src.agent.steps import StepGuard
from src.config import Settings
from src.llm.client import LLMClient
from src.llm.prompts import build_critique_prompt
from src.llm.schemas import Critique, Finding, Report, ResearchPlan
from src.rag.retrieve import VectorStore, retrieve_for_report


def critique_report(
    topic: str,
    plan: ResearchPlan,
    findings: list[Finding],
    report: Report,
    *,
    llm: LLMClient,
    store: VectorStore,
    settings: Settings,
    steps: StepGuard,
) -> Critique:
    steps.tick("critique")
    questions = [item.question for item in plan.sub_questions]
    chunks = retrieve_for_report(store, topic, questions, settings.top_k)
    return llm.complete_model(
        build_critique_prompt(topic, report, findings, chunks),
        Critique,
    )
