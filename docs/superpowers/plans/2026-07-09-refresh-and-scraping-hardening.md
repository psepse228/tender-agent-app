# Refresh Endpoint & Scraping Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tenant-scoped tender refresh pipeline (on-demand endpoint + scheduled cron script) to the Phase 0 FastAPI backend, hardening the existing scraping/scoring logic (bicotender.ru retry, 8,000-char truncation fix) as it's ported from the Node implementation.

**Architecture:** A single orchestration function, `refresh_tenant(tenant_id, client)`, scrapes all 6 sources concurrently via a `ThreadPoolExecutor` (each source wrapped in retry-with-backoff), scores results with GPT-4o, replaces that tenant's `tenders` rows, and updates `tenants.last_refresh_at`. Both an auth-protected `POST /api/refresh` (with a 5-minute cooldown) and a standalone cron script call this same function.

**Tech Stack:** Python 3.12, FastAPI, `httpx` (Firecrawl calls), `openai` SDK (GPT-4o), `supabase-py`, `pytest` + `monkeypatch`.

**Reference spec:** `docs/superpowers/specs/2026-07-09-refresh-and-scraping-hardening-design.md`

**Reference for exact prompt/formula being ported:** `Tender Agent/api/tender-refresh.js` (Node, current production version — do not change its scoring formula or prompt rules, only the 8,000→40,000 char cap).

---

### Task 1: Add `openai` dependency and scaffold the `scraping` package

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/scraping/__init__.py`

- [ ] **Step 1: Add the `openai` package to requirements**

Edit `backend/requirements.txt` to add one line (keep existing lines unchanged):

```
fastapi>=0.115,<1.0
uvicorn[standard]>=0.30,<1.0
pydantic-settings>=2.4,<3.0
supabase>=2.6,<3.0
pytest>=8.0,<9.0
pytest-asyncio>=0.24,<1.0
httpx>=0.27,<1.0
openai>=1.40,<2.0
```

- [ ] **Step 2: Create the empty package file**

Create `backend/app/scraping/__init__.py` with no content (empty file, same as `backend/app/auth/__init__.py`).

- [ ] **Step 3: Install and verify**

Run (from `backend/`, with the project's virtualenv activated):
```bash
pip install -r requirements.txt
python -c "import openai; import app.scraping; print('ok')"
```
Expected: prints `ok` with no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt backend/app/scraping/__init__.py
git commit -m "chore: add openai dependency and scraping package"
```

---

### Task 2: Firecrawl scraping with retry-with-backoff

**Files:**
- Create: `backend/app/scraping/firecrawl.py`
- Test: `backend/tests/test_firecrawl.py`

This fixes the bicotender.ru intermittent Bad Gateway problem: retry up to 3 total attempts, with backoff delays of 1s then 2s between attempts, before giving up and returning `None`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_firecrawl.py`:

```python
import httpx

from app.scraping.firecrawl import scrape_source

SOURCE = {"name": "BicoTender", "url": "https://bicotender.ru"}


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


def test_returns_markdown_on_first_success(monkeypatch):
    monkeypatch.setattr(
        "app.scraping.firecrawl.httpx.post",
        lambda *a, **k: _FakeResponse(200, {"data": {"markdown": "# Tenders"}}),
    )
    sleeps = []

    result = scrape_source(SOURCE, sleep=sleeps.append)

    assert result == "# Tenders"
    assert sleeps == []


def test_retries_on_bad_gateway_then_succeeds(monkeypatch):
    responses = iter(
        [_FakeResponse(502), _FakeResponse(502), _FakeResponse(200, {"data": {"markdown": "ok"}})]
    )
    monkeypatch.setattr("app.scraping.firecrawl.httpx.post", lambda *a, **k: next(responses))
    sleeps = []

    result = scrape_source(SOURCE, sleep=sleeps.append)

    assert result == "ok"
    assert sleeps == [1, 2]


def test_returns_none_after_all_retries_fail(monkeypatch):
    monkeypatch.setattr("app.scraping.firecrawl.httpx.post", lambda *a, **k: _FakeResponse(502))
    sleeps = []

    result = scrape_source(SOURCE, sleep=sleeps.append)

    assert result is None
    assert sleeps == [1, 2]


def test_retries_on_network_error(monkeypatch):
    def raise_error(*_a, **_k):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr("app.scraping.firecrawl.httpx.post", raise_error)
    sleeps = []

    result = scrape_source(SOURCE, sleep=sleeps.append)

    assert result is None
    assert sleeps == [1, 2]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_firecrawl.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.scraping.firecrawl'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/scraping/firecrawl.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_firecrawl.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/scraping/firecrawl.py backend/tests/test_firecrawl.py
git commit -m "feat: add Firecrawl scraping with retry-with-backoff"
```

---

### Task 3: GPT-4o extraction and scoring with raised truncation cap

**Files:**
- Create: `backend/app/scraping/scoring.py`
- Test: `backend/tests/test_scoring.py`

Ports `extractAndScore` from `Tender Agent/api/tender-refresh.js`. Same model, same prompt rules, same scoring formula, same 10-tender cap — only the content truncation limit changes, from 8,000 to 40,000 characters.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_scoring.py`:

```python
import json
from types import SimpleNamespace

import pytest

from app.scraping.scoring import CONTENT_CHAR_LIMIT, extract_and_score

SOURCE = {"name": "eTender UzEx", "url": "https://etender.uzex.uz"}


class _FakeOpenAI:
    def __init__(self, payload):
        self._payload = payload
        self.last_kwargs = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.last_kwargs = kwargs
        message = SimpleNamespace(content=json.dumps(self._payload))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_maps_gpt_response_to_tender_dicts():
    fake_client = _FakeOpenAI(
        {
            "tenders": [
                {
                    "title": "Road repair",
                    "matchPercent": 82,
                    "compliance": 90,
                    "financial": 70,
                    "feasibility": 80,
                    "winChance": 75,
                }
            ]
        }
    )

    result = extract_and_score("some markdown", SOURCE, "We build roads.", client=fake_client)

    assert result[0]["title"] == "Road repair"
    assert result[0]["platform"] == "eTender UzEx"
    assert result[0]["source"] == "https://etender.uzex.uz"


def test_returns_empty_list_when_no_tenders_found():
    fake_client = _FakeOpenAI({"tenders": []})

    result = extract_and_score("some markdown", SOURCE, "We build roads.", client=fake_client)

    assert result == []


def test_truncates_content_before_sending_to_model():
    fake_client = _FakeOpenAI({"tenders": []})
    long_content = "x" * 100_000

    extract_and_score(long_content, SOURCE, "profile", client=fake_client)

    user_message = fake_client.last_kwargs["messages"][1]["content"]
    assert "x" * CONTENT_CHAR_LIMIT in user_message
    assert "x" * (CONTENT_CHAR_LIMIT + 1) not in user_message


def test_uses_source_url_when_tender_has_no_own_url():
    fake_client = _FakeOpenAI({"tenders": [{"title": "T", "matchPercent": 50}]})

    result = extract_and_score("md", SOURCE, "profile", client=fake_client)

    assert result[0]["source"] == SOURCE["url"]


def test_propagates_error_on_malformed_json_response():
    class _BadJSONClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **_kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))])

    with pytest.raises(json.JSONDecodeError):
        extract_and_score("md", SOURCE, "profile", client=_BadJSONClient())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.scraping.scoring'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/scraping/scoring.py`:

```python
import json

from openai import OpenAI

from app.config import get_settings

CONTENT_CHAR_LIMIT = 40_000

SYSTEM_PROMPT_TEMPLATE = """You are a tender analyst for a company in Tashkent, Uzbekistan.

Company profile:
{profile_text}

Extract all tenders from the page content and score each for relevance to this company.

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

Extract up to 10 most relevant tenders. If no tenders found return {{ "tenders": [] }}."""


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
        max_tokens=3000,
        temperature=0.1,
    )

    parsed = json.loads(response.choices[0].message.content)
    tenders = parsed.get("tenders", [])
    for tender in tenders:
        tender["source"] = tender.get("url") or source["url"]
        tender["platform"] = source["name"]
    return tenders
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scoring.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/scraping/scoring.py backend/tests/test_scoring.py
git commit -m "feat: add GPT-4o extraction/scoring with 40,000-char truncation cap"
```

---

### Task 4: Tenant refresh orchestration (`refresh_tenant`)

**Files:**
- Create: `backend/app/scraping/pipeline.py`
- Test: `backend/tests/test_pipeline.py`

The shared function both the on-demand endpoint and the cron script call. Scrapes all 6 sources concurrently via a `ThreadPoolExecutor` (real parallelism for synchronous I/O — `asyncio.gather` would just run these sequentially since `httpx`/`openai` calls are blocking), isolates each source's failure, replaces the tenant's `tenders` rows, and stamps `last_refresh_at`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_pipeline.py`:

```python
from types import SimpleNamespace

from app.scraping.pipeline import _process_source, refresh_tenant

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.scraping.pipeline'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/scraping/pipeline.py`:

```python
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.scraping.firecrawl import scrape_source
from app.scraping.scoring import extract_and_score

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
        return {"name": source["name"], "status": "failed", "tenders": []}


def _to_row(tender: dict, tenant_id: str) -> dict:
    return {
        "tenant_id": tenant_id,
        "title": tender.get("title") or "",
        "organization": tender.get("organization") or "",
        "budget": tender.get("budget") or "",
        "deadline": tender.get("deadline") or "",
        "source": tender.get("source") or "",
        "platform": tender.get("platform") or "",
        "match_percent": tender.get("matchPercent") or 0,
        "recommendation": tender.get("recommendation") or "",
        "compliance": tender.get("compliance") or 0,
        "financial": tender.get("financial") or 0,
        "feasibility": tender.get("feasibility") or 0,
        "win_chance": tender.get("winChance") or 0,
        "why_participate": tender.get("whyParticipate") or "",
        "risks": tender.get("risks") or "",
        "action_plan": tender.get("actionPlan") or "",
        "risk_level": tender.get("riskLevel") or "",
        "profit_potential": tender.get("profitPotential") or "",
    }


def refresh_tenant(tenant_id: str, client) -> dict:
    profile_text = _load_profile_text(tenant_id, client)

    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        results = list(
            pool.map(lambda source: _process_source(source, profile_text), SOURCES)
        )

    tenders = [t for r in results for t in r["tenders"]]
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/scraping/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: add tenant-scoped refresh orchestration"
```

---

### Task 5: Schema migration — `last_refresh_at` column

**Files:**
- Create: `supabase/migrations/0002_add_last_refresh_at.sql`

This column is not yet applied to the live database (Phase 0's migration wasn't either — still blocked on the Postgres connection string). This task just writes the migration file for whenever the connection string is available.

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/0002_add_last_refresh_at.sql`:

```sql
-- 0002_add_last_refresh_at.sql
-- Tracks the last time each tenant's tenders were refreshed, so
-- POST /api/refresh can enforce a cooldown between on-demand refreshes.

alter table tenants add column last_refresh_at timestamptz;
```

- [ ] **Step 2: Commit**

```bash
git add supabase/migrations/0002_add_last_refresh_at.sql
git commit -m "feat: add last_refresh_at migration for refresh cooldown"
```

---

### Task 6: `POST /api/refresh` endpoint with cooldown

**Files:**
- Create: `backend/app/routers/refresh.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_refresh.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_refresh.py`:

```python
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import sign_init_data

BOT_TOKEN = "123456:TEST-fake-token-for-tests"
TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"

client = TestClient(app)


class _FakeQuery:
    def __init__(self, table_data):
        self._table_data = table_data
        self._filters = {}

    def select(self, *_a, **_k):
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        rows = [
            r for r in self._table_data if all(r.get(k) == v for k, v in self._filters.items())
        ]
        return SimpleNamespace(data=rows)


class _FakeClient:
    def __init__(self, table_data):
        self._table_data = table_data

    def table(self, name):
        return _FakeQuery(self._table_data.get(name, []))


def _auth_header(telegram_user_id: int) -> dict[str, str]:
    fields = {"user": f'{{"id":{telegram_user_id}}}', "auth_date": str(int(time.time()))}
    return {"Authorization": f"tma {sign_init_data(fields, BOT_TOKEN)}"}


def test_rejects_refresh_within_cooldown(monkeypatch):
    recent = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    fake_client = _FakeClient(
        {
            "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
            "tenants": [{"id": TENANT_ID, "last_refresh_at": recent}],
        }
    )
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.refresh.get_supabase_client", lambda: fake_client)

    response = client.post("/api/refresh", headers=_auth_header(111))

    assert response.status_code == 429


def test_allows_refresh_after_cooldown_expires(monkeypatch):
    long_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    fake_client = _FakeClient(
        {
            "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
            "tenants": [{"id": TENANT_ID, "last_refresh_at": long_ago}],
        }
    )
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.refresh.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr(
        "app.routers.refresh.refresh_tenant",
        lambda tenant_id, client: {"tenders": [], "sources_status": []},
    )

    response = client.post("/api/refresh", headers=_auth_header(111))

    assert response.status_code == 200
    assert response.json() == {"tenders": [], "sources_status": []}


def test_allows_refresh_when_never_refreshed_before(monkeypatch):
    fake_client = _FakeClient(
        {
            "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
            "tenants": [{"id": TENANT_ID, "last_refresh_at": None}],
        }
    )
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.refresh.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr(
        "app.routers.refresh.refresh_tenant",
        lambda tenant_id, client: {"tenders": [], "sources_status": []},
    )

    response = client.post("/api/refresh", headers=_auth_header(111))

    assert response.status_code == 200


def test_requires_auth():
    response = client.post("/api/refresh")

    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_refresh.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.routers.refresh'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/routers/refresh.py`:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_tenant_id
from app.db import get_supabase_client
from app.scraping.pipeline import refresh_tenant

router = APIRouter()

COOLDOWN_SECONDS = 5 * 60


@router.post("/api/refresh")
def trigger_refresh(tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    response = (
        client.table("tenants")
        .select("last_refresh_at")
        .eq("id", tenant_id)
        .limit(1)
        .execute()
    )
    rows = response.data
    last_refresh_at = rows[0]["last_refresh_at"] if rows else None

    if last_refresh_at:
        elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(last_refresh_at)
        if elapsed.total_seconds() < COOLDOWN_SECONDS:
            raise HTTPException(
                status_code=429, detail="Refresh is on cooldown, try again shortly"
            )

    return refresh_tenant(tenant_id, client)
```

Modify `backend/app/main.py` to register the new router:

```python
from fastapi import FastAPI

from app.routers import health, refresh, tenders

app = FastAPI(title="Tender Agent Backend")
app.include_router(health.router)
app.include_router(tenders.router)
app.include_router(refresh.router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_refresh.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the full suite to confirm nothing else broke**

Run: `pytest -v`
Expected: all tests pass (Phase 0's 20 plus this task's new tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/refresh.py backend/app/main.py backend/tests/test_refresh.py
git commit -m "feat: add POST /api/refresh with cooldown"
```

---

### Task 7: Scheduled refresh script for Railway Cron Job

**Files:**
- Create: `backend/app/jobs/__init__.py`
- Create: `backend/app/jobs/refresh_all_tenants.py`
- Test: `backend/tests/test_refresh_all_tenants_job.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_refresh_all_tenants_job.py`:

```python
from types import SimpleNamespace

from app.jobs.refresh_all_tenants import run


class _FakeTenantsQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_a, **_k):
        return self

    def execute(self):
        return SimpleNamespace(data=self._rows)


class _FakeClient:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        assert name == "tenants"
        return _FakeTenantsQuery(self._rows)


def test_refreshes_every_tenant(monkeypatch):
    fake_client = _FakeClient([{"id": "t1"}, {"id": "t2"}])
    monkeypatch.setattr(
        "app.jobs.refresh_all_tenants.get_supabase_client", lambda: fake_client
    )
    calls = []
    monkeypatch.setattr(
        "app.jobs.refresh_all_tenants.refresh_tenant",
        lambda tenant_id, client: calls.append(tenant_id),
    )

    run()

    assert calls == ["t1", "t2"]


def test_continues_past_a_failing_tenant(monkeypatch):
    fake_client = _FakeClient([{"id": "bad"}, {"id": "good"}])
    monkeypatch.setattr(
        "app.jobs.refresh_all_tenants.get_supabase_client", lambda: fake_client
    )

    def fake_refresh(tenant_id, _client):
        if tenant_id == "bad":
            raise RuntimeError("boom")
        return {"tenders": [], "sources_status": []}

    monkeypatch.setattr("app.jobs.refresh_all_tenants.refresh_tenant", fake_refresh)

    run()  # must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_refresh_all_tenants_job.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.jobs'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/jobs/__init__.py` with no content (empty file).

Create `backend/app/jobs/refresh_all_tenants.py`:

```python
import logging

from app.db import get_supabase_client
from app.scraping.pipeline import refresh_tenant

logging.basicConfig(level=logging.INFO)
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
    run()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_refresh_all_tenants_job.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full suite one more time**

Run: `pytest -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/jobs/__init__.py backend/app/jobs/refresh_all_tenants.py backend/tests/test_refresh_all_tenants_job.py
git commit -m "feat: add standalone cron script for scheduled tenant refresh"
```

---

## After This Plan

Not covered here, and not yet planned:
- Configuring the actual Railway Cron Job (schedule expression, command `python -m app.jobs.refresh_all_tenants`, deploy wiring) — this plan only produces the script; wiring it into Railway's dashboard/config is an operational step outside this codebase.
- Sub-project 2 (frontend auth wiring: `initData` headers on every API call, empty/loading states, surfacing `sources_status` and the 429 cooldown response to the user).
- Sub-project 3 (the profile-setup chatbot).
- Actually applying `0001_multi_tenant_schema.sql` and `0002_add_last_refresh_at.sql` to the live database — still blocked on the Postgres connection string.
