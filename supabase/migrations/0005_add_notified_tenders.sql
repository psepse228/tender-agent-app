-- 0005_add_notified_tenders.sql
-- Dedup ledger for the "great tender found" push notification. Tenders get
-- fully wiped and re-scraped on every refresh, so without this a tender
-- scoring >=70 would trigger a fresh Telegram alert every single day it
-- keeps showing up, instead of only the first time it's seen.

create table notified_tenders (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id),
  title text not null,
  organization text not null,
  notified_at timestamptz default now()
);
create index idx_notified_tenders_tenant_id on notified_tenders(tenant_id);
create unique index idx_notified_tenders_dedup on notified_tenders(tenant_id, title, organization);
