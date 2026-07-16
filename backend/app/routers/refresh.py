from datetime import datetime, timezone

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
    client = get_supabase_client()
    response = (
        client.table("tenants")
        .select("last_refresh_at")
        .eq("id", tenant_id)
        .limit(1)
        .execute()
    )
    rows = response.data
    last_refresh_at = rows[0]["last_refresh_at"] if rows else None

    if last_refresh_at:
        elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(last_refresh_at)
        if elapsed.total_seconds() < COOLDOWN_SECONDS:
            raise HTTPException(
                status_code=429, detail="Refresh is on cooldown, try again shortly"
            )

    return refresh_tenant(tenant_id, client)
