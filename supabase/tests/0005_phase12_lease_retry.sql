begin;

select plan(17);

insert into auth.users (id, aud, role, email, encrypted_password, email_confirmed_at)
values (
  '00000000-0000-4000-8000-000000000031',
  'authenticated',
  'authenticated',
  'phase12-runner@example.invalid',
  'synthetic',
  '2026-01-01T00:00:00+00:00'::timestamptz
);

insert into public.workspaces (id, name)
values ('00000000-0000-4000-8000-000000000032', 'Synthetic Phase 1-2 Workspace');

insert into public.automation_jobs (
  id,
  workspace_id,
  type,
  status,
  idempotency_key,
  requested_by,
  payload_json,
  max_attempts,
  attempt_count
)
values
(
  '00000000-0000-4000-8000-000000000033',
  '00000000-0000-4000-8000-000000000032',
  'read_lms_pending',
  'dispatched',
  'phase12-active-001',
  '00000000-0000-4000-8000-000000000031',
  '{}'::jsonb,
  3,
  0
),
(
  '00000000-0000-4000-8000-000000000034',
  '00000000-0000-4000-8000-000000000032',
  'read_lms_pending',
  'running',
  'phase12-stale-001',
  '00000000-0000-4000-8000-000000000031',
  '{}'::jsonb,
  3,
  1
),
(
  '00000000-0000-4000-8000-000000000035',
  '00000000-0000-4000-8000-000000000032',
  'read_lms_pending',
  'failed',
  'phase12-terminal-001',
  '00000000-0000-4000-8000-000000000031',
  '{}'::jsonb,
  3,
  3
);

insert into public.automation_runs (
  id,
  workspace_id,
  job_id,
  attempt,
  status,
  runner_id,
  records_read,
  started_at,
  heartbeat_at,
  lease_expires_at
)
values
(
  '00000000-0000-4000-8000-000000000036',
  '00000000-0000-4000-8000-000000000032',
  '00000000-0000-4000-8000-000000000034',
  1,
  'running',
  'runner-old',
  0,
  now() - interval '11 minutes',
  now() - interval '11 minutes',
  now() - interval '1 minute'
),
(
  '00000000-0000-4000-8000-000000000037',
  '00000000-0000-4000-8000-000000000032',
  '00000000-0000-4000-8000-000000000035',
  1,
  'failed',
  'runner-old',
  0,
  now() - interval '30 minutes',
  now() - interval '30 minutes',
  null
),
(
  '00000000-0000-4000-8000-000000000038',
  '00000000-0000-4000-8000-000000000032',
  '00000000-0000-4000-8000-000000000035',
  2,
  'failed',
  'runner-old',
  0,
  now() - interval '20 minutes',
  now() - interval '20 minutes',
  null
),
(
  '00000000-0000-4000-8000-000000000039',
  '00000000-0000-4000-8000-000000000032',
  '00000000-0000-4000-8000-000000000035',
  3,
  'failed',
  'runner-old',
  0,
  now() - interval '10 minutes',
  now() - interval '10 minutes',
  null
);

set local role service_role;
select set_config('request.jwt.claim.role', 'service_role', true);

select ok(
  (select claimed
   from public.claim_automation_job_run(
     '00000000-0000-4000-8000-000000000033',
     'runner-a'
   )),
  'runner A can claim a dispatched job'
);
select is(
  (select runner_id from public.automation_runs
   where job_id = '00000000-0000-4000-8000-000000000033'
     and status = 'running'),
  'runner-a',
  'claim records the owning runner id'
);
select ok(
  not (select claimed
       from public.claim_automation_job_run(
         '00000000-0000-4000-8000-000000000033',
         'runner-b'
       )),
  'an active lease cannot be claimed by another runner'
);
select ok(
  (select lease_expires_at > now() + interval '9 minutes'
   from public.heartbeat_automation_job(
     '00000000-0000-4000-8000-000000000033',
     'runner-a'
   )),
  'the owning runner can extend its ten minute lease'
);
select throws_ok(
  $$select * from public.finish_automation_job_run(
    (select id from public.automation_runs
     where job_id = '00000000-0000-4000-8000-000000000033'
       and status = 'running'),
    'runner-b',
    'succeeded',
    0,
    null,
    10
  )$$,
  '42501',
  'JOB_RUNNER_MISMATCH',
  'a different runner cannot finish the active run'
);
select is(
  (select status from public.finish_automation_job_run(
    (select id from public.automation_runs
     where job_id = '00000000-0000-4000-8000-000000000033'
       and status = 'running'),
    'runner-a',
    'succeeded',
    4,
    null,
    123
  )),
  'succeeded',
  'the owning runner can finish the active run'
);
select is(
  (select records_read from public.automation_runs
   where job_id = '00000000-0000-4000-8000-000000000033'),
  4,
  'finish stores the numeric records-read metric'
);
select is(
  (select duration_ms from public.automation_runs
   where job_id = '00000000-0000-4000-8000-000000000033'),
  123,
  'finish stores the bounded duration metric'
);
select is(
  (select status from public.automation_jobs
   where id = '00000000-0000-4000-8000-000000000033'),
  'succeeded',
  'finishing a run updates its job status'
);

select ok(
  (select claimed
   from public.claim_automation_job_run(
     '00000000-0000-4000-8000-000000000034',
     'runner-b'
   )),
  'an expired lease can be recovered by another runner'
);
select is(
  (select error_code from public.automation_runs
   where id = '00000000-0000-4000-8000-000000000036'),
  'JOB_LEASE_EXPIRED',
  'expired runs close with a safe lease error'
);
select is(
  (select attempt from public.automation_runs
   where job_id = '00000000-0000-4000-8000-000000000034'
     and status = 'running'),
  2,
  'lease recovery increments the attempt number'
);
select is(
  (select runner_id from public.automation_runs
   where job_id = '00000000-0000-4000-8000-000000000034'
     and status = 'running'),
  'runner-b',
  'lease recovery transfers ownership only through a new run'
);
select throws_ok(
  $$select * from public.claim_automation_job_run(
    '00000000-0000-4000-8000-000000000035',
    'runner-a'
  )$$,
  '55000',
  'JOB_MAX_ATTEMPTS_EXCEEDED',
  'a job cannot be claimed after three attempts'
);

set local role authenticated;
select set_config('request.jwt.claim.role', 'authenticated', true);
select throws_ok(
  $$select * from public.claim_automation_job_run(
    '00000000-0000-4000-8000-000000000035',
    'runner-a'
  )$$,
  '42501',
  null,
  'authenticated clients cannot claim runner jobs'
);
select throws_ok(
  $$select * from public.heartbeat_automation_job(
    '00000000-0000-4000-8000-000000000033',
    'runner-a'
  )$$,
  '42501',
  null,
  'authenticated clients cannot heartbeat runner jobs'
);
select throws_ok(
  $$select * from public.finish_automation_job_run(
    '00000000-0000-4000-8000-000000000033',
    'runner-a',
    'failed',
    0,
    'RUNNER_FAILED',
    0
  )$$,
  '42501',
  null,
  'authenticated clients cannot finish runner jobs'
);

select * from finish();
rollback;
