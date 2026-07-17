from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.auth.dependencies import SESSION_COOKIE_NAME
from app.main import app
from tests.helpers import session_cookie

TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"
SESSION_SECRET = "test-session-secret-for-all-router-tests"

client = TestClient(app)


class _FakeQuery:
    def __init__(self, table_data):
        self._table_data = table_data
        self._filters = {}

    def select(self, *_a, **_k):
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        rows = [
            r for r in self._table_data if all(r.get(k) == v for k, v in self._filters.items())
        ]
        return SimpleNamespace(data=rows)


class _FakeClient:
    def __init__(self, table_data):
        self._table_data = table_data

    def table(self, name):
        return _FakeQuery(self._table_data.get(name, []))


def _auth_cookie(tenant_id: str) -> dict[str, str]:
    return {SESSION_COOKIE_NAME: session_cookie(tenant_id, SESSION_SECRET)}


def test_rejects_refresh_within_cooldown(monkeypatch):
    recent = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    fake_client = _FakeClient({"tenants": [{"id": TENANT_ID, "last_refresh_at": recent}]})
    monkeypatch.setattr("app.routers.refresh.get_supabase_client", lambda: fake_client)

    response = client.post("/api/refresh", cookies=_auth_cookie(TENANT_ID))

    assert response.status_code == 429


def test_allows_refresh_after_cooldown_expires(monkeypatch):
    long_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    fake_client = _FakeClient({"tenants": [{"id": TENANT_ID, "last_refresh_at": long_ago}]})
    monkeypatch.setattr("app.routers.refresh.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr(
        "app.routers.refresh.refresh_tenant",
        lambda tenant_id, client: {"tenders": [], "sources_status": []},
    )

    response = client.post("/api/refresh", cookies=_auth_cookie(TENANT_ID))

    assert response.status_code == 200
    assert response.json() == {"tenders": [], "sources_status": []}


def test_allows_refresh_when_never_refreshed_before(monkeypatch):
    fake_client = _FakeClient({"tenants": [{"id": TENANT_ID, "last_refresh_at": None}]})
    monkeypatch.setattr("app.routers.refresh.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr(
        "app.routers.refresh.refresh_tenant",
        lambda tenant_id, client: {"tenders": [], "sources_status": []},
    )

    response = client.post("/api/refresh", cookies=_auth_cookie(TENANT_ID))

    assert response.status_code == 200


def test_requires_auth():
    response = client.post("/api/refresh")

    assert response.status_code == 401


def test_status_reports_no_progress_for_a_tenant_that_never_refreshed(monkeypatch):
    monkeypatch.setattr("app.scraping.pipeline._progress", {}, raising=False)

    response = client.get("/api/refresh/status", cookies=_auth_cookie(TENANT_ID))

    assert response.status_code == 200
    body = response.json()
    assert body["done"] == 0
    assert body["running"] is False


def test_status_reflects_in_flight_progress(monkeypatch):
    monkeypatch.setattr(
        "app.scraping.pipeline._progress",
        {TENANT_ID: {"total": 6, "done": 3, "sources": [{"name": "eTender UzEx", "status": "ok"}], "running": True}},
        raising=False,
    )

    response = client.get("/api/refresh/status", cookies=_auth_cookie(TENANT_ID))

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "total": 6,
        "done": 3,
        "sources": [{"name": "eTender UzEx", "status": "ok"}],
        "running": True,
    }
