import json
from types import SimpleNamespace

import pytest

from app.chat.profile_chat import MAX_HISTORY_MESSAGES, generate_reply


class _FakeOpenAI:
    def __init__(self, payload):
        self._payload = payload
        self.last_kwargs = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.last_kwargs = kwargs
        message = SimpleNamespace(content=json.dumps(self._payload))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_returns_reply_and_profile_text():
    fake_client = _FakeOpenAI({"reply": "Расскажите про вашу компанию", "profile_text": "We build roads."})

    result = generate_reply([{"role": "client", "content": "Hi"}], "", client=fake_client)

    assert result == {"reply": "Расскажите про вашу компанию", "profile_text": "We build roads."}


def test_maps_bot_role_to_assistant_and_client_role_to_user():
    fake_client = _FakeOpenAI({"reply": "ok", "profile_text": "x"})

    generate_reply(
        [
            {"role": "client", "content": "Hi"},
            {"role": "bot", "content": "Hello, tell me about your company"},
            {"role": "client", "content": "We build roads"},
        ],
        "",
        client=fake_client,
    )

    roles = [m["role"] for m in fake_client.last_kwargs["messages"][1:]]
    assert roles == ["user", "assistant", "user"]


def test_truncates_to_last_20_messages():
    fake_client = _FakeOpenAI({"reply": "ok", "profile_text": "x"})
    long_conversation = [{"role": "client", "content": f"msg {i}"} for i in range(30)]

    generate_reply(long_conversation, "", client=fake_client)

    sent_messages = fake_client.last_kwargs["messages"][1:]
    assert len(sent_messages) == MAX_HISTORY_MESSAGES
    assert sent_messages[0]["content"] == "msg 10"
    assert sent_messages[-1]["content"] == "msg 29"


def test_includes_current_profile_text_in_system_prompt():
    fake_client = _FakeOpenAI({"reply": "ok", "profile_text": "x"})

    generate_reply([{"role": "client", "content": "Hi"}], "We build roads.", client=fake_client)

    system_message = fake_client.last_kwargs["messages"][0]["content"]
    assert "We build roads." in system_message


def test_propagates_error_on_malformed_json_response():
    class _BadJSONClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **_kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))])

    with pytest.raises(json.JSONDecodeError):
        generate_reply([{"role": "client", "content": "Hi"}], "", client=_BadJSONClient())


def test_propagates_error_when_response_missing_required_keys():
    fake_client = _FakeOpenAI({"reply": "ok"})  # missing profile_text

    with pytest.raises(KeyError):
        generate_reply([{"role": "client", "content": "Hi"}], "", client=fake_client)


def test_raises_on_unrecognized_message_role():
    fake_client = _FakeOpenAI({"reply": "ok", "profile_text": "x"})

    with pytest.raises(ValueError):
        generate_reply([{"role": "system", "content": "x"}], "", client=fake_client)
