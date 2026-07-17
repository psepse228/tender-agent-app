import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


def send_telegram_message(chat_id: int, text: str) -> bool:
    """Best-effort send -- never raises. A failed notification should never
    take down a refresh that otherwise succeeded."""
    settings = get_settings()
    try:
        response = httpx.post(
            f"{TELEGRAM_API_BASE}/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10.0,
        )
        if response.status_code != 200:
            logger.warning(
                "Telegram sendMessage failed for chat_id %s: HTTP %s", chat_id, response.status_code
            )
            return False
        return True
    except httpx.HTTPError as exc:
        logger.warning("Telegram sendMessage error for chat_id %s: %s", chat_id, exc)
        return False
