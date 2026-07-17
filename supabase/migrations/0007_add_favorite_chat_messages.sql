-- 0007_add_favorite_chat_messages.sql
-- A dedicated AI chat thread per favorited tender, requested by the client
-- for "further detailed review" once a tender is saved. Scoped to
-- favorite_tenders (the permanent snapshot), not the volatile `tenders`
-- table, for the same reason favorites themselves live there.

create table favorite_chat_messages (
  id uuid primary key default gen_random_uuid(),
  favorite_id uuid not null references favorite_tenders(id),
  tenant_id uuid not null references tenants(id),
  role text not null check (role in ('client', 'bot')),
  content text not null,
  created_at timestamptz default now()
);
create index idx_favorite_chat_messages_favorite_id on favorite_chat_messages(favorite_id);
