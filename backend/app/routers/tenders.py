from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_tenant_id
from app.db import get_supabase_client

router = APIRouter()


@router.get("/api/tenders")
def list_tenders(tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    response = (
        client.table("tenders")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("match_percent", desc=True)
        .limit(100)
        .execute()
    )
    return {"tenders": response.data or []}
