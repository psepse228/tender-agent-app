import json

from openai import OpenAI

from app.config import get_settings

CONTENT_CHAR_LIMIT = 40_000

SYSTEM_PROMPT_TEMPLATE = """You are a tender analyst for a company in Tashkent, Uzbekistan.

Company profile:
{profile_text}

Extract all tenders from the page content and score each for relevance to this company.

Scoring rules:
- If budget is missing or unclear -> set "financial" to 40-50 (NEVER 0)
- matchPercent = compliance*0.4 + financial*0.2 + feasibility*0.25 + winChance*0.15
- matchPercent >= 70 -> recommendation = "Подать заявку"
- matchPercent 40-69 -> recommendation = "Рассмотреть"
- matchPercent < 40 -> recommendation = "Пропустить"

Return ONLY valid JSON: {{ "tenders": [ ... ] }}

Each tender object:
{{
  "title": "string",
  "organization": "string",
  "budget": "string or null",
  "deadline": "string or null",
  "url": "string or null",
  "matchPercent": number 0-100,
  "recommendation": "Подать заявку" | "Рассмотреть" | "Пропустить",
  "compliance": number 0-100,
  "financial": number 0-100,
  "feasibility": number 0-100,
  "winChance": number 0-100,
  "whyParticipate": "string",
  "risks": "string",
  "actionPlan": "string",
  "riskLevel": "Низкий" | "Средний" | "Высокий",
  "profitPotential": "Низкий" | "Средний" | "Высокий"
}}

Extract up to 10 most relevant tenders. If no tenders found return {{ "tenders": [] }}."""


def extract_and_score(content: str, source: dict, profile_text: str, client=None) -> list[dict]:
    if client is None:
        client = OpenAI(api_key=get_settings().openai_api_key)

    truncated = content[:CONTENT_CHAR_LIMIT]
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(profile_text=profile_text)

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Platform: {source['name']}\nURL: {source['url']}\n\nContent:\n{truncated}",
            },
        ],
        max_tokens=3000,
        temperature=0.1,
    )

    parsed = json.loads(response.choices[0].message.content)
    tenders = parsed.get("tenders", [])
    for tender in tenders:
        tender["source"] = tender.get("url") or source["url"]
        tender["platform"] = source["name"]
    return tenders
