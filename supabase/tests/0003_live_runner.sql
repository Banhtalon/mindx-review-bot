begin;

select plan(29);

insert into auth.users (id, aud, role, email, encrypted_password, email_confirmed_at)
values
  ('00000000-0000-4000-8000-000000000011', 'authenticated', 'authenticated', 'runner@example.invalid', 'synthetic', now());

insert into public.workspaces (id, name)
values ('00000000-0000-4000-8000-000000000012', 'Synthetic Live Runner Workspace');

insert into public.automation_jobs (
  id,
  workspace_id,
  type,
  status,
  idempotency_key,
  requested_by,
  payload_json
)
values (
  '00000000-0000-4000-8000-000000000013',
  '00000000-0000-4000-8000-000000000012',
  'read_lms_pending',
  'dispatched',
  'synthetic-live-runner-001',
  '00000000-0000-4000-8000-000000000011',
  '{}'::jsonb
);

insert into public.automation_jobs (
  id,
  workspace_id,
  type,
  status,
  idempotency_key,
  requested_by,
  payload_json
)
values (
  '00000000-0000-4000-8000-000000000014',
  '00000000-0000-4000-8000-000000000012',
  'read_lms_pending',
  'dispatched',
  'synthetic-live-runner-002',
  '00000000-0000-4000-8000-000000000011',
  '{}'::jsonb
);

insert into public.automation_runs (
  id, workspace_id, job_id, attempt, status, started_at
)
values (
  '00000000-0000-4000-8000-000000000015',
  '00000000-0000-4000-8000-000000000012',
  '00000000-0000-4000-8000-000000000014',
  1,
  'running',
  now() - interval '21 minutes'
);

set local role service_role;
select set_config('request.jwt.claim.role', 'service_role', true);

select ok(
  (select claimed
   from public.claim_automation_job_run('00000000-0000-4000-8000-000000000013')),
  'service runner can atomically claim a dispatched job'
);
select is(
  (select status from public.automation_jobs where id = '00000000-0000-4000-8000-000000000013'),
  'running',
  'claim changes the job to running'
);
select is(
  (select count(*)::integer from public.automation_runs where job_id = '00000000-0000-4000-8000-000000000013'),
  1,
  'claim creates exactly one automation run'
);
select ok(
  not (select claimed
       from public.claim_automation_job_run('00000000-0000-4000-8000-000000000013')),
  'a running job cannot be claimed twice'
);

select ok(
  (select claimed
   from public.claim_automation_job_run('00000000-0000-4000-8000-000000000014')),
  'a stale running job can be reclaimed after the lease window'
);
select is(
  (select error_code from public.automation_runs where id = '00000000-0000-4000-8000-000000000015'),
  'JOB_LEASE_EXPIRED',
  'stale run is closed with a safe lease error'
);
select is(
  (select attempt from public.automation_runs where job_id = '00000000-0000-4000-8000-000000000014' and status = 'running'),
  2,
  'reclaimed job receives the next attempt number'
);
select is(
  (select count(*)::integer from public.automation_runs where job_id = '00000000-0000-4000-8000-000000000014'),
  2,
  'reclaim preserves the stale run audit row'
);

select is(
  (select status
   from public.finish_automation_job_run(
     (select id from public.automation_runs where job_id = '00000000-0000-4000-8000-000000000013'),
     'succeeded',
     4,
     null
   )),
  'succeeded',
  'service runner can finish a successful run'
);
select is(
  (select status from public.automation_jobs where id = '00000000-0000-4000-8000-000000000013'),
  'succeeded',
  'finishing a run updates its job status'
);
select is(
  (select records_read from public.automation_runs where job_id = '00000000-0000-4000-8000-000000000013'),
  4,
  'finish stores only the numeric records-read metric'
);

select lives_ok(
  $$select * from public.activate_browser_state_version(
    '00000000-0000-4000-8000-000000000012',
    'lms',
    '00000000-0000-4000-8000-000000000021',
    'browser-state/00000000-0000-4000-8000-000000000012/lms/00000000-0000-4000-8000-000000000021.json',
    1,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
  )$$,
  'first browser state version can be activated'
);
select is(
  (select status from public.browser_state_versions where id = '00000000-0000-4000-8000-000000000021'),
  'active',
  'first browser state version is active'
);
select lives_ok(
  $$select * from public.activate_browser_state_version(
    '00000000-0000-4000-8000-000000000012',
    'lms',
    '00000000-0000-4000-8000-000000000022',
    'browser-state/00000000-0000-4000-8000-000000000012/lms/00000000-0000-4000-8000-000000000022.json',
    2,
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
  )$$,
  'key rotation can activate a replacement version'
);
select is(
  (select status from public.browser_state_versions where id = '00000000-0000-4000-8000-000000000021'),
  'revoked',
  'activating a replacement revokes the previous version'
);
select is(
  (select status from public.browser_state_versions where id = '00000000-0000-4000-8000-000000000022'),
  'active',
  'replacement browser state version is active'
);
select is(
  (select object_path from public.reset_browser_state('00000000-0000-4000-8000-000000000012', 'lms')),
  'browser-state/00000000-0000-4000-8000-000000000012/lms/00000000-0000-4000-8000-000000000022.json',
  'reset returns only the active object path for deletion'
);
select is(
  (select status from public.browser_state_versions where id = '00000000-0000-4000-8000-000000000022'),
  'revoked',
  'reset revokes the active browser state version'
);
select is(
  (select public from storage.buckets where id = 'browser-state'),
  false,
  'browser-state bucket is private'
);
select ok(
  (select relrowsecurity from pg_class where oid = 'storage.objects'::regclass)
  and not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
  ),
  'storage objects are RLS-enabled with no public policies'
);

set local role authenticated;
select set_config('request.jwt.claim.role', 'authenticated', true);
select is(
  (select count(*)::integer from storage.objects where bucket_id = 'browser-state'),
  0,
  'authenticated clients cannot read browser-state objects'
);
select throws_ok(
  $$insert into storage.objects (bucket_id, name, metadata)
    values ('browser-state', 'synthetic-denied.json', '{}'::jsonb)$$,
  '42501',
  null,
  'authenticated clients cannot upload browser-state objects'
);
select throws_ok(
  $$select * from public.claim_automation_job_run('00000000-0000-4000-8000-000000000013')$$,
  '42501',
  null,
  'authenticated clients cannot claim runner jobs'
);
select throws_ok(
  $$select * from public.finish_automation_job_run(
    '00000000-0000-4000-8000-000000000013', 'failed', 0, null
  )$$,
  '42501',
  null,
  'authenticated clients cannot finish runner jobs'
);
select throws_ok(
  $$select * from public.activate_browser_state_version(
    '00000000-0000-4000-8000-000000000012', 'lms',
    '00000000-0000-4000-8000-000000000023',
    'browser-state/00000000-0000-4000-8000-000000000012/lms/00000000-0000-4000-8000-000000000023.json',
    1,
    'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'
  )$$,
  '42501',
  null,
  'authenticated clients cannot activate browser state'
);
select throws_ok(
  $$select * from public.reset_browser_state(
    '00000000-0000-4000-8000-000000000012', 'lms'
  )$$,
  '42501',
  null,
  'authenticated clients cannot reset browser state'
);
select throws_ok(
  $$select * from public.browser_state_versions$$,
  '42501',
  null,
  'authenticated clients cannot read browser state metadata'
);

set local role anon;
select set_config('request.jwt.claim.role', 'anon', true);
select is(
  (select count(*)::integer from storage.objects where bucket_id = 'browser-state'),
  0,
  'anonymous clients cannot read browser-state objects'
);
select throws_ok(
  $$insert into storage.objects (bucket_id, name, metadata)
    values ('browser-state', 'synthetic-anon-denied.json', '{}'::jsonb)$$,
  '42501',
  null,
  'anonymous clients cannot upload browser-state objects'
);

select * from finish();
rollback;
