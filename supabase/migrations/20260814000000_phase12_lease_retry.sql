alter table public.automation_jobs
  add column if not exists max_attempts integer not null default 3,
  add column if not exists attempt_count integer not null default 0;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'automation_jobs_attempt_bounds'
      and conrelid = 'public.automation_jobs'::regclass
  ) then
    alter table public.automation_jobs
      add constraint automation_jobs_attempt_bounds
      check (max_attempts between 1 and 3 and attempt_count between 0 and max_attempts);
  end if;
end;
$$;

alter table public.automation_runs
  add column if not exists runner_id text,
  add column if not exists heartbeat_at timestamptz,
  add column if not exists lease_expires_at timestamptz,
  add column if not exists duration_ms integer not null default 0;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'automation_runs_runner_id_format'
      and conrelid = 'public.automation_runs'::regclass
  ) then
    alter table public.automation_runs
      add constraint automation_runs_runner_id_format
      check (runner_id is null or runner_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$');
  end if;
  if not exists (
    select 1
    from pg_constraint
    where conname = 'automation_runs_duration_bounds'
      and conrelid = 'public.automation_runs'::regclass
  ) then
    alter table public.automation_runs
      add constraint automation_runs_duration_bounds
      check (duration_ms between 0 and 86400000);
  end if;
end;
$$;

update public.automation_jobs as job
set attempt_count = greatest(
  job.attempt_count,
  coalesce((
    select max(run.attempt)
    from public.automation_runs as run
    where run.job_id = job.id
  ), 0)
);

update public.automation_runs
set heartbeat_at = coalesce(heartbeat_at, started_at),
    lease_expires_at = coalesce(lease_expires_at, started_at + interval '10 minutes')
where status = 'running';

create index if not exists automation_runs_active_lease_idx
on public.automation_runs (job_id, lease_expires_at)
where status = 'running';

drop function if exists public.claim_automation_job_run(uuid);
drop function if exists public.finish_automation_job_run(uuid, text, integer, text);

create or replace function public.claim_automation_job_run(
  target_job_id uuid,
  target_runner_id text
)
returns table (
  claimed boolean,
  run_id uuid,
  job_id uuid,
  workspace_id uuid,
  job_type text,
  payload_json jsonb,
  attempt integer,
  runner_id text,
  lease_expires_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  target_job public.automation_jobs;
  existing_run public.automation_runs;
  current_attempt integer;
  next_attempt integer;
  new_run_id uuid;
  new_lease timestamptz;
begin
  if auth.role() <> 'service_role' then
    raise exception 'RUNNER_RPC_INTERNAL_ONLY' using errcode = '42501';
  end if;
  if target_runner_id is null
     or target_runner_id !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$' then
    raise exception 'RUNNER_ID_INVALID' using errcode = '22023';
  end if;

  select * into target_job
  from public.automation_jobs
  where public.automation_jobs.id = target_job_id
  for update;

  if not found then
    raise exception 'JOB_NOT_FOUND' using errcode = 'P0002';
  end if;

  select * into existing_run
  from public.automation_runs as run
  where run.job_id = target_job_id
    and run.status = 'running'
  order by run.attempt desc
  limit 1
  for update;

  if found then
    if existing_run.lease_expires_at is not null
       and existing_run.lease_expires_at > now() then
      return query
      select
        false,
        existing_run.id,
        target_job.id,
        target_job.workspace_id,
        target_job.type,
        target_job.payload_json,
        existing_run.attempt,
        existing_run.runner_id,
        existing_run.lease_expires_at;
      return;
    end if;

    update public.automation_runs
    set status = 'failed',
        error_code = 'JOB_LEASE_EXPIRED',
        finished_at = now(),
        lease_expires_at = null,
        heartbeat_at = now()
    where public.automation_runs.id = existing_run.id;

    update public.automation_jobs
    set status = 'failed'
    where public.automation_jobs.id = target_job.id;
    target_job.status := 'failed';
  end if;

  if target_job.status not in ('dispatched', 'failed', 'partial') then
    raise exception 'JOB_NOT_READY' using errcode = '55000';
  end if;

  select greatest(
    target_job.attempt_count,
    coalesce(max(run.attempt), 0)
  )
  into current_attempt
  from public.automation_runs as run
  where run.job_id = target_job_id;

  if current_attempt >= target_job.max_attempts then
    raise exception 'JOB_MAX_ATTEMPTS_EXCEEDED' using errcode = '55000';
  end if;

  next_attempt := current_attempt + 1;
  new_lease := now() + interval '10 minutes';

  insert into public.automation_runs (
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
  values (
    target_job.workspace_id,
    target_job.id,
    next_attempt,
    'running',
    target_runner_id,
    0,
    now(),
    now(),
    new_lease
  )
  returning id into new_run_id;

  update public.automation_jobs
  set status = 'running',
      attempt_count = next_attempt
  where public.automation_jobs.id = target_job.id;

  return query
  select
    true,
    new_run_id,
    target_job.id,
    target_job.workspace_id,
    target_job.type,
    target_job.payload_json,
    next_attempt,
    target_runner_id,
    new_lease;
end;
$$;

create or replace function public.heartbeat_automation_job(
  target_job_id uuid,
  target_runner_id text
)
returns table (
  job_id uuid,
  runner_id text,
  lease_expires_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  target_run public.automation_runs;
  new_lease timestamptz;
begin
  if auth.role() <> 'service_role' then
    raise exception 'RUNNER_RPC_INTERNAL_ONLY' using errcode = '42501';
  end if;
  if target_runner_id is null
     or target_runner_id !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$' then
    raise exception 'RUNNER_ID_INVALID' using errcode = '22023';
  end if;

  select * into target_run
  from public.automation_runs as run
  where run.job_id = target_job_id
    and run.status = 'running'
  order by run.attempt desc
  limit 1
  for update;

  if not found or target_run.runner_id is distinct from target_runner_id then
    raise exception 'JOB_RUNNER_MISMATCH' using errcode = '42501';
  end if;
  if target_run.lease_expires_at is null or target_run.lease_expires_at <= now() then
    raise exception 'JOB_LEASE_EXPIRED' using errcode = '55000';
  end if;

  new_lease := now() + interval '10 minutes';
  update public.automation_runs
  set heartbeat_at = now(),
      lease_expires_at = new_lease
  where public.automation_runs.id = target_run.id;

  return query select target_job_id, target_runner_id, new_lease;
end;
$$;

create or replace function public.finish_automation_job_run(
  target_run_id uuid,
  target_runner_id text,
  target_status text,
  target_records_read integer,
  target_error_code text,
  target_duration_ms integer default 0
)
returns table (status text)
language plpgsql
security definer
set search_path = ''
as $$
declare
  target_run public.automation_runs;
begin
  if auth.role() <> 'service_role' then
    raise exception 'RUNNER_RPC_INTERNAL_ONLY' using errcode = '42501';
  end if;
  if target_runner_id is null
     or target_runner_id !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$'
     or target_status not in ('succeeded', 'partial', 'failed', 'cancelled')
     or target_records_read is null
     or target_records_read < 0
     or target_duration_ms is null
     or target_duration_ms < 0
     or target_duration_ms > 86400000
     or (target_error_code is not null
         and target_error_code !~ '^[A-Z][A-Z0-9_]{0,63}$') then
    raise exception 'RUNNER_RESULT_INVALID' using errcode = '22023';
  end if;

  select * into target_run
  from public.automation_runs
  where public.automation_runs.id = target_run_id
  for update;

  if not found then
    raise exception 'RUN_NOT_FOUND' using errcode = 'P0002';
  end if;
  if target_run.runner_id is distinct from target_runner_id then
    raise exception 'JOB_RUNNER_MISMATCH' using errcode = '42501';
  end if;
  if target_run.status <> 'running' then
    raise exception 'RUN_ALREADY_FINISHED' using errcode = '55000';
  end if;
  if target_run.lease_expires_at is null or target_run.lease_expires_at <= now() then
    raise exception 'JOB_LEASE_EXPIRED' using errcode = '55000';
  end if;

  update public.automation_runs
  set status = target_status,
      records_read = target_records_read,
      error_code = target_error_code,
      duration_ms = target_duration_ms,
      heartbeat_at = now(),
      lease_expires_at = null,
      finished_at = now()
  where public.automation_runs.id = target_run_id;

  update public.automation_jobs
  set status = target_status
  where public.automation_jobs.id = target_run.job_id;

  return query select target_status;
end;
$$;

revoke all on function public.claim_automation_job_run(uuid, text)
  from public, anon, authenticated;
revoke all on function public.heartbeat_automation_job(uuid, text)
  from public, anon, authenticated;
revoke all on function public.finish_automation_job_run(uuid, text, text, integer, text, integer)
  from public, anon, authenticated;

grant execute on function public.claim_automation_job_run(uuid, text) to service_role;
grant execute on function public.heartbeat_automation_job(uuid, text) to service_role;
grant execute on function public.finish_automation_job_run(uuid, text, text, integer, text, integer)
  to service_role;
