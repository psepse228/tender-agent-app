-- 0003_add_owner_email.sql
-- Google OAuth self-serve signup: a tenant created via the web login flow is
-- identified by the owner's email instead of a telegram_user_id row in
-- tenant_users. Telegram Mini App auth (tenant_users) is unaffected --
-- both paths resolve to the same tenants.id.

alter table tenants add column owner_email text unique;
