import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.auth.dependencies import SESSION_COOKIE_NAME
from app.main import app
from tests.helpers import session_cookie, sign_init_data

BOT_TOKEN = "123456:TEST-fake-token-for-tests"
TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"
SESSION_SECRET = "test-session-secret-for-all-router-tests"

client = TestClient(app)


class _FakeTable:
    def __init__(self, name, store):
        self.name = name
        self.store = store
        self._filters = {}

    def select(self, *_a, **_k):
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, row):
        self.store.setdefault(self.name, []).append(row)
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=[row]))

    def execute(self):
        rows = [
            r for r in self.store.get(self.name, []) if all(r.get(k) == v for k, v in self._filters.items())
        ]
        return SimpleNamespace(data=rows)


class _FakeClient:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _FakeTable(name, self.store)


def _auth_cookie(tenant_id: str) -> dict[str, str]:
    return {SESSION_COOKIE_NAME: session_cookie(tenant_id, SESSION_SECRET)}


def _signed_init_data(telegram_user_id: int) -> str:
    fields = {"user": f'{{"id":{telegram_user_id}}}', "auth_date": str(int(time.time()))}
    return sign_init_data(fields, BOT_TOKEN)


def test_status_reports_not_linked_for_new_tenant(monkeypatch):
    fake_client = _FakeClient({"tenant_users": []})
    monkeypatch.setattr("app.routers.telegram_link.get_supabase_client", lambda: fake_client)

    response = client.get("/api/link-telegram", cookies=_auth_cookie(TENANT_ID))

    assert response.status_code == 200
    assert response.json() == {"linked": False}


def test_status_reports_linked_when_a_row_exists(monkeypatch):
    fake_client = _FakeClient({"tenant_users": [{"tenant_id": TENANT_ID, "telegram_user_id": 111}]})
    monkeypatch.setattr("app.routers.telegram_link.get_supabase_client", lambda: fake_client)

    response = client.get("/api/link-telegram", cookies=_auth_cookie(TENANT_ID))

    assert response.json() == {"linked": True}


def test_get_status_requires_auth():
    response = client.get("/api/link-telegram")

    assert response.status_code == 401


def test_links_a_new_telegram_account(monkeypatch):
    store = {"tenant_users": []}
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.routers.telegram_link.get_supabase_client", lambda: fake_client)

    response = client.post(
        "/api/link-telegram",
        cookies=_auth_cookie(TENANT_ID),
        json={"init_data": _signed_init_data(111)},
    )

    assert response.status_code == 200
    assert response.json() == {"linked": True, "already_linked": False}
    assert store["tenant_users"] == [{"tenant_id": TENANT_ID, "telegram_user_id": 111}]


def test_relinking_the_same_account_is_idempotent(monkeypatch):
    store = {"tenant_users": [{"tenant_id": TENANT_ID, "telegram_user_id": 111}]}
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.routers.telegram_link.get_supabase_client", lambda: fake_client)

    response = client.post(
        "/api/link-telegram",
        cookies=_auth_cookie(TENANT_ID),
        json={"init_data": _signed_init_data(111)},
    )

    assert response.status_code == 200
    assert response.json() == {"linked": True, "already_linked": True}
    assert len(store["tenant_users"]) == 1


def test_rejects_linking_a_telegram_account_already_tied_to_another_tenant(monkeypatch):
    store = {"tenant_users": [{"tenant_id": "other-tenant", "telegram_user_id": 111}]}
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.routers.telegram_link.get_supabase_client", lambda: fake_client)

    response = client.post(
        "/api/link-telegram",
        cookies=_auth_cookie(TENANT_ID),
        json={"init_data": _signed_init_data(111)},
    )

    assert response.status_code == 409
    assert len(store["tenant_users"]) == 1


def test_rejects_invalid_init_data(monkeypatch):
    fake_client = _FakeClient({"tenant_users": []})
    monkeypatch.setattr("app.routers.telegram_link.get_supabase_client", lambda: fake_client)

    response = client.post(
        "/api/link-telegram", cookies=_auth_cookie(TENANT_ID), json={"init_data": "garbage"}
    )

    assert response.status_code == 400


def test_post_requires_auth():
    response = client.post("/api/link-telegram", json={"init_data": _signed_init_data(111)})

    assert response.status_code == 401
