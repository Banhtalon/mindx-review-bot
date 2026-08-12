insert into storage.buckets (id, name, public)
values ('browser-state', 'browser-state', false)
on conflict (id) do update set public = false;

create table public.browser_state_versions (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  site text not null check (site in ('teaching', 'lms')),
  object_path text not null check (
    object_path ~ '^browser-state/[0-9a-f-]{36}/(teaching|lms)/[0-9a-f-]{36}\.json$'
  ),
  key_version integer not null check (key_version > 0),
  state_hash text not null check (state_hash ~ '^[0-9a-f]{64}$'),
  status text not null check (status in ('active', 'revoked')),
  created_at timestamptz not null default now(),
  revoked_at timestamptz
);

create unique index browser_state_one_active_per_site
on public.browser_state_versions (workspace_id, site)
where status = 'active';

alter table public.browser_state_versions enable row level security;
revoke all on public.browser_state_versions from public, anon, authenticated;
grant select, insert, update on public.browser_state_versions to service_role;
grant select, insert, update on public.automation_runs to service_role;
grant update on public.automation_jobs to service_role;

create or replace function public.claim_automation_job_run(target_job_id uuid)
returns table (
  claimed boolean,
  run_id uuid,
  job_id uuid,
  workspace_id uuid,
  job_type text,
  payload_json jsonb,
  attempt integer
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  target_job public.automation_jobs;
  existing_run public.automation_runs;
  next_attempt integer;
  new_run_id uuid;
begin
  if auth.role() <> 'service_role' then
    raise exception 'RUNNER_RPC_INTERNAL_ONLY' using errcode = '42501';
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
  limit 1;

  if found then
    return query
    select
      false,
      existing_run.id,
      target_job.id,
      target_job.workspace_id,
      target_job.type,
      target_job.payload_json,
      existing_run.attempt;
    return;
  end if;

  if target_job.status not in ('dispatched', 'failed', 'partial') then
    raise exception 'JOB_NOT_READY' using errcode = '55000';
  end if;

  select coalesce(max(run.attempt), 0) + 1
  into next_attempt
  from public.automation_runs as run
  where run.job_id = target_job_id;

  insert into public.automation_runs (
    workspace_id,
    job_id,
    attempt,
    status,
    records_read,
    started_at
  )
  values (
    target_job.workspace_id,
    target_job.id,
    next_attempt,
    'running',
    0,
    now()
  )
  returning id into new_run_id;

  update public.automation_jobs
  set status = 'running'
  where public.automation_jobs.id = target_job.id;

  return query
  select
    true,
    new_run_id,
    target_job.id,
    target_job.workspace_id,
    target_job.type,
    target_job.payload_json,
    next_attempt;
end;
$$;

create or replace function public.finish_automation_job_run(
  target_run_id uuid,
  target_status text,
  target_records_read integer,
  target_error_code text
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

  if target_status not in ('succeeded', 'partial', 'failed', 'cancelled')
     or target_records_read is null
     or target_records_read < 0
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
  if target_run.status <> 'running' then
    raise exception 'RUN_ALREADY_FINISHED' using errcode = '55000';
  end if;

  update public.automation_runs
  set status = target_status,
      records_read = target_records_read,
      error_code = target_error_code,
      finished_at = now()
  where public.automation_runs.id = target_run_id;

  update public.automation_jobs
  set status = target_status
  where public.automation_jobs.id = target_run.job_id;

  return query select target_status;
end;
$$;

create or replace function public.activate_browser_state_version(
  target_workspace_id uuid,
  target_site text,
  target_version_id uuid,
  target_object_path text,
  target_key_version integer,
  target_state_hash text
)
returns table (version_id uuid, object_path text, status text)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.role() <> 'service_role' then
    raise exception 'RUNNER_RPC_INTERNAL_ONLY' using errcode = '42501';
  end if;
  if target_site not in ('teaching', 'lms')
     or target_key_version is null
     or target_key_version < 1
     or target_state_hash !~ '^[0-9a-f]{64}$'
     or target_object_path <> format(
       'browser-state/%s/%s/%s.json',
       target_workspace_id,
       target_site,
       target_version_id
     )
     or not exists (
       select 1 from public.workspaces where id = target_workspace_id
     ) then
    raise exception 'BROWSER_STATE_METADATA_INVALID' using errcode = '22023';
  end if;

  update public.browser_state_versions
  set status = 'revoked', revoked_at = now()
  where workspace_id = target_workspace_id
    and site = target_site
    and public.browser_state_versions.status = 'active';

  insert into public.browser_state_versions (
    id,
    workspace_id,
    site,
    object_path,
    key_version,
    state_hash,
    status
  )
  values (
    target_version_id,
    target_workspace_id,
    target_site,
    target_object_path,
    target_key_version,
    target_state_hash,
    'active'
  );

  return query
  select target_version_id, target_object_path, 'active'::text;
end;
$$;

create or replace function public.reset_browser_state(
  target_workspace_id uuid,
  target_site text
)
returns table (object_path text)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.role() <> 'service_role' or target_site not in ('teaching', 'lms') then
    raise exception 'RUNNER_RPC_INTERNAL_ONLY' using errcode = '42501';
  end if;

  return query
  update public.browser_state_versions
  set status = 'revoked', revoked_at = now()
  where workspace_id = target_workspace_id
    and site = target_site
    and status = 'active'
  returning browser_state_versions.object_path;
end;
$$;

revoke all on function public.claim_automation_job_run(uuid)
  from public, anon, authenticated;
revoke all on function public.finish_automation_job_run(uuid, text, integer, text)
  from public, anon, authenticated;
revoke all on function public.activate_browser_state_version(uuid, text, uuid, text, integer, text)
  from public, anon, authenticated;
revoke all on function public.reset_browser_state(uuid, text)
  from public, anon, authenticated;

grant execute on function public.claim_automation_job_run(uuid) to service_role;
grant execute on function public.finish_automation_job_run(uuid, text, integer, text)
  to service_role;
grant execute on function public.activate_browser_state_version(uuid, text, uuid, text, integer, text)
  to service_role;
grant execute on function public.reset_browser_state(uuid, text) to service_role;
