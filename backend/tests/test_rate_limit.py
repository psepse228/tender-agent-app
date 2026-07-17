from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.chat.rate_limit import MAX_MESSAGES_PER_DAY, enforce_chat_rate_limit

TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"


class _FakeTable:
    def __init__(self, rows):
        self.rows = rows
        self._filters = {}
        self._gte_filters = {}

    def select(self, *_a, **_k):
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def gte(self, column, value):
        self._gte_filters[column] = value
        return self

    def order(self, *_a, **_k):
        return self

    def execute(self):
        rows = [
            r
            for r in self.rows
            if all(r.get(k) == v for k, v in self._filters.items())
            and all(r.get(k, "") >= v for k, v in self._gte_filters.items())
        ]
        return SimpleNamespace(data=rows)


class _FakeClient:
    def __init__(self, rows):
        self.rows = rows

    def table(self, _name):
        return _FakeTable(self.rows)


def _iso(minutes_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def test_allows_first_message_with_no_history():
    client = _FakeClient([])

    enforce_chat_rate_limit("profile_chat_messages", TENANT_ID, {}, client)  # should not raise


def test_blocks_a_message_sent_immediately_after_the_last_one():
    rows = [{"tenant_id": TENANT_ID, "role": "client", "created_at": _iso(0)}]
    client = _FakeClient(rows)

    with pytest.raises(HTTPException) as exc_info:
        enforce_chat_rate_limit("profile_chat_messages", TENANT_ID, {}, client)
    assert exc_info.value.status_code == 429


def test_allows_a_message_sent_after_the_cooldown_elapsed():
    rows = [{"tenant_id": TENANT_ID, "role": "client", "created_at": _iso(1)}]
    client = _FakeClient(rows)

    enforce_chat_rate_limit("profile_chat_messages", TENANT_ID, {}, client)  # should not raise


def test_blocks_once_the_daily_cap_is_reached():
    rows = [
        {"tenant_id": TENANT_ID, "role": "client", "created_at": _iso(60 + i)}
        for i in range(MAX_MESSAGES_PER_DAY)
    ]
    client = _FakeClient(rows)

    with pytest.raises(HTTPException) as exc_info:
        enforce_chat_rate_limit("profile_chat_messages", TENANT_ID, {}, client)
    assert exc_info.value.status_code == 429
    assert "limit" in exc_info.value.detail.lower()


def test_messages_older_than_24h_do_not_count_toward_the_daily_cap():
    rows = [
        {"tenant_id": TENANT_ID, "role": "client", "created_at": _iso(60 * 25)}
        for _ in range(MAX_MESSAGES_PER_DAY)
    ]
    client = _FakeClient(rows)

    enforce_chat_rate_limit("profile_chat_messages", TENANT_ID, {}, client)  # should not raise


def test_scopes_by_extra_filters_independently():
    # A different favorite_id's message history should not affect this one's limit.
    rows = [
        {"tenant_id": TENANT_ID, "favorite_id": "other-fav", "role": "client", "created_at": _iso(0)},
    ]
    client = _FakeClient(rows)

    enforce_chat_rate_limit(
        "favorite_chat_messages", TENANT_ID, {"favorite_id": "this-fav"}, client
    )  # should not raise -- scoped to a different favorite_id


def test_other_tenants_messages_do_not_count():
    rows = [{"tenant_id": "other-tenant", "role": "client", "created_at": _iso(0)}]
    client = _FakeClient(rows)

    enforce_chat_rate_limit("profile_chat_messages", TENANT_ID, {}, client)  # should not raise
