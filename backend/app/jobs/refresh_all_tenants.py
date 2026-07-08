import logging

from app.db import get_supabase_client
from app.scraping.pipeline import refresh_tenant

logger = logging.getLogger(__name__)


def run() -> None:
    client = get_supabase_client()
    response = client.table("tenants").select("id").execute()
    tenant_ids = [row["id"] for row in response.data or []]

    for tenant_id in tenant_ids:
        try:
            refresh_tenant(tenant_id, client)
            logger.info("Refreshed tenant %s", tenant_id)
        except Exception:
            logger.exception("Refresh failed for tenant %s", tenant_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
