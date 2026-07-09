# Tender Agent — profile-setup chatbot

## Context / motivation

This is sub-project 3 of Tender Agent's Phase 1 — the last of the three
sub-projects the original Phase 1 scope was split into during brainstorming.
[Sub-project 1](2026-07-09-refresh-and-scraping-hardening-design.md)
(refresh + scraping hardening) and
[sub-project 2](2026-07-09-frontend-auth-wiring-design.md) (frontend auth
wiring, including a stopgap `POST`/`GET /api/profile` for the existing
structured Profile form) are both merged to `main`.

The original [multi-tenant rebuild spec](2026-07-08-multi-tenant-rebuild-design.md)
named a conversational profile-setup flow as the intended long-term
replacement for the structured 16-field form: "help a tenant articulate what
they're looking for and turn that into `company_profile.profile_text`."
This sub-project builds that chatbot and replaces the form with it.

## Architecture & data flow

New backend router, `backend/app/routers/profile_chat.py`:

- **`GET /api/profile-chat`** — returns the tenant's message history:
  `{"messages": [{"role": "client"|"bot", "content": str, "created_at": str}, ...]}`,
  read from `profile_chat_messages` (already in the Phase 0 schema).
- **`POST /api/profile-chat`** — takes `{"message": str}`. Persists the
  client's message as a `profile_chat_messages` row first (so it's never
  lost even if what follows fails), loads the last 20 messages of
  conversation history plus the tenant's current `company_profile.profile_text`,
  sends both to GPT-4o in a single completion call — no function-calling,
  per the original spec — asking for JSON output shaped
  `{"reply": str, "profile_text": str}` (same `response_format: json_object`
  pattern already used in `scoring.py`). On success: persists the bot's
  `reply` as a `profile_chat_messages` row, upserts
  `company_profile.profile_text` with the model's updated version, and
  returns `{"reply": str, "profile_text": str}`.

On the frontend, the Profile tab's content is replaced entirely with a chat
panel: message bubbles for `client`/`bot` roles, a text input, and a send
button, styled with the existing glass/`ai-block` visual language (no new
design system introduced). Opening the tab loads history via
`GET /api/profile-chat`; if empty, a static greeting bubble is shown
client-side (no API call needed for that). Sending a message posts to
`POST /api/profile-chat` and appends both the user's bubble and the bot's
reply bubble once the response arrives.

## Components & files

- `backend/app/chat/profile_chat.py` (new) — `generate_reply(conversation:
  list[dict], profile_text: str, client=None) -> dict`. Mirrors
  `scoring.py`'s `extract_and_score` pattern: injectable `client` parameter
  for testability, lets exceptions propagate rather than swallowing them
  (the caller needs to distinguish "generation failed" from "generation
  succeeded," same reasoning as sub-project 1's scoring module).
- `backend/app/routers/profile_chat.py` (new) — the two endpoints above,
  both tenant-scoped via the existing `get_current_tenant_id` dependency,
  both plain `def` (not `async def` — this codebase has a hard rule against
  blocking I/O inside async routes, enforced repeatedly across Phase 0 and
  sub-project 1).
- `backend/app/main.py` (modified) — registers the new router.
- `index.html` (modified in place):
  - The Profile screen's HTML (the 16-field structured form) is deleted and
    replaced with a chat panel (message list + input row).
  - `saveProfile()`, the `PROFILE_FIELDS` array, and the field-row CSS
    become dead code and are removed.
  - New `loadProfileChat()` (called when the Profile screen becomes active,
    hooked into the existing `switchScreen('profile')` path) and
    `sendChatMessage()` functions, both using the existing `authHeaders()`
    helper.
  - The existing `POST`/`GET /api/profile` backend endpoints (from
    sub-project 2) are **left as-is, untouched**: `GET /api/profile` is
    still used by the Tenders screen's empty-state nudge
    (`checkProfileExists()`) to check whether a profile exists, regardless
    of which UI wrote it. `POST /api/profile` simply stops being called by
    anything once the structured form is removed — it costs nothing to
    leave in place, and removing working, tested code for no functional
    reason isn't worth the churn.

## Error handling & loading state

- **GPT-4o call fails or returns malformed JSON**: the client's message is
  already persisted before the model call, so it's never lost. The bot's
  reply is only persisted if generation succeeds. On failure, the endpoint
  returns `500`; the frontend shows the existing generic error toast and
  leaves the user's message bubble visible with no bot reply — on retry or
  reload, nothing is lost, the user can just send again.
- **Empty/whitespace-only message**: rejected client-side (send button
  no-ops on empty input) and backend-side (`400`) — no empty rows ever
  reach `profile_chat_messages`.
- **Unbounded conversation growth**: only the last 20 messages are sent to
  GPT-4o as context, not the full history — bounds prompt size without
  losing the recent context that actually matters for an evolving profile.
  Consistent with sub-project 1's truncation-hardening approach.
- **Loading state**: while waiting for a reply, the send button disables
  and a lightweight "..." typing-indicator bubble is shown, removed once
  the real reply arrives or the request fails — mirrors the existing
  `saving`/`spinning` button-state pattern already used elsewhere in this
  file (`saveProfile()`'s old saving state, `refreshTenders()`'s spinner).

## Testing approach

**Backend**: TDD per component, matching every other module in this
codebase — `generate_reply()` tested with a mocked OpenAI client (prompt
construction, JSON parsing, the 20-message truncation, and confirming it
does NOT swallow exceptions, mirroring `scoring.py`'s test suite exactly);
`profile_chat.py`'s router tested via FastAPI `TestClient` + a fake
Supabase client (auth required on both endpoints, message persistence order
— client message saved before the model call — profile_text upsert, and
the "user message persisted even if generation fails" behavior specifically).

**Frontend**: no test framework exists for this file (same situation as
sub-projects 1 and 2), so this is verified manually via a real browser,
walking the golden path (open chat → see greeting or history → send
message → see reply → `profile_text` updates, confirmed via the existing
`GET /api/profile` check) and the edge cases (empty conversation on first
open, a simulated generation failure, empty-message rejection).

## Out of scope for this spec

- No editing or deleting past chat messages — append-only, matching how
  `profile_chat_messages` was originally designed in Phase 0.
- No typing/streaming response (token-by-token) — a single request/response
  per turn, matching every other GPT-4o call in this codebase (scoring is
  also single-shot, not streamed).
- No changes to `POST`/`GET /api/profile` — both stay exactly as
  sub-project 2 left them.
