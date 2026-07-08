# Tender Agent — refresh endpoint & scraping/scoring hardening

## Context / motivation

This is sub-project 1 of Tender Agent's Phase 1 (the first sub-project after
[Phase 0's multi-tenant foundation](2026-07-08-multi-tenant-rebuild-design.md),
which shipped the schema, FastAPI skeleton, Telegram auth, and a tenant-scoped
`GET /api/tenders`). Phase 1 was originally scoped as three things — refresh,
frontend wiring, and the profile-setup chatbot — but those are independent
enough to build and review separately, so each gets its own spec/plan/build
cycle. This spec covers only the refresh + hardening piece.

The current single-tenant Node implementation
(`Tender Agent/api/tender-refresh.js`) has two known problems, both carried
over from the original spec's hardening requirements:

- **bicotender.ru** fails intermittently with Bad Gateway, with no retry.
- **8,000-character truncation** on scraped page content before GPT-4o
  extraction risks silently cutting off real tenders on long listing pages.

It's also entirely single-tenant: it wipes and rebuilds the *whole* `tenders`
table on every run, with no tenant scoping and no way to trigger a refresh
for just one tenant.

## Architecture & data flow

A single shared function, `refresh_tenant(tenant_id, client) -> dict`, does
the actual work and is called by both triggers:

1. Load `company_profile.profile_text` for the tenant (fallback: `"No
   profile configured yet."` if none exists yet).
2. Scrape all 6 sources in parallel, each wrapped in retry-with-backoff.
3. For each source that scraped successfully, run GPT-4o extraction+scoring.
4. Flatten all sources' tenders into one list.
5. Delete `tenders` WHERE `tenant_id = X`, insert the new rows.
6. Update `tenants.last_refresh_at`.
7. Return `{"tenders": [...], "sources_status": [...]}`.

**On-demand trigger**: `POST /api/refresh`, protected by the existing
`get_current_tenant_id` auth dependency (same as `/api/tenders`). Checks a
5-minute cooldown against `tenants.last_refresh_at` before doing any work —
returns `429` if the tenant refreshed too recently. Fully synchronous: the
DB write completes before the response is returned (see "Response timing"
below).

**Scheduled trigger**: `python -m app.jobs.refresh_all_tenants`, a
standalone script invoked by a Railway Cron Job on a daily schedule. Not an
HTTP endpoint — no auth needed since it's not a user request. Loops every
row in `tenants` sequentially and calls `refresh_tenant` for each,
independent of the on-demand cooldown (the schedule itself is the rate
limit).

## Components & files

- `backend/app/scraping/firecrawl.py` — `scrape_source(source) -> str |
  None`. Wraps the Firecrawl `POST /v1/scrape` call (unchanged request
  shape from the Node version) with retry-with-backoff: 3 attempts, delays
  of 1s / 2s / 4s between attempts. Returns `None` only after all 3 attempts
  fail (network error, timeout, or non-2xx response) — this is what fixes
  bicotender.ru's intermittent Bad Gateway.
- `backend/app/scraping/scoring.py` — `extract_and_score(content, source,
  profile_text) -> list[dict]`. Ported from the Node `extractAndScore`:
  same GPT-4o model (`gpt-4o`), same system prompt structure, same scoring
  formula (`compliance×0.4 + financial×0.2 + feasibility×0.25 +
  winChance×0.15`), same "missing budget → 40-50, never 0" rule, same
  "up to 10 most relevant tenders per source" cap. The only change: content
  is truncated to **40,000 characters** (up from 8,000) before being sent to
  GPT-4o — comfortably within its 128k context window alongside the system
  prompt, and large enough that no real tender-listing page should hit the
  cap. No chunking — a single generous cap is simpler and avoids
  cross-chunk duplicate-tender risk.
- `backend/app/scraping/pipeline.py` — `refresh_tenant(tenant_id, client) ->
  dict`, the orchestration function described above. Scrapes all 6 sources
  concurrently via `asyncio.gather(..., return_exceptions=True)` so one
  source's failure never aborts the others (mirrors the Node version's
  `Promise.allSettled`).
- `backend/app/routers/refresh.py` — `POST /api/refresh`. Thin: resolves
  `tenant_id` via the existing auth dependency, checks the cooldown, calls
  `refresh_tenant`, returns its result.
- `backend/app/jobs/refresh_all_tenants.py` — standalone script for the
  Railway Cron Job. Uses the existing `get_supabase_client()`. Loops every
  `tenants` row; if one tenant's `refresh_tenant` call raises, logs the
  tenant ID and exception and continues to the next tenant rather than
  aborting the whole nightly run.
- `supabase/migrations/0002_add_last_refresh_at.sql` — adds
  `last_refresh_at timestamptz` (nullable) to `tenants`.

The 6 sources scraped are unchanged from the current implementation:
etender.uzex.uz, xt-xarid.uz, tenderweek.com, adb.org, worldbank.org,
bicotender.ru. No new source platforms in this pass.

## Response timing

The current Node implementation returns the response to the client the
moment scoring finishes, then persists to Supabase afterward as a
fire-and-forget background write. This rebuild makes the flow fully
synchronous instead: persist first, then respond. The scrape+score pipeline
is already the slow part of a refresh; the extra DB round-trip afterward is
negligible by comparison, and it removes a real correctness gap — the old
pattern could show a client "success" moments before a background save
silently failed.

## Error handling

- **Per-source scrape or scoring failure** (after 3 retries, or a bad/failed
  GPT-4o call): that source contributes `{"name": ..., "status": "failed",
  "count": 0}` to `sources_status` and zero tenders. Never fails the whole
  refresh.
- **All sources fail**: `refresh_tenant` still completes normally —
  `tenders: []`, every `sources_status` entry `"failed"`. The tenant's
  `tenders` table is still cleared (a bad run empties the list rather than
  leaving stale data, matching current behavior) and `last_refresh_at` still
  updates, since a refresh did happen.
- **Cooldown violation**: `POST /api/refresh` returns `429` before any
  scraping starts — no wasted Firecrawl/OpenAI spend on a rejected request.
- **DB write failure** (delete/insert on `tenders`, or the `last_refresh_at`
  update): raises, endpoint returns `500`. No more silent-failure gap now
  that persistence happens before the response.
- **Cron script**: isolates failures per tenant (see Components above) so
  one tenant's bad data or a transient DB error doesn't block the rest of
  that night's tenants.

## Out of scope for this spec

- No new source platforms — hardening only.
- Per-source status is **not persisted** to the database; it only appears in
  the `POST /api/refresh` response for that request. A tenant reopening the
  Mini App later won't see "bicotender.ru failed last night" unless they
  refresh again. Revisit if this turns out to matter in practice.
- Frontend wiring (calling this endpoint with the `initData` auth header,
  showing the refresh result/cooldown to the user) is sub-project 2, not
  this spec.
- The profile-setup chatbot is sub-project 3, not this spec.

## Testing approach

TDD per component, mirroring Phase 0's pattern:

- `firecrawl.py`: fake HTTP client that fails N times then succeeds —
  verifies retry count and backoff without real network calls.
- `scoring.py`: fixed markdown string + mocked OpenAI client — verifies
  prompt construction, the 40,000-char truncation point, and result
  mapping.
- `pipeline.py`: both scraping and scoring mocked — verifies tenant-scoped
  delete/insert, the `sources_status` shape, and per-source fault isolation.
- `routers/refresh.py`: FastAPI `TestClient` with a fake Supabase client
  (same pattern as `test_tenders.py`) — covers auth, cooldown enforcement,
  and the happy path.
- `jobs/refresh_all_tenants.py`: `refresh_tenant` mocked — verifies it loops
  every tenant row and isolates one tenant's failure from the rest.
