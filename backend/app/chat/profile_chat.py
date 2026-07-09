import json

from openai import OpenAI

from app.config import get_settings

MAX_HISTORY_MESSAGES = 20

SYSTEM_PROMPT_TEMPLATE = """You are a friendly assistant helping a company in Tashkent, Uzbekistan set up their tender-matching profile.

Current profile:
{profile_text}

Talk with the client conversationally to understand their business, services, experience, and what kinds of tenders they're looking for. After each message, update the profile to reflect everything learned so far -- a clear, well-organized free-text summary an AI can use later to score tenders for relevance to this company. Always preserve information from the current profile the client hasn't contradicted. Keep profile_text focused and well-organized rather than letting it grow indefinitely -- summarize and consolidate rather than appending verbatim.

Return ONLY valid JSON: {{ "reply": "your conversational reply in Russian", "profile_text": "the full updated profile text" }}

If the client hasn't shared much yet, keep profile_text close to what it was, and use reply to ask a helpful follow-up question."""


def generate_reply(conversation: list[dict], profile_text: str, client=None) -> dict:
    if client is None:
        client = OpenAI(api_key=get_settings().openai_api_key)

    truncated_conversation = conversation[-MAX_HISTORY_MESSAGES:]
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        profile_text=profile_text or "No profile configured yet."
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
        max_tokens=2500,
        temperature=0.4,
    )

    parsed = json.loads(response.choices[0].message.content)
    return {"reply": parsed["reply"], "profile_text": parsed["profile_text"]}
