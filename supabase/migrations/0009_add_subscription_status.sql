-- 0009_add_subscription_status.sql
-- v1 billing: no payment processor yet, manual bank transfer only. This is a
-- manually-managed lever, not automated dunning -- the owner marks a tenant
-- 'suspended' after chasing an unpaid invoice, and 'active' again once paid.
-- Defaults every existing and new tenant to 'active' so nobody currently
-- using the product gets locked out by this migration landing.

alter table tenants add column if not exists subscription_status text not null default 'active'
  check (subscription_status in ('active', 'suspended'));

-- Flat monthly fee, same for everyone (per-tenant so a negotiated rate can
-- still be recorded later without a schema change). Nullable -- the actual
-- number is a business decision to be filled in per tenant, not guessed here.
alter table tenants add column if not exists plan_price_monthly numeric;
