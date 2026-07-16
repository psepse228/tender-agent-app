import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import sign_init_data

BOT_TOKEN = "123456:TEST-fake-token-for-tests"
TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"
TENDER_ID = "a1b2c3d4-0000-0000-0000-000000000001"

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

    def order(self, *_a, **_k):
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
            if op == "insert":
                row = {"id": f"fav-{len(self.store.get(self.name, []))}", **payload}
                self.store.setdefault(self.name, []).append(row)
                self._pending = None
                return SimpleNamespace(data=[row])
            if op == "delete":
                self.store[self.name] = [
                    r
                    for r in self.store.get(self.name, [])
                    if not all(r.get(k) == v for k, v in self._filters.items())
                ]
                self._pending = None
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


def _auth_header(telegram_user_id: int) -> dict[str, str]:
    fields = {"user": f'{{"id":{telegram_user_id}}}', "auth_date": str(int(time.time()))}
    return {"Authorization": f"tma {sign_init_data(fields, BOT_TOKEN)}"}


def _base_store(**tender_overrides):
    tender = {
        "id": TENDER_ID,
        "tenant_id": TENANT_ID,
        "title": "Road repair",
        "organization": "City Council",
        "match_percent": 82,
    }
    tender.update(tender_overrides)
    return {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "tenders": [tender],
        "favorite_tenders": [],
    }


def _patch(monkeypatch, fake_client):
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.favorites.get_supabase_client", lambda: fake_client)


def test_lists_favorites_for_caller_tenant(monkeypatch):
    store = _base_store()
    store["favorite_tenders"] = [
        {"id": "fav-1", "tenant_id": TENANT_ID, "title": "Saved one", "match_percent": 90},
        {"id": "fav-2", "tenant_id": "other-tenant", "title": "Not mine", "match_percent": 99},
    ]
    _patch(monkeypatch, _FakeClient(store))

    response = client.get("/api/favorites", headers=_auth_header(111))

    assert response.status_code == 200
    titles = [f["title"] for f in response.json()["favorites"]]
    assert titles == ["Saved one"]


def test_get_favorites_requires_auth():
    response = client.get("/api/favorites")

    assert response.status_code == 401


def test_adds_a_tender_to_favorites(monkeypatch):
    store = _base_store()
    _patch(monkeypatch, _FakeClient(store))

    response = client.post(
        "/api/favorites", headers=_auth_header(111), json={"tender_id": TENDER_ID}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["already_existed"] is False
    assert len(store["favorite_tenders"]) == 1
    saved = store["favorite_tenders"][0]
    assert saved["title"] == "Road repair"
    assert saved["organization"] == "City Council"
    assert saved["tenant_id"] == TENANT_ID


def test_returns_404_for_a_tender_from_another_tenant(monkeypatch):
    store = _base_store(tenant_id="other-tenant")
    _patch(monkeypatch, _FakeClient(store))

    response = client.post(
        "/api/favorites", headers=_auth_header(111), json={"tender_id": TENDER_ID}
    )

    assert response.status_code == 404
    assert store["favorite_tenders"] == []


def test_favoriting_the_same_tender_twice_does_not_duplicate(monkeypatch):
    store = _base_store()
    _patch(monkeypatch, _FakeClient(store))

    client.post("/api/favorites", headers=_auth_header(111), json={"tender_id": TENDER_ID})
    response = client.post("/api/favorites", headers=_auth_header(111), json={"tender_id": TENDER_ID})

    assert response.status_code == 200
    assert response.json()["already_existed"] is True
    assert len(store["favorite_tenders"]) == 1


def test_post_favorites_requires_auth():
    response = client.post("/api/favorites", json={"tender_id": TENDER_ID})

    assert response.status_code == 401


def test_removes_a_favorite(monkeypatch):
    store = _base_store()
    store["favorite_tenders"] = [{"id": "fav-1", "tenant_id": TENANT_ID, "title": "Saved one"}]
    _patch(monkeypatch, _FakeClient(store))

    response = client.delete("/api/favorites/fav-1", headers=_auth_header(111))

    assert response.status_code == 200
    assert store["favorite_tenders"] == []


def test_removing_a_favorite_does_not_affect_other_tenants(monkeypatch):
    store = _base_store()
    store["favorite_tenders"] = [
        {"id": "fav-1", "tenant_id": TENANT_ID, "title": "Mine"},
        {"id": "fav-2", "tenant_id": "other-tenant", "title": "Not mine"},
    ]
    _patch(monkeypatch, _FakeClient(store))

    client.delete("/api/favorites/fav-2", headers=_auth_header(111))

    assert len(store["favorite_tenders"]) == 2


def test_delete_favorites_requires_auth():
    response = client.delete("/api/favorites/fav-1")

    assert response.status_code == 401
