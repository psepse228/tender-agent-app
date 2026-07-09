# Profile Setup Chatbot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Tender Agent's structured 16-field Profile form with a GPT-4o chat panel that conversationally builds `company_profile.profile_text`.

**Architecture:** A `generate_reply()` module (mirrors `scoring.py`'s pattern) takes the conversation history + current profile text and returns `{"reply", "profile_text"}` in one GPT-4o call (no function-calling). A new router persists every turn to `profile_chat_messages` and upserts `company_profile`. The frontend replaces the Profile screen's form with chat bubbles.

**Tech Stack:** Python 3.12 / FastAPI (backend, TDD via pytest), vanilla JS (frontend, no build step, manual verification).

**Reference spec:** `docs/superpowers/specs/2026-07-09-profile-setup-chatbot-design.md`

**Reference for existing patterns:** `backend/app/scraping/scoring.py` (the `extract_and_score` pattern being mirrored — injectable client, no exception swallowing), `backend/app/routers/profile.py` (upsert pattern, tenant-scoped router style), `backend/tests/test_scoring.py` (fake-OpenAI-client test style).

---

### Task 1: `generate_reply()` chat generation module

**Files:**
- Create: `backend/app/chat/__init__.py`
- Create: `backend/app/chat/profile_chat.py`
- Test: `backend/tests/test_profile_chat_generation.py`

- [ ] **Step 1: Create the empty package file**

Create `backend/app/chat/__init__.py` with no content (empty file, same as `backend/app/scraping/__init__.py`).

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_profile_chat_generation.py`:

```python
import json
from types import SimpleNamespace

import pytest

from app.chat.profile_chat import MAX_HISTORY_MESSAGES, generate_reply


class _FakeOpenAI:
    def __init__(self, payload):
        self._payload = payload
        self.last_kwargs = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.last_kwargs = kwargs
        message = SimpleNamespace(content=json.dumps(self._payload))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_returns_reply_and_profile_text():
    fake_client = _FakeOpenAI({"reply": "Расскажите про вашу компанию", "profile_text": "We build roads."})

    result = generate_reply([{"role": "client", "content": "Hi"}], "", client=fake_client)

    assert result == {"reply": "Расскажите про вашу компанию", "profile_text": "We build roads."}


def test_maps_bot_role_to_assistant_and_client_role_to_user():
    fake_client = _FakeOpenAI({"reply": "ok", "profile_text": "x"})

    generate_reply(
        [
            {"role": "client", "content": "Hi"},
            {"role": "bot", "content": "Hello, tell me about your company"},
            {"role": "client", "content": "We build roads"},
        ],
        "",
        client=fake_client,
    )

    roles = [m["role"] for m in fake_client.last_kwargs["messages"][1:]]
    assert roles == ["user", "assistant", "user"]


def test_truncates_to_last_20_messages():
    fake_client = _FakeOpenAI({"reply": "ok", "profile_text": "x"})
    long_conversation = [{"role": "client", "content": f"msg {i}"} for i in range(30)]

    generate_reply(long_conversation, "", client=fake_client)

    sent_messages = fake_client.last_kwargs["messages"][1:]
    assert len(sent_messages) == MAX_HISTORY_MESSAGES
    assert sent_messages[0]["content"] == "msg 10"
    assert sent_messages[-1]["content"] == "msg 29"


def test_includes_current_profile_text_in_system_prompt():
    fake_client = _FakeOpenAI({"reply": "ok", "profile_text": "x"})

    generate_reply([{"role": "client", "content": "Hi"}], "We build roads.", client=fake_client)

    system_message = fake_client.last_kwargs["messages"][0]["content"]
    assert "We build roads." in system_message


def test_propagates_error_on_malformed_json_response():
    class _BadJSONClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **_kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))])

    with pytest.raises(json.JSONDecodeError):
        generate_reply([{"role": "client", "content": "Hi"}], "", client=_BadJSONClient())


def test_propagates_error_when_response_missing_required_keys():
    fake_client = _FakeOpenAI({"reply": "ok"})  # missing profile_text

    with pytest.raises(KeyError):
        generate_reply([{"role": "client", "content": "Hi"}], "", client=fake_client)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_profile_chat_generation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.chat.profile_chat'`

- [ ] **Step 4: Write the implementation**

Create `backend/app/chat/profile_chat.py`:

```python
import json

from openai import OpenAI

from app.config import get_settings

MAX_HISTORY_MESSAGES = 20

SYSTEM_PROMPT_TEMPLATE = """You are a friendly assistant helping a company in Tashkent, Uzbekistan set up their tender-matching profile.

Current profile:
{profile_text}

Talk with the client conversationally to understand their business, services, experience, and what kinds of tenders they're looking for. After each message, update the profile to reflect everything learned so far -- a clear, well-organized free-text summary an AI can use later to score tenders for relevance to this company. Always preserve information from the current profile the client hasn't contradicted.

Return ONLY valid JSON: {{ "reply": "your conversational reply in Russian", "profile_text": "the full updated profile text" }}

If the client hasn't shared much yet, keep profile_text close to what it was, and use reply to ask a helpful follow-up question."""


def generate_reply(conversation: list[dict], profile_text: str, client=None) -> dict:
    if client is None:
        client = OpenAI(api_key=get_settings().openai_api_key)

    truncated_conversation = conversation[-MAX_HISTORY_MESSAGES:]
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        profile_text=profile_text or "No profile configured yet."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for msg in truncated_conversation:
        role = "assistant" if msg["role"] == "bot" else "user"
        messages.append({"role": role, "content": msg["content"]})

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=messages,
        max_tokens=1500,
        temperature=0.4,
    )

    parsed = json.loads(response.choices[0].message.content)
    return {"reply": parsed["reply"], "profile_text": parsed["profile_text"]}
```

No try/except anywhere in this function, matching `scoring.py`'s `extract_and_score` — errors must propagate uncaught so the caller (a later task) can tell "generation failed" apart from "generation succeeded."

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_profile_chat_generation.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/chat/__init__.py backend/app/chat/profile_chat.py backend/tests/test_profile_chat_generation.py
git commit -m "feat: add GPT-4o profile chat generation module"
```

---

### Task 2: `GET`/`POST /api/profile-chat` endpoints

**Files:**
- Create: `backend/app/routers/profile_chat.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_profile_chat_router.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_profile_chat_router.py`:

```python
import time
from types import SimpleNamespace

import pytest
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
        self._order_by = None
        self._pending = None

    def select(self, *_a, **_k):
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def order(self, column, *_a, **_k):
        self._order_by = column
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, row):
        self._pending = ("insert", row)
        return self

    def upsert(self, row, on_conflict=None):
        self._pending = ("upsert", row)
        return self

    def execute(self):
        if self._pending:
            op, payload = self._pending
            if op == "insert":
                self.store.setdefault(self.name, []).append(payload)
            elif op == "upsert":
                existing = next(
                    (
                        r
                        for r in self.store.get(self.name, [])
                        if r.get("tenant_id") == payload["tenant_id"]
                    ),
                    None,
                )
                if existing:
                    existing.update(payload)
                else:
                    self.store.setdefault(self.name, []).append(payload)
            return SimpleNamespace(data=None)

        rows = [
            r
            for r in self.store.get(self.name, [])
            if all(r.get(k) == v for k, v in self._filters.items())
        ]
        if self._order_by:
            rows = sorted(rows, key=lambda r: r.get(self._order_by, ""))
        return SimpleNamespace(data=rows)


class _FakeClient:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _FakeTable(name, self.store)


def _auth_header(telegram_user_id: int) -> dict[str, str]:
    fields = {"user": f'{{"id":{telegram_user_id}}}', "auth_date": str(int(time.time()))}
    return {"Authorization": f"tma {sign_init_data(fields, BOT_TOKEN)}"}


def test_get_returns_empty_history_for_new_tenant(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "profile_chat_messages": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile_chat.get_supabase_client", lambda: fake_client)

    response = client.get("/api/profile-chat", headers=_auth_header(111))

    assert response.status_code == 200
    assert response.json() == {"messages": []}


def test_get_returns_only_caller_tenants_messages(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "profile_chat_messages": [
            {
                "tenant_id": TENANT_ID,
                "role": "client",
                "content": "Hi",
                "created_at": "2026-07-09T00:00:00Z",
            },
            {
                "tenant_id": "other-tenant",
                "role": "client",
                "content": "Not ours",
                "created_at": "2026-07-09T00:00:01Z",
            },
        ],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile_chat.get_supabase_client", lambda: fake_client)

    response = client.get("/api/profile-chat", headers=_auth_header(111))

    assert response.status_code == 200
    contents = [m["content"] for m in response.json()["messages"]]
    assert contents == ["Hi"]


def test_get_requires_auth():
    response = client.get("/api/profile-chat")

    assert response.status_code == 422


def test_post_persists_client_message_and_bot_reply(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "profile_chat_messages": [],
        "company_profile": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile_chat.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr(
        "app.routers.profile_chat.generate_reply",
        lambda conversation, profile_text: {
            "reply": "Расскажи о компании",
            "profile_text": "We build roads.",
        },
    )

    response = client.post("/api/profile-chat", headers=_auth_header(111), json={"message": "Hi"})

    assert response.status_code == 200
    assert response.json() == {"reply": "Расскажи о компании", "profile_text": "We build roads."}
    roles = [m["role"] for m in store["profile_chat_messages"]]
    assert roles == ["client", "bot"]
    assert store["company_profile"][0]["profile_text"] == "We build roads."


def test_post_persists_client_message_even_if_generation_fails(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "profile_chat_messages": [],
        "company_profile": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile_chat.get_supabase_client", lambda: fake_client)

    def raise_error(conversation, profile_text):
        raise RuntimeError("model call failed")

    monkeypatch.setattr("app.routers.profile_chat.generate_reply", raise_error)

    with pytest.raises(RuntimeError):
        client.post("/api/profile-chat", headers=_auth_header(111), json={"message": "Hi"})

    assert len(store["profile_chat_messages"]) == 1
    assert store["profile_chat_messages"][0]["role"] == "client"


def test_post_rejects_empty_message(monkeypatch):
    store = {
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "profile_chat_messages": [],
        "company_profile": [],
    }
    fake_client = _FakeClient(store)
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.profile_chat.get_supabase_client", lambda: fake_client)

    response = client.post("/api/profile-chat", headers=_auth_header(111), json={"message": "   "})

    assert response.status_code == 400
    assert store["profile_chat_messages"] == []


def test_post_requires_auth():
    response = client.post("/api/profile-chat", json={"message": "Hi"})

    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_profile_chat_router.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.routers.profile_chat'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/routers/profile_chat.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_tenant_id
from app.chat.profile_chat import generate_reply
from app.db import get_supabase_client

router = APIRouter()


class ChatMessagePayload(BaseModel):
    message: str


@router.get("/api/profile-chat")
def get_chat_history(tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    response = (
        client.table("profile_chat_messages")
        .select("role,content,created_at")
        .eq("tenant_id", tenant_id)
        .order("created_at")
        .execute()
    )
    return {"messages": response.data or []}


@router.post("/api/profile-chat")
def send_chat_message(
    payload: ChatMessagePayload, tenant_id: str = Depends(get_current_tenant_id)
) -> dict:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    client = get_supabase_client()

    client.table("profile_chat_messages").insert(
        {"tenant_id": tenant_id, "role": "client", "content": message}
    ).execute()

    history_response = (
        client.table("profile_chat_messages")
        .select("role,content")
        .eq("tenant_id", tenant_id)
        .order("created_at")
        .execute()
    )
    conversation = history_response.data or []

    profile_response = (
        client.table("company_profile")
        .select("profile_text")
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    profile_rows = profile_response.data
    current_profile_text = profile_rows[0]["profile_text"] if profile_rows else ""

    result = generate_reply(conversation, current_profile_text)

    client.table("profile_chat_messages").insert(
        {"tenant_id": tenant_id, "role": "bot", "content": result["reply"]}
    ).execute()

    client.table("company_profile").upsert(
        {"tenant_id": tenant_id, "profile_text": result["profile_text"]},
        on_conflict="tenant_id",
    ).execute()

    return {"reply": result["reply"], "profile_text": result["profile_text"]}
```

Both routes are plain `def`, not `async def` — this codebase's hard rule against blocking I/O inside async routes.

Modify `backend/app/main.py` (read the current file first — it currently registers `health`, `tenders`, `refresh`, `profile`; add `profile_chat` alongside them):

```python
from fastapi import FastAPI

from app.routers import health, profile, profile_chat, refresh, tenders

app = FastAPI(title="Tender Agent Backend")
app.include_router(health.router)
app.include_router(tenders.router)
app.include_router(refresh.router)
app.include_router(profile.router)
app.include_router(profile_chat.router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_profile_chat_router.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Run the full suite to confirm nothing else broke**

Run: `pytest -v`
Expected: all tests pass (68 total: 55 baseline + 6 from Task 1 + 7 from this task)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/profile_chat.py backend/app/main.py backend/tests/test_profile_chat_router.py
git commit -m "feat: add GET/POST /api/profile-chat"
```

---

### Task 3: Frontend — chat panel replaces the structured Profile form

**Files:**
- Modify: `index.html` (at the repo root, NOT inside `backend/`)

Deletes the 16-field form and its CSS/JS, replaces the Profile screen with a chat panel. Does NOT touch `backend/app/routers/profile.py` or the `PROFILE_URL` constant/`checkProfileExists()` in `index.html` — `GET /api/profile` stays in use by the Tenders empty-state nudge.

There is no test framework for this file. Verified manually in a browser — Step 5 is required, not optional.

- [ ] **Step 1: Replace the Profile-screen CSS**

Find this CSS block (search for `/* ─── PROFILE SCREEN ─── */`):

```css
/* ─── PROFILE SCREEN ─── */
.profile-screen { padding: 20px 16px 0; }
.profile-header { margin-bottom: 24px; }
.profile-title {
  font-family: var(--fd); font-size: 24px; font-weight: 800;
  letter-spacing: -.03em; line-height: 1.2; margin-bottom: 6px;
  background: var(--grad); -webkit-background-clip: text;
  -webkit-text-fill-color: transparent; background-clip: text;
  display: inline-block;
}
.profile-sub { font-size: 12px; color: rgba(148,163,184,.55); font-weight: 300; }

.profile-section { margin-bottom: 24px; }
.profile-section-label {
  font-size: 9px; color: var(--cyan); text-transform: uppercase;
  letter-spacing: .2em; margin-bottom: 10px; font-weight: 700;
  display: flex; align-items: center; gap: 8px;
}
.profile-section-label::before { content: ''; width: 18px; height: 1px; background: var(--cyan); }

.field-group { display: flex; flex-direction: column; gap: 7px; }
.field-row {
  background: rgba(255,255,255,.03); border: 1px solid var(--border);
  border-radius: 13px; padding: 12px 14px;
  transition: border-color .2s, box-shadow .2s;
}
.field-row:focus-within {
  border-color: rgba(56,189,248,.35);
  box-shadow: 0 0 0 3px rgba(56,189,248,.06);
}
.field-label {
  font-size: 9px; color: rgba(148,163,184,.5); text-transform: uppercase;
  letter-spacing: .1em; margin-bottom: 6px; font-weight: 600;
}
.field-input {
  width: 100%; background: none; border: none; outline: none;
  color: var(--white); font-family: var(--fb);
  font-size: 13px; font-weight: 400; resize: none;
  caret-color: var(--cyan);
}
.field-input::placeholder { color: rgba(255,255,255,.16); }
.field-input.textarea { min-height: 60px; line-height: 1.55; }
.field-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }

.save-profile-btn {
  width: 100%; padding: 15px;
  background: var(--grad); border: none; border-radius: 13px;
  font-family: var(--fd); font-size: 14px; font-weight: 700;
  color: var(--bg); cursor: pointer;
  box-shadow: 0 4px 24px rgba(56,189,248,.22);
  transition: opacity .2s, transform .2s;
  margin-top: 8px; margin-bottom: 24px; letter-spacing: .01em;
}
.save-profile-btn:active { opacity: .85; transform: scale(.98); }
.save-profile-btn.saving { opacity: .55; pointer-events: none; }

.profile-status {
  text-align: center; font-size: 11px; color: var(--silver);
  margin-bottom: 16px; display: none; font-weight: 300; line-height: 1.6;
}
.profile-status.show { display: block; }
.profile-status.success { color: var(--green); }
.profile-status.error   { color: var(--red); }
```

Replace it with (keeps `.profile-title`/`.profile-sub`, reused by the new chat header; everything else is new):

```css
/* ─── PROFILE CHAT ─── */
.profile-title {
  font-family: var(--fd); font-size: 24px; font-weight: 800;
  letter-spacing: -.03em; line-height: 1.2; margin-bottom: 6px;
  background: var(--grad); -webkit-background-clip: text;
  -webkit-text-fill-color: transparent; background-clip: text;
  display: inline-block;
}
.profile-sub { font-size: 12px; color: rgba(148,163,184,.55); font-weight: 300; }

.chat-screen { display: flex; flex-direction: column; min-height: calc(100vh - 140px); padding: 0 16px; }
.chat-header { padding: 20px 0 16px; }
.chat-messages { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding: 4px 0 12px; }
.chat-bubble { max-width: 82%; padding: 11px 14px; border-radius: 16px; font-size: 13px; line-height: 1.6; animation: fadeIn .25s ease both; }
.chat-bubble.client { align-self: flex-end; background: var(--grad); color: var(--bg); border-bottom-right-radius: 4px; font-weight: 500; }
.chat-bubble.bot { align-self: flex-start; background: rgba(255,255,255,.04); border: 1px solid var(--border); color: var(--white); border-bottom-left-radius: 4px; }
.chat-bubble.typing { display: flex; gap: 4px; align-items: center; padding: 13px 16px; }
.chat-typing-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--silver); animation: typingPulse 1.2s ease-in-out infinite; }
.chat-typing-dot:nth-child(2) { animation-delay: .2s; }
.chat-typing-dot:nth-child(3) { animation-delay: .4s; }
@keyframes typingPulse { 0%,60%,100%{opacity:.3} 30%{opacity:1} }
.chat-input-row { display: flex; gap: 8px; padding: 12px 0 calc(12px + env(safe-area-inset-bottom)); border-top: 1px solid var(--border); }
.chat-input {
  flex: 1; background: rgba(255,255,255,.03); border: 1px solid var(--border);
  border-radius: 13px; padding: 12px 14px; color: var(--white); font-family: var(--fb);
  font-size: 13px; outline: none;
}
.chat-input:focus { border-color: rgba(56,189,248,.35); }
.chat-input:disabled { opacity: .5; }
.chat-send-btn {
  width: 44px; height: 44px; border-radius: 13px; flex-shrink: 0;
  background: var(--grad); border: none; color: var(--bg); font-size: 17px;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
}
.chat-send-btn:disabled { opacity: .5; cursor: default; }
```

- [ ] **Step 2: Replace the Profile-screen HTML**

Find the entire block starting at `<!-- SCREEN: PROFILE -->` and ending at the `</div>` immediately before `<!-- BOTTOM NAV -->`:

```html
<!-- SCREEN: PROFILE -->
<div class="screen" id="screenProfile">
  <div class="profile-screen">
    <div class="profile-header">
      <div class="profile-title">Профиль компании</div>
      <div class="profile-sub">AI анализирует тендеры на основе этих данных</div>
    </div>

    <div class="profile-section">
      <div class="profile-section-label">Основное</div>
      <div class="field-group">
        <div class="field-row">
          <div class="field-label">Название компании</div>
          <input class="field-input" id="f-company-name" placeholder="Введите название" type="text">
        </div>
        <div class="field-row">
          <div class="field-label">Локация</div>
          <input class="field-input" id="f-location" placeholder="Tashkent, Uzbekistan" type="text">
        </div>
        <div class="field-row">
          <div class="field-label">Языки</div>
          <input class="field-input" id="f-languages" placeholder="Russian, Uzbek, English" type="text">
        </div>
        <div class="field-row-2">
          <div class="field-row">
            <div class="field-label">Лет опыта</div>
            <input class="field-input" id="f-exp-years" placeholder="8" type="number">
          </div>
          <div class="field-row">
            <div class="field-label">Размер команды</div>
            <input class="field-input" id="f-team-size" placeholder="15" type="number">
          </div>
        </div>
      </div>
    </div>

    <div class="profile-section">
      <div class="profile-section-label">Услуги и опыт</div>
      <div class="field-group">
        <div class="field-row">
          <div class="field-label">Услуги</div>
          <textarea class="field-input textarea" id="f-services" placeholder="Financial consulting, audit, strategy, ESG..."></textarea>
        </div>
        <div class="field-row">
          <div class="field-label">Ключевые слова для поиска</div>
          <input class="field-input" id="f-keywords" placeholder="аудит, финансы, бухгалтерия, ESG...">
        </div>
        <div class="field-row">
          <div class="field-label">Предыдущие проекты</div>
          <textarea class="field-input textarea" id="f-prev-projects" placeholder="Опишите 3 релевантных проекта..."></textarea>
        </div>
        <div class="field-row">
          <div class="field-label">Релевантный опыт</div>
          <textarea class="field-input textarea" id="f-rel-exp" placeholder="Опыт в аудите, МСФО, финансовой отчётности..."></textarea>
        </div>
      </div>
    </div>

    <div class="profile-section">
      <div class="profile-section-label">Финансы и условия</div>
      <div class="field-group">
        <div class="field-row-2">
          <div class="field-row">
            <div class="field-label">Мин. контракт (UZS)</div>
            <input class="field-input" id="f-min-contract" placeholder="5,000,000" type="text">
          </div>
          <div class="field-row">
            <div class="field-label">Макс. контракт (UZS)</div>
            <input class="field-input" id="f-max-contract" placeholder="500,000,000" type="text">
          </div>
        </div>
      </div>
    </div>

    <div class="profile-section">
      <div class="profile-section-label">Статистика и достижения</div>
      <div class="field-group">
        <div class="field-row-2">
          <div class="field-row">
            <div class="field-label">Всего заявок</div>
            <input class="field-input" id="f-total-bids" placeholder="0" type="number">
          </div>
          <div class="field-row">
            <div class="field-label">Побед</div>
            <input class="field-input" id="f-total-wins" placeholder="0" type="number">
          </div>
        </div>
        <div class="field-row">
          <div class="field-label">Вовремя сдача (%)</div>
          <input class="field-input" id="f-on-time" placeholder="95" type="number">
        </div>
        <div class="field-row">
          <div class="field-label">Сертификаты</div>
          <input class="field-input" id="f-certifications" placeholder="ISO 9001, CPA...">
        </div>
        <div class="field-row">
          <div class="field-label">Награды</div>
          <input class="field-input" id="f-awards" placeholder="Best Audit Firm 2024...">
        </div>
        <div class="field-row">
          <div class="field-label">Ключевые члены команды</div>
          <textarea class="field-input textarea" id="f-team-members" placeholder="CEO: Иванов И.И. — 15 лет в аудите..."></textarea>
        </div>
      </div>
    </div>

    <div class="profile-status" id="profileStatus"></div>
    <button class="save-profile-btn" id="saveBtn" onclick="saveProfile()">Сохранить профиль</button>
  </div>
</div>
```

Replace it with:

```html
<!-- SCREEN: PROFILE CHAT -->
<div class="screen" id="screenProfile">
  <div class="chat-screen">
    <div class="chat-header">
      <div class="profile-title">Профиль компании</div>
      <div class="profile-sub">Опиши свою компанию в чате — AI обновит профиль для поиска тендеров</div>
    </div>
    <div class="chat-messages" id="chatMessages"></div>
    <div class="chat-input-row">
      <input class="chat-input" id="chatInput" type="text" placeholder="Напиши сообщение..." onkeydown="if(event.key==='Enter')sendChatMessage()">
      <button class="chat-send-btn" id="chatSendBtn" onclick="sendChatMessage()">→</button>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Remove `saveProfile()` and `PROFILE_FIELDS`, add the chat functions**

Find and delete this entire block (the `PROFILE_FIELDS` array and `saveProfile()` function):

```javascript
// ── PROFILE ──
const PROFILE_FIELDS = [
  { id: 'f-company-name',  field: 'Company Name' },
  { id: 'f-location',      field: 'Location' },
  { id: 'f-languages',     field: 'Languages' },
  { id: 'f-exp-years',     field: 'Experience Years' },
  { id: 'f-team-size',     field: 'Team Size' },
  { id: 'f-services',      field: 'Services' },
  { id: 'f-keywords',      field: 'Keywords' },
  { id: 'f-prev-projects', field: 'Previous Projects' },
  { id: 'f-rel-exp',       field: 'Relevant Experience' },
  { id: 'f-min-contract',  field: 'Min Contract UZS' },
  { id: 'f-max-contract',  field: 'Max Contract UZS' },
  { id: 'f-total-bids',    field: 'Total bids submitted' },
  { id: 'f-total-wins',    field: 'Total Wins' },
  { id: 'f-on-time',       field: 'On time delivery' },
  { id: 'f-certifications',field: 'Certifications' },
  { id: 'f-awards',        field: 'Awards' },
  { id: 'f-team-members',  field: 'Key team members' },
];

async function saveProfile() {
  const btn    = document.getElementById('saveBtn');
  const status = document.getElementById('profileStatus');
  btn.classList.add('saving');
  btn.textContent = 'Сохранение...';

  const updates = {};
  PROFILE_FIELDS.forEach(f => {
    const el = document.getElementById(f.id);
    if (el && el.value.trim()) updates[f.field] = el.value.trim();
  });

  try {
    const res  = await fetch(PROFILE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ updates })
    });
    const data = await res.json();
    if (data.success) {
      status.textContent = '✓ Профиль сохранён — AI обновит анализ при следующем запуске';
      status.className = 'profile-status show success';
      showToast('✓ Профиль сохранён');
    } else {
      throw new Error('Save failed');
    }
  } catch (e) {
    status.textContent = '✕ Ошибка при сохранении — попробуй ещё раз';
    status.className = 'profile-status show error';
    showToast('Ошибка при сохранении');
  } finally {
    btn.classList.remove('saving');
    btn.textContent = 'Сохранить профиль';
  }
}
```

Replace it with:

```javascript
// ── PROFILE CHAT ──
let chatSending = false;

function renderChatMessage(role, content) {
  const container = document.getElementById('chatMessages');
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble ' + (role === 'client' ? 'client' : 'bot');
  bubble.textContent = content;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function showTypingIndicator() {
  const container = document.getElementById('chatMessages');
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble bot typing';
  bubble.id = 'typingIndicator';
  bubble.innerHTML = '<div class="chat-typing-dot"></div><div class="chat-typing-dot"></div><div class="chat-typing-dot"></div>';
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function hideTypingIndicator() {
  const el = document.getElementById('typingIndicator');
  if (el) el.remove();
}

async function loadProfileChat() {
  const container = document.getElementById('chatMessages');
  container.innerHTML = '';
  try {
    const res  = await fetch('/api/profile-chat', { headers: authHeaders() });
    const data = await res.json();
    const messages = data.messages || [];
    if (messages.length === 0) {
      renderChatMessage('bot', 'Привет! Расскажи о своей компании — чем вы занимаетесь, какой у вас опыт, какие тендеры вам интересны. Это поможет AI точнее находить подходящие тендеры.');
    } else {
      messages.forEach(m => renderChatMessage(m.role, m.content));
    }
  } catch (e) {
    showToast('Ошибка загрузки чата');
  }
}

async function sendChatMessage() {
  if (chatSending) return;
  const input = document.getElementById('chatInput');
  const message = input.value.trim();
  if (!message) return;

  const btn = document.getElementById('chatSendBtn');
  chatSending = true;
  input.disabled = true;
  btn.disabled = true;
  renderChatMessage('client', message);
  input.value = '';
  showTypingIndicator();

  try {
    const res = await fetch('/api/profile-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ message }),
    });
    hideTypingIndicator();
    if (!res.ok) {
      showToast('Ошибка при отправке сообщения');
      return;
    }
    const data = await res.json();
    renderChatMessage('bot', data.reply);
  } catch (e) {
    hideTypingIndicator();
    showToast('Ошибка при отправке сообщения');
  } finally {
    chatSending = false;
    input.disabled = false;
    btn.disabled = false;
    input.focus();
  }
}
```

Note: `PROFILE_URL` itself must NOT be deleted — it's still used by `checkProfileExists()` on the Tenders screen (a `GET` call, unrelated to this form's old `POST` usage). Only the `saveProfile()` function and `PROFILE_FIELDS` array are removed.

- [ ] **Step 4: Hook `loadProfileChat()` into `switchScreen()`**

Find `switchScreen()`:

```javascript
function switchScreen(name) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  if (name === 'tenders') {
    document.getElementById('screenTenders').classList.add('active');
    document.getElementById('navTenders').classList.add('active');
    document.getElementById('refreshBtn').style.display = 'flex';
  } else {
    document.getElementById('screenProfile').classList.add('active');
    document.getElementById('navProfile').classList.add('active');
    document.getElementById('refreshBtn').style.display = 'none';
  }
}
```

Replace it with (adds one line, `loadProfileChat();`, at the end of the `else` branch):

```javascript
function switchScreen(name) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  if (name === 'tenders') {
    document.getElementById('screenTenders').classList.add('active');
    document.getElementById('navTenders').classList.add('active');
    document.getElementById('refreshBtn').style.display = 'flex';
  } else {
    document.getElementById('screenProfile').classList.add('active');
    document.getElementById('navProfile').classList.add('active');
    document.getElementById('refreshBtn').style.display = 'none';
    loadProfileChat();
  }
}
```

- [ ] **Step 5: Verify manually in a browser**

Serve the file locally (from the repo root):

```bash
py -3 -m http.server 8080
```

Open `http://localhost:8080/index.html`. If you have a way to drive a real browser and its console (e.g. a browser automation tool), use it — don't just eyeball the source code and assume it works. Run each of the following:

**5a. Greeting shown on first open (empty history):**
```javascript
window.fetch = async (url, opts) => {
  if (url.includes('/api/profile-chat') && (!opts || opts.method !== 'POST')) {
    return new Response(JSON.stringify({ messages: [] }), { status: 200 });
  }
};
switchScreen('profile');
```
Expected (after the async load resolves): one bot bubble with the greeting text; chat screen visible; "Профиль" nav highlighted.

**5b. Existing history renders in order:**
```javascript
window.fetch = async (url, opts) => {
  if (url.includes('/api/profile-chat') && (!opts || opts.method !== 'POST')) {
    return new Response(JSON.stringify({ messages: [
      { role: 'client', content: 'We build roads' },
      { role: 'bot', content: 'Great, tell me more' },
    ] }), { status: 200 });
  }
};
await loadProfileChat();
```
Expected: two bubbles in order, first right-aligned (client), second left-aligned (bot), no greeting shown (history is non-empty).

**5c. Sending a message shows both bubbles and the auth header:**
```javascript
window.fetch = async (url, opts) => {
  console.log('URL:', url, 'AUTH:', opts?.headers?.Authorization, 'BODY:', opts?.body);
  return new Response(JSON.stringify({ reply: 'Спасибо! Что насчёт опыта?', profile_text: 'We build roads.' }), { status: 200 });
};
document.getElementById('chatInput').value = 'We build roads';
await sendChatMessage();
```
Expected: console logs `AUTH: tma ` and a body containing `{"message":"We build roads"}`; a client bubble "We build roads" appears immediately, followed by a bot bubble "Спасибо! Что насчёт опыта?"; the input is cleared and re-enabled afterward.

**5d. Generation failure shows an error toast, not a crash:**
```javascript
window.fetch = async () => new Response('{}', { status: 500 });
document.getElementById('chatInput').value = 'test';
await sendChatMessage();
```
Expected: toast reads "Ошибка при отправке сообщения"; the client's own bubble ("test") is still visible (it was rendered optimistically before the failed request); no bot bubble appears; input re-enabled afterward.

Report exactly which of 5a-5d you actually ran and what you actually observed.

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "feat: replace structured Profile form with GPT-4o chat panel"
```

---

## After This Plan

Not covered here, and not yet planned:
- Configuring/applying `0001_multi_tenant_schema.sql` / `0002_add_last_refresh_at.sql` to the live database — still blocked on the Postgres connection string, so none of Phase 1's work (including this chatbot) can be exercised end-to-end against production Supabase yet.
- Configuring the actual Railway Cron Job — sub-project 1 only produced the script.
- Payment/billing — explicitly deferred since the original Phase 0 spec.
- This was the last planned sub-project of Phase 1. After this merges, Phase 1 as originally scoped is complete.
