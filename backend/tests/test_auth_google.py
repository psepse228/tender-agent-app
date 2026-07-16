from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.auth.dependencies import SESSION_COOKIE_NAME
from app.auth.session import verify_session_token
from app.main import app
from app.routers.auth_google import STATE_COOKIE_NAME

client = TestClient(app, follow_redirects=False)

TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"


def _settings(**overrides):
    base = dict(
        google_oauth_client_id=None,
        google_oauth_client_secret=None,
        google_oauth_redirect_uri=None,
        session_secret=None,
        dev_bypass_email=None,
        environment="development",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_login_page_renders():
    response = client.get("/login")

    assert response.status_code == 200
    assert "Войти через Google" in response.text


def test_login_page_shows_mapped_error_message():
    response = client.get("/login?error=unverified")

    assert "не подтверждён" in response.text


def test_start_returns_500_when_oauth_not_configured(monkeypatch):
    monkeypatch.setattr("app.routers.auth_google.get_settings", lambda: _settings())

    response = client.get("/api/auth/google/start")

    assert response.status_code == 500


def test_start_redirects_to_google_with_state_cookie(monkeypatch):
    monkeypatch.setattr(
        "app.routers.auth_google.get_settings",
        lambda: _settings(google_oauth_client_id="client-id", google_oauth_redirect_uri="https://app/callback"),
    )

    response = client.get("/api/auth/google/start")

    assert response.status_code in (302, 307)
    assert response.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=client-id" in response.headers["location"]
    assert STATE_COOKIE_NAME in response.cookies


def test_start_dev_bypass_issues_session_directly(monkeypatch):
    monkeypatch.setattr(
        "app.routers.auth_google.get_settings",
        lambda: _settings(dev_bypass_email="dev@example.com", session_secret="secret"),
    )
    monkeypatch.setattr(
        "app.routers.auth_google.resolve_or_create_tenant_by_email",
        lambda email, name, client: TENANT_ID,
    )
    monkeypatch.setattr("app.routers.auth_google.get_supabase_client", lambda: object())

    response = client.get("/api/auth/google/start")

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/"
    token = response.cookies[SESSION_COOKIE_NAME]
    payload = verify_session_token(token, "secret")
    assert payload["tenantId"] == TENANT_ID
    assert payload["email"] == "dev@example.com"


def test_callback_rejects_missing_code_or_state():
    response = client.get("/api/auth/google/callback")

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/login?error=state"


def test_callback_rejects_state_mismatch():
    response = client.get(
        "/api/auth/google/callback?code=abc&state=one",
        cookies={STATE_COOKIE_NAME: "different"},
    )

    assert response.headers["location"] == "/login?error=state"


def test_callback_rejects_when_not_configured(monkeypatch):
    monkeypatch.setattr("app.routers.auth_google.get_settings", lambda: _settings())

    response = client.get(
        "/api/auth/google/callback?code=abc&state=matching",
        cookies={STATE_COOKIE_NAME: "matching"},
    )

    assert response.headers["location"] == "/login?error=config"


def _configured_settings():
    return _settings(
        google_oauth_client_id="client-id",
        google_oauth_client_secret="client-secret",
        google_oauth_redirect_uri="https://app/callback",
        session_secret="secret",
    )


def test_callback_rejects_unverified_email(monkeypatch):
    monkeypatch.setattr("app.routers.auth_google.get_settings", _configured_settings)
    monkeypatch.setattr(
        "app.routers.auth_google.httpx.post",
        lambda *a, **k: _FakeResponse(200, {"access_token": "tok"}),
    )
    monkeypatch.setattr(
        "app.routers.auth_google.httpx.get",
        lambda *a, **k: _FakeResponse(200, {"email": "user@example.com", "email_verified": False}),
    )

    response = client.get(
        "/api/auth/google/callback?code=abc&state=matching",
        cookies={STATE_COOKIE_NAME: "matching"},
    )

    assert response.headers["location"] == "/login?error=unverified"


def test_callback_happy_path_sets_session_and_redirects_home(monkeypatch):
    monkeypatch.setattr("app.routers.auth_google.get_settings", _configured_settings)
    monkeypatch.setattr(
        "app.routers.auth_google.httpx.post",
        lambda *a, **k: _FakeResponse(200, {"access_token": "tok"}),
    )
    monkeypatch.setattr(
        "app.routers.auth_google.httpx.get",
        lambda *a, **k: _FakeResponse(
            200, {"email": "owner@example.com", "email_verified": True, "name": "Owner"}
        ),
    )
    monkeypatch.setattr(
        "app.routers.auth_google.resolve_or_create_tenant_by_email",
        lambda email, name, client: TENANT_ID,
    )
    monkeypatch.setattr("app.routers.auth_google.get_supabase_client", lambda: object())

    response = client.get(
        "/api/auth/google/callback?code=abc&state=matching",
        cookies={STATE_COOKIE_NAME: "matching"},
    )

    assert response.headers["location"] == "/"
    token = response.cookies[SESSION_COOKIE_NAME]
    payload = verify_session_token(token, "secret")
    assert payload["tenantId"] == TENANT_ID
    assert payload["email"] == "owner@example.com"


def test_callback_redirects_to_error_when_token_exchange_fails(monkeypatch):
    monkeypatch.setattr("app.routers.auth_google.get_settings", _configured_settings)
    monkeypatch.setattr(
        "app.routers.auth_google.httpx.post",
        lambda *a, **k: _FakeResponse(400, {"error": "invalid_grant"}),
    )

    response = client.get(
        "/api/auth/google/callback?code=abc&state=matching",
        cookies={STATE_COOKIE_NAME: "matching"},
    )

    assert response.headers["location"] == "/login?error=token"


def test_logout_clears_session_cookie():
    response = client.post("/api/auth/logout", cookies={SESSION_COOKIE_NAME: "whatever"})

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert SESSION_COOKIE_NAME in set_cookie
