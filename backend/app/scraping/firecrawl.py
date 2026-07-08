import json
import logging
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

FIRECRAWL_URL = "https://api.firecrawl.dev/v1/scrape"
MAX_ATTEMPTS = 3


def scrape_source(source: dict, sleep=time.sleep) -> str | None:
    settings = get_settings()

    for attempt in range(MAX_ATTEMPTS):
        try:
            response = httpx.post(
                FIRECRAWL_URL,
                headers={
                    "Authorization": f"Bearer {settings.firecrawl_api_key}",
                    "Content-Type": "application/json",
                },
                json={"url": source["url"], "formats": ["markdown"], "onlyMainContent": True},
                timeout=25.0,
            )
            if response.status_code == 200:
                data = response.json()
                # Mirrors the existing Node implementation
                # (tender-refresh.js: data.data?.markdown || data.markdown || null) —
                # the flat data.get("markdown") fallback is intentional, not dead code.
                markdown = (data.get("data") or {}).get("markdown") or data.get("markdown")
                if markdown:
                    return markdown
                # A 200 with no usable markdown (e.g. {"success": false, "data": null})
                # is an error-shaped response — treat it the same as a retryable failure.
                logger.warning(
                    "Firecrawl scrape returned no markdown for %s (attempt %s/%s)",
                    source["name"],
                    attempt + 1,
                    MAX_ATTEMPTS,
                )
            else:
                logger.warning(
                    "Firecrawl scrape failed for %s: HTTP %s (attempt %s/%s)",
                    source["name"],
                    response.status_code,
                    attempt + 1,
                    MAX_ATTEMPTS,
                )
        except (httpx.HTTPError, json.JSONDecodeError, AttributeError) as exc:
            logger.warning(
                "Firecrawl scrape error for %s: %s (attempt %s/%s)",
                source["name"],
                exc,
                attempt + 1,
                MAX_ATTEMPTS,
            )

        if attempt < MAX_ATTEMPTS - 1:
            sleep(2**attempt)

    logger.warning("Firecrawl scrape exhausted all %s attempts for %s", MAX_ATTEMPTS, source["name"])
    return None
