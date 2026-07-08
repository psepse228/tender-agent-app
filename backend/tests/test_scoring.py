import json
from types import SimpleNamespace

import pytest

from app.scraping.scoring import CONTENT_CHAR_LIMIT, extract_and_score

SOURCE = {"name": "eTender UzEx", "url": "https://etender.uzex.uz"}


class _FakeOpenAI:
    def __init__(self, payload):
        self._payload = payload
        self.last_kwargs = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.last_kwargs = kwargs
        message = SimpleNamespace(content=json.dumps(self._payload))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_maps_gpt_response_to_tender_dicts():
    fake_client = _FakeOpenAI(
        {
            "tenders": [
                {
                    "title": "Road repair",
                    "matchPercent": 82,
                    "compliance": 90,
                    "financial": 70,
                    "feasibility": 80,
                    "winChance": 75,
                }
            ]
        }
    )

    result = extract_and_score("some markdown", SOURCE, "We build roads.", client=fake_client)

    assert result[0]["title"] == "Road repair"
    assert result[0]["platform"] == "eTender UzEx"
    assert result[0]["source"] == "https://etender.uzex.uz"


def test_returns_empty_list_when_no_tenders_found():
    fake_client = _FakeOpenAI({"tenders": []})

    result = extract_and_score("some markdown", SOURCE, "We build roads.", client=fake_client)

    assert result == []


def test_truncates_content_before_sending_to_model():
    fake_client = _FakeOpenAI({"tenders": []})
    long_content = "x" * 100_000

    extract_and_score(long_content, SOURCE, "profile", client=fake_client)

    user_message = fake_client.last_kwargs["messages"][1]["content"]
    assert "x" * CONTENT_CHAR_LIMIT in user_message
    assert "x" * (CONTENT_CHAR_LIMIT + 1) not in user_message


def test_uses_source_url_when_tender_has_no_own_url():
    fake_client = _FakeOpenAI({"tenders": [{"title": "T", "matchPercent": 50}]})

    result = extract_and_score("md", SOURCE, "profile", client=fake_client)

    assert result[0]["source"] == SOURCE["url"]


def test_uses_tenders_own_url_when_present():
    fake_client = _FakeOpenAI(
        {"tenders": [{"title": "T", "matchPercent": 50, "url": "https://etender.uzex.uz/lot/123"}]}
    )

    result = extract_and_score("md", SOURCE, "profile", client=fake_client)

    assert result[0]["source"] == "https://etender.uzex.uz/lot/123"


def test_propagates_error_on_malformed_json_response():
    class _BadJSONClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **_kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))])

    with pytest.raises(json.JSONDecodeError):
        extract_and_score("md", SOURCE, "profile", client=_BadJSONClient())
