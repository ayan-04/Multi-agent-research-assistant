import json

import pytest
from pydantic import BaseModel

from src.errors import BudgetExceededError, OutputValidationError, TransientLLMError
from src.llm.client import GeminiBackend, is_transient_message
from src.llm.jsonio import parse_json_object
from src.llm.schemas import ResearchPlan
from tests.conftest import FlakyBackend, ScriptedBackend, make_llm, make_settings


class Tiny(BaseModel):
    answer: str


def test_parse_json_object_accepts_fences():
    data = parse_json_object('```json\n{"answer": "yes"}\n```')
    assert data == {"answer": "yes"}


def test_parse_json_object_rejects_prose():
    with pytest.raises(ValueError):
        parse_json_object("no object here")


def test_structured_output_and_cache(tmp_path):
    from src.cache import DiskCache

    settings = make_settings()
    backend = ScriptedBackend([json.dumps({"answer": "yes"})])
    client = make_llm(settings, backend)
    client.cache = DiskCache(tmp_path)
    first = client.complete_model("question", Tiny)
    second = client.complete_model("question", Tiny)
    assert first.answer == "yes"
    assert second.answer == "yes"
    assert backend.calls == 1


def test_validation_repair_retries_once():
    settings = make_settings(validation_repairs=1)
    backend = ScriptedBackend(["not json", json.dumps({"answer": "fixed"})])
    client = make_llm(settings, backend)
    result = client.complete_model("question", Tiny)
    assert result.answer == "fixed"
    assert backend.calls == 2
    assert "failed validation" in backend.prompts[1]


def test_validation_failure_after_repair_raises():
    settings = make_settings(validation_repairs=1)
    backend = ScriptedBackend(["nope", "still nope"])
    client = make_llm(settings, backend)
    with pytest.raises(OutputValidationError):
        client.complete_model("question", Tiny)
    assert backend.calls == 2


def test_backoff_then_success():
    settings = make_settings(max_retries=3, retry_base_seconds=0.5)
    delays: list[float] = []
    backend = FlakyBackend(failures=2, success="ok")
    client = make_llm(settings, backend, sleeper=delays.append)
    assert client.complete_text("hello") == "ok"
    assert delays == [0.5, 1.0]
    assert backend.calls == 3


def test_budget_counts_retries():
    settings = make_settings(max_llm_calls=2, max_retries=3)
    from src.budget import Budget

    budget = Budget(settings)
    backend = FlakyBackend(failures=5, success="ok")
    client = make_llm(settings, backend, budget=budget)
    with pytest.raises(BudgetExceededError):
        client.complete_text("hello")
    assert backend.calls == 2
    assert budget.llm_calls == 2


def test_text_cache_skips_backend(tmp_path):
    from src.cache import DiskCache

    settings = make_settings()
    backend = ScriptedBackend(["hello"])
    client = make_llm(settings, backend)
    client.cache = DiskCache(tmp_path)
    assert client.complete_text("same") == "hello"
    assert client.complete_text("same") == "hello"
    assert backend.calls == 1


def test_transient_marker_detection():
    assert is_transient_message("RESOURCE_EXHAUSTED")
    assert not is_transient_message("invalid api key")


def test_gemini_backend_refuses_without_a_key():
    backend = GeminiBackend(make_settings(gemini_api_key=""))
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        backend.generate("do not call the network")


def test_research_plan_schema_limits_questions():
    with pytest.raises(ValueError):
        ResearchPlan.model_validate(
            {
                "topic": "t",
                "sub_questions": [{"question": f"Question number {i}?"} for i in range(5)],
            }
        )
