"""Hand-written research loop with a step cap and a two-pass critic revision cap."""

from __future__ import annotations

from collections.abc import Callable

from src.agent.critic import critique_report
from src.agent.planner import create_plan
from src.agent.researcher import research
from src.agent.steps import StepGuard
from src.agent.writer import revise_report, write_report
from src.budget import Budget
from src.config import Settings
from src.errors import BudgetExceededError, StepLimitError
from src.llm.client import LLMClient
from src.llm.schemas import ResearchPlan, ResearchRun
from src.rag.retrieve import VectorStore
from src.tools.fetch import PageFetcher
from src.tools.search import SearchProvider


def run_research(
    topic: str,
    *,
    settings: Settings,
    llm: LLMClient,
    search: SearchProvider,
    fetch: PageFetcher,
    store: VectorStore,
    budget: Budget | None = None,
    approve_outline: bool = False,
    approver: Callable[[ResearchPlan], bool] | None = None,
) -> ResearchRun:
    """Run plan -> research -> write -> critic. Outline approval is off unless asked."""
    settings = settings.trimmed()
    steps = StepGuard(settings.max_steps)
    active_budget = budget if budget is not None else llm.budget
    plan = None
    findings = []
    report = None
    critiques = []
    stopped_reason = "completed"
    try:
        steps.tick("plan")
        plan = create_plan(topic, llm)
        plan = plan.model_copy(
            update={"sub_questions": plan.sub_questions[: settings.max_subquestions]}
        )
        if approve_outline:
            allow = approver(plan) if approver is not None else True
            if not allow:
                stopped_reason = "outline_rejected"
                return _result(
                    topic, plan, findings, report, critiques, stopped_reason, steps, active_budget
                )
        research(
            plan,
            llm=llm,
            search=search,
            fetch=fetch,
            store=store,
            settings=settings,
            steps=steps,
            found=findings,
        )
        report = write_report(
            topic,
            plan,
            findings,
            llm=llm,
            store=store,
            settings=settings,
            steps=steps,
        )
        # critic_max_iterations is capped at 2 in Settings.trimmed.
        for index in range(settings.critic_max_iterations):
            critique = critique_report(
                topic,
                plan,
                findings,
                report,
                llm=llm,
                store=store,
                settings=settings,
                steps=steps,
            )
            critiques.append(critique)
            if critique.approved:
                break
            if index >= settings.critic_max_iterations - 1:
                break
            report = revise_report(
                topic,
                plan,
                findings,
                report,
                critique,
                llm=llm,
                store=store,
                settings=settings,
                steps=steps,
            )
    except StepLimitError:
        stopped_reason = "step_limit"
    except BudgetExceededError:
        stopped_reason = "budget"
    return _result(topic, plan, findings, report, critiques, stopped_reason, steps, active_budget)


def _result(topic, plan, findings, report, critiques, stopped_reason, steps, budget) -> ResearchRun:
    return ResearchRun(
        topic=topic,
        plan=plan,
        findings=findings,
        report=report,
        critiques=critiques,
        stopped_reason=stopped_reason,
        steps=steps.steps,
        llm_calls=budget.llm_calls if budget is not None else 0,
        search_calls=budget.search_calls if budget is not None else 0,
        fetch_calls=budget.fetch_calls if budget is not None else 0,
    )
