from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_tenant_id
from app.db import get_supabase_client

router = APIRouter()


def _count(client, table: str, tenant_id: str, **filters: str) -> int:
    query = client.table(table).select("id", count="exact").eq("tenant_id", tenant_id)
    for column, value in filters.items():
        query = query.eq(column, value)
    return query.limit(1).execute().count or 0


@router.get("/api/stats")
def get_stats(tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    """Aggregate usage numbers for this tenant -- real product usage, not
    fabricated, for the owner's own visibility and for pulling real numbers
    when talking to investors/clients about what the product actually does."""
    client = get_supabase_client()

    tenders_scored = _count(client, "tenders", tenant_id)
    matches_found = _count(client, "tenders", tenant_id, recommendation="Подать заявку")
    worth_considering = _count(client, "tenders", tenant_id, recommendation="Рассмотреть")
    favorites_saved = _count(client, "favorite_tenders", tenant_id)
    profile_chat_messages = _count(client, "profile_chat_messages", tenant_id)
    favorite_chat_messages = _count(client, "favorite_chat_messages", tenant_id)

    tenant_row = (
        client.table("tenants")
        .select("last_refresh_at,subscription_status")
        .eq("id", tenant_id)
        .limit(1)
        .execute()
        .data
    )
    last_refresh_at = tenant_row[0]["last_refresh_at"] if tenant_row else None
    # v1 billing has no payment processor -- this is a manually-managed lever
    # (the owner flips it after chasing an unpaid invoice), surfaced here so
    # the frontend can show a blocking notice. Fails open to "active" if the
    # row lookup comes back empty, same reasoning as last_refresh_at above:
    # a lookup hiccup should never look identical to a real suspension.
    subscription_status = tenant_row[0].get("subscription_status", "active") if tenant_row else "active"

    return {
        "tendersScored": tenders_scored,
        "matchesFound": matches_found,
        "worthConsidering": worth_considering,
        "favoritesSaved": favorites_saved,
        "chatMessages": profile_chat_messages + favorite_chat_messages,
        "lastRefreshAt": last_refresh_at,
        "subscriptionStatus": subscription_status,
    }
