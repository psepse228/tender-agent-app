from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.auth.dependencies import SESSION_COOKIE_NAME
from app.main import app
from tests.helpers import session_cookie

TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"
SESSION_SECRET = "test-session-secret-for-all-router-tests"

client = TestClient(app)


class _FakeTable:
    def __init__(self, name, store):
        self.name = name
        self.store = store
        self._filters = {}
        self._pending = None

    def select(self, *_a, **_k):
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, row):
        self._pending = ("insert", row)
        return self

    def delete(self):
        self._pending = ("delete", None)
        return self

    def execute(self):
        if self._pending:
            op, payload = self._pending
            self._pending = None
            if op == "insert":
                row = {"id": f"src-{len(self.store.get(self.name, []))}", **payload}
                self.store.setdefault(self.name, []).append(row)
                return SimpleNamespace(data=[row])
            if op == "delete":
                self.store[self.name] = [
                    r
                    for r in self.store.get(self.name, [])
                    if not all(r.get(k) == v for k, v in self._filters.items())
                ]
                return SimpleNamespace(data=None)

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


def _base_store():
    return {"tenant_sources": []}


def _patch(monkeypatch, fake_client):
    monkeypatch.setattr("app.routers.sources.get_supabase_client", lambda: fake_client)


def test_lists_sources_for_caller_tenant(monkeypatch):
    store = _base_store()
    store["tenant_sources"] = [
        {"id": "src-1", "tenant_id": TENANT_ID, "name": "Mine", "url": "https://example.com"},
        {"id": "src-2", "tenant_id": "other-tenant", "name": "Not mine", "url": "https://other.com"},
    ]
    _patch(monkeypatch, _FakeClient(store))

    response = client.get("/api/sources", cookies=_auth_cookie(TENANT_ID))

    assert response.status_code == 200
    names = [s["name"] for s in response.json()["sources"]]
    assert names == ["Mine"]


def test_get_sources_requires_auth():
    response = client.get("/api/sources")

    assert response.status_code == 401


def test_adds_a_source(monkeypatch):
    store = _base_store()
    _patch(monkeypatch, _FakeClient(store))

    response = client.post(
        "/api/sources",
        cookies=_auth_cookie(TENANT_ID),
        json={"name": "My Own Source", "url": "https://example.com/tenders"},
    )

    assert response.status_code == 200
    assert len(store["tenant_sources"]) == 1
    assert store["tenant_sources"][0]["tenant_id"] == TENANT_ID
    assert store["tenant_sources"][0]["name"] == "My Own Source"


def test_rejects_a_blank_name(monkeypatch):
    store = _base_store()
    _patch(monkeypatch, _FakeClient(store))

    response = client.post(
        "/api/sources", cookies=_auth_cookie(TENANT_ID), json={"name": "   ", "url": "https://example.com"}
    )

    assert response.status_code == 422
    assert store["tenant_sources"] == []


def test_rejects_a_non_http_url(monkeypatch):
    store = _base_store()
    _patch(monkeypatch, _FakeClient(store))

    response = client.post(
        "/api/sources", cookies=_auth_cookie(TENANT_ID), json={"name": "Bad", "url": "javascript:alert(1)"}
    )

    assert response.status_code == 422
    assert store["tenant_sources"] == []


def test_post_sources_requires_auth():
    response = client.post("/api/sources", json={"name": "X", "url": "https://example.com"})

    assert response.status_code == 401


def test_removes_a_source(monkeypatch):
    store = _base_store()
    store["tenant_sources"] = [{"id": "src-1", "tenant_id": TENANT_ID, "name": "Mine", "url": "https://x.com"}]
    _patch(monkeypatch, _FakeClient(store))

    response = client.delete("/api/sources/src-1", cookies=_auth_cookie(TENANT_ID))

    assert response.status_code == 200
    assert store["tenant_sources"] == []


def test_removing_a_source_does_not_affect_other_tenants(monkeypatch):
    store = _base_store()
    store["tenant_sources"] = [
        {"id": "src-1", "tenant_id": TENANT_ID, "name": "Mine", "url": "https://x.com"},
        {"id": "src-2", "tenant_id": "other-tenant", "name": "Not mine", "url": "https://y.com"},
    ]
    _patch(monkeypatch, _FakeClient(store))

    client.delete("/api/sources/src-2", cookies=_auth_cookie(TENANT_ID))

    assert len(store["tenant_sources"]) == 2


def test_delete_sources_requires_auth():
    response = client.delete("/api/sources/src-1")

    assert response.status_code == 401
