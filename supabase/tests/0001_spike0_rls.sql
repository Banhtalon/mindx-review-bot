begin;

select plan(22);

select has_table('public', 'workspaces', 'workspaces table exists');
select has_table('public', 'workspace_members', 'workspace_members table exists');
select has_table('public', 'automation_jobs', 'automation_jobs table exists');
select has_table('public', 'automation_runs', 'automation_runs table exists');
select is(
  (select attnotnull from pg_attribute
    where attrelid = 'public.automation_jobs'::regclass
      and attname = 'requested_by'),
  true,
  'automation job attribution is not nullable'
);

select is(
  (select relrowsecurity from pg_class where oid = 'public.workspaces'::regclass),
  true,
  'workspaces has RLS enabled'
);

select is(
  (select relrowsecurity from pg_class where oid = 'public.automation_jobs'::regclass),
  true,
  'automation_jobs has RLS enabled'
);
select is(
  (select relrowsecurity from pg_class where oid = 'public.workspace_members'::regclass),
  true,
  'workspace_members has RLS enabled'
);
select is(
  (select relrowsecurity from pg_class where oid = 'public.automation_runs'::regclass),
  true,
  'automation_runs has RLS enabled'
);

select policies_are('public', 'workspaces', array['workspaces_select_member'], 'workspaces policies exist');
select policies_are(
  'public',
  'automation_jobs',
  array['automation_jobs_insert_owner', 'automation_jobs_select_member'],
  'job policies exist'
);
select policies_are(
  'public',
  'workspace_members',
  array['workspace_members_select_member'],
  'workspace member policies exist'
);
select policies_are(
  'public',
  'automation_runs',
  array['automation_runs_select_member'],
  'automation run policies exist'
);

insert into auth.users (id, aud, role, email, encrypted_password, email_confirmed_at)
values
  ('00000000-0000-0000-0000-0000000000a1', 'authenticated', 'authenticated', 'owner-a@example.invalid', 'synthetic', now()),
  ('00000000-0000-0000-0000-0000000000b1', 'authenticated', 'authenticated', 'owner-b@example.invalid', 'synthetic', now());

insert into public.workspaces (id, name)
values
  ('00000000-0000-0000-0000-0000000000aa', 'Synthetic Workspace A'),
  ('00000000-0000-0000-0000-0000000000bb', 'Synthetic Workspace B');

insert into public.workspace_members (workspace_id, user_id, role)
values
  ('00000000-0000-0000-0000-0000000000aa', '00000000-0000-0000-0000-0000000000a1', 'owner'),
  ('00000000-0000-0000-0000-0000000000bb', '00000000-0000-0000-0000-0000000000b1', 'owner');

set local role anon;
select set_config('request.jwt.claim.sub', '', true);
select is((select count(*) from public.workspaces), 0::bigint, 'anonymous cannot read workspaces');

set local role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000a1', true);
select is((select count(*) from public.workspaces), 1::bigint, 'owner A reads only workspace A');
select lives_ok(
  $$insert into public.automation_jobs (workspace_id, type, idempotency_key, requested_by)
    values ('00000000-0000-0000-0000-0000000000aa', 'sync_teaching', 'synthetic-key-a', auth.uid())$$,
  'owner A can create a job in workspace A'
);
select throws_ok(
  $$insert into public.automation_jobs (workspace_id, type, idempotency_key, requested_by)
    values ('00000000-0000-0000-0000-0000000000aa', 'sync_teaching', 'synthetic-key-a', auth.uid())$$,
  '23505',
  null,
  'duplicate idempotency key is rejected'
);
select throws_ok(
  $$insert into public.automation_jobs (workspace_id, type, idempotency_key, requested_by)
    values ('00000000-0000-0000-0000-0000000000aa', 'sync_teaching', 'synthetic-key-wrong-attribution', '00000000-0000-0000-0000-0000000000b1')$$,
  '42501',
  null,
  'owner A cannot attribute a job to another user'
);
select throws_ok(
  $$insert into public.automation_jobs (workspace_id, type, idempotency_key, requested_by)
    values ('00000000-0000-0000-0000-0000000000aa', 'sync_teaching', 'synthetic-key-null-attribution', null)$$,
  '42501',
  null,
  'job attribution cannot be omitted'
);

select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-0000000000b1', true);
select is((select count(*) from public.workspaces), 1::bigint, 'owner B reads only workspace B');
select is(
  (select count(*) from public.automation_jobs where idempotency_key = 'synthetic-key-a'),
  0::bigint,
  'owner B cannot read workspace A jobs'
);
select throws_ok(
  $$insert into public.automation_jobs (workspace_id, type, idempotency_key, requested_by)
    values ('00000000-0000-0000-0000-0000000000aa', 'sync_teaching', 'synthetic-key-b', auth.uid())$$,
  '42501',
  null,
  'owner B cannot create a job in workspace A'
);

select * from finish();
rollback;
