import logging
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.auth.dependencies import SESSION_COOKIE_NAME, resolve_or_create_tenant_by_email
from app.auth.session import create_session_token, verify_session_token
from app.config import get_settings
from app.db import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()

STATE_COOKIE_NAME = "google_oauth_state"
STATE_MAX_AGE_SECONDS = 5 * 60
SESSION_MAX_AGE_SECONDS = 30 * 24 * 3600

LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tender Agent — Вход</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center;
    background: #050810; color: #f1f5f9; font-family: 'DM Sans', sans-serif; gap: 24px;
  }
  .mark {
    width: 56px; height: 56px; border-radius: 22%;
    background: linear-gradient(135deg, #38bdf8, #818cf8);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Manrope', sans-serif; font-size: 26px; font-weight: 800; color: #050810;
    box-shadow: 0 0 32px rgba(56,189,248,.35);
  }
  h1 { font-family: 'Manrope', sans-serif; font-weight: 800; font-size: 20px; letter-spacing: -.02em; }
  p { color: #94a3b8; font-size: 13px; }
  .error { color: #ef4444; font-size: 12px; }
  a.google-btn {
    display: flex; align-items: center; gap: 10px; text-decoration: none;
    background: #f1f5f9; color: #050810; font-weight: 700; font-size: 14px;
    padding: 12px 22px; border-radius: 12px; margin-top: 8px;
  }
</style>
</head>
<body>
  <div class="mark">T</div>
  <h1>Tender Agent</h1>
  <p>Войдите, чтобы открыть панель тендеров</p>
  {error_html}
  <a class="google-btn" href="/api/auth/google/start">Войти через Google</a>
</body>
</html>"""

_ERROR_MESSAGES = {
    "state": "Не удалось подтвердить запрос входа. Попробуйте ещё раз.",
    "config": "Вход через Google временно недоступен.",
    "token": "Не удалось войти через Google. Попробуйте ещё раз.",
    "userinfo": "Не удалось получить данные аккаунта Google.",
    "unverified": "Этот email не подтверждён в Google.",
    "tenant": "Не удалось создать рабочее пространство. Попробуйте ещё раз.",
}


@router.get("/login", include_in_schema=False)
def login_page(error: str | None = None) -> HTMLResponse:
    error_html = f'<p class="error">{_ERROR_MESSAGES.get(error, "Что-то пошло не так.")}</p>' if error else ""
    return HTMLResponse(LOGIN_PAGE_HTML.replace("{error_html}", error_html))


def _issue_session_redirect(email: str, tenant_id: str) -> RedirectResponse:
    settings = get_settings()
    token = create_session_token(
        {"email": email, "tenantId": tenant_id, "exp": time.time() + SESSION_MAX_AGE_SECONDS},
        settings.session_secret,
    )
    response = RedirectResponse("/")
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE_SECONDS,
        path="/",
    )
    return response


@router.get("/api/auth/google/start", include_in_schema=False)
def google_oauth_start():
    settings = get_settings()

    if settings.dev_bypass_email and settings.environment != "production":
        if not settings.session_secret:
            return JSONResponse({"error": "SESSION_SECRET is not configured on the server"}, status_code=500)
        tenant_id = resolve_or_create_tenant_by_email(
            settings.dev_bypass_email, None, get_supabase_client()
        )
        return _issue_session_redirect(settings.dev_bypass_email, tenant_id)

    if not settings.google_oauth_client_id or not settings.google_oauth_redirect_uri:
        return JSONResponse({"error": "Google OAuth is not configured on the server"}, status_code=500)

    state = secrets.token_hex(24)
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )

    response = RedirectResponse(auth_url)
    response.set_cookie(
        STATE_COOKIE_NAME,
        state,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=STATE_MAX_AGE_SECONDS,
        path="/api/auth/google",
    )
    return response


def _error_redirect(reason: str) -> RedirectResponse:
    response = RedirectResponse(f"/login?error={reason}")
    response.delete_cookie(STATE_COOKIE_NAME, path="/api/auth/google")
    return response


@router.get("/api/auth/google/callback", include_in_schema=False)
def google_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    oauth_state: str | None = Cookie(None, alias=STATE_COOKIE_NAME),
):
    """Google's OAuth redirect target. No `next`/redirect-target query param
    is ever honored here -- the post-login destination is always "/",
    closing off any open-redirect vector through this endpoint."""
    if not code or not state or not oauth_state or state != oauth_state:
        return _error_redirect("state")

    settings = get_settings()
    if not all(
        [
            settings.google_oauth_client_id,
            settings.google_oauth_client_secret,
            settings.google_oauth_redirect_uri,
            settings.session_secret,
        ]
    ):
        return _error_redirect("config")

    try:
        token_response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "code": code,
                "redirect_uri": settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10.0,
        )
        token_body = token_response.json()
        if token_response.status_code != 200 or not token_body.get("access_token"):
            return _error_redirect("token")
        access_token = token_body["access_token"]
    except (httpx.HTTPError, ValueError):
        return _error_redirect("token")

    try:
        userinfo_response = httpx.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        if userinfo_response.status_code != 200:
            return _error_redirect("userinfo")
        userinfo = userinfo_response.json()
    except (httpx.HTTPError, ValueError):
        return _error_redirect("userinfo")

    email = userinfo.get("email")
    if not email or not userinfo.get("email_verified"):
        return _error_redirect("unverified")

    try:
        tenant_id = resolve_or_create_tenant_by_email(email, userinfo.get("name"), get_supabase_client())
    except Exception:
        logger.exception("Failed to resolve or create tenant for email %s", email)
        return _error_redirect("tenant")

    response = _issue_session_redirect(email, tenant_id)
    response.delete_cookie(STATE_COOKIE_NAME, path="/api/auth/google")
    return response


@router.post("/api/auth/logout", include_in_schema=False)
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@router.get("/api/auth/me", include_in_schema=False)
def get_current_session_user(session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME)) -> dict:
    """Only ever returns an email for the Google-OAuth web-login path -- a
    Telegram Mini App session has no session cookie at all, so this
    correctly reports {"email": null} there and the frontend hides the
    account menu (Telegram already shows the user's own identity via its
    own chrome)."""
    if session_token is None:
        return {"email": None}

    settings = get_settings()
    if not settings.session_secret:
        return {"email": None}

    payload = verify_session_token(session_token, settings.session_secret)
    return {"email": payload["email"] if payload else None}
