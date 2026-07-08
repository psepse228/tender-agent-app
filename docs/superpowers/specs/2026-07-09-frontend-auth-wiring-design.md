# Tender Agent — frontend auth wiring

## Context / motivation

This is sub-project 2 of Tender Agent's Phase 1 (the second sub-project after
[sub-project 1's refresh endpoint & scraping hardening](2026-07-09-refresh-and-scraping-hardening-design.md),
which is merged to `main`). Phase 1 was split into three independent
sub-projects during brainstorming: refresh/hardening (done), this one
(frontend auth wiring), and the profile-setup chatbot (sub-project 3, not
yet started — it will eventually replace the structured Profile form this
spec is keeping alive).

The existing Mini App (`Tender Agent/index.html`) sends zero authentication
on any of its three API calls today, and points at the old single-tenant
Node endpoints (`/api/get-tenders`, `/api/tender-refresh`,
`/api/save-profile`) instead of the new multi-tenant Python backend
(`GET /api/tenders`, `POST /api/refresh` — both merged from sub-project 1).
This spec wires the frontend to the real backend with real per-tenant auth,
and gives the Profile form a matching backend endpoint so it keeps working
(with real tenant scoping) until the chatbot replaces it.

**Explicitly out of scope for this spec:**
- The profile-setup chatbot itself (sub-project 3).
- Any redesign of the Profile form's 16 fields, or teaching the backend to
  parse `profile_text` back into those fields — the form stays exactly as
  it is today, write-only, just with a real backend behind it.
- Visual/layout changes beyond what's needed for the new empty-state copy.

## Architecture & endpoints

Two small backend additions in a new `backend/app/routers/profile.py`,
following the exact auth/router pattern already used by `tenders.py` and
`refresh.py`:

- **`POST /api/profile`** — reads `{"updates": {field: value, ...}}` (same
  request shape the frontend already sends), joins non-empty entries into
  `"key: value"` lines (identical logic to the old
  `Tender Agent/api/save-profile.js`), and upserts into `company_profile`
  scoped by `tenant_id`: updates `profile_text` + `updated_at` if a row
  already exists for that tenant, otherwise inserts one.
- **`GET /api/profile`** — returns `{"profile_text": <str or null>}` for the
  caller's tenant. Used only to check *whether* a profile exists (drives the
  new-tenant empty-state nudge below) — **not** used to pre-fill the
  16-field form. Parsing `profile_text` back into individual fields isn't
  reliably reversible (especially once the chatbot starts writing to the
  same column in free-form prose), so the form stays write-only, matching
  its current behavior exactly.

On the frontend (`index.html`, edited in place — no new files):
- A shared `authHeaders()` helper reads `Telegram.WebApp.initData` and
  returns `{"Authorization": "tma " + initData}`, added to all four fetch
  calls (tenders, refresh, profile save, profile existence check).
- `GET_URL` → `/api/tenders`, `REFRESH_URL` → `/api/refresh`,
  `PROFILE_URL` → `/api/profile`.
- `N8N_WEBHOOK_URL` and the dead n8n branch in `refreshTenders()` are
  deleted — vestigial, the company no longer uses n8n anywhere.
- The camelCase-normalization helper (currently only used inside
  `refreshTenders()`) is hoisted out and reused by `loadTenders()` too,
  since `GET /api/tenders` returns raw snake_case Supabase rows
  (`match_percent`, `why_participate`, etc.) while every render function in
  this file expects camelCase (`matchPercent`, `whyParticipate`, etc.).

## Components & files

- `backend/app/routers/profile.py` (new) — `POST /api/profile`,
  `GET /api/profile`, both behind the existing `get_current_tenant_id`
  dependency.
- `backend/app/main.py` (modified) — registers `profile.router`.
- `Tender Agent/index.html` (modified in place):
  - `authHeaders()` helper added near the top of the `<script>` block.
  - `loadTenders()`: adds auth header, applies the (now-shared) `normalize()`
    step to convert snake_case rows to the camelCase shape the rest of the
    file expects.
  - `refreshTenders()`: adds auth header; branches on `429` (cooldown toast)
    vs. other errors (existing generic error toast); on success, appends a
    source-failure summary to the toast only when `sources_status` contains
    at least one `"failed"` entry.
  - `saveProfile()`: adds auth header, points at `/api/profile`.
  - New `checkProfileExists()`: called only when `loadTenders()` resolves to
    zero tenders. Calls `GET /api/profile`; if `profile_text` is null/empty,
    swaps the empty-state copy to a profile nudge with a tap-through
    (`onclick="switchScreen('profile')"`) to the Profile screen. If the
    check itself fails (network error) or a profile already exists, falls
    back to the existing generic "no tenders, press refresh" copy.

## Error handling

- **Missing/invalid Telegram `initData`** (e.g. opened outside Telegram):
  the backend already returns 401 via the existing auth dependency — no new
  frontend handling. Falls into the existing generic catch blocks
  (`loadTenders()` shows "Ошибка загрузки" + empty state;
  `refreshTenders()` shows "Ошибка при обновлении"). Not worth a bespoke
  message for a Mini-App-only product where this should essentially never
  happen in practice.
- **`POST /api/refresh` → 429**: distinct toast ("Обновлялось недавно,
  попробуй чуть позже") instead of the generic error — the only
  response-code-specific branch added to `refreshTenders()`. No countdown
  timer, no client-side cooldown tracking.
- **`POST /api/refresh` → sources_status with failures**: folded into the
  existing success toast; silent when all 6 sources succeeded.
- **`GET /api/profile` failure** during the empty-state check: fails soft,
  falls back to the generic empty-state copy — this is a nice-to-have nudge,
  not critical path.
- **`POST /api/profile` failure**: unchanged from today (existing
  try/catch already shows a red error status + toast).
- **Loading state**: unchanged. The existing full-screen loader already
  covers the initial `loadTenders()` fetch and only hides after it settles
  (success or failure) — this already satisfies "proper loading state for a
  first-time load," no redesign needed.

## Testing approach

**Backend (`profile.py`)**: same TDD pattern as every other router in this
codebase — `pytest` + FastAPI `TestClient` + a fake Supabase client
(matching `test_tenders.py`/`test_refresh.py`'s style), covering:
insert-when-no-row-exists, update-when-a-row-already-exists, tenant scoping
(can't read/write another tenant's profile), and auth-required.

**Frontend (`index.html`)**: there's no existing JS test framework or build
step for this file (a static page served as-is), and introducing one for a
single-file vanilla-JS Mini App would be disproportionate to this change.
Per standing instructions for UI changes, this will be verified manually:
a local static server with mocked `fetch` responses (or a lightweight local
stand-in for the backend), walking the golden path (load → cards render →
refresh → toast) and the edge cases (empty tenders + no profile → nudge
shown; empty tenders + profile exists → generic copy; 429 → cooldown toast;
source failure → toast mentions it) — reporting exactly what was verified
rather than claiming untested coverage.

## Open items (not blocking this spec, but unresolved)

- Same open items carried over from the Phase 0 and sub-project 1 specs:
  the Postgres connection string (still needed to apply any migration),
  the existing client's Telegram user id (for their `tenant_users`
  migration), and the disposition of `api/_apify.js`/`api/debug-scrape.js`
  in the old Node app.
