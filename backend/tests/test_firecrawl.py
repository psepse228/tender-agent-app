import json

import httpx

from app.scraping.firecrawl import scrape_source

SOURCE = {"name": "BicoTender", "url": "https://bicotender.ru"}


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


class _InvalidJsonResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def json(self):
        raise json.JSONDecodeError("Expecting value", "", 0)


def test_returns_markdown_on_first_success(monkeypatch):
    monkeypatch.setattr(
        "app.scraping.firecrawl.httpx.post",
        lambda *a, **k: _FakeResponse(200, {"data": {"markdown": "# Tenders"}}),
    )
    sleeps = []

    result = scrape_source(SOURCE, sleep=sleeps.append)

    assert result == "# Tenders"
    assert sleeps == []


def test_retries_on_bad_gateway_then_succeeds(monkeypatch):
    responses = iter(
        [_FakeResponse(502), _FakeResponse(502), _FakeResponse(200, {"data": {"markdown": "ok"}})]
    )
    monkeypatch.setattr("app.scraping.firecrawl.httpx.post", lambda *a, **k: next(responses))
    sleeps = []

    result = scrape_source(SOURCE, sleep=sleeps.append)

    assert result == "ok"
    assert sleeps == [1, 2]


def test_returns_none_after_all_retries_fail(monkeypatch):
    monkeypatch.setattr("app.scraping.firecrawl.httpx.post", lambda *a, **k: _FakeResponse(502))
    sleeps = []

    result = scrape_source(SOURCE, sleep=sleeps.append)

    assert result is None
    assert sleeps == [1, 2]


def test_retries_on_network_error(monkeypatch):
    def raise_error(*_a, **_k):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr("app.scraping.firecrawl.httpx.post", raise_error)
    sleeps = []

    result = scrape_source(SOURCE, sleep=sleeps.append)

    assert result is None
    assert sleeps == [1, 2]


def test_treats_error_shaped_200_response_as_retryable_failure(monkeypatch):
    # A 200 with a null "data" field (e.g. {"success": false, "data": null}) must
    # not raise AttributeError — it should be treated like any other failed attempt.
    monkeypatch.setattr(
        "app.scraping.firecrawl.httpx.post",
        lambda *a, **k: _FakeResponse(200, {"success": False, "data": None, "error": "boom"}),
    )
    sleeps = []

    result = scrape_source(SOURCE, sleep=sleeps.append)

    assert result is None
    assert sleeps == [1, 2]


def test_treats_invalid_json_200_response_as_retryable_failure(monkeypatch):
    monkeypatch.setattr(
        "app.scraping.firecrawl.httpx.post",
        lambda *a, **k: _InvalidJsonResponse(),
    )
    sleeps = []

    result = scrape_source(SOURCE, sleep=sleeps.append)

    assert result is None
    assert sleeps == [1, 2]
