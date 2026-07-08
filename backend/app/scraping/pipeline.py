import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.scraping.firecrawl import scrape_source
from app.scraping.scoring import extract_and_score

logger = logging.getLogger(__name__)

SOURCES = [
    {"name": "eTender UzEx", "url": "https://etender.uzex.uz"},
    {"name": "XT-Xarid", "url": "https://xt-xarid.uz"},
    {"name": "TenderWeek", "url": "https://tenderweek.com"},
    {"name": "ADB", "url": "https://www.adb.org/projects?filter=business_opportunity"},
    {
        "name": "World Bank",
        "url": "https://projects.worldbank.org/en/projects-operations/procurement",
    },
    {"name": "BicoTender", "url": "https://bicotender.ru"},
]


def _load_profile_text(tenant_id: str, client) -> str:
    response = (
        client.table("company_profile")
        .select("profile_text")
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    rows = response.data
    if rows and rows[0].get("profile_text"):
        return rows[0]["profile_text"]
    return "No profile configured yet."


def _process_source(source: dict, profile_text: str) -> dict:
    try:
        markdown = scrape_source(source)
        if markdown is None:
            return {"name": source["name"], "status": "failed", "tenders": []}
        tenders = extract_and_score(markdown, source, profile_text)
        return {"name": source["name"], "status": "ok", "tenders": tenders}
    except Exception:
        logger.exception("Failed to process source %s", source["name"])
        return {"name": source["name"], "status": "failed", "tenders": []}


def _to_number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def _to_row(tender: dict, tenant_id: str) -> dict:
    return {
        "tenant_id": tenant_id,
        "title": tender.get("title") or "",
        "organization": tender.get("organization") or "",
        "budget": tender.get("budget") or "",
        "deadline": tender.get("deadline") or "",
        "source": tender.get("source") or "",
        "platform": tender.get("platform") or "",
        "match_percent": _to_number(tender.get("matchPercent")),
        "recommendation": tender.get("recommendation") or "",
        "compliance": _to_number(tender.get("compliance")),
        "financial": _to_number(tender.get("financial")),
        "feasibility": _to_number(tender.get("feasibility")),
        "win_chance": _to_number(tender.get("winChance")),
        "why_participate": tender.get("whyParticipate") or "",
        "risks": tender.get("risks") or "",
        "action_plan": tender.get("actionPlan") or "",
        "risk_level": tender.get("riskLevel") or "",
        "profit_potential": tender.get("profitPotential") or "",
    }


def refresh_tenant(tenant_id: str, client) -> dict:
    """Shared refresh seam called by `POST /api/refresh` (app/routers/refresh.py) and
    the scheduled cron script (app/jobs/refresh_all_tenants.py).

    Scrapes all sources for the tenant, replaces ALL of its `tenders` rows with
    the fresh results (even clearing them to empty if every source fails), and
    updates `last_refresh_at`. Returns {"tenders": [...], "sources_status": [...]}.
    """
    profile_text = _load_profile_text(tenant_id, client)

    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        results = list(
            pool.map(lambda source: _process_source(source, profile_text), SOURCES)
        )

    tenders = [t for r in results for t in r["tenders"] if t.get("title")]
    sources_status = [
        {"name": r["name"], "status": r["status"], "count": len(r["tenders"])}
        for r in results
    ]

    client.table("tenders").delete().eq("tenant_id", tenant_id).execute()
    if tenders:
        client.table("tenders").insert([_to_row(t, tenant_id) for t in tenders]).execute()
    client.table("tenants").update(
        {"last_refresh_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", tenant_id).execute()

    return {"tenders": tenders, "sources_status": sources_status}
