import time
from types import SimpleNamespace

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
        self._pending = None

    def select(self, *_a, **_k):
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, row):
        self._pending = ("insert", row)
        return self

    def update(self, values):
        self._pending = ("update", values)
        return self

    def execute(self):
        if self._pending:
            op, payload = self._pending
            if op == "insert":
                self.store.setdefault(self.name, []).append(payload)
            elif op == "update":
                for row in self.store.get(self.name, []):
                    if all(row.get(k) == v for k, v in self._filters.items()):
                        row.update(payload)
            return SimpleNamespace(data=None)

        rows = [
            r
            for r in self.store.get(self.name, [])
            if all(r.get(k) == v for k, v in self._filters.items())
        ]
        return SimpleNamespace(data=rows)


class _FakeClient:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _FakeTable(name, self.store)


def _auth_header(telegram_user_id: int) -> dict[str, str]:
    fields = {"user": f'{{"id":{telegram_user_id}}}', "auth_date": str(int(time.time()))}
    return {"Authorization": f"tma {sign_init_data(fields, BOT_TOKEN)}"}


def test_creates_profile_when_none_exists(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "company_profile": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile.get_supabase_client", lambda: fake_client)

    response = client.post(
        "/api/profile",
        headers=_auth_header(111),
        json={"updates": {"Company Name": "Acme LLC", "Location": "Tashkent"}},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert len(store["company_profile"]) == 1
    assert store["company_profile"][0]["tenant_id"] == TENANT_ID
    assert "Company Name: Acme LLC" in store["company_profile"][0]["profile_text"]
    assert "Location: Tashkent" in store["company_profile"][0]["profile_text"]


def test_updates_existing_profile(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "company_profile": [{"tenant_id": TENANT_ID, "profile_text": "Old text"}],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile.get_supabase_client", lambda: fake_client)

    response = client.post(
        "/api/profile",
        headers=_auth_header(111),
        json={"updates": {"Company Name": "New Name"}},
    )

    assert response.status_code == 200
    assert len(store["company_profile"]) == 1
    assert store["company_profile"][0]["profile_text"] == "Company Name: New Name"


def test_skips_empty_values(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "company_profile": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile.get_supabase_client", lambda: fake_client)

    response = client.post(
        "/api/profile",
        headers=_auth_header(111),
        json={"updates": {"Company Name": "Acme LLC", "Location": ""}},
    )

    assert response.status_code == 200
    assert store["company_profile"][0]["profile_text"] == "Company Name: Acme LLC"


def test_post_requires_auth():
    response = client.post("/api/profile", json={"updates": {"Company Name": "Acme"}})

    assert response.status_code == 422


def test_get_returns_profile_text_for_caller_tenant(monkeypatch):
    store = {
        "tenant_users": [
            {"telegram_user_id": 111, "tenant_id": TENANT_ID},
            {"telegram_user_id": 222, "tenant_id": "other-tenant"},
        ],
        "company_profile": [
            {"tenant_id": TENANT_ID, "profile_text": "Our profile"},
            {"tenant_id": "other-tenant", "profile_text": "Someone else's profile"},
        ],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile.get_supabase_client", lambda: fake_client)

    response = client.get("/api/profile", headers=_auth_header(111))

    assert response.status_code == 200
    assert response.json() == {"profile_text": "Our profile"}


def test_get_returns_null_when_no_profile_exists(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "company_profile": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile.get_supabase_client", lambda: fake_client)

    response = client.get("/api/profile", headers=_auth_header(111))

    assert response.status_code == 200
    assert response.json() == {"profile_text": None}


def test_get_requires_auth():
    response = client.get("/api/profile")

    assert response.status_code == 422
