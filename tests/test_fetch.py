import httpx

from src.cache import DiskCache
from src.tools.fetch import HttpxFetcher, html_to_text, truncate_text


class FakeHttp:
    def __init__(self, response=None, error=None) -> None:
        self.response = response
        self.error = error
        self.calls = 0

    def get(self, url: str, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.response


class FakeResponse:
    def __init__(self, status_code: int, text: str, content_type: str = "text/html; charset=utf-8"):
        self.status_code = status_code
        self.text = text
        self.headers = {"content-type": content_type}


def test_html_to_text_drops_scripts():
    title, text = html_to_text(
        "<html><title> Hello </title><body><p>Visible fact.</p><script>ignore me</script></body></html>"
    )
    assert title == "Hello"
    assert "Visible fact." in text
    assert "ignore me" not in text


def test_truncate_text_marks_the_cut():
    assert truncate_text("abcdef", 3) == "abc\n[truncated]"
    assert truncate_text("ab", 3) == "ab"


def test_fetch_truncates_long_pages():
    body = "A" * 100
    html = f"<html><title>Long</title><body><p>{body}</p></body></html>"
    client = FakeHttp(FakeResponse(200, html))
    fetcher = HttpxFetcher(max_chars=20, client=client)
    result = fetcher.fetch("https://example.com/long")
    assert result.ok
    assert result.title == "Long"
    assert result.text.endswith("[truncated]")
    assert len(result.text) < 40


def test_dead_link_is_a_result():
    client = FakeHttp(FakeResponse(404, "missing", content_type="text/html"))
    result = HttpxFetcher(client=client).fetch("https://example.com/missing")
    assert result.ok is False
    assert result.status_code == 404
    assert result.error == "HTTP 404"


def test_network_error_is_a_result():
    client = FakeHttp(error=httpx.ConnectError("down"))
    result = HttpxFetcher(client=client).fetch("https://example.com/down")
    assert result.ok is False
    assert result.status_code is None
    assert "down" in result.error


def test_unsupported_type_is_skipped():
    client = FakeHttp(FakeResponse(200, "%PDF", content_type="application/pdf"))
    result = HttpxFetcher(client=client).fetch("https://example.com/file.pdf")
    assert result.ok is False
    assert "unsupported" in result.error


def test_completed_fetch_is_cached(tmp_path):
    client = FakeHttp(FakeResponse(200, "<html><title>T</title><body><p>Cached fact.</p></body></html>"))
    fetcher = HttpxFetcher(client=client, cache=DiskCache(tmp_path))
    first = fetcher.fetch("https://example.com/a")
    second = fetcher.fetch("https://example.com/a")
    assert first.text == second.text
    assert client.calls == 1


def test_timeout_is_not_cached(tmp_path):
    client = FakeHttp(error=httpx.ConnectError("timeout"))
    fetcher = HttpxFetcher(client=client, cache=DiskCache(tmp_path))
    fetcher.fetch("https://example.com/slow")
    fetcher.fetch("https://example.com/slow")
    assert client.calls == 2
