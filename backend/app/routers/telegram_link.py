import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_tenant_id
from app.auth.telegram import InitDataError, validate_init_data
from app.config import get_settings
from app.db import get_supabase_client

router = APIRouter()


class LinkTelegramPayload(BaseModel):
    init_data: str


@router.get("/api/link-telegram")
def get_telegram_link_status(tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    response = client.table("tenant_users").select("id").eq("tenant_id", tenant_id).limit(1).execute()
    return {"linked": bool(response.data)}


@router.post("/api/link-telegram")
def link_telegram(
    payload: LinkTelegramPayload, tenant_id: str = Depends(get_current_tenant_id)
) -> dict:
    """Explicitly links a *verified* Telegram identity to the caller's
    already-authenticated (Google) tenant, purely so notify_high_scoring_tenders
    has somewhere to send alerts -- this is never a login path. `init_data` is
    HMAC-validated the same way the old Telegram auth was, so a client can't
    just claim an arbitrary telegram_user_id belongs to them."""
    settings = get_settings()
    try:
        pairs = validate_init_data(payload.init_data, settings.telegram_bot_token)
    except InitDataError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        user = json.loads(pairs["user"])
        telegram_user_id = user["id"]
    except (KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="invalid user data in initData")

    client = get_supabase_client()

    existing = (
        client.table("tenant_users")
        .select("tenant_id")
        .eq("telegram_user_id", telegram_user_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        if existing.data[0]["tenant_id"] != tenant_id:
            raise HTTPException(
                status_code=409,
                detail="This Telegram account is already linked to a different account",
            )
        return {"linked": True, "already_linked": True}

    client.table("tenant_users").insert(
        {"tenant_id": tenant_id, "telegram_user_id": telegram_user_id}
    ).execute()
    return {"linked": True, "already_linked": False}
