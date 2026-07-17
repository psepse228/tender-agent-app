-- 0006_add_tenant_sources.sql
-- Lets a tenant add their own tender-listing websites on top of the shared
-- SOURCES list in app/scraping/pipeline.py, without a developer needing to
-- hardcode it. Read by refresh_tenant() and scraped the same way as the
-- shared sources.

create table tenant_sources (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id),
  name text not null,
  url text not null,
  created_at timestamptz default now()
);
create index idx_tenant_sources_tenant_id on tenant_sources(tenant_id);
