import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import sign_init_data

BOT_TOKEN = "123456:TEST-fake-token-for-tests"
TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"
OTHER_TENANT_ID = "11111111-1111-1111-1111-111111111111"

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

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        rows = [r for r in self._table_data if all(r.get(k) == v for k, v in self._filters.items())]
        return SimpleNamespace(data=rows)


class _FakeClient:
    def __init__(self, table_data):
        self._table_data = table_data

    def table(self, name):
        return _FakeQuery(self._table_data.get(name, []))


def _auth_header(telegram_user_id: int) -> dict[str, str]:
    fields = {"user": f'{{"id":{telegram_user_id}}}', "auth_date": str(int(time.time()))}
    return {"Authorization": f"tma {sign_init_data(fields, BOT_TOKEN)}"}


def test_returns_only_the_callers_tenant_tenders(monkeypatch):
    fake_client = _FakeClient({
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "tenders": [
            {"id": "t1", "tenant_id": TENANT_ID, "title": "Ours", "match_percent": 80},
            {"id": "t2", "tenant_id": OTHER_TENANT_ID, "title": "Not ours", "match_percent": 90},
        ],
    })
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.tenders.get_supabase_client", lambda: fake_client)

    response = client.get("/api/tenders", headers=_auth_header(111))

    assert response.status_code == 200
    titles = [t["title"] for t in response.json()["tenders"]]
    assert titles == ["Ours"]


def test_requires_auth():
    response = client.get("/api/tenders")

    assert response.status_code == 422
