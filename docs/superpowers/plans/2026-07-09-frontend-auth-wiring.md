# Frontend Auth Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing Tender Agent Mini App (`index.html`) to the new multi-tenant Python backend with real Telegram `initData` auth on every call, and give the existing structured Profile form a matching backend endpoint so it keeps working with tenant scoping.

**Architecture:** One new backend router (`POST`/`GET /api/profile`, mirroring the existing `tenders.py`/`refresh.py` pattern), plus in-place edits to `index.html`'s single `<script>` block: a shared `authHeaders()` helper added to every fetch call, endpoint URLs updated to the new paths, a shared snake_case→camelCase normalizer reused by both the load and refresh flows, and a new-tenant empty-state nudge driven by a profile-existence check.

**Tech Stack:** Python 3.12 / FastAPI (backend, TDD via pytest), vanilla JS (frontend, no build step, no test framework — verified manually).

**Reference spec:** `docs/superpowers/specs/2026-07-09-frontend-auth-wiring-design.md`

**Reference for existing patterns:** `backend/app/routers/tenders.py` and `backend/app/routers/refresh.py` (router/auth style), `backend/tests/test_refresh.py` and `backend/tests/test_pipeline.py` (fake-Supabase-client test style), `Tender Agent/api/save-profile.js` (the exact text-joining logic being ported).

---

### Task 1: `POST`/`GET /api/profile` backend endpoints

**Files:**
- Create: `backend/app/routers/profile.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_profile.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_profile.py`:

```python
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import sign_init_data

BOT_TOKEN = "123456:TEST-fake-token-for-tests"
TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"

client = TestClient(app)


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

    def update(self, values):
        self._pending = ("update", values)
        return self

    def execute(self):
        if self._pending:
            op, payload = self._pending
            if op == "insert":
                self.store.setdefault(self.name, []).append(payload)
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


def _auth_header(telegram_user_id: int) -> dict[str, str]:
    fields = {"user": f'{{"id":{telegram_user_id}}}', "auth_date": str(int(time.time()))}
    return {"Authorization": f"tma {sign_init_data(fields, BOT_TOKEN)}"}


def test_creates_profile_when_none_exists(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "company_profile": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile.get_supabase_client", lambda: fake_client)

    response = client.post(
        "/api/profile",
        headers=_auth_header(111),
        json={"updates": {"Company Name": "Acme LLC", "Location": "Tashkent"}},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert len(store["company_profile"]) == 1
    assert store["company_profile"][0]["tenant_id"] == TENANT_ID
    assert "Company Name: Acme LLC" in store["company_profile"][0]["profile_text"]
    assert "Location: Tashkent" in store["company_profile"][0]["profile_text"]


def test_updates_existing_profile(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "company_profile": [{"tenant_id": TENANT_ID, "profile_text": "Old text"}],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile.get_supabase_client", lambda: fake_client)

    response = client.post(
        "/api/profile",
        headers=_auth_header(111),
        json={"updates": {"Company Name": "New Name"}},
    )

    assert response.status_code == 200
    assert len(store["company_profile"]) == 1
    assert store["company_profile"][0]["profile_text"] == "Company Name: New Name"


def test_skips_empty_values(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "company_profile": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile.get_supabase_client", lambda: fake_client)

    response = client.post(
        "/api/profile",
        headers=_auth_header(111),
        json={"updates": {"Company Name": "Acme LLC", "Location": ""}},
    )

    assert response.status_code == 200
    assert store["company_profile"][0]["profile_text"] == "Company Name: Acme LLC"


def test_post_requires_auth():
    response = client.post("/api/profile", json={"updates": {"Company Name": "Acme"}})

    assert response.status_code == 422


def test_get_returns_profile_text_for_caller_tenant(monkeypatch):
    store = {
        "tenant_users": [
            {"telegram_user_id": 111, "tenant_id": TENANT_ID},
            {"telegram_user_id": 222, "tenant_id": "other-tenant"},
        ],
        "company_profile": [
            {"tenant_id": TENANT_ID, "profile_text": "Our profile"},
            {"tenant_id": "other-tenant", "profile_text": "Someone else's profile"},
        ],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile.get_supabase_client", lambda: fake_client)

    response = client.get("/api/profile", headers=_auth_header(111))

    assert response.status_code == 200
    assert response.json() == {"profile_text": "Our profile"}


def test_get_returns_null_when_no_profile_exists(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "company_profile": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile.get_supabase_client", lambda: fake_client)

    response = client.get("/api/profile", headers=_auth_header(111))

    assert response.status_code == 200
    assert response.json() == {"profile_text": None}


def test_get_requires_auth():
    response = client.get("/api/profile")

    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_profile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.routers.profile'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/routers/profile.py`:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_tenant_id
from app.db import get_supabase_client

router = APIRouter()


class ProfileUpdatePayload(BaseModel):
    updates: dict[str, str]


@router.post("/api/profile")
def save_profile(
    payload: ProfileUpdatePayload, tenant_id: str = Depends(get_current_tenant_id)
) -> dict:
    profile_text = "\n".join(
        f"{key}: {value}" for key, value in payload.updates.items() if value
    )

    client = get_supabase_client()
    response = (
        client.table("company_profile")
        .select("id")
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )

    if response.data:
        client.table("company_profile").update(
            {
                "profile_text": profile_text,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("tenant_id", tenant_id).execute()
    else:
        client.table("company_profile").insert(
            {"tenant_id": tenant_id, "profile_text": profile_text}
        ).execute()

    return {"success": True}


@router.get("/api/profile")
def get_profile(tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    response = (
        client.table("company_profile")
        .select("profile_text")
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    rows = response.data
    return {"profile_text": rows[0]["profile_text"] if rows else None}
```

Both route handlers are plain `def`, not `async def` — this codebase has a hard rule against blocking I/O inside async routes (FastAPI/Starlette only threadpool-dispatches fully-sync callables), so this must stay synchronous.

Modify `backend/app/main.py` to register the new router:

```python
from fastapi import FastAPI

from app.routers import health, profile, refresh, tenders

app = FastAPI(title="Tender Agent Backend")
app.include_router(health.router)
app.include_router(tenders.router)
app.include_router(refresh.router)
app.include_router(profile.router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_profile.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Run the full suite to confirm nothing else broke**

Run: `pytest -v`
Expected: all tests pass (55 total: 48 baseline + 7 new)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/profile.py backend/app/main.py backend/tests/test_profile.py
git commit -m "feat: add POST/GET /api/profile"
```

---

### Task 2: Frontend — Tenders screen auth wiring

**Files:**
- Modify: `Tender Agent/index.html`

Wires `loadTenders()` and `refreshTenders()` to the new backend with real auth, adds the shared `authHeaders()`/`normalizeTender()` helpers, and removes the vestigial n8n branch. This task does NOT touch the Profile screen or the empty-state nudge — that's Task 3.

There is no test framework for this file (a static page, no build step). This task is verified manually in a browser instead of via automated tests — see Step 3.

- [ ] **Step 1: Replace the top-of-script constants and add the shared helpers**

Find this block near the top of the `<script>` tag in `index.html`:

```javascript
const GET_URL         = '/api/get-tenders';
const REFRESH_URL     = '/api/tender-refresh';
const PROFILE_URL     = '/api/save-profile';
const N8N_WEBHOOK_URL = '';

let allTenders = [];
let currentFilter = 'all';

if (window.Telegram?.WebApp) { Telegram.WebApp.ready(); Telegram.WebApp.expand(); }
```

Replace it with:

```javascript
const GET_URL     = '/api/tenders';
const REFRESH_URL = '/api/refresh';
const PROFILE_URL = '/api/profile';

let allTenders = [];
let currentFilter = 'all';

if (window.Telegram?.WebApp) { Telegram.WebApp.ready(); Telegram.WebApp.expand(); }

function authHeaders() {
  const initData = window.Telegram?.WebApp?.initData || '';
  return { 'Authorization': 'tma ' + initData };
}

function normalizeTender(t) {
  return {
    ...t,
    matchPercent:    t.matchPercent    ?? t.match_percent    ?? 0,
    winChance:       t.winChance       ?? t.win_chance       ?? 0,
    whyParticipate:  t.whyParticipate  ?? t.why_participate  ?? '',
    actionPlan:      t.actionPlan      ?? t.action_plan      ?? '',
    riskLevel:       t.riskLevel       ?? t.risk_level       ?? '',
    profitPotential: t.profitPotential ?? t.profit_potential ?? '',
  };
}
```

- [ ] **Step 2: Update `loadTenders()` and `refreshTenders()`**

Find `loadTenders()`:

```javascript
async function loadTenders() {
  try {
    const res  = await fetch(GET_URL);
    const data = await res.json();
    const raw  = data.tenders || data;
    allTenders = Array.isArray(raw)
      ? raw.filter(t => t.title && t.title !== 'Без названия' && (t.matchPercent || 0) > 0)
      : [];
    updateStats(allTenders);
    renderCards();
    setTime();
  } catch (e) {
    showToast('Ошибка загрузки');
    document.getElementById('emptyState').classList.add('show');
  } finally {
    setTimeout(() => document.getElementById('loader').classList.add('gone'), 700);
  }
}
```

Replace it with:

```javascript
async function loadTenders() {
  try {
    const res  = await fetch(GET_URL, { headers: authHeaders() });
    const data = await res.json();
    const raw  = data.tenders || data;
    allTenders = Array.isArray(raw)
      ? raw.map(normalizeTender).filter(t => t.title && t.title !== 'Без названия' && (t.matchPercent || 0) > 0)
      : [];
    updateStats(allTenders);
    renderCards();
    setTime();
  } catch (e) {
    showToast('Ошибка загрузки');
    document.getElementById('emptyState').classList.add('show');
  } finally {
    setTimeout(() => document.getElementById('loader').classList.add('gone'), 700);
  }
}
```

(Note: this does not yet call the profile-existence check for the empty-state nudge — that hook is added in Task 3, along with the function it calls.)

Find `refreshTenders()`:

```javascript
async function refreshTenders() {
  const btn = document.getElementById('refreshBtn');
  btn.classList.add('spinning');
  showToast('Ищем тендеры... (1-2 мин)', 120000);
  try {
    const useN8n = N8N_WEBHOOK_URL && !N8N_WEBHOOK_URL.startsWith('YOUR_');
    const url    = useN8n ? N8N_WEBHOOK_URL : REFRESH_URL;
    const ctrl   = new AbortController();
    const timer  = setTimeout(() => ctrl.abort(), useN8n ? 120000 : 60000);
    const res    = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
      signal: ctrl.signal,
    });
    clearTimeout(timer);
    const data = await res.json();
    const raw  = data.tenders || data;
    const normalize = t => ({
      ...t,
      matchPercent:    t.matchPercent    ?? t.match_percent    ?? 0,
      winChance:       t.winChance       ?? t.win_chance       ?? 0,
      whyParticipate:  t.whyParticipate  ?? t.why_participate  ?? '',
      actionPlan:      t.actionPlan      ?? t.action_plan      ?? '',
      riskLevel:       t.riskLevel       ?? t.risk_level       ?? '',
      profitPotential: t.profitPotential ?? t.profit_potential ?? '',
    });
    const tenders = Array.isArray(raw)
      ? raw.map(normalize).filter(t => t.title && t.title !== 'Без названия' && (t.matchPercent || 0) > 0)
      : [];
    if (tenders.length > 0) {
      allTenders = tenders; updateStats(allTenders); renderCards(); setTime();
      showToast('Найдено ' + tenders.length + ' тендеров');
    } else {
      showToast('Новых тендеров не найдено');
    }
  } catch (e) {
    showToast(e.name === 'AbortError' ? 'Превышено время ожидания' : 'Ошибка при обновлении');
  } finally {
    btn.classList.remove('spinning');
  }
}
```

Replace it with:

```javascript
async function refreshTenders() {
  const btn = document.getElementById('refreshBtn');
  btn.classList.add('spinning');
  showToast('Ищем тендеры... (1-2 мин)', 120000);
  try {
    const ctrl  = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 60000);
    const res   = await fetch(REFRESH_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: '{}',
      signal: ctrl.signal,
    });
    clearTimeout(timer);

    if (res.status === 429) {
      showToast('Обновлялось недавно, попробуй чуть позже');
      return;
    }

    const data    = await res.json();
    const raw     = data.tenders || data;
    const tenders = Array.isArray(raw)
      ? raw.map(normalizeTender).filter(t => t.title && t.title !== 'Без названия' && (t.matchPercent || 0) > 0)
      : [];

    const failedSources = (data.sources_status || []).filter(s => s.status === 'failed');
    const failedSuffix  = failedSources.length
      ? ' · ' + failedSources.map(s => s.name).join(', ') + ' недоступен'
      : '';

    if (tenders.length > 0) {
      allTenders = tenders; updateStats(allTenders); renderCards(); setTime();
      showToast('Найдено ' + tenders.length + ' тендеров' + failedSuffix);
    } else {
      showToast('Новых тендеров не найдено' + failedSuffix);
    }
  } catch (e) {
    showToast(e.name === 'AbortError' ? 'Превышено время ожидания' : 'Ошибка при обновлении');
  } finally {
    btn.classList.remove('spinning');
  }
}
```

- [ ] **Step 3: Verify manually in a browser**

Serve the file locally (from the `Tender Agent` repo root):

```bash
py -3 -m http.server 8080
```

Open `http://localhost:8080/index.html` in a browser (Telegram-specific APIs are optional-chained throughout, so it won't crash outside Telegram — `authHeaders()` will just send an empty `initData`). Open DevTools console and run each of the following, confirming the described observation before moving to the next:

**3a. Auth header + snake_case normalization on load:**
```javascript
window.fetch = async (url, opts) => {
  console.log('URL:', url, 'AUTH:', opts?.headers?.Authorization);
  return new Response(JSON.stringify({ tenders: [
    { title: 'Test tender', organization: 'Org', match_percent: 82, recommendation: 'Подать заявку',
      compliance: 90, financial: 70, feasibility: 80, win_chance: 75,
      why_participate: 'x', risks: 'y', action_plan: 'z',
      risk_level: 'Низкий', profit_potential: 'Высокий',
      budget: '1000000', deadline: '2026-08-01', source: 'https://example.com' }
  ] }), { status: 200 });
};
await loadTenders();
```
Expected: console logs `AUTH: tma ` (empty initData outside Telegram, but the `tma ` prefix confirms the header is being sent); one card renders with an 82% score pill; tapping it opens the bottom sheet showing 75% under "Шанс победы" (proving `win_chance` → `winChance` mapped correctly, not just the fields that happened to already match).

**3b. Refresh cooldown (429):**
```javascript
window.fetch = async (url, opts) => {
  if (url.includes('/api/refresh')) return new Response('{}', { status: 429 });
  return new Response(JSON.stringify({ tenders: [] }), { status: 200 });
};
await refreshTenders();
```
Expected: toast reads "Обновлялось недавно, попробуй чуть позже" — not the generic error message.

**3c. Refresh success with a partial source failure:**
```javascript
window.fetch = async (url, opts) => {
  if (url.includes('/api/refresh')) {
    return new Response(JSON.stringify({
      tenders: [{ title: 'New', match_percent: 60, recommendation: 'Рассмотреть' }],
      sources_status: [
        { name: 'BicoTender', status: 'failed', count: 0 },
        { name: 'eTender UzEx', status: 'ok', count: 1 },
      ],
    }), { status: 200 });
  }
  return new Response(JSON.stringify({ tenders: [] }), { status: 200 });
};
await refreshTenders();
```
Expected: toast reads "Найдено 1 тендеров · BicoTender недоступен".

**3d. Refresh success with all sources ok (no failure suffix):**
```javascript
window.fetch = async (url, opts) => {
  if (url.includes('/api/refresh')) {
    return new Response(JSON.stringify({
      tenders: [{ title: 'New', match_percent: 60, recommendation: 'Рассмотреть' }],
      sources_status: [{ name: 'eTender UzEx', status: 'ok', count: 1 }],
    }), { status: 200 });
  }
  return new Response(JSON.stringify({ tenders: [] }), { status: 200 });
};
await refreshTenders();
```
Expected: toast reads "Найдено 1 тендеров" with no " · ... недоступен" suffix.

Report exactly which of 3a-3d were run and what was actually observed (per the spec's testing approach — report what was verified, don't claim untested coverage).

- [ ] **Step 4: Commit**

```bash
git add "Tender Agent/index.html"
git commit -m "feat: wire Tenders screen to new backend with Telegram auth"
```

---

### Task 3: Frontend — Profile screen wiring and new-tenant empty-state nudge

**Files:**
- Modify: `Tender Agent/index.html`

Wires `saveProfile()` to the new endpoint with auth, adds `checkProfileExists()` and hooks it into `loadTenders()`, and adds the empty-state nudge for a tenant with no profile configured yet.

- [ ] **Step 1: Add an `id` to the empty-state text element**

Find this HTML block:

```html
  <div class="cards" id="cardsContainer"></div>
  <div class="empty" id="emptyState">
    <div class="empty-icon">◎</div>
    <div class="empty-text">Тендеров не найдено.<br>Нажми ↻ чтобы запустить поиск.</div>
  </div>
```

Replace it with:

```html
  <div class="cards" id="cardsContainer"></div>
  <div class="empty" id="emptyState">
    <div class="empty-icon">◎</div>
    <div class="empty-text" id="emptyText">Тендеров не найдено.<br>Нажми ↻ чтобы запустить поиск.</div>
  </div>
```

- [ ] **Step 2: Add `checkProfileExists()` and hook it into `loadTenders()`**

Find the constants block you edited in Task 2 (near the top of the `<script>` tag):

```javascript
const GET_URL     = '/api/tenders';
const REFRESH_URL = '/api/refresh';
const PROFILE_URL = '/api/profile';
```

Add two new constants directly below it:

```javascript
const GET_URL     = '/api/tenders';
const REFRESH_URL = '/api/refresh';
const PROFILE_URL = '/api/profile';

const DEFAULT_EMPTY_TEXT = 'Тендеров не найдено.<br>Нажми ↻ чтобы запустить поиск.';
const NUDGE_EMPTY_TEXT   = 'Сначала настрой профиль компании — это поможет AI точнее находить тендеры.<br>Затем нажми ↻ чтобы запустить поиск.';
```

Find `loadTenders()` (as it was left after Task 2):

```javascript
async function loadTenders() {
  try {
    const res  = await fetch(GET_URL, { headers: authHeaders() });
    const data = await res.json();
    const raw  = data.tenders || data;
    allTenders = Array.isArray(raw)
      ? raw.map(normalizeTender).filter(t => t.title && t.title !== 'Без названия' && (t.matchPercent || 0) > 0)
      : [];
    updateStats(allTenders);
    renderCards();
    setTime();
  } catch (e) {
    showToast('Ошибка загрузки');
    document.getElementById('emptyState').classList.add('show');
  } finally {
    setTimeout(() => document.getElementById('loader').classList.add('gone'), 700);
  }
}
```

Replace it with (adds one line calling the new check, only when there are zero tenders):

```javascript
async function loadTenders() {
  try {
    const res  = await fetch(GET_URL, { headers: authHeaders() });
    const data = await res.json();
    const raw  = data.tenders || data;
    allTenders = Array.isArray(raw)
      ? raw.map(normalizeTender).filter(t => t.title && t.title !== 'Без названия' && (t.matchPercent || 0) > 0)
      : [];
    updateStats(allTenders);
    renderCards();
    if (allTenders.length === 0) await checkProfileExists();
    setTime();
  } catch (e) {
    showToast('Ошибка загрузки');
    document.getElementById('emptyState').classList.add('show');
  } finally {
    setTimeout(() => document.getElementById('loader').classList.add('gone'), 700);
  }
}

async function checkProfileExists() {
  const emptyTextEl  = document.getElementById('emptyText');
  const emptyStateEl = document.getElementById('emptyState');
  try {
    const res  = await fetch(PROFILE_URL, { headers: authHeaders() });
    const data = await res.json();
    if (!data.profile_text) {
      emptyTextEl.innerHTML = NUDGE_EMPTY_TEXT;
      emptyStateEl.onclick = () => switchScreen('profile');
      emptyStateEl.style.cursor = 'pointer';
    } else {
      emptyTextEl.innerHTML = DEFAULT_EMPTY_TEXT;
      emptyStateEl.onclick = null;
      emptyStateEl.style.cursor = 'default';
    }
  } catch (e) {
    emptyTextEl.innerHTML = DEFAULT_EMPTY_TEXT;
    emptyStateEl.onclick = null;
    emptyStateEl.style.cursor = 'default';
  }
}
```

`checkProfileExists()` always sets both branches explicitly (nudge vs. default), so re-entering the empty state later (e.g. after a profile gets configured) can't leave a stale nudge/click-handler behind from an earlier visit.

- [ ] **Step 3: Add auth to `saveProfile()`**

Find `saveProfile()`:

```javascript
  try {
    const res  = await fetch(PROFILE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ updates })
    });
```

Replace it with:

```javascript
  try {
    const res  = await fetch(PROFILE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ updates })
    });
```

- [ ] **Step 4: Verify manually in a browser**

Continue from the same local server as Task 2 (`py -3 -m http.server 8080` from the `Tender Agent` repo root, if not already running). Open DevTools console and run each of the following:

**4a. Nudge appears when no profile exists:**
```javascript
window.fetch = async (url, opts) => {
  if (url.includes('/api/tenders')) return new Response(JSON.stringify({ tenders: [] }), { status: 200 });
  if (url.includes('/api/profile') && (!opts || opts.method !== 'POST')) {
    return new Response(JSON.stringify({ profile_text: null }), { status: 200 });
  }
};
await loadTenders();
```
Expected: the empty state shows "Сначала настрой профиль компании..."; clicking anywhere on the empty state switches to the Profile screen (bottom nav highlights "Профиль").

**4b. Default copy shown when a profile already exists:**
```javascript
window.fetch = async (url, opts) => {
  if (url.includes('/api/tenders')) return new Response(JSON.stringify({ tenders: [] }), { status: 200 });
  if (url.includes('/api/profile') && (!opts || opts.method !== 'POST')) {
    return new Response(JSON.stringify({ profile_text: 'Some saved text' }), { status: 200 });
  }
};
await loadTenders();
```
Expected: the empty state shows the original "Тендеров не найдено..." copy; clicking it does nothing (no screen switch).

**4c. Auth header sent on profile save:**
```javascript
window.fetch = async (url, opts) => {
  console.log('SAVE URL:', url, 'AUTH:', opts?.headers?.Authorization, 'BODY:', opts?.body);
  return new Response(JSON.stringify({ success: true }), { status: 200 });
};
document.getElementById('f-company-name').value = 'Acme LLC';
await saveProfile();
```
Expected: console logs `AUTH: tma ` and a body containing `"Company Name":"Acme LLC"`; on-screen status text shows "✓ Профиль сохранён — AI обновит анализ при следующем запуске".

Report exactly which of 4a-4c were run and what was actually observed.

- [ ] **Step 5: Commit**

```bash
git add "Tender Agent/index.html"
git commit -m "feat: wire Profile screen to new backend and add new-tenant empty-state nudge"
```

---

## After This Plan

Not covered here, and not yet planned:
- Sub-project 3: the profile-setup chatbot, which will eventually replace the structured Profile form this plan just wired up.
- Configuring the actual deployment (this plan only edits the static `index.html` — no build/deploy step is part of this plan).
- Applying `0001_multi_tenant_schema.sql` / `0002_add_last_refresh_at.sql` to the live database — still blocked on the Postgres connection string, meaning none of this can be truly end-to-end tested against production Supabase until that's resolved.
