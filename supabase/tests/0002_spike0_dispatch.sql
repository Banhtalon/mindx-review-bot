begin;

select plan(16);

insert into auth.users (id, aud, role, email, encrypted_password, email_confirmed_at)
values
  ('00000000-0000-0000-0000-0000000000c1', 'authenticated', 'authenticated', 'system@example.invalid', 'synthetic', now());

insert into public.workspaces (id, name)
values ('00000000-0000-0000-0000-0000000000cc', 'Synthetic Dispatch Workspace');

set local role service_role;
select set_config('request.jwt.claim.role', 'service_role', true);

select is(
  (select created
   from public.enqueue_automation_job(
     '00000000-0000-0000-0000-0000000000cc',
     'sync_teaching',
     'synthetic-dispatch-001',
     '{}'::jsonb,
     '00000000-0000-0000-0000-0000000000c1'
   )),
  true,
  'first enqueue creates a job'
);
select is(
  (select status
   from public.automation_jobs
   where idempotency_key = 'synthetic-dispatch-001'),
  'queued',
  'new job starts queued'
);
select is(
  (select created
   from public.enqueue_automation_job(
     '00000000-0000-0000-0000-0000000000cc',
     'sync_teaching',
     'synthetic-dispatch-001',
     '{}'::jsonb,
     '00000000-0000-0000-0000-0000000000c1'
   )),
  false,
  'same idempotency key reuses the job'
);
select is(
  (select job_id
   from public.enqueue_automation_job(
     '00000000-0000-0000-0000-0000000000cc',
     'sync_teaching',
     'synthetic-dispatch-001',
     '{}'::jsonb,
     '00000000-0000-0000-0000-0000000000c1'
   )),
  (select id from public.automation_jobs where idempotency_key = 'synthetic-dispatch-001'),
  'same idempotency key returns the same job id'
);
select throws_ok(
  $$select * from public.enqueue_automation_job(
    '00000000-0000-0000-0000-0000000000cc',
    'sync_teaching',
    'synthetic-dispatch-001',
    '{"different": true}'::jsonb,
    '00000000-0000-0000-0000-0000000000c1'
  )$$,
  '23505',
  'IDEMPOTENCY_KEY_REUSED',
  'same key with different payload is rejected'
);

select is(
  (select claimed
   from public.claim_automation_job_dispatch(
     (select id from public.automation_jobs where idempotency_key = 'synthetic-dispatch-001')
   )),
  true,
  'first dispatch claim succeeds'
);
select is(
  (select status
   from public.automation_jobs
   where idempotency_key = 'synthetic-dispatch-001'),
  'dispatching',
  'claimed job becomes dispatching'
);
select is(
  (select claimed
   from public.claim_automation_job_dispatch(
     (select id from public.automation_jobs where idempotency_key = 'synthetic-dispatch-001')
   )),
  false,
  'second dispatch claim is rejected'
);
select is(
  (select status
   from public.claim_automation_job_dispatch(
     (select id from public.automation_jobs where idempotency_key = 'synthetic-dispatch-001')
   )),
  'dispatching',
  'second claim observes dispatching status'
);
select is(
  (select status
   from public.finish_automation_job_dispatch(
     (select id from public.automation_jobs where idempotency_key = 'synthetic-dispatch-001'),
     'dispatched'
   )),
  'dispatched',
  'successful GitHub dispatch becomes dispatched'
);
select is(
  (select claimed
   from public.claim_automation_job_dispatch(
     (select id from public.automation_jobs where idempotency_key = 'synthetic-dispatch-001')
   )),
  false,
  'dispatched job cannot be dispatched again'
);

select lives_ok(
  $$select * from public.enqueue_automation_job(
    '00000000-0000-0000-0000-0000000000cc',
    'read_lms_pending',
    'synthetic-dispatch-002',
    '{}'::jsonb,
    '00000000-0000-0000-0000-0000000000c1'
  )$$,
  'second job can be enqueued'
);
select lives_ok(
  $$select * from public.claim_automation_job_dispatch(
    (select id from public.automation_jobs where idempotency_key = 'synthetic-dispatch-002')
  )$$,
  'second job can be claimed'
);
select is(
  (select status
   from public.finish_automation_job_dispatch(
     (select id from public.automation_jobs where idempotency_key = 'synthetic-dispatch-002'),
     'dispatch_failed'
   )),
  'dispatch_failed',
  'failed GitHub dispatch is retained for retry'
);

set local role authenticated;
select set_config('request.jwt.claim.role', 'authenticated', true);
select throws_ok(
  $$select * from public.claim_automation_job_dispatch(
    (select id from public.automation_jobs where idempotency_key = 'synthetic-dispatch-001')
  )$$,
  '42501',
  null,
  'authenticated clients cannot call internal dispatch RPC'
);
select throws_ok(
  $$select * from public.enqueue_automation_job(
    '00000000-0000-0000-0000-0000000000cc',
    'unsupported',
    'synthetic-dispatch-003',
    '{}'::jsonb,
    '00000000-0000-0000-0000-0000000000c1'
  )$$,
  '42501',
  null,
  'unsupported job types are rejected before enqueue'
);

select * from finish();
rollback;
