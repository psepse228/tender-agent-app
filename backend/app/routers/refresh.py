from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_tenant_id
from app.db import get_supabase_client
from app.scraping.pipeline import get_refresh_progress, refresh_tenant

router = APIRouter()

COOLDOWN_SECONDS = 5 * 60


@router.get("/api/refresh/status")
def refresh_status(tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    return get_refresh_progress(tenant_id)


@router.post("/api/refresh")
def trigger_refresh(tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    """The cooldown claim below is an atomic conditional UPDATE (claim
    succeeds only if last_refresh_at is null or older than the cooldown),
    not a separate read-then-check -- several concurrent POSTs from the same
    tenant used to all read the same stale last_refresh_at and all pass the
    check before any of them had written a new value, letting a burst of
    requests each kick off a full scrape+scoring run (real Firecrawl/GPT-4o
    cost multiplied by however many fired before the first one finished)."""
    client = get_supabase_client()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(seconds=COOLDOWN_SECONDS)).isoformat()

    claim = (
        client.table("tenants")
        .update({"last_refresh_at": now.isoformat()})
        .eq("id", tenant_id)
        .or_(f"last_refresh_at.is.null,last_refresh_at.lt.{cutoff}")
        .execute()
    )
    if not claim.data:
        raise HTTPException(status_code=429, detail="Refresh is on cooldown, try again shortly")

    return refresh_tenant(tenant_id, client)
