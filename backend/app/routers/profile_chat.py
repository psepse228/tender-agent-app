from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_tenant_id
from app.chat.profile_chat import generate_reply
from app.chat.rate_limit import enforce_chat_rate_limit
from app.db import get_supabase_client

router = APIRouter()


class ChatMessagePayload(BaseModel):
    message: str


@router.get("/api/profile-chat")
def get_chat_history(tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    response = (
        client.table("profile_chat_messages")
        .select("role,content,created_at")
        .eq("tenant_id", tenant_id)
        .order("created_at")
        .execute()
    )
    return {"messages": response.data or []}


@router.post("/api/profile-chat")
def send_chat_message(
    payload: ChatMessagePayload, tenant_id: str = Depends(get_current_tenant_id)
) -> dict:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    client = get_supabase_client()
    enforce_chat_rate_limit("profile_chat_messages", tenant_id, {}, client)

    client.table("profile_chat_messages").insert(
        {"tenant_id": tenant_id, "role": "client", "content": message}
    ).execute()

    history_response = (
        client.table("profile_chat_messages")
        .select("role,content")
        .eq("tenant_id", tenant_id)
        .order("created_at")
        .execute()
    )
    conversation = history_response.data or []

    profile_response = (
        client.table("company_profile")
        .select("profile_text")
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    profile_rows = profile_response.data
    current_profile_text = profile_rows[0]["profile_text"] if profile_rows else ""

    result = generate_reply(conversation, current_profile_text)

    client.table("profile_chat_messages").insert(
        {"tenant_id": tenant_id, "role": "bot", "content": result["reply"]}
    ).execute()

    client.table("company_profile").upsert(
        {"tenant_id": tenant_id, "profile_text": result["profile_text"]},
        on_conflict="tenant_id",
    ).execute()

    return {"reply": result["reply"], "profile_text": result["profile_text"]}
