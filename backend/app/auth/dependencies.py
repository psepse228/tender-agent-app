import json

from fastapi import Header, HTTPException

from app.auth.telegram import InitDataError, validate_init_data
from app.config import get_settings
from app.db import get_supabase_client


async def get_current_tenant_id(authorization: str = Header(...)) -> str:
    if not authorization.startswith("tma "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header must use the 'tma <initData>' scheme",
        )

    init_data = authorization.removeprefix("tma ")
    settings = get_settings()

    try:
        pairs = validate_init_data(init_data, settings.telegram_bot_token)
    except InitDataError as e:
        raise HTTPException(status_code=401, detail=str(e))

    user = json.loads(pairs["user"])
    telegram_user_id = user["id"]

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
