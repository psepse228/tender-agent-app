-- 0004_add_favorite_tenders.sql
-- Favorites are a permanent copy of a tender, not a flag on the scraped
-- `tenders` table -- that table gets fully deleted and re-inserted on every
-- refresh (manual or the daily cron), so a flag there would vanish the next
-- time either one runs. Favoriting a tender snapshots it into this table
-- instead, where it survives refreshes untouched.

create table favorite_tenders (
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
create index idx_favorite_tenders_tenant_id on favorite_tenders(tenant_id);
