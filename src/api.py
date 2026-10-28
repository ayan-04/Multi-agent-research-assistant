"""HTTP API over the same research loop the CLI uses."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agent.loop import run_research
from src.cli import report_to_markdown
from src.config import load_settings
from src.db import apply_schema, load_research_run, save_research_run
from src.runtime import build_runtime


class ResearchRequest(BaseModel):
    topic: str = Field(min_length=1)


class ResearchResponse(BaseModel):
    id: str
    topic: str
    stopped_reason: str
    markdown: str


def database_ok(database_url: str) -> bool:
    if not database_url.strip():
        return False
    try:
        from src.db import connect

        with connect(database_url) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    if settings.database_url:
        apply_schema(settings.database_url)
    yield


app = FastAPI(title="Research agent", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    settings = load_settings()
    if not database_ok(settings.database_url):
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ok"}


@app.post("/research", response_model=ResearchResponse)
def create_research(body: ResearchRequest) -> ResearchResponse:
    settings = load_settings()
    runtime = build_runtime(settings)
    result = run_research(
        body.topic,
        settings=settings,
        llm=runtime.llm,
        search=runtime.search,
        fetch=runtime.fetch,
        store=runtime.store,
        budget=runtime.budget,
    )
    markdown = report_to_markdown(result.report) if result.report is not None else ""
    run_id = uuid.uuid4().hex
    save_research_run(
        settings.database_url,
        run_id=run_id,
        topic=body.topic,
        stopped_reason=result.stopped_reason,
        markdown=markdown,
        result=result.model_dump(),
    )
    return ResearchResponse(
        id=run_id,
        topic=body.topic,
        stopped_reason=result.stopped_reason,
        markdown=markdown,
    )


@app.get("/research/{run_id}", response_model=ResearchResponse)
def get_research(run_id: str) -> ResearchResponse:
    settings = load_settings()
    row = load_research_run(settings.database_url, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    return ResearchResponse(
        id=row["id"],
        topic=row["topic"],
        stopped_reason=row["stopped_reason"],
        markdown=row["markdown"],
    )
