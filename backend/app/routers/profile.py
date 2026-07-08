from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_tenant_id
from app.db import get_supabase_client

router = APIRouter()


class ProfileUpdatePayload(BaseModel):
    updates: dict[str, str]


@router.post("/api/profile")
def save_profile(
    payload: ProfileUpdatePayload, tenant_id: str = Depends(get_current_tenant_id)
) -> dict:
    profile_text = "\n".join(
        f"{key}: {value}" for key, value in payload.updates.items() if value
    )

    client = get_supabase_client()
    response = (
        client.table("company_profile")
        .select("id")
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )

    if response.data:
        client.table("company_profile").update(
            {
                "profile_text": profile_text,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("tenant_id", tenant_id).execute()
    else:
        client.table("company_profile").insert(
            {"tenant_id": tenant_id, "profile_text": profile_text}
        ).execute()

    return {"success": True}


@router.get("/api/profile")
def get_profile(tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    response = (
        client.table("company_profile")
        .select("profile_text")
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    rows = response.data
    return {"profile_text": rows[0]["profile_text"] if rows else None}
