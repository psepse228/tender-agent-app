import logging
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.auth.dependencies import SESSION_COOKIE_NAME, resolve_or_create_tenant_by_email
from app.auth.session import create_session_token, verify_session_token
from app.config import get_settings
from app.db import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()

STATE_COOKIE_NAME = "google_oauth_state"
VIA_COOKIE_NAME = "google_oauth_via"
STATE_MAX_AGE_SECONDS = 5 * 60
SESSION_MAX_AGE_SECONDS = 30 * 24 * 3600

# Public info (a bot's @username is how anyone starts it, not a secret) --
# one-line change if the bot is ever renamed.
TELEGRAM_BOT_USERNAME = "Solura_tenderagenbot"

EXCHANGE_TOKEN_MAX_AGE_SECONDS = 2 * 60

# Google blocks OAuth sign-in from embedded webviews it flags as insecure --
# Telegram's mobile Mini App webview gets flagged this way (desktop's
# doesn't). Fix: escape to the phone's real browser for the Google step
# (see login_page's platform check + Telegram.WebApp.openLink), then hand
# the resulting session back to the Mini App via a one-time exchange token
# carried on a `https://t.me/<bot>?startapp=<token>` deep link, since the
# external browser and the Mini App's embedded webview don't share cookies.
# In-memory and short-lived by design -- a restart just means an in-flight
# login has to be retried, never a security concern.
_pending_exchanges: dict[str, dict] = {}

LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tender Agent — Вход</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
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
  .legal-links { margin-top: 28px; font-size: 11px; color: #64748b; }
  .legal-links a { color: #64748b; text-decoration: underline; }
</style>
</head>
<body>
  <div class="mark">T</div>
  <h1>Tender Agent</h1>
  <p>Войдите, чтобы открыть панель тендеров</p>
  {error_html}
  <a class="google-btn" id="googleBtn" href="/api/auth/google/start">Войти через Google</a>
  <div class="legal-links">
    <a href="/terms">Условия использования</a> · <a href="/privacy">Конфиденциальность</a>
  </div>
  <script>
    // Mobile Telegram's embedded webview gets blocked by Google's OAuth
    // security check; desktop Telegram doesn't. Only mobile needs the
    // escape-to-real-browser + deep-link-back dance.
    if (window.Telegram?.WebApp) {
      Telegram.WebApp.ready();
      const platform = Telegram.WebApp.platform;
      if (platform === 'android' || platform === 'ios') {
        const btn = document.getElementById('googleBtn');
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          // openLink is a native bridge call, not page navigation -- it has
          // no document to resolve a relative path against, so this must be
          // a fully-qualified URL or the native client silently no-ops.
          Telegram.WebApp.openLink(location.origin + '/api/auth/google/start?via=telegram_deeplink');
        });
      }
    }
  </script>
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


def _create_session_cookie_value(email: str, tenant_id: str, picture: str | None) -> str:
    settings = get_settings()
    return create_session_token(
        {
            "email": email,
            "tenantId": tenant_id,
            "picture": picture,
            "exp": time.time() + SESSION_MAX_AGE_SECONDS,
        },
        settings.session_secret,
    )


def _issue_session_redirect(email: str, tenant_id: str, picture: str | None = None) -> RedirectResponse:
    token = _create_session_cookie_value(email, tenant_id, picture)
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
def google_oauth_start(via: str | None = None):
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
    if via == "telegram_deeplink":
        response.set_cookie(
            VIA_COOKIE_NAME,
            "telegram_deeplink",
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
    response.delete_cookie(VIA_COOKIE_NAME, path="/api/auth/google")
    return response


def _prune_expired_exchanges() -> None:
    now = time.time()
    expired = [token for token, data in _pending_exchanges.items() if data["exp"] < now]
    for token in expired:
        del _pending_exchanges[token]


@router.get("/api/auth/google/callback", include_in_schema=False)
def google_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    oauth_state: str | None = Cookie(None, alias=STATE_COOKIE_NAME),
    oauth_via: str | None = Cookie(None, alias=VIA_COOKIE_NAME),
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

    picture = userinfo.get("picture")

    if oauth_via == "telegram_deeplink":
        _prune_expired_exchanges()
        exchange_token = secrets.token_urlsafe(24)
        _pending_exchanges[exchange_token] = {
            "email": email,
            "tenantId": tenant_id,
            "picture": picture,
            "exp": time.time() + EXCHANGE_TOKEN_MAX_AGE_SECONDS,
        }
        response = RedirectResponse(f"https://t.me/{TELEGRAM_BOT_USERNAME}?startapp={exchange_token}")
        response.delete_cookie(STATE_COOKIE_NAME, path="/api/auth/google")
        response.delete_cookie(VIA_COOKIE_NAME, path="/api/auth/google")
        return response

    response = _issue_session_redirect(email, tenant_id, picture)
    response.delete_cookie(STATE_COOKIE_NAME, path="/api/auth/google")
    return response


class ExchangeTokenPayload(BaseModel):
    token: str


@router.post("/api/auth/exchange-token", include_in_schema=False)
def exchange_token(payload: ExchangeTokenPayload):
    """Called from *within* the Mini App's own webview after it reopens via
    the `startapp` deep link -- this is the one request that can actually
    set the session cookie in the Mini App's cookie jar, since it's
    same-origin from inside the app itself."""
    _prune_expired_exchanges()
    data = _pending_exchanges.pop(payload.token, None)
    if data is None:
        return JSONResponse({"ok": False, "error": "invalid or expired token"}, status_code=400)

    token = _create_session_cookie_value(data["email"], data["tenantId"], data["picture"])
    response = JSONResponse({"ok": True})
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
        return {"email": None, "picture": None}

    settings = get_settings()
    if not settings.session_secret:
        return {"email": None, "picture": None}

    payload = verify_session_token(session_token, settings.session_secret)
    if not payload:
        return {"email": None, "picture": None}
    return {"email": payload["email"], "picture": payload.get("picture")}
