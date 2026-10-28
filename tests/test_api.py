from fastapi.testclient import TestClient

from src.api import app
from src.llm.schemas import Report, ResearchRun


def test_health_reports_database_down(monkeypatch):
    monkeypatch.setattr("src.api.database_ok", lambda _url: False)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503


def test_health_ok(monkeypatch):
    monkeypatch.setattr("src.api.database_ok", lambda _url: True)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_post_research_saves_a_run(monkeypatch):
    report = Report(
        title="Solid-state batteries",
        summary="They replace liquid electrolytes.",
        sections=[
            {
                "heading": "Mechanism",
                "body": "Solid electrolytes replace liquid ones.",
                "citations": ["https://example.com/ssb"],
            }
        ],
        sources=["https://example.com/ssb"],
    )
    saved = {}

    def fake_runtime(_settings):
        class Runtime:
            llm = search = fetch = store = budget = object()

        return Runtime()

    def fake_run(topic, **kwargs):
        assert topic == "solid-state batteries"
        return ResearchRun(topic=topic, report=report, stopped_reason="completed")

    def fake_save(database_url, **kwargs):
        saved["url"] = database_url
        saved.update(kwargs)

    monkeypatch.setattr("src.api.apply_schema", lambda _url: None)
    monkeypatch.setattr("src.api.build_runtime", fake_runtime)
    monkeypatch.setattr("src.api.run_research", fake_run)
    monkeypatch.setattr("src.api.save_research_run", fake_save)
    monkeypatch.setattr("src.api.load_settings", lambda: type("S", (), {"database_url": "postgresql://test"})())

    with TestClient(app) as client:
        response = client.post("/research", json={"topic": "solid-state batteries"})
    assert response.status_code == 200
    body = response.json()
    assert body["stopped_reason"] == "completed"
    assert "Solid-state batteries" in body["markdown"]
    assert saved["topic"] == "solid-state batteries"
    assert saved["run_id"] == body["id"]


def test_get_research_404(monkeypatch):
    monkeypatch.setattr("src.api.apply_schema", lambda _url: None)
    monkeypatch.setattr("src.api.load_research_run", lambda _url, _run_id: None)
    monkeypatch.setattr("src.api.load_settings", lambda: type("S", (), {"database_url": "postgresql://test"})())
    with TestClient(app) as client:
        response = client.get("/research/missing")
    assert response.status_code == 404
