import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import sign_init_data

BOT_TOKEN = "123456:TEST-fake-token-for-tests"
TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"

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


def _auth_header(telegram_user_id: int) -> dict[str, str]:
    fields = {"user": f'{{"id":{telegram_user_id}}}', "auth_date": str(int(time.time()))}
    return {"Authorization": f"tma {sign_init_data(fields, BOT_TOKEN)}"}


def test_rejects_refresh_within_cooldown(monkeypatch):
    recent = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    fake_client = _FakeClient(
        {
            "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
            "tenants": [{"id": TENANT_ID, "last_refresh_at": recent}],
        }
    )
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.refresh.get_supabase_client", lambda: fake_client)

    response = client.post("/api/refresh", headers=_auth_header(111))

    assert response.status_code == 429


def test_allows_refresh_after_cooldown_expires(monkeypatch):
    long_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    fake_client = _FakeClient(
        {
            "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
            "tenants": [{"id": TENANT_ID, "last_refresh_at": long_ago}],
        }
    )
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.refresh.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr(
        "app.routers.refresh.refresh_tenant",
        lambda tenant_id, client: {"tenders": [], "sources_status": []},
    )

    response = client.post("/api/refresh", headers=_auth_header(111))

    assert response.status_code == 200
    assert response.json() == {"tenders": [], "sources_status": []}


def test_allows_refresh_when_never_refreshed_before(monkeypatch):
    fake_client = _FakeClient(
        {
            "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
            "tenants": [{"id": TENANT_ID, "last_refresh_at": None}],
        }
    )
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.refresh.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr(
        "app.routers.refresh.refresh_tenant",
        lambda tenant_id, client: {"tenders": [], "sources_status": []},
    )

    response = client.post("/api/refresh", headers=_auth_header(111))

    assert response.status_code == 200


def test_requires_auth():
    response = client.post("/api/refresh")

    assert response.status_code == 422


def test_status_reports_no_progress_for_a_tenant_that_never_refreshed(monkeypatch):
    fake_client = _FakeClient({"tenant_users": [{"telegram_user_id": 222, "tenant_id": TENANT_ID}]})
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.scraping.pipeline._progress", {}, raising=False)

    response = client.get("/api/refresh/status", headers=_auth_header(222))

    assert response.status_code == 200
    body = response.json()
    assert body["done"] == 0
    assert body["running"] is False


def test_status_reflects_in_flight_progress(monkeypatch):
    fake_client = _FakeClient({"tenant_users": [{"telegram_user_id": 333, "tenant_id": TENANT_ID}]})
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr(
        "app.scraping.pipeline._progress",
        {TENANT_ID: {"total": 6, "done": 3, "sources": [{"name": "eTender UzEx", "status": "ok"}], "running": True}},
        raising=False,
    )

    response = client.get("/api/refresh/status", headers=_auth_header(333))

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "total": 6,
        "done": 3,
        "sources": [{"name": "eTender UzEx", "status": "ok"}],
        "running": True,
    }
