from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.auth.dependencies import SESSION_COOKIE_NAME
from app.main import app
from tests.helpers import session_cookie

TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"
OTHER_TENANT_ID = "11111111-1111-1111-1111-111111111111"
SESSION_SECRET = "test-session-secret-for-all-router-tests"

client = TestClient(app)


class _FakeQuery:
    def __init__(self, table_data):
        self._table_data = table_data
        self._filters = {}
        self._count_mode = False

    def select(self, *_a, count=None, **_k):
        self._count_mode = count == "exact"
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        rows = [r for r in self._table_data if all(r.get(k) == v for k, v in self._filters.items())]
        return SimpleNamespace(data=rows, count=len(rows) if self._count_mode else None)


class _FakeClient:
    def __init__(self, table_data):
        self._table_data = table_data

    def table(self, name):
        return _FakeQuery(self._table_data.get(name, []))


def _auth_cookie(tenant_id: str) -> dict[str, str]:
    return {SESSION_COOKIE_NAME: session_cookie(tenant_id, SESSION_SECRET)}


def test_returns_aggregate_counts_scoped_to_the_callers_tenant(monkeypatch):
    fake_client = _FakeClient(
        {
            "tenders": [
                {"id": "t1", "tenant_id": TENANT_ID, "recommendation": "Подать заявку"},
                {"id": "t2", "tenant_id": TENANT_ID, "recommendation": "Подать заявку"},
                {"id": "t3", "tenant_id": TENANT_ID, "recommendation": "Рассмотреть"},
                {"id": "t4", "tenant_id": TENANT_ID, "recommendation": "Пропустить"},
                {"id": "t5", "tenant_id": OTHER_TENANT_ID, "recommendation": "Подать заявку"},
            ],
            "favorite_tenders": [{"id": "f1", "tenant_id": TENANT_ID}],
            "profile_chat_messages": [
                {"id": "m1", "tenant_id": TENANT_ID},
                {"id": "m2", "tenant_id": TENANT_ID},
            ],
            "favorite_chat_messages": [{"id": "m3", "tenant_id": TENANT_ID}],
            "tenants": [
                {"id": TENANT_ID, "last_refresh_at": "2026-07-19T10:00:00Z", "subscription_status": "active"}
            ],
        }
    )
    monkeypatch.setattr("app.routers.stats.get_supabase_client", lambda: fake_client)

    response = client.get("/api/stats", cookies=_auth_cookie(TENANT_ID))

    assert response.status_code == 200
    assert response.json() == {
        "tendersScored": 4,
        "matchesFound": 2,
        "worthConsidering": 1,
        "favoritesSaved": 1,
        "chatMessages": 3,
        "lastRefreshAt": "2026-07-19T10:00:00Z",
        "subscriptionStatus": "active",
    }


def test_reports_suspended_subscription_status(monkeypatch):
    fake_client = _FakeClient(
        {
            "tenants": [
                {"id": TENANT_ID, "last_refresh_at": None, "subscription_status": "suspended"}
            ],
        }
    )
    monkeypatch.setattr("app.routers.stats.get_supabase_client", lambda: fake_client)

    response = client.get("/api/stats", cookies=_auth_cookie(TENANT_ID))

    assert response.status_code == 200
    assert response.json()["subscriptionStatus"] == "suspended"


def test_requires_auth():
    response = client.get("/api/stats")

    assert response.status_code == 401
