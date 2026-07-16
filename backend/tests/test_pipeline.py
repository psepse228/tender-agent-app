from types import SimpleNamespace

from app.scraping import pipeline
from app.scraping.pipeline import _process_source, get_refresh_progress, refresh_tenant

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

    def delete(self):
        self._pending = ("delete", None)
        return self

    def insert(self, rows):
        self._pending = ("insert", rows)
        return self

    def update(self, values):
        self._pending = ("update", values)
        return self

    def execute(self):
        if self._pending:
            op, payload = self._pending
            if op == "delete":
                self.store[self.name] = [
                    r
                    for r in self.store.get(self.name, [])
                    if not all(r.get(k) == v for k, v in self._filters.items())
                ]
            elif op == "insert":
                self.store.setdefault(self.name, []).extend(payload)
            elif op == "update":
                for row in self.store.get(self.name, []):
                    if all(row.get(k) == v for k, v in self._filters.items()):
                        row.update(payload)
            return SimpleNamespace(data=None)

        rows = [
            r
            for r in self.store.get(self.name, [])
            if all(r.get(k) == v for k, v in self._filters.items())
        ]
        return SimpleNamespace(data=rows)


class _FakeClient:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _FakeTable(name, self.store)


def test_uses_configured_profile_text(monkeypatch):
    store = {
        "company_profile": [{"tenant_id": TENANT_ID, "profile_text": "We build roads."}],
        "tenants": [{"id": TENANT_ID}],
        "tenders": [],
    }
    seen_profiles = []
    monkeypatch.setattr(
        "app.scraping.pipeline._process_source",
        lambda source, profile_text: seen_profiles.append(profile_text)
        or {"name": source["name"], "status": "ok", "tenders": []},
    )

    refresh_tenant(TENANT_ID, _FakeClient(store))

    assert all(p == "We build roads." for p in seen_profiles)


def test_falls_back_to_default_profile_text_when_none_configured(monkeypatch):
    store = {"company_profile": [], "tenants": [{"id": TENANT_ID}], "tenders": []}
    seen_profiles = []
    monkeypatch.setattr(
        "app.scraping.pipeline._process_source",
        lambda source, profile_text: seen_profiles.append(profile_text)
        or {"name": source["name"], "status": "ok", "tenders": []},
    )

    refresh_tenant(TENANT_ID, _FakeClient(store))

    assert all(p == "No profile configured yet." for p in seen_profiles)


def test_replaces_only_this_tenants_tenders(monkeypatch):
    store = {
        "company_profile": [],
        "tenants": [{"id": TENANT_ID}],
        "tenders": [
            {"id": "old-1", "tenant_id": TENANT_ID, "title": "Stale"},
            {"id": "old-2", "tenant_id": "other-tenant", "title": "Someone else's"},
        ],
    }

    def fake_process(source, _profile_text):
        if source["name"] == "eTender UzEx":
            return {
                "name": source["name"],
                "status": "ok",
                "tenders": [{"title": "New from eTender UzEx", "matchPercent": 60}],
            }
        return {"name": source["name"], "status": "ok", "tenders": []}

    monkeypatch.setattr("app.scraping.pipeline._process_source", fake_process)

    result = refresh_tenant(TENANT_ID, _FakeClient(store))

    remaining_titles = {r["title"] for r in store["tenders"]}
    assert "Stale" not in remaining_titles
    assert "Someone else's" in remaining_titles
    assert "New from eTender UzEx" in remaining_titles
    assert result["tenders"][0]["title"] == "New from eTender UzEx"


def test_updates_last_refresh_at(monkeypatch):
    store = {
        "company_profile": [],
        "tenants": [{"id": TENANT_ID, "last_refresh_at": None}],
        "tenders": [],
    }
    monkeypatch.setattr(
        "app.scraping.pipeline._process_source",
        lambda source, _profile_text: {"name": source["name"], "status": "ok", "tenders": []},
    )

    refresh_tenant(TENANT_ID, _FakeClient(store))

    assert store["tenants"][0]["last_refresh_at"] is not None


def test_reports_per_source_status(monkeypatch):
    store = {"company_profile": [], "tenants": [{"id": TENANT_ID}], "tenders": []}

    def fake_process(source, _profile_text):
        if source["name"] == "BicoTender":
            return {"name": source["name"], "status": "failed", "tenders": []}
        return {"name": source["name"], "status": "ok", "tenders": []}

    monkeypatch.setattr("app.scraping.pipeline._process_source", fake_process)

    result = refresh_tenant(TENANT_ID, _FakeClient(store))

    statuses = {s["name"]: s["status"] for s in result["sources_status"]}
    assert statuses["BicoTender"] == "failed"
    assert statuses["eTender UzEx"] == "ok"
    assert len(result["sources_status"]) == 6


def test_process_source_marks_failed_when_scrape_returns_none(monkeypatch):
    monkeypatch.setattr("app.scraping.pipeline.scrape_source", lambda source: None)

    result = _process_source({"name": "BicoTender", "url": "https://bicotender.ru"}, "profile")

    assert result == {"name": "BicoTender", "status": "failed", "tenders": []}


def test_process_source_marks_failed_when_scoring_raises(monkeypatch):
    monkeypatch.setattr("app.scraping.pipeline.scrape_source", lambda source: "# markdown")

    def raise_error(*_a, **_k):
        raise ValueError("bad json from model")

    monkeypatch.setattr("app.scraping.pipeline.extract_and_score", raise_error)

    result = _process_source(
        {"name": "eTender UzEx", "url": "https://etender.uzex.uz"}, "profile"
    )

    assert result == {"name": "eTender UzEx", "status": "failed", "tenders": []}


def test_process_source_returns_ok_with_zero_count_when_no_tenders_found(monkeypatch):
    monkeypatch.setattr("app.scraping.pipeline.scrape_source", lambda source: "# markdown")
    monkeypatch.setattr("app.scraping.pipeline.extract_and_score", lambda *a, **k: [])

    result = _process_source(
        {"name": "eTender UzEx", "url": "https://etender.uzex.uz"}, "profile"
    )

    assert result == {"name": "eTender UzEx", "status": "ok", "tenders": []}


def test_coerces_stringified_numeric_fields_before_insert(monkeypatch):
    store = {"company_profile": [], "tenants": [{"id": TENANT_ID}], "tenders": []}

    def fake_process(source, _profile_text):
        if source["name"] == "eTender UzEx":
            return {
                "name": source["name"],
                "status": "ok",
                "tenders": [
                    {
                        "title": "Stringified numbers",
                        "matchPercent": "75",
                        "compliance": "80",
                        "financial": "50",
                        "feasibility": "60",
                        "winChance": "40",
                    }
                ],
            }
        return {"name": source["name"], "status": "ok", "tenders": []}

    monkeypatch.setattr("app.scraping.pipeline._process_source", fake_process)

    refresh_tenant(TENANT_ID, _FakeClient(store))

    row = next(r for r in store["tenders"] if r["title"] == "Stringified numbers")
    assert row["match_percent"] == 75
    assert row["compliance"] == 80
    assert row["financial"] == 50
    assert row["feasibility"] == 60
    assert row["win_chance"] == 40


def test_drops_tenders_with_no_title_before_insert(monkeypatch):
    store = {"company_profile": [], "tenants": [{"id": TENANT_ID}], "tenders": []}

    def fake_process(source, _profile_text):
        if source["name"] == "eTender UzEx":
            return {
                "name": source["name"],
                "status": "ok",
                "tenders": [
                    {"title": "", "matchPercent": 90},
                    {"matchPercent": 90},
                    {"title": "Valid tender", "matchPercent": 90},
                ],
            }
        return {"name": source["name"], "status": "ok", "tenders": []}

    monkeypatch.setattr("app.scraping.pipeline._process_source", fake_process)

    result = refresh_tenant(TENANT_ID, _FakeClient(store))

    assert [t["title"] for t in result["tenders"]] == ["Valid tender"]
    assert [r["title"] for r in store["tenders"]] == ["Valid tender"]


def test_reports_no_progress_before_any_refresh_has_run():
    progress = get_refresh_progress("never-refreshed-tenant")

    assert progress == {"total": 6, "done": 0, "sources": [], "running": False}


def test_progress_reaches_all_sources_done_and_not_running_after_refresh(monkeypatch):
    store = {"company_profile": [], "tenants": [{"id": TENANT_ID}], "tenders": []}
    monkeypatch.setattr(
        "app.scraping.pipeline._process_source",
        lambda source, _profile_text: {"name": source["name"], "status": "ok", "tenders": []},
    )

    refresh_tenant(TENANT_ID, _FakeClient(store))

    progress = get_refresh_progress(TENANT_ID)
    assert progress["done"] == 6
    assert progress["total"] == 6
    assert progress["running"] is False
    assert {s["name"] for s in progress["sources"]} == {s["name"] for s in pipeline.SOURCES}
