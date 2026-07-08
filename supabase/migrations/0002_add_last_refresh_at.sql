-- 0002_add_last_refresh_at.sql
-- Tracks the last time each tenant's tenders were refreshed, so
-- POST /api/refresh can enforce a cooldown between on-demand refreshes.

alter table tenants add column last_refresh_at timestamptz;
