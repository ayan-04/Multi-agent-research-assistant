"""Planner: one structured call that returns sub-questions."""

from __future__ import annotations

from src.llm.client import LLMClient
from src.llm.prompts import build_plan_prompt
from src.llm.schemas import ResearchPlan


def create_plan(topic: str, llm: LLMClient) -> ResearchPlan:
    plan = llm.complete_model(build_plan_prompt(topic), ResearchPlan)
    # The user topic wins if the model rewrites it.
    return plan.model_copy(update={"topic": topic})
