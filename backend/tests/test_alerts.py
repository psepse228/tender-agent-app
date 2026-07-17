from types import SimpleNamespace

from app.notifications import alerts

TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"


class _FakeTable:
    def __init__(self, name, store):
        self.name = name
        self.store = store
        self._filters = {}
        self._pending = None

    def select(self, *_a, **_k):
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, row):
        self._pending = ("insert", row)
        return self

    def execute(self):
        if self._pending:
            op, payload = self._pending
            self._pending = None
            if op == "insert":
                self.store.setdefault(self.name, []).append(payload)
            return SimpleNamespace(data=None)

        rows = [
            r for r in self.store.get(self.name, []) if all(r.get(k) == v for k, v in self._filters.items())
        ]
        return SimpleNamespace(data=rows)


class _FakeClient:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _FakeTable(name, self.store)


def _tender(**overrides):
    base = {"title": "Road repair", "organization": "City Council", "matchPercent": 80}
    base.update(overrides)
    return base


def test_sends_no_notification_when_nothing_scores_high(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "send_telegram_message", lambda chat_id, text: sent.append((chat_id, text)))
    store = {"tenant_users": [{"telegram_user_id": 111}], "notified_tenders": []}

    alerts.notify_high_scoring_tenders(TENANT_ID, [_tender(matchPercent=50)], _FakeClient(store))

    assert sent == []


def test_sends_notification_to_every_linked_telegram_user(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "send_telegram_message", lambda chat_id, text: sent.append((chat_id, text)))
    store = {
        "tenant_users": [
            {"tenant_id": TENANT_ID, "telegram_user_id": 111},
            {"tenant_id": TENANT_ID, "telegram_user_id": 222},
        ],
        "notified_tenders": [],
    }

    alerts.notify_high_scoring_tenders(TENANT_ID, [_tender()], _FakeClient(store))

    assert {chat_id for chat_id, _ in sent} == {111, 222}
    assert len(store["notified_tenders"]) == 1


def test_does_not_notify_when_tenant_has_no_linked_telegram_user(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "send_telegram_message", lambda chat_id, text: sent.append((chat_id, text)))
    store = {"tenant_users": [], "notified_tenders": []}

    alerts.notify_high_scoring_tenders(TENANT_ID, [_tender()], _FakeClient(store))

    assert sent == []


def test_does_not_renotify_the_same_tender_twice(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "send_telegram_message", lambda chat_id, text: sent.append((chat_id, text)))
    store = {
        "tenant_users": [{"tenant_id": TENANT_ID, "telegram_user_id": 111}],
        "notified_tenders": [
            {"tenant_id": TENANT_ID, "title": "Road repair", "organization": "City Council"}
        ],
    }

    alerts.notify_high_scoring_tenders(TENANT_ID, [_tender()], _FakeClient(store))

    assert sent == []


def test_notifies_for_a_different_tender_even_if_another_was_already_notified(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "send_telegram_message", lambda chat_id, text: sent.append((chat_id, text)))
    store = {
        "tenant_users": [{"tenant_id": TENANT_ID, "telegram_user_id": 111}],
        "notified_tenders": [
            {"tenant_id": TENANT_ID, "title": "Road repair", "organization": "City Council"}
        ],
    }

    alerts.notify_high_scoring_tenders(
        TENANT_ID, [_tender(title="New bridge", organization="Ministry")], _FakeClient(store)
    )

    assert len(sent) == 1


def test_notification_text_includes_key_tender_details():
    text = alerts._format_notification(
        {
            "title": "Road repair",
            "organization": "City Council",
            "matchPercent": 82,
            "budget": "1 000 000 UZS",
            "deadline": "01.08.2026",
            "source": "https://example.com/lot/1",
        }
    )

    assert "82%" in text
    assert "Road repair" in text
    assert "City Council" in text
    assert "1 000 000 UZS" in text
    assert "01.08.2026" in text
    assert "https://example.com/lot/1" in text
