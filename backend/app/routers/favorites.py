from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_tenant_id
from app.chat.favorite_chat import generate_reply
from app.db import get_supabase_client

router = APIRouter()

_COPY_FIELDS = [
    "title",
    "organization",
    "budget",
    "deadline",
    "source",
    "platform",
    "match_percent",
    "recommendation",
    "compliance",
    "financial",
    "feasibility",
    "win_chance",
    "why_participate",
    "risks",
    "action_plan",
    "risk_level",
    "profit_potential",
]


class AddFavoritePayload(BaseModel):
    tender_id: str


@router.get("/api/favorites")
def list_favorites(tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    response = (
        client.table("favorite_tenders")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("match_percent", desc=True)
        .execute()
    )
    return {"favorites": response.data or []}


@router.post("/api/favorites")
def add_favorite(payload: AddFavoritePayload, tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()

    tender_response = (
        client.table("tenders")
        .select("*")
        .eq("id", payload.tender_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    rows = tender_response.data
    if not rows:
        raise HTTPException(status_code=404, detail="Tender not found")
    tender = rows[0]

    # A tender's own row gets a fresh id every refresh, so there's no stable
    # foreign key to dedupe against across refreshes -- title+organization is
    # the closest available proxy for "this is the same real-world tender".
    existing = (
        client.table("favorite_tenders")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("title", tender.get("title") or "")
        .eq("organization", tender.get("organization") or "")
        .limit(1)
        .execute()
    )
    if existing.data:
        return {"favorite_id": existing.data[0]["id"], "already_existed": True}

    row = {field: tender.get(field) for field in _COPY_FIELDS}
    row["tenant_id"] = tenant_id
    created = client.table("favorite_tenders").insert(row).execute()
    return {"favorite_id": created.data[0]["id"], "already_existed": False}


@router.delete("/api/favorites/{favorite_id}")
def remove_favorite(favorite_id: str, tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    client.table("favorite_tenders").delete().eq("id", favorite_id).eq("tenant_id", tenant_id).execute()
    return {"ok": True}


def _get_owned_favorite(favorite_id: str, tenant_id: str, client) -> dict:
    response = (
        client.table("favorite_tenders")
        .select("*")
        .eq("id", favorite_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    rows = response.data
    if not rows:
        raise HTTPException(status_code=404, detail="Favorite not found")
    return rows[0]


@router.get("/api/favorites/{favorite_id}/chat")
def get_favorite_chat_history(favorite_id: str, tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    _get_owned_favorite(favorite_id, tenant_id, client)

    response = (
        client.table("favorite_chat_messages")
        .select("role,content,created_at")
        .eq("favorite_id", favorite_id)
        .order("created_at")
        .execute()
    )
    return {"messages": response.data or []}


class FavoriteChatMessagePayload(BaseModel):
    message: str


@router.post("/api/favorites/{favorite_id}/chat")
def send_favorite_chat_message(
    favorite_id: str,
    payload: FavoriteChatMessagePayload,
    tenant_id: str = Depends(get_current_tenant_id),
) -> dict:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    client = get_supabase_client()
    tender = _get_owned_favorite(favorite_id, tenant_id, client)

    client.table("favorite_chat_messages").insert(
        {"favorite_id": favorite_id, "tenant_id": tenant_id, "role": "client", "content": message}
    ).execute()

    history_response = (
        client.table("favorite_chat_messages")
        .select("role,content")
        .eq("favorite_id", favorite_id)
        .order("created_at")
        .execute()
    )
    conversation = history_response.data or []

    profile_response = (
        client.table("company_profile").select("profile_text").eq("tenant_id", tenant_id).limit(1).execute()
    )
    profile_rows = profile_response.data
    profile_text = profile_rows[0]["profile_text"] if profile_rows else ""

    reply = generate_reply(conversation, tender, profile_text)

    client.table("favorite_chat_messages").insert(
        {"favorite_id": favorite_id, "tenant_id": tenant_id, "role": "bot", "content": reply}
    ).execute()

    return {"reply": reply}
