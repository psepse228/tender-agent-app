# Tender Agent — Phase 0: Multi-Tenant Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the multi-tenant foundation for Tender Agent's rebuild: the new Supabase schema, a FastAPI backend skeleton on Railway, Telegram Mini App `initData` authentication resolving to a `tenant_id` via a real `tenant_users` table, and the first tenant-scoped endpoint (`GET /api/tenders`) — runnable and tested locally before the existing client is migrated.

**Architecture:** A single FastAPI app (`backend/app`) exposes `/health` and `/api/tenders`. Telegram `initData` validation is a pure, dependency-free function (`app/auth/telegram.py`) so it's trivially unit-testable; a separate FastAPI dependency (`app/auth/dependencies.py`) wires that validation to settings and looks up the caller's `tenant_id` in `tenant_users`. The Supabase schema migration is applied manually (via the SQL Editor or a direct connection once available) since the REST API can't run DDL — this plan documents the exact SQL and says so at the step that needs it, rather than pretending it's automated.

**Tech Stack:** Python 3.12, FastAPI, pydantic-settings, supabase-py, pytest + pytest-asyncio, Railway (Procfile-based deploy), Supabase (Postgres).

---

## File Structure

```
Tender Agent/
  supabase/
    migrations/
      0001_multi_tenant_schema.sql   # tenants, tenant_users, company_profile,
                                      # profile_chat_messages, tenders.tenant_id
  backend/
    pyproject.toml                   # pytest config
    requirements.txt
    .env.example
    Procfile                         # Railway start command
    runtime.txt                      # pins Railway's Python build to 3.12
    app/
      __init__.py
      config.py                      # Settings (env vars) via pydantic-settings
      db.py                          # lazy Supabase client factory
      main.py                        # FastAPI app, router registration
      auth/
        __init__.py
        telegram.py                  # pure initData HMAC validation (no deps)
        dependencies.py              # FastAPI dependency: header -> tenant_id
      routers/
        __init__.py
        health.py                    # GET /health
        tenders.py                   # GET /api/tenders (tenant-scoped)
    tests/
      __init__.py
      conftest.py                    # fake env vars for test runs
      helpers.py                     # test-only initData signer
      test_config.py
      test_health.py
      test_db.py
      test_telegram_auth.py
      test_auth_dependency.py
      test_tenders.py
```

Each module has one job: `telegram.py` only validates a signature (no I/O, no settings coupling — takes the bot token as a parameter so it's testable without touching env vars or the cache); `dependencies.py` is the only place that wires `telegram.py` to `config.py` and `db.py`; `routers/tenders.py` never talks to Supabase directly except through the dependency's resolved `tenant_id`.

---

### Task 1: Initialize the backend project

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Test: `backend/tests/__init__.py`
- Test: `backend/tests/conftest.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Create `backend/requirements.txt`**

```
fastapi>=0.115,<1.0
uvicorn[standard]>=0.30,<1.0
pydantic-settings>=2.4,<3.0
supabase>=2.6,<3.0
pytest>=8.0,<9.0
pytest-asyncio>=0.24,<1.0
httpx>=0.27,<1.0
```

Run (from `backend/`):
```bash
py -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```
Expected: all packages install without errors.

- [ ] **Step 2: Create pytest config**

```toml
# backend/pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
```

- [ ] **Step 3: Create `.env.example`**

```
SUPABASE_URL=
SUPABASE_KEY=
OPENAI_API_KEY=
FIRECRAWL_API_KEY=
TELEGRAM_BOT_TOKEN=
ENVIRONMENT=development
```

- [ ] **Step 4: Create `app/__init__.py`** (empty file) and `tests/__init__.py`** (empty file)

- [ ] **Step 5: Create the test conftest**

```python
# backend/tests/conftest.py
import os

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-role-key")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")
os.environ.setdefault("FIRECRAWL_API_KEY", "fc-test-fake-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST-fake-token-for-tests")
```

This runs before pytest imports any test module, so modules that construct
`Settings()` at import time still work in tests without a real `.env`.

- [ ] **Step 6: Write the failing test**

```python
# backend/tests/test_config.py
from app.config import Settings


def test_settings_reads_from_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://tenant.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "secret-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-real")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:real-token")

    settings = Settings()

    assert settings.supabase_url == "https://tenant.supabase.co"
    assert settings.supabase_key == "secret-key"
    assert settings.telegram_bot_token == "999:real-token"


def test_settings_requires_all_credentials(monkeypatch):
    for var in ("SUPABASE_URL", "SUPABASE_KEY", "OPENAI_API_KEY", "FIRECRAWL_API_KEY", "TELEGRAM_BOT_TOKEN"):
        monkeypatch.delenv(var, raising=False)

    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
```

- [ ] **Step 7: Run test to verify it fails**

Run (from `backend/`, venv active): `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 8: Write minimal implementation**

```python
# backend/app/config.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_key: str
    openai_api_key: str
    firecrawl_api_key: str
    telegram_bot_token: str
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

All five credentials are required (no default) so a misconfigured deployment
fails immediately with a clear `ValidationError` instead of booting on fake
values. Only `environment` gets a default.

- [ ] **Step 9: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 2 passed

- [ ] **Step 10: Commit**

```bash
git add backend/requirements.txt backend/pyproject.toml backend/.env.example backend/app/__init__.py backend/app/config.py backend/tests/__init__.py backend/tests/conftest.py backend/tests/test_config.py
git commit -m "feat: add backend scaffolding and settings"
```

---

### Task 2: FastAPI app skeleton with health check

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/health.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/test_health.py`

- [ ] **Step 1: Create `app/routers/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 4: Write minimal implementation**

```python
# backend/app/routers/health.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

```python
# backend/app/main.py
from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="Tender Agent Backend")
app.include_router(health.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/__init__.py backend/app/routers/health.py backend/app/main.py backend/tests/test_health.py
git commit -m "feat: add FastAPI app skeleton with health check"
```

---

### Task 3: Supabase client factory

**Files:**
- Create: `backend/app/db.py`
- Test: `backend/tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_db.py
from unittest.mock import MagicMock

from app import db


def test_get_supabase_client_uses_settings(monkeypatch):
    db.get_supabase_client.cache_clear()
    create_client_mock = MagicMock(return_value="fake-client")
    monkeypatch.setattr(db, "create_client", create_client_mock)

    try:
        client = db.get_supabase_client()

        assert client == "fake-client"
        create_client_mock.assert_called_once_with(
            "https://example.supabase.co", "test-service-role-key"
        )
    finally:
        db.get_supabase_client.cache_clear()
```

The `finally` clears the `lru_cache` after the test too — otherwise the
mocked `"fake-client"` value stays cached for the rest of the pytest process
and leaks into later tests.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/db.py
from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/tests/test_db.py
git commit -m "feat: add lazy supabase client factory"
```

---

### Task 4: Multi-tenant Supabase schema migration

**Files:**
- Create: `supabase/migrations/0001_multi_tenant_schema.sql`

- [ ] **Step 1: Write the migration**

```sql
-- 0001_multi_tenant_schema.sql
-- Multi-tenant schema for Tender Agent's public rebuild.

create table tenants (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  status text not null default 'active' check (status in ('active', 'trial', 'paused')),
  created_at timestamptz default now()
);

create table tenant_users (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id),
  telegram_user_id bigint not null unique,
  created_at timestamptz default now()
);
create index idx_tenant_users_tenant_id on tenant_users(tenant_id);

create table company_profile (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) unique,
  profile_text text,
  updated_at timestamptz default now()
);

create table profile_chat_messages (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id),
  role text not null check (role in ('client', 'bot')),
  content text not null,
  created_at timestamptz default now()
);
create index idx_profile_chat_messages_tenant_id on profile_chat_messages(tenant_id);

-- Existing `tenders` table gains a tenant_id. If this is a fresh table
-- (no existing rows worth keeping — refresh always wipes and re-scrapes),
-- drop and recreate for a clean slate instead of an ALTER:
drop table if exists tenders;

create table tenders (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id),
  title text,
  organization text,
  budget text,
  deadline text,
  source text,
  platform text,
  match_percent numeric,
  recommendation text,
  compliance numeric,
  financial numeric,
  feasibility numeric,
  win_chance numeric,
  why_participate text,
  risks text,
  action_plan text,
  risk_level text,
  profit_potential text,
  created_at timestamptz default now()
);
create index idx_tenders_tenant_id on tenders(tenant_id);
```

- [ ] **Step 2: Apply the migration**

The Supabase REST API can't run DDL — this needs either the Supabase SQL
Editor (paste the file's contents and run) or a direct Postgres connection
string (`psql` or a migration tool). **Blocked on**: the owner providing the
Postgres connection string, or running this manually via the SQL Editor.
Once applied, confirm all 5 tables exist with:

```sql
select table_name from information_schema.tables
where table_schema = 'public'
  and table_name in ('tenants', 'tenant_users', 'company_profile', 'profile_chat_messages', 'tenders');
```
Expected: 5 rows.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/0001_multi_tenant_schema.sql
git commit -m "feat: add multi-tenant supabase schema migration"
```

---

### Task 5: Telegram initData validation (pure function)

**Files:**
- Create: `backend/app/auth/__init__.py`
- Create: `backend/app/auth/telegram.py`
- Create: `backend/tests/helpers.py`
- Test: `backend/tests/test_telegram_auth.py`

- [ ] **Step 1: Create `app/auth/__init__.py`** (empty file)

- [ ] **Step 2: Write the test-only initData signer**

```python
# backend/tests/helpers.py
"""Test-only helpers. Independently re-implements Telegram's initData
signing spec so tests can produce validly-signed payloads without
depending on app.auth.telegram (which is the thing under test)."""
import hashlib
import hmac
from urllib.parse import urlencode


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(fields.items())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode({**fields, "hash": computed_hash})
```

- [ ] **Step 3: Write the failing tests**

```python
# backend/tests/test_telegram_auth.py
import time

import pytest

from app.auth.telegram import InitDataError, validate_init_data
from tests.helpers import sign_init_data

BOT_TOKEN = "123456:TEST-fake-token-for-tests"


def test_accepts_correctly_signed_payload():
    fields = {
        "user": '{"id":111,"first_name":"Test"}',
        "auth_date": str(int(time.time())),
        "query_id": "AAH_test",
    }
    init_data = sign_init_data(fields, BOT_TOKEN)

    result = validate_init_data(init_data, BOT_TOKEN)

    assert result["auth_date"] == fields["auth_date"]
    assert result["user"] == fields["user"]


def test_rejects_payload_signed_with_a_different_token():
    fields = {"user": '{"id":111}', "auth_date": str(int(time.time()))}
    init_data = sign_init_data(fields, "999:a-different-bot-token")

    with pytest.raises(InitDataError, match="invalid hash"):
        validate_init_data(init_data, BOT_TOKEN)


def test_rejects_tampered_field():
    fields = {"user": '{"id":111}', "auth_date": str(int(time.time()))}
    init_data = sign_init_data(fields, BOT_TOKEN)
    tampered = init_data.replace("id%22%3A111", "id%22%3A999")

    with pytest.raises(InitDataError, match="invalid hash"):
        validate_init_data(tampered, BOT_TOKEN)


def test_rejects_stale_auth_date():
    stale_time = int(time.time()) - (25 * 60 * 60)
    fields = {"user": '{"id":111}', "auth_date": str(stale_time)}
    init_data = sign_init_data(fields, BOT_TOKEN)

    with pytest.raises(InitDataError, match="stale"):
        validate_init_data(init_data, BOT_TOKEN)


def test_rejects_missing_hash():
    with pytest.raises(InitDataError, match="missing hash"):
        validate_init_data("user=%7B%22id%22%3A111%7D&auth_date=123", BOT_TOKEN)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_telegram_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.telegram'`

- [ ] **Step 5: Write the implementation**

```python
# backend/app/auth/telegram.py
import hashlib
import hmac
import time
from urllib.parse import parse_qsl

MAX_AUTH_AGE_SECONDS = 24 * 60 * 60


class InitDataError(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str) -> dict[str, str]:
    """Validate a Telegram Mini App initData string against bot_token.

    Returns the parsed key-value pairs (hash removed) on success.
    Raises InitDataError on missing/invalid hash or a stale auth_date
    (more than 24h old).
    """
    pairs = dict(parse_qsl(init_data, strict_parsing=True))

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("missing hash field")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(pairs.items())
    )

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InitDataError("invalid hash")

    auth_date = int(pairs.get("auth_date", 0))
    if time.time() - auth_date > MAX_AUTH_AGE_SECONDS:
        raise InitDataError("stale auth_date")

    return pairs
```

`bot_token` is a parameter, not read from global settings — this keeps the
function pure and trivially testable. The FastAPI dependency in Task 6 is
the only place that wires it to `get_settings()`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_telegram_auth.py -v`
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/auth/__init__.py backend/app/auth/telegram.py backend/tests/helpers.py backend/tests/test_telegram_auth.py
git commit -m "feat: add pure telegram initData validation"
```

---

### Task 6: Auth dependency — resolve initData to a tenant_id

**Files:**
- Create: `backend/app/auth/dependencies.py`
- Test: `backend/tests/test_auth_dependency.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_auth_dependency.py
import time
from types import SimpleNamespace

from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_tenant_id
from tests.helpers import sign_init_data

BOT_TOKEN = "123456:TEST-fake-token-for-tests"
TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"


class _FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        return SimpleNamespace(data=self._data)


class _FakeClient:
    def __init__(self, tenant_users_rows):
        self._rows = tenant_users_rows

    def table(self, name):
        assert name == "tenant_users"
        return _FakeQuery(self._rows)


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(tenant_id: str = Depends(get_current_tenant_id)):
        return {"tenant_id": tenant_id}

    return app


def _signed_init_data(telegram_user_id: int) -> str:
    fields = {
        "user": f'{{"id":{telegram_user_id}}}',
        "auth_date": str(int(time.time())),
    }
    return sign_init_data(fields, BOT_TOKEN)


def test_resolves_known_telegram_user_to_their_tenant(monkeypatch):
    monkeypatch.setattr(
        "app.auth.dependencies.get_supabase_client",
        lambda: _FakeClient([{"tenant_id": TENANT_ID}]),
    )
    app = _build_app()
    client = TestClient(app)

    response = client.get(
        "/whoami",
        headers={"Authorization": f"tma {_signed_init_data(111)}"},
    )

    assert response.status_code == 200
    assert response.json() == {"tenant_id": TENANT_ID}


def test_rejects_missing_authorization_header():
    app = _build_app()
    client = TestClient(app)

    response = client.get("/whoami")

    assert response.status_code == 422  # FastAPI's own missing-header error


def test_rejects_wrong_auth_scheme():
    app = _build_app()
    client = TestClient(app)

    response = client.get("/whoami", headers={"Authorization": "Bearer something"})

    assert response.status_code == 401


def test_rejects_telegram_user_with_no_tenant(monkeypatch):
    monkeypatch.setattr(
        "app.auth.dependencies.get_supabase_client",
        lambda: _FakeClient([]),
    )
    app = _build_app()
    client = TestClient(app)

    response = client.get(
        "/whoami",
        headers={"Authorization": f"tma {_signed_init_data(999)}"},
    )

    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth_dependency.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.dependencies'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/auth/dependencies.py
import json

from fastapi import Header, HTTPException

from app.auth.telegram import InitDataError, validate_init_data
from app.config import get_settings
from app.db import get_supabase_client


async def get_current_tenant_id(authorization: str = Header(...)) -> str:
    if not authorization.startswith("tma "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header must use the 'tma <initData>' scheme",
        )

    init_data = authorization.removeprefix("tma ")
    settings = get_settings()

    try:
        pairs = validate_init_data(init_data, settings.telegram_bot_token)
    except InitDataError as e:
        raise HTTPException(status_code=401, detail=str(e))

    user = json.loads(pairs["user"])
    telegram_user_id = user["id"]

    client = get_supabase_client()
    response = (
        client.table("tenant_users")
        .select("tenant_id")
        .eq("telegram_user_id", telegram_user_id)
        .limit(1)
        .execute()
    )
    rows = response.data
    if not rows:
        raise HTTPException(
            status_code=403,
            detail="No tenant registered for this Telegram account",
        )

    return rows[0]["tenant_id"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_auth_dependency.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/dependencies.py backend/tests/test_auth_dependency.py
git commit -m "feat: add auth dependency resolving initData to a tenant_id"
```

---

### Task 7: `GET /api/tenders` — first tenant-scoped endpoint

**Files:**
- Create: `backend/app/routers/tenders.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_tenders.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_tenders.py
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import sign_init_data

BOT_TOKEN = "123456:TEST-fake-token-for-tests"
TENANT_ID = "005ece7a-2af4-4f22-84f7-25d5e743af9e"
OTHER_TENANT_ID = "11111111-1111-1111-1111-111111111111"

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

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        rows = [r for r in self._table_data if all(r.get(k) == v for k, v in self._filters.items())]
        return SimpleNamespace(data=rows)


class _FakeClient:
    def __init__(self, table_data):
        self._table_data = table_data

    def table(self, name):
        return _FakeQuery(self._table_data.get(name, []))


def _auth_header(telegram_user_id: int) -> dict[str, str]:
    fields = {"user": f'{{"id":{telegram_user_id}}}', "auth_date": str(int(time.time()))}
    return {"Authorization": f"tma {sign_init_data(fields, BOT_TOKEN)}"}


def test_returns_only_the_callers_tenant_tenders(monkeypatch):
    fake_client = _FakeClient({
        "tenant_users": [{"telegram_user_id": 111, "tenant_id": TENANT_ID}],
        "tenders": [
            {"id": "t1", "tenant_id": TENANT_ID, "title": "Ours", "match_percent": 80},
            {"id": "t2", "tenant_id": OTHER_TENANT_ID, "title": "Not ours", "match_percent": 90},
        ],
    })
    monkeypatch.setattr("app.auth.dependencies.get_supabase_client", lambda: fake_client)
    monkeypatch.setattr("app.routers.tenders.get_supabase_client", lambda: fake_client)

    response = client.get("/api/tenders", headers=_auth_header(111))

    assert response.status_code == 200
    titles = [t["title"] for t in response.json()["tenders"]]
    assert titles == ["Ours"]


def test_requires_auth():
    response = client.get("/api/tenders")

    assert response.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tenders.py -v`
Expected: FAIL with 404 (route doesn't exist) on the first assertion

- [ ] **Step 3: Write the implementation**

```python
# backend/app/routers/tenders.py
from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_tenant_id
from app.db import get_supabase_client

router = APIRouter()


@router.get("/api/tenders")
async def list_tenders(tenant_id: str = Depends(get_current_tenant_id)) -> dict:
    client = get_supabase_client()
    response = (
        client.table("tenders")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("match_percent", desc=True)
        .limit(100)
        .execute()
    )
    return {"tenders": response.data or []}
```

```python
# backend/app/main.py
from fastapi import FastAPI

from app.routers import health, tenders

app = FastAPI(title="Tender Agent Backend")
app.include_router(health.router)
app.include_router(tenders.router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tenders.py -v`
Expected: 2 passed

- [ ] **Step 5: Run the full suite**

Run (from `backend/`, venv active): `pytest -v`
Expected: all tests across every file PASS (config, health, db, telegram
auth, auth dependency, tenders).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/tenders.py backend/app/main.py backend/tests/test_tenders.py
git commit -m "feat: add tenant-scoped GET /api/tenders endpoint"
```

---

### Task 8: Railway deploy config

**Files:**
- Create: `backend/Procfile`
- Create: `backend/runtime.txt`

- [ ] **Step 1: Create the Procfile**

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

- [ ] **Step 2: Create the runtime pin**

```
python-3.12
```

- [ ] **Step 3: Run the server locally and smoke-test it**

Run: `uvicorn app.main:app --reload` (from `backend/`, venv active, with a
real `.env` filled in)
In another terminal: `curl http://127.0.0.1:8000/health`
Expected: `{"status":"ok"}`

- [ ] **Step 4: Manual Railway setup (one-time, dashboard)**

Create a new Railway service (or reuse the existing Tender Agent project),
set **Root Directory** to `backend` (monorepo — Railway needs this to find
`Procfile`/`requirements.txt`), and set `SUPABASE_URL`, `SUPABASE_KEY`,
`OPENAI_API_KEY`, `FIRECRAWL_API_KEY`, `TELEGRAM_BOT_TOKEN` as environment
variables. Deploy and confirm `/health` responds on the public Railway URL.
**Do not point this at the existing single-tenant deployment yet** — until
the existing client is migrated (a later task, blocked on knowing their
Telegram user id), keep this as a separate/staging deployment.

- [ ] **Step 5: Commit**

```bash
git add backend/Procfile backend/runtime.txt
git commit -m "feat: add railway deploy config"
```

---

## After This Plan

This lands the foundation: schema, auth, and one read endpoint — but the
Node/Express app is still what's actually serving the existing client, and
nothing here touches it yet. Follow-on plans (not yet written):

1. **Refresh + scraping hardening** — port `tender-refresh.js`'s scraping/
   scoring logic to `scraping/firecrawl.py` + `scraping/scoring.py`, add the
   `POST /api/refresh` endpoint (tenant-scoped), add retry-with-backoff for
   bicotender.ru, fix the content-truncation issue.
2. **Profile-setup chatbot** — `POST /api/profile-chat` + `company_profile`/
   `profile_chat_messages` read-write logic.
3. **Scheduled refresh** — the Railway Cron Job service.
4. **Frontend** — `initData` on every `index.html` API call, the new
   profile-chat panel, empty/loading states.
5. **Existing client migration** — once their Telegram user id is known,
   insert their `tenants`/`tenant_users`/`company_profile` rows and cut over
   from the Node app to this one.
