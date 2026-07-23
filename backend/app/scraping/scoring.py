import json

from openai import OpenAI

from app.config import get_settings

CONTENT_CHAR_LIMIT = 40_000

SYSTEM_PROMPT_TEMPLATE = """You are a tender analyst for a company in Tashkent, Uzbekistan.

Company profile:
{profile_text}

Extract all tenders from the page content and score each for relevance to this company.

Language: this is a Russian-speaking client. Always write "title", "organization",
"whyParticipate", "risks", and "actionPlan" in Russian, translating from the
source language if the source page is in English or another language. Never
leave any of these fields in their original non-Russian language. "budget"
and "deadline" should also be translated/reformatted into Russian
conventions (e.g. a date like "July 15, 2026" becomes "15.07.2026").

Relevance check -- do this BEFORE scoring, not after:
State to yourself, in one sentence, what the tender actually procures (the
real deliverable: a physical good, a specific service, a construction work,
etc.), then check whether the company's profile describes providing that
exact deliverable -- not just a related word. Surface keyword overlap is NOT
relevance. A company that sells two-way radios (рации) does not match a
tender selecting FM broadcast stations, even though both mention "radio" --
one is hardware, the other is media/broadcasting. A furniture retailer does
not match a tender for architectural design services just because both
involve "buildings". When the source text is in a foreign language and you
are translating a term, first confirm which sense of that term the tender
actually means before treating it as a match. If a tender is real but the
company's profile clearly does not offer that deliverable, that is a
genuine mismatch: score compliance low (0-25) and say so plainly in
"whyParticipate" and "risks" -- do not soften this to find a way to include
it. The goal is precision (only real matches score high), not maximizing
how many tenders get a passing score.

Geography: if the company's profile describes operating within a specific
country/region only, and the tender's actual place of performance is
clearly elsewhere with no indication the company could realistically
deliver there, treat that as a real compliance problem -- unless the
company's own described service is inherently international (e.g. it
organizes trips/events abroad, exports goods internationally), in which
case a foreign location can be exactly the match, not a mismatch.

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

Extract up to 30 most relevant tenders -- a listing page routinely shows more
than 10 real tenders, and a low cap was silently discarding tenders that were
already scraped and available. If no tenders found return {{ "tenders": [] }}."""


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
        # Raised alongside the 10->30 tender cap above -- 3000 tokens wasn't
        # enough headroom for 30 fully-detailed tender objects and risked
        # truncating the JSON mid-response.
        max_tokens=8000,
        temperature=0.1,
    )

    parsed = json.loads(response.choices[0].message.content)
    tenders = parsed.get("tenders", [])
    for tender in tenders:
        tender["source"] = tender.get("url") or source["url"]
        tender["platform"] = source["name"]
        _recompute_match_score(tender)
    return tenders


def _to_score(value) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _recompute_match_score(tender: dict) -> None:
    """Recompute matchPercent/recommendation from the sub-scores in code rather
    than trusting the model's own arithmetic, which is unverified and can drift
    across a single completion covering multiple tenders."""
    compliance = _to_score(tender.get("compliance"))
    financial = _to_score(tender.get("financial"))
    feasibility = _to_score(tender.get("feasibility"))
    win_chance = _to_score(tender.get("winChance"))

    match_percent = round(
        compliance * 0.4 + financial * 0.2 + feasibility * 0.25 + win_chance * 0.15
    )
    tender["matchPercent"] = match_percent

    if match_percent >= 70:
        tender["recommendation"] = "Подать заявку"
    elif match_percent >= 40:
        tender["recommendation"] = "Рассмотреть"
    else:
        tender["recommendation"] = "Пропустить"
