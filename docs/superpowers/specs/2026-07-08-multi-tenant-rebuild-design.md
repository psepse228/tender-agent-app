# Tender Agent — multi-tenant public rebuild

## Context / motivation

Tender Agent is Solura's flagship product, currently live for one anonymized
client only. The owner wants to take it public as a multi-tenant SaaS
product, following the same playbook as [[Cortège]] (Solura's other
in-progress public SaaS bet): keep serving the existing private client while
building toward multiple paying tenants on shared infrastructure.

The current implementation (Node/Express on Railway, Supabase) is
thoroughly single-tenant: the `tenders` table has no tenant concept at all,
and the refresh endpoint deletes and repopulates the *entire* table on every
run — a second tenant's refresh would wipe the first tenant's data. The
`profile` table is a single hardcoded row. None of this survives adding a
second client, so this is a rebuild, not an incremental patch.

**Explicitly out of scope for this spec:**
- Payment/billing (token system vs. monthly subscription) — a deliberate
  follow-on decision, not part of this build.
- Public self-serve signup — new tenants are added manually (a `tenants` row
  + `tenant_users` entry) until a payment flow exists to gate it.
- New tender source platforms — this rebuild hardens the existing 6 sources,
  it doesn't add more.

## Stack

Mirrors Cortège's actual stack, replacing the current Node/Express app:
**Python/FastAPI on Railway**, same Supabase project
(`djtdvxtfhqhbqsymzkyq.supabase.co`, just a redesigned schema — confirmed
this project stays, no new Supabase project).

## Database schema

All in the existing `djtdvxtfhqhbqsymzkyq` Supabase project.

### `tenants`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid, pk | |
| `name` | text | |
| `status` | text | `active` / `trial` / `paused` |
| `created_at` | timestamptz | |

### `tenant_users`
A real mapping table from day one — deliberately **not** the env-var stopgap
Cortège used for speed, since Tender Agent already has a real client and
this is a full rebuild anyway.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid, pk | |
| `tenant_id` | uuid, fk → tenants | |
| `telegram_user_id` | bigint, unique | one person → one tenant |
| `created_at` | timestamptz | |

Supports multiple people per client company from day one.

### `company_profile`
One row per tenant. Kept as free text, not structured jsonb like Cortège's
`packages`/`faq`/`partners` — the scoring prompt already consumes this
holistically as GPT-4o context, and there's no function-calling read
pattern here that would benefit from structured columns.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid, pk | |
| `tenant_id` | uuid, fk → tenants, unique | |
| `profile_text` | text | |
| `updated_at` | timestamptz | |

### `profile_chat_messages`
The profile-setup chatbot's conversation log, so a client can leave and
resume.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid, pk | |
| `tenant_id` | uuid, fk → tenants | |
| `role` | text | `client` / `bot` |
| `content` | text | |
| `created_at` | timestamptz | |

### `tenders`
Existing table, `tenant_id` added.

Existing columns unchanged: `title`, `organization`, `budget`, `deadline`,
`source`, `platform`, `match_percent`, `recommendation`, `compliance`,
`financial`, `feasibility`, `win_chance`, `why_participate`, `risks`,
`action_plan`, `risk_level`, `profit_potential`.

**Behavior change:** refresh logic moves from `DELETE FROM tenders` (whole
table) to `DELETE FROM tenders WHERE tenant_id = X`, scoped per tenant.

### Migration for the existing live client

Create their `tenants` row, move their current `profile.data` text into
`company_profile.profile_text`, add their Telegram user id to
`tenant_users`. Their existing `tenders` rows don't need migrating — the
refresh logic wipes and re-scrapes every run anyway, so the next refresh
repopulates them correctly under their `tenant_id`. Their actual Telegram
user id needs to be identified before this migration runs (not yet known —
check current Mini App usage/logs, or ask the client directly).

## Backend (`Tender Agent/backend/`)

Replaces the current `server.js` + `api/*.js` Node app. Structure mirrors
Cortège's `backend/app/`:

- `config.py` — settings via pydantic-settings (Supabase URL/key, OpenAI,
  Firecrawl, Telegram bot token)
- `db.py` — lazy Supabase client factory
- `auth/telegram.py` — validates Telegram Mini App `initData` HMAC, then
  resolves the Telegram user to a `tenant_id` via `tenant_users` — same
  validation mechanism as Cortège's `initData.ts`, ported to Python, backed
  by a real table instead of an env var
- `routers/tenders.py` — `GET /api/tenders`, tenant-scoped (replaces
  `get-tenders.js`)
- `routers/refresh.py` — `POST /api/refresh`, tenant-scoped manual trigger
  (replaces `tender-refresh.js`)
- `routers/profile_chat.py` — new: the profile-setup chatbot endpoint
- `scraping/firecrawl.py` — scraping logic ported from `tender-refresh.js`'s
  `scrapeSource`, with retry-with-backoff added for transient failures
  (see Hardening below)
- `scraping/scoring.py` — GPT-4o extraction/scoring ported from
  `extractAndScore`, parameterized by the tenant's `profile_text` instead of
  a single hardcoded one. Scoring formula and prompt rules are unchanged
  (compliance×0.4 + financial×0.2 + feasibility×0.25 + winChance×0.15;
  missing budget → 40-50, never 0) — they already work, no redesign.

## Scheduled + on-demand refresh

**Both**, per the owner's explicit choice:
- **Scheduled**: a Railway **Cron Job** (a separate scheduled service, not
  embedded in the always-running web process) runs daily, loops every row in
  `tenants`, and re-runs the scrape+score pipeline per tenant. Deliberately
  not n8n — the owner has moved the whole stack off n8n and doesn't want it
  reintroduced just for scheduling.
- **On-demand**: the existing manual "refresh" button stays, now scoped to
  the authenticated tenant's own data only.

## Scraping & scoring hardening

- **bicotender.ru**: currently fails intermittently with Bad Gateway
  (unresolved as of the original June 2026 handoff doc). Add retry-with-backoff
  (2-3 attempts) for transient failures. Surface per-source status in the
  API response (e.g. "5 of 6 sources returned results this run") instead of
  silently dropping a failed source — a tenant should be able to tell a
  source outage from "no matching tenders today."
- **Extraction truncation**: the current GPT-4o scoring call truncates
  scraped page content to 8,000 characters before extraction. On a source
  with a long tender listing, this risks silently cutting off real tenders.
  Raise the cap and/or chunk a source's content across multiple scoring
  calls when it exceeds the cap, rather than a single truncated pass.
- No new source platforms in this pass — hardening the existing 6
  (etender.uzex.uz, xt-xarid.uz, tenderweek.com, adb.org, worldbank.org,
  bicotender.ru) is the whole scope here.

## Profile-setup chatbot

Lives inside the Mini App as a new chat panel/tab. Simple conversational
loop (GPT-4o, no function-calling) — narrower than Cortège's client-facing
bot because it only has one job: help a tenant articulate what they're
looking for and turn that into `company_profile.profile_text`.

Flow: client sends a message → appended to `profile_chat_messages` →
model reads the running conversation (plus current `profile_text`) and
produces an updated `profile_text` → client sees it reflected immediately in
the profile view. No hallucination-guard complexity is needed here (unlike
Cortège's `escalate_to_human` pattern) since this bot only ever writes back
what the client themselves stated — it doesn't answer questions using the
data.

## Frontend

Keep the existing `index.html` Mini App and its established look — evolve
it, don't replace it. **Correction from an earlier draft of this spec**: the
"Superhuman-inspired, DM Serif Display" description was based on a stale
local copy. The actual current design (shipped 2026-06-28, commit
`0e0e133`, "Glass Premium / Variant C") is already Solura's real brand
fonts — **Syne + DM Sans** — on a darker base (`#050810`), with glassmorphism
cards tinted by score color (green/amber/red), pill-shaped score badges with
progress bars, backdrop-blur throughout, and Linear-style filter chips. This
is the look to build on:
- Add `initData` to every API call's Authorization header (mirrors
  Cortège's `tma <initData>` header scheme)
- Add the new profile-chat panel/tab, matching the existing visual language
- Add proper empty/loading states, especially for a brand-new tenant with no
  profile or tenders yet — this is the actual first-run experience that
  didn't exist when there was only ever one hardcoded client
- Exact visual details are implementation-level work, not specified further
  here

## Open items (not blocking this spec, but unresolved)

- The existing client's Telegram user id needs to be identified before
  their migration can run.
- Direct Postgres connection string (for running the schema migration) —
  service_role key alone can't run DDL; still needed from the owner.
- `api/_apify.js` (untracked) and a local uncommitted edit to
  `api/debug-scrape.js` exist in the current repo — unclear if they're
  meant to be kept, finished, or discarded as part of this rebuild. Worth a
  decision before or during implementation.
