import json
from pathlib import Path

from src.cli import ask_user_to_approve, main, report_to_markdown, render_outline
from src.llm.schemas import Report, ResearchPlan, ResearchRun
from tests.conftest import plan_json, report_json


def test_report_markdown_includes_citations():
    report = Report.model_validate(json.loads(report_json()))
    markdown = report_to_markdown(report)
    assert markdown.startswith("# Solid-state batteries")
    assert "https://example.com/ssb" in markdown
    assert "## Mechanism" in markdown


def test_cli_prints_a_report(monkeypatch, capsys):
    report = Report.model_validate(json.loads(report_json()))
    plan = ResearchPlan.model_validate(json.loads(plan_json()))

    def fake_runtime(_settings):
        class Runtime:
            llm = object()
            search = object()
            fetch = object()
            store = object()
            budget = object()

        return Runtime()

    def fake_run(topic, **kwargs):
        assert topic == "solid-state batteries"
        assert kwargs["approve_outline"] is False
        assert kwargs["approver"] is None
        return ResearchRun(topic=topic, plan=plan, report=report, stopped_reason="completed")

    monkeypatch.setattr("src.cli.build_runtime", fake_runtime)
    monkeypatch.setattr("src.cli.run_research", fake_run)
    code = main(["solid-state batteries"])
    captured = capsys.readouterr()
    assert code == 0
    assert "Solid-state batteries" in captured.out


def test_cli_approve_flag_uses_the_prompter(monkeypatch):
    seen = {}

    def fake_runtime(_settings):
        class Runtime:
            llm = search = fetch = store = budget = object()

        return Runtime()

    def fake_run(topic, **kwargs):
        seen["approve"] = kwargs["approve_outline"]
        seen["approver"] = kwargs["approver"]
        return ResearchRun(topic=topic, stopped_reason="outline_rejected")

    monkeypatch.setattr("src.cli.build_runtime", fake_runtime)
    monkeypatch.setattr("src.cli.run_research", fake_run)
    code = main(["topic", "--approve-outline"])
    assert code == 1
    assert seen["approve"] is True
    assert seen["approver"].__name__ == "ask_user_to_approve"


def test_ask_user_to_approve(monkeypatch, capsys):
    plan = ResearchPlan.model_validate(json.loads(plan_json())).model_copy(update={"topic": "batteries"})
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    assert ask_user_to_approve(plan) is False
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")
    assert ask_user_to_approve(plan) is True
    assert "batteries" in capsys.readouterr().out
    assert "Outline" in render_outline(plan)


def test_cli_writes_out_file(monkeypatch, tmp_path: Path):
    report = Report.model_validate(json.loads(report_json()))
    out = tmp_path / "nested" / "report.md"

    def fake_runtime(_settings):
        class Runtime:
            llm = search = fetch = store = budget = object()

        return Runtime()

    monkeypatch.setattr("src.cli.build_runtime", fake_runtime)
    monkeypatch.setattr(
        "src.cli.run_research",
        lambda topic, **kwargs: ResearchRun(topic=topic, report=report, stopped_reason="completed"),
    )
    code = main(["topic", "--out", str(out)])
    assert code == 0
    assert "Mechanism" in out.read_text(encoding="utf-8")
