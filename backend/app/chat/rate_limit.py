from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

MIN_SECONDS_BETWEEN_MESSAGES = 2
MAX_MESSAGES_PER_DAY = 200


def enforce_chat_rate_limit(table: str, tenant_id: str, filters: dict, client) -> None:
    """Shared guard for both profile-chat and per-tender favorite-chat --
    bounds worst-case OpenAI cost exposure from a scripted spam loop (or a
    compromised session) without getting in the way of a real conversation.

    `filters` scopes the query beyond tenant_id -- e.g. {} for profile chat
    (one thread per tenant) or {"favorite_id": ...} for a specific tender's
    thread, since a tenant can have many of those.
    """
    query = client.table(table).select("created_at").eq("tenant_id", tenant_id).eq("role", "client")
    for column, value in filters.items():
        query = query.eq(column, value)

    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    rows = query.gte("created_at", since).order("created_at", desc=True).execute().data or []

    if len(rows) >= MAX_MESSAGES_PER_DAY:
        raise HTTPException(status_code=429, detail="Daily message limit reached, try again tomorrow")

    if rows:
        last_sent = datetime.fromisoformat(rows[0]["created_at"])
        elapsed = (datetime.now(timezone.utc) - last_sent).total_seconds()
        if elapsed < MIN_SECONDS_BETWEEN_MESSAGES:
            raise HTTPException(status_code=429, detail="Sending messages too quickly, slow down")
