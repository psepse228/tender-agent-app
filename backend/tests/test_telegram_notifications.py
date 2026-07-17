from types import SimpleNamespace

import httpx

from app.notifications.telegram import send_telegram_message


def test_returns_true_on_successful_send(monkeypatch):
    monkeypatch.setattr(
        "app.notifications.telegram.get_settings",
        lambda: SimpleNamespace(telegram_bot_token="123:test-token"),
    )
    monkeypatch.setattr(
        "app.notifications.telegram.httpx.post",
        lambda url, json, timeout: SimpleNamespace(status_code=200),
    )

    assert send_telegram_message(111, "hello") is True


def test_returns_false_on_non_200_response(monkeypatch):
    monkeypatch.setattr(
        "app.notifications.telegram.get_settings",
        lambda: SimpleNamespace(telegram_bot_token="123:test-token"),
    )
    monkeypatch.setattr(
        "app.notifications.telegram.httpx.post",
        lambda url, json, timeout: SimpleNamespace(status_code=400),
    )

    assert send_telegram_message(111, "hello") is False


def test_returns_false_and_does_not_raise_on_network_error(monkeypatch):
    monkeypatch.setattr(
        "app.notifications.telegram.get_settings",
        lambda: SimpleNamespace(telegram_bot_token="123:test-token"),
    )

    def _raise(*_a, **_k):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr("app.notifications.telegram.httpx.post", _raise)

    assert send_telegram_message(111, "hello") is False
