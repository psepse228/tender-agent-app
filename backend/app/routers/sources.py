from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.auth.dependencies import get_current_tenant_id
from app.db import get_supabase_client

router = APIRouter()


class AddSourcePayload(BaseModel):
    name: str
    url: str

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name cannot be empty")
        return value.strip()

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return value


@router.get("/api/sources")
def list_sources(tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    response = (
        client.table("tenant_sources")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"sources": response.data or []}


@router.post("/api/sources")
def add_source(payload: AddSourcePayload, tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    created = (
        client.table("tenant_sources")
        .insert({"tenant_id": tenant_id, "name": payload.name, "url": payload.url})
        .execute()
    )
    return {"source": created.data[0]}


@router.delete("/api/sources/{source_id}")
def remove_source(source_id: str, tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    client.table("tenant_sources").delete().eq("id", source_id).eq("tenant_id", tenant_id).execute()
    return {"ok": True}
