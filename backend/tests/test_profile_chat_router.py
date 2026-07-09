import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import sign_init_data

BOT_TOKEN = "123456:TEST-fake-token-for-tests"
TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"

client = TestClient(app)


class _FakeTable:
    def __init__(self, name, store):
        self.name = name
        self.store = store
        self._filters = {}
        self._order_by = None
        self._pending = None

    def select(self, *_a, **_k):
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def order(self, column, *_a, **_k):
        self._order_by = column
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, row):
        self._pending = ("insert", row)
        return self

    def upsert(self, row, on_conflict=None):
        self._pending = ("upsert", row)
        return self

    def execute(self):
        if self._pending:
            op, payload = self._pending
            if op == "insert":
                self.store.setdefault(self.name, []).append(payload)
            elif op == "upsert":
                existing = next(
                    (
                        r
                        for r in self.store.get(self.name, [])
                        if r.get("tenant_id") == payload["tenant_id"]
                    ),
                    None,
                )
                if existing:
                    existing.update(payload)
                else:
                    self.store.setdefault(self.name, []).append(payload)
            return SimpleNamespace(data=None)

        rows = [
            r
            for r in self.store.get(self.name, [])
            if all(r.get(k) == v for k, v in self._filters.items())
        ]
        if self._order_by:
            rows = sorted(rows, key=lambda r: r.get(self._order_by, ""))
        return SimpleNamespace(data=rows)


class _FakeClient:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _FakeTable(name, self.store)


def _auth_header(telegram_user_id: int) -> dict[str, str]:
    fields = {"user": f'{{"id":{telegram_user_id}}}', "auth_date": str(int(time.time()))}
    return {"Authorization": f"tma {sign_init_data(fields, BOT_TOKEN)}"}


def test_get_returns_empty_history_for_new_tenant(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "profile_chat_messages": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile_chat.get_supabase_client", lambda: fake_client)

    response = client.get("/api/profile-chat", headers=_auth_header(111))

    assert response.status_code == 200
    assert response.json() == {"messages": []}


def test_get_returns_only_caller_tenants_messages(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "profile_chat_messages": [
            {
                "tenant_id": TENANT_ID,
                "role": "client",
                "content": "Hi",
                "created_at": "2026-07-09T00:00:00Z",
            },
            {
                "tenant_id": "other-tenant",
                "role": "client",
                "content": "Not ours",
                "created_at": "2026-07-09T00:00:01Z",
            },
        ],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile_chat.get_supabase_client", lambda: fake_client)

    response = client.get("/api/profile-chat", headers=_auth_header(111))

    assert response.status_code == 200
    contents = [m["content"] for m in response.json()["messages"]]
    assert contents == ["Hi"]


def test_get_requires_auth():
    response = client.get("/api/profile-chat")

    assert response.status_code == 422


def test_post_persists_client_message_and_bot_reply(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "profile_chat_messages": [],
        "company_profile": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile_chat.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr(
        "app.routers.profile_chat.generate_reply",
        lambda conversation, profile_text: {
            "reply": "Расскажи о компании",
            "profile_text": "We build roads.",
        },
    )

    response = client.post("/api/profile-chat", headers=_auth_header(111), json={"message": "Hi"})

    assert response.status_code == 200
    assert response.json() == {"reply": "Расскажи о компании", "profile_text": "We build roads."}
    roles = [m["role"] for m in store["profile_chat_messages"]]
    assert roles == ["client", "bot"]
    assert store["company_profile"][0]["profile_text"] == "We build roads."


def test_post_persists_client_message_even_if_generation_fails(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "profile_chat_messages": [],
        "company_profile": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile_chat.get_supabase_client", lambda: fake_client)

    def raise_error(conversation, profile_text):
        raise RuntimeError("model call failed")

    monkeypatch.setattr("app.routers.profile_chat.generate_reply", raise_error)

    with pytest.raises(RuntimeError):
        client.post("/api/profile-chat", headers=_auth_header(111), json={"message": "Hi"})

    assert len(store["profile_chat_messages"]) == 1
    assert store["profile_chat_messages"][0]["role"] == "client"


def test_post_rejects_empty_message(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "profile_chat_messages": [],
        "company_profile": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile_chat.get_supabase_client", lambda: fake_client)

    response = client.post("/api/profile-chat", headers=_auth_header(111), json={"message": "   "})

    assert response.status_code == 400
    assert store["profile_chat_messages"] == []


def test_post_requires_auth():
    response = client.post("/api/profile-chat", json={"message": "Hi"})

    assert response.status_code == 422
