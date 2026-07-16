import json

from fastapi import Cookie, Header, HTTPException
from postgrest.exceptions import APIError

from app.auth.session import verify_session_token
from app.auth.telegram import InitDataError, validate_init_data
from app.config import get_settings
from app.db import get_supabase_client

SESSION_COOKIE_NAME = "tender_agent_session"


def _tenant_id_from_telegram(authorization: str) -> str:
    init_data = authorization.removeprefix("tma ")
    settings = get_settings()

    try:
        pairs = validate_init_data(init_data, settings.telegram_bot_token)
    except InitDataError as e:
        raise HTTPException(status_code=401, detail=str(e))

    try:
        user = json.loads(pairs["user"])
        telegram_user_id = user["id"]
    except (KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="invalid user data in initData")

    client = get_supabase_client()
    response = (
        client.table("tenant_users")
        .select("tenant_id")
        .eq("telegram_user_id", telegram_user_id)
        .limit(1)
        .execute()
    )
    rows = response.data
    if not rows:
        raise HTTPException(
            status_code=403,
            detail="No tenant registered for this Telegram account",
        )

    return rows[0]["tenant_id"]


def _tenant_id_from_session(session_token: str) -> str:
    settings = get_settings()
    if not settings.session_secret:
        raise HTTPException(status_code=401, detail="web login is not configured")

    payload = verify_session_token(session_token, settings.session_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")

    return payload["tenantId"]


def get_current_tenant_id(
    authorization: str | None = Header(None),
    session_cookie: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> str:
    """Resolves the caller's tenant from either auth path this backend
    supports: the Telegram Mini App's `tma <initData>` header, or the
    `tender_agent_session` cookie set by the Google OAuth web-login flow.
    Both resolve to the same tenants.id -- an existing Telegram tenant and a
    self-serve web signup are treated identically everywhere else."""
    if authorization is not None:
        if not authorization.startswith("tma "):
            raise HTTPException(
                status_code=401,
                detail="Authorization header must use the 'tma <initData>' scheme",
            )
        return _tenant_id_from_telegram(authorization)

    if session_cookie is not None:
        return _tenant_id_from_session(session_cookie)

    raise HTTPException(status_code=401, detail="not authenticated")


def resolve_or_create_tenant_by_email(email: str, name: str | None, client) -> str:
    """Looks up the tenant owned by this Google account's email, creating a
    new tenant on first login -- self-serve signup, no manual tenant_users
    row needed the way the Telegram path still requires."""
    existing = (
        client.table("tenants").select("id").eq("owner_email", email).limit(1).execute()
    )
    if existing.data:
        return existing.data[0]["id"]

    try:
        created = (
            client.table("tenants")
            .insert({"name": (name or "").strip() or email, "owner_email": email})
            .execute()
        )
        return created.data[0]["id"]
    except APIError as exc:
        if exc.code != "23505":
            raise
        # Unique-violation race: another concurrent first-login for the same
        # brand-new email won the insert between our select and insert above.
        reselect = client.table("tenants").select("id").eq("owner_email", email).limit(1).execute()
        if reselect.data:
            return reselect.data[0]["id"]
        raise
