"""Structured outputs. Every agent talks to the model through these models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SubQuestion(BaseModel):
    question: str = Field(min_length=3)
    rationale: str = ""


class ResearchPlan(BaseModel):
    topic: str = Field(min_length=1)
    sub_questions: list[SubQuestion] = Field(min_length=1, max_length=4)


class Finding(BaseModel):
    sub_question: str = ""
    claim: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    title: str = ""


class FindingBatch(BaseModel):
    items: list[Finding] = Field(default_factory=list)


class ReportSection(BaseModel):
    heading: str = Field(min_length=1)
    body: str = Field(min_length=1)
    citations: list[str] = Field(default_factory=list)


class Report(BaseModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    sections: list[ReportSection] = Field(min_length=1)
    sources: list[str] = Field(default_factory=list)


class Critique(BaseModel):
    approved: bool
    issues: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)


class ResearchRun(BaseModel):
    topic: str
    plan: ResearchPlan | None = None
    findings: list[Finding] = Field(default_factory=list)
    report: Report | None = None
    critiques: list[Critique] = Field(default_factory=list)
    stopped_reason: str = "completed"
    steps: int = 0
    llm_calls: int = 0
    search_calls: int = 0
    fetch_calls: int = 0
