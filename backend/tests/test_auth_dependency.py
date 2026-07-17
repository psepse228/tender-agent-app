import time
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.auth.dependencies import SESSION_COOKIE_NAME, get_current_tenant_id, resolve_or_create_tenant_by_email
from app.auth.session import create_session_token

TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"
SESSION_SECRET = "test-session-secret"


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(tenant_id: str = Depends(get_current_tenant_id)):
        return {"tenant_id": tenant_id}

    return app


def test_resolves_session_cookie_to_its_tenant(monkeypatch):
    monkeypatch.setattr(
        "app.auth.dependencies.get_settings",
        lambda: SimpleNamespace(session_secret=SESSION_SECRET),
    )
    app = _build_app()
    client = TestClient(app)
    token = create_session_token(
        {"email": "owner@example.com", "tenantId": TENANT_ID, "exp": time.time() + 3600}, SESSION_SECRET
    )

    response = client.get("/whoami", cookies={SESSION_COOKIE_NAME: token})

    assert response.status_code == 200
    assert response.json() == {"tenant_id": TENANT_ID}


def test_rejects_missing_session_cookie():
    app = _build_app()
    client = TestClient(app)

    response = client.get("/whoami")

    assert response.status_code == 401


def test_rejects_session_cookie_when_web_login_not_configured(monkeypatch):
    monkeypatch.setattr(
        "app.auth.dependencies.get_settings",
        lambda: SimpleNamespace(session_secret=None),
    )
    app = _build_app()
    client = TestClient(app)
    token = create_session_token(
        {"email": "owner@example.com", "tenantId": TENANT_ID, "exp": time.time() + 3600}, SESSION_SECRET
    )

    response = client.get("/whoami", cookies={SESSION_COOKIE_NAME: token})

    assert response.status_code == 401


def test_rejects_invalid_session_cookie(monkeypatch):
    monkeypatch.setattr(
        "app.auth.dependencies.get_settings",
        lambda: SimpleNamespace(session_secret=SESSION_SECRET),
    )
    app = _build_app()
    client = TestClient(app)

    response = client.get("/whoami", cookies={SESSION_COOKIE_NAME: "garbage"})

    assert response.status_code == 401


def test_rejects_expired_session_cookie(monkeypatch):
    monkeypatch.setattr(
        "app.auth.dependencies.get_settings",
        lambda: SimpleNamespace(session_secret=SESSION_SECRET),
    )
    app = _build_app()
    client = TestClient(app)
    token = create_session_token(
        {"email": "owner@example.com", "tenantId": TENANT_ID, "exp": time.time() - 10}, SESSION_SECRET
    )

    response = client.get("/whoami", cookies={SESSION_COOKIE_NAME: token})

    assert response.status_code == 401


class _FakeTenantsTable:
    def __init__(self, rows, fail_first_insert_with=None):
        self.rows = rows
        self._filters = {}
        self._pending_insert = None
        self._fail_first_insert_with = fail_first_insert_with

    def select(self, *_a, **_k):
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, values):
        self._pending_insert = values
        return self

    def execute(self):
        if self._pending_insert is not None:
            pending = self._pending_insert
            self._pending_insert = None
            if self._fail_first_insert_with is not None:
                err = self._fail_first_insert_with
                self._fail_first_insert_with = None
                raise APIError({"code": err, "message": "boom"})
            row = {"id": "new-tenant-id", **pending}
            self.rows.append(row)
            return SimpleNamespace(data=[row])

        matches = [r for r in self.rows if all(r.get(k) == v for k, v in self._filters.items())]
        return SimpleNamespace(data=matches)


class _FakeTenantsClient:
    def __init__(self, rows, fail_first_insert_with=None):
        self._table = _FakeTenantsTable(rows, fail_first_insert_with)

    def table(self, name):
        assert name == "tenants"
        return self._table


def test_resolve_or_create_returns_existing_tenant_for_known_email():
    client = _FakeTenantsClient([{"id": TENANT_ID, "owner_email": "owner@example.com"}])

    tenant_id = resolve_or_create_tenant_by_email("owner@example.com", "Owner", client)

    assert tenant_id == TENANT_ID


def test_resolve_or_create_creates_new_tenant_for_unknown_email():
    client = _FakeTenantsClient([])

    tenant_id = resolve_or_create_tenant_by_email("new@example.com", "New Owner", client)

    assert tenant_id == "new-tenant-id"


def test_resolve_or_create_falls_back_to_email_when_name_is_blank():
    client = _FakeTenantsClient([])
    resolve_or_create_tenant_by_email("new@example.com", "  ", client)

    assert client._table.rows[0]["name"] == "new@example.com"


def test_resolve_or_create_recovers_from_concurrent_insert_race():
    rows = [{"id": TENANT_ID, "owner_email": "racer@example.com"}]
    client = _FakeTenantsClient(rows, fail_first_insert_with="23505")

    tenant_id = resolve_or_create_tenant_by_email("racer@example.com", "Racer", client)

    assert tenant_id == TENANT_ID


def test_resolve_or_create_reraises_non_unique_violation_errors():
    client = _FakeTenantsClient([], fail_first_insert_with="23000")

    with pytest.raises(APIError):
        resolve_or_create_tenant_by_email("broken@example.com", "Broken", client)
