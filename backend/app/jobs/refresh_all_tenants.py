import logging

from app.db import get_supabase_client
from app.scraping.pipeline import refresh_tenant

logger = logging.getLogger(__name__)


def _get_active_tenant_ids(client) -> list[str]:
    """Skips two real categories of pure waste (found 2026-07-25 auditing
    real OpenAI cost -- Tender Agent was ~97% of all three products'
    combined spend): internal test fixtures, and self-serve signups that
    never finished onboarding. Neither can ever produce a meaningful match,
    so scoring real scraped content against them every cron cycle burns
    real money for nothing.

    - owner_email IS NULL -> not a real Google self-serve signup (a manually
      seeded test tenant like "Beta Test").
    - No company_profile row / empty profile_text -> signed up but never
      described their business, so get_units-style matching has nothing
      real to score against.

    Deliberately NOT a hardcoded id allowlist: any *new* real signup that
    finishes onboarding (real email + real profile) is picked up
    automatically next cron run, same as today's real tenants were."""
    tenants = client.table("tenants").select("id, owner_email").execute().data or []
    profiles = client.table("company_profile").select("tenant_id, profile_text").execute().data or []
    has_real_profile = {p["tenant_id"] for p in profiles if (p.get("profile_text") or "").strip()}

    return [
        t["id"] for t in tenants
        if t.get("owner_email") and t["id"] in has_real_profile
    ]


def run() -> None:
    client = get_supabase_client()
    tenant_ids = _get_active_tenant_ids(client)

    for tenant_id in tenant_ids:
        try:
            refresh_tenant(tenant_id, client)
            logger.info("Refreshed tenant %s", tenant_id)
        except Exception:
            logger.exception("Refresh failed for tenant %s", tenant_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
