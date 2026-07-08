import time

import httpx

from app.config import get_settings

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
                return data.get("data", {}).get("markdown") or data.get("markdown")
        except httpx.HTTPError:
            pass

        if attempt < MAX_ATTEMPTS - 1:
            sleep(2**attempt)

    return None
