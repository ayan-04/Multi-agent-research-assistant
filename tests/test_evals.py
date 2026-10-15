from evals.checks import quote_in_source, url_resolves
from evals.run_evals import evaluate_topic, load_topics
from src.llm.schemas import Finding
from src.tools.fetch import FetchResult


class StubFetch:
    def __init__(self, result: FetchResult) -> None:
        self.result = result
        self.urls: list[str] = []

    def fetch(self, url: str) -> FetchResult:
        self.urls.append(url)
        return self.result.model_copy(update={"url": url})


def test_topics_file_has_eight_to_ten_rows():
    topics = load_topics()
    assert 8 <= len(topics) <= 10
    assert len({topic.id for topic in topics}) == len(topics)
    assert all(topic.topic.strip() for topic in topics)


def test_quote_check_ignores_spacing_and_case():
    assert quote_in_source("Solid Electrolytes", "solid   electrolytes are used")
    assert not quote_in_source("liquid metal", "solid electrolytes are used")


def test_url_resolves_requires_success_status():
    assert url_resolves(FetchResult(url="https://example.com", ok=True, status_code=200, text="x"))
    assert not url_resolves(FetchResult(url="https://example.com", ok=False, status_code=404, error="HTTP 404"))
    assert not url_resolves(FetchResult(url="https://example.com", ok=False, error="down"))


def test_evaluate_topic_checks_quote_against_fetched_page():
    from evals.run_evals import EvalTopic

    topic = EvalTopic(id="t01", topic="batteries")
    finding = Finding(
        claim="They use solid electrolytes.",
        source_url="https://example.com/ssb",
        quote="solid electrolytes",
    )
    page = FetchResult(
        url="https://example.com/ssb",
        ok=True,
        status_code=200,
        text="Cells with solid electrolytes last longer.",
    )
    rows = evaluate_topic(topic, [finding], StubFetch(page))
    assert rows[0].url_resolves is True
    assert rows[0].quote_in_source is True

    missing = evaluate_topic(topic, [], StubFetch(page))
    assert missing[0].note == "no findings"
    assert missing[0].quote_in_source is False
