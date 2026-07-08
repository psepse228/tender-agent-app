import time
from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_tenant_id
from tests.helpers import sign_init_data

BOT_TOKEN = "123456:TEST-fake-token-for-tests"
TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"


class _FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        return SimpleNamespace(data=self._data)


class _FakeClient:
    def __init__(self, tenant_users_rows):
        self._rows = tenant_users_rows

    def table(self, name):
        assert name == "tenant_users"
        return _FakeQuery(self._rows)


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(tenant_id: str = Depends(get_current_tenant_id)):
        return {"tenant_id": tenant_id}

    return app


def _signed_init_data(telegram_user_id: int) -> str:
    fields = {
        "user": f'{{"id":{telegram_user_id}}}',
        "auth_date": str(int(time.time())),
    }
    return sign_init_data(fields, BOT_TOKEN)


def test_resolves_known_telegram_user_to_their_tenant(monkeypatch):
    monkeypatch.setattr(
        "app.auth.dependencies.get_supabase_client",
        lambda: _FakeClient([{"tenant_id": TENANT_ID}]),
    )
    app = _build_app()
    client = TestClient(app)

    response = client.get(
        "/whoami",
        headers={"Authorization": f"tma {_signed_init_data(111)}"},
    )

    assert response.status_code == 200
    assert response.json() == {"tenant_id": TENANT_ID}


def test_rejects_missing_authorization_header():
    app = _build_app()
    client = TestClient(app)

    response = client.get("/whoami")

    assert response.status_code == 422  # FastAPI's own missing-header error


def test_rejects_wrong_auth_scheme():
    app = _build_app()
    client = TestClient(app)

    response = client.get("/whoami", headers={"Authorization": "Bearer something"})

    assert response.status_code == 401


def test_rejects_telegram_user_with_no_tenant(monkeypatch):
    monkeypatch.setattr(
        "app.auth.dependencies.get_supabase_client",
        lambda: _FakeClient([]),
    )
    app = _build_app()
    client = TestClient(app)

    response = client.get(
        "/whoami",
        headers={"Authorization": f"tma {_signed_init_data(999)}"},
    )

    assert response.status_code == 403
