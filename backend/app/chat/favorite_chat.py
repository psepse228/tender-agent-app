import json

from openai import OpenAI

from app.config import get_settings

MAX_HISTORY_MESSAGES = 20

SYSTEM_PROMPT_TEMPLATE = """You are helping a company in Tashkent, Uzbekistan think through a specific tender they've saved to their favorites, so they can review it in more detail before deciding whether to bid.

Company profile:
{profile_text}

Tender details:
Title: {title}
Organization: {organization}
Budget: {budget}
Deadline: {deadline}
AI match score: {match_percent}%
Why participate (from initial AI scoring): {why_participate}
Risks (from initial AI scoring): {risks}
Suggested action plan (from initial AI scoring): {action_plan}

Answer the client's follow-up questions about this specific tender -- requirements, risks, whether to bid, what documents might be needed, how to position their proposal, competitor considerations, etc. Be concrete and reference the tender's actual details above. If something isn't covered by the data you have (e.g. exact document checklists, procurement-office contact details), say so honestly instead of inventing specifics, and suggest checking the original tender source page or contacting the procuring organization directly.

Return ONLY valid JSON: {{ "reply": "your reply in Russian" }}"""


def generate_reply(conversation: list[dict], tender: dict, profile_text: str, client=None) -> str:
    if client is None:
        client = OpenAI(api_key=get_settings().openai_api_key)

    truncated_conversation = conversation[-MAX_HISTORY_MESSAGES:]
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        profile_text=profile_text or "No profile configured yet.",
        title=tender.get("title") or "",
        organization=tender.get("organization") or "",
        budget=tender.get("budget") or "Не указан",
        deadline=tender.get("deadline") or "Не указан",
        match_percent=tender.get("match_percent") or 0,
        why_participate=tender.get("why_participate") or "",
        risks=tender.get("risks") or "",
        action_plan=tender.get("action_plan") or "",
    )

    messages = [{"role": "system", "content": system_prompt}]
    for msg in truncated_conversation:
        if msg["role"] == "bot":
            role = "assistant"
        elif msg["role"] == "client":
            role = "user"
        else:
            raise ValueError(f"unrecognized message role: {msg['role']!r}")
        messages.append({"role": role, "content": msg["content"]})

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=messages,
        max_tokens=1500,
        temperature=0.4,
    )

    parsed = json.loads(response.choices[0].message.content)
    return parsed["reply"]
