-- 0008_enable_rls.sql
-- Defense-in-depth: the backend exclusively uses the service_role key, which
-- bypasses RLS entirely, so this changes nothing about how the app behaves.
-- What it does change: if the anon/authenticated key were ever accidentally
-- exposed (client-side code, a leaked .env, a future feature added without
-- checking) or misused, it could not read or write a single row -- RLS
-- enabled with zero policies is a hard deny-by-default for every other role.

alter table tenants enable row level security;
alter table tenant_users enable row level security;
alter table company_profile enable row level security;
alter table tenders enable row level security;
alter table profile_chat_messages enable row level security;
alter table favorite_tenders enable row level security;
alter table favorite_chat_messages enable row level security;
alter table notified_tenders enable row level security;
alter table tenant_sources enable row level security;
