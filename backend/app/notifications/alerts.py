import logging

from app.notifications.telegram import send_telegram_message

logger = logging.getLogger(__name__)

HIGH_SCORE_THRESHOLD = 70


def _format_notification(tender: dict) -> str:
    pct = tender.get("matchPercent") or tender.get("match_percent") or 0
    lines = [
        f"\U0001f3af Найден тендер с высоким соответствием: {pct}%",
        tender.get("title") or "Без названия",
    ]
    if tender.get("organization"):
        lines.append(tender["organization"])
    if tender.get("budget"):
        lines.append(f"\U0001f4b0 {tender['budget']}")
    if tender.get("deadline"):
        lines.append(f"\U0001f4c5 до {tender['deadline']}")
    source = tender.get("source")
    if source and source.startswith("http"):
        lines.append(source)
    return "\n".join(lines)


def notify_high_scoring_tenders(tenant_id: str, tenders: list[dict], client) -> None:
    """Sends a Telegram alert the first time a tender scores >= 70% for this
    tenant. Dedupes against `notified_tenders` by title+organization (the
    same proxy-identity approach favorites uses) so the same tender
    resurfacing on a later refresh doesn't spam a fresh alert every day.
    Only tenants with a Telegram-linked user get notified -- there's no
    equivalent contact channel for a Google-OAuth-only signup yet."""
    high_scorers = [t for t in tenders if (t.get("matchPercent") or 0) >= HIGH_SCORE_THRESHOLD]
    if not high_scorers:
        return

    users_response = (
        client.table("tenant_users").select("telegram_user_id").eq("tenant_id", tenant_id).execute()
    )
    chat_ids = [row["telegram_user_id"] for row in (users_response.data or [])]
    if not chat_ids:
        return

    for tender in high_scorers:
        title = tender.get("title") or ""
        organization = tender.get("organization") or ""

        existing = (
            client.table("notified_tenders")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("title", title)
            .eq("organization", organization)
            .limit(1)
            .execute()
        )
        if existing.data:
            continue

        text = _format_notification(tender)
        for chat_id in chat_ids:
            send_telegram_message(chat_id, text)

        try:
            client.table("notified_tenders").insert(
                {"tenant_id": tenant_id, "title": title, "organization": organization}
            ).execute()
        except Exception:
            # Unique-violation race (two refreshes overlapping) is harmless
            # here -- worst case a duplicate alert on a rare overlap, not
            # worth failing the refresh over.
            logger.exception("Failed to record notified_tenders row for tenant %s", tenant_id)
