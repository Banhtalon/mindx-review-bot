-- Local synthetic Phase 1 seed only.
-- This file must remain deterministic, repeatable, and free of real identities or secrets.

insert into auth.users (
  id,
  aud,
  role,
  email,
  encrypted_password,
  email_confirmed_at
)
values (
  '11111111-1111-4111-8111-111111111111',
  'authenticated',
  'authenticated',
  'owner@example.invalid',
  'synthetic',
  now()
)
on conflict (id) do update
set aud = excluded.aud,
    role = excluded.role,
    email = excluded.email,
    encrypted_password = excluded.encrypted_password,
    email_confirmed_at = excluded.email_confirmed_at;

insert into public.workspaces (
  id,
  name,
  timezone
)
values (
  '22222222-2222-4222-8222-222222222222',
  'Synthetic Owner Workspace',
  'Asia/Ho_Chi_Minh'
)
on conflict (id) do update
set name = excluded.name,
    timezone = excluded.timezone;

insert into public.workspace_members (
  workspace_id,
  user_id,
  role
)
values (
  '22222222-2222-4222-8222-222222222222',
  '11111111-1111-4111-8111-111111111111',
  'owner'
)
on conflict (workspace_id, user_id) do update
set role = excluded.role;
