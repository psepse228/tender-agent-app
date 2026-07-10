import json
import logging

from fastapi import Header, HTTPException

from app.auth.telegram import InitDataError, validate_init_data
from app.config import get_settings
from app.db import get_supabase_client

logger = logging.getLogger(__name__)


def get_current_tenant_id(authorization: str = Header(...)) -> str:
    if not authorization.startswith("tma "):
        logger.warning(
            "auth rejected: bad scheme, header starts with %r (len=%d)",
            authorization[:10],
            len(authorization),
        )
        raise HTTPException(
            status_code=401,
            detail="Authorization header must use the 'tma <initData>' scheme",
        )

    init_data = authorization.removeprefix("tma ")
    settings = get_settings()

    try:
        pairs = validate_init_data(init_data, settings.telegram_bot_token)
    except InitDataError as e:
        tok = settings.telegram_bot_token
        logger.warning(
            "auth rejected: %s (init_data length=%d, bot_token_len=%d, "
            "stripped_len=%d, has_colon=%s, colon_index=%d)",
            str(e),
            len(init_data),
            len(tok),
            len(tok.strip()),
            ":" in tok,
            tok.find(":"),
        )
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
