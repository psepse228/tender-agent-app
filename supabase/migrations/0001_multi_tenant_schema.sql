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
