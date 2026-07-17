from fastapi import Cookie, HTTPException
from postgrest.exceptions import APIError

from app.auth.session import verify_session_token
from app.config import get_settings
from app.db import get_supabase_client

SESSION_COOKIE_NAME = "tender_agent_session"


def get_current_tenant_id(
    session_cookie: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> str:
    """Google login is the only auth path -- a tenant is identified by its
    owner_email, resolved via the `tender_agent_session` cookie set by
    /api/auth/google/callback. This is deliberately the *only* way in: it
    lets a team share one Google account/tenant, which a per-person
    Telegram identity couldn't. (A separate, explicit "connect Telegram"
    step -- see /api/link-telegram -- lets an already-authenticated tenant
    additionally receive Telegram alerts; it is not a login path.)"""
    if session_cookie is None:
        raise HTTPException(status_code=401, detail="not authenticated")

    settings = get_settings()
    if not settings.session_secret:
        raise HTTPException(status_code=401, detail="web login is not configured")

    payload = verify_session_token(session_cookie, settings.session_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")

    return payload["tenantId"]


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
