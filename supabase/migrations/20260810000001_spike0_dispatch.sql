create or replace function public.enqueue_automation_job(
  target_workspace_id uuid,
  target_type text,
  target_idempotency_key text,
  target_payload jsonb,
  target_requested_by uuid
)
returns table (
  job_id uuid,
  workspace_id uuid,
  job_type text,
  status text,
  idempotency_key text,
  payload_json jsonb,
  requested_by uuid,
  created boolean
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  existing_job public.automation_jobs;
begin
  if auth.role() <> 'service_role' then
    raise exception 'DISPATCH_RPC_INTERNAL_ONLY' using errcode = '42501';
  end if;

  if target_type not in ('sync_teaching', 'read_lms_pending') then
    raise exception 'UNSUPPORTED_JOB_TYPE' using errcode = '22023';
  end if;

  if target_workspace_id is null
     or not exists (
       select 1 from public.workspaces
       where id = target_workspace_id
     ) then
    raise exception 'WORKSPACE_NOT_FOUND' using errcode = '22023';
  end if;

  if target_idempotency_key is null
     or length(target_idempotency_key) > 128
     or target_idempotency_key !~ '^[a-z0-9][a-z0-9._:-]{0,127}$' then
    raise exception 'INVALID_IDEMPOTENCY_KEY' using errcode = '22023';
  end if;

  if target_payload is null or jsonb_typeof(target_payload) <> 'object' then
    raise exception 'INVALID_JOB_PAYLOAD' using errcode = '22023';
  end if;

  if target_requested_by is null
     or not exists (
       select 1 from auth.users
       where id = target_requested_by
     ) then
    raise exception 'REQUESTED_BY_NOT_FOUND' using errcode = '22023';
  end if;

  insert into public.automation_jobs (
    workspace_id,
    type,
    status,
    idempotency_key,
    requested_by,
    payload_json
  )
  values (
    target_workspace_id,
    target_type,
    'queued',
    target_idempotency_key,
    target_requested_by,
    target_payload
  )
  on conflict on constraint automation_jobs_workspace_id_idempotency_key_key do nothing
  returning * into existing_job;

  if found then
    return query
    select
      existing_job.id,
      existing_job.workspace_id,
      existing_job.type,
      existing_job.status,
      existing_job.idempotency_key,
      existing_job.payload_json,
      existing_job.requested_by,
      true;
    return;
  end if;

  select * into existing_job
  from public.automation_jobs as job
  where job.workspace_id = target_workspace_id
    and job.idempotency_key = target_idempotency_key;

  if existing_job.type is distinct from target_type
     or existing_job.payload_json is distinct from target_payload then
    raise exception 'IDEMPOTENCY_KEY_REUSED' using errcode = '23505';
  end if;

  return query
  select
    existing_job.id,
    existing_job.workspace_id,
    existing_job.type,
    existing_job.status,
    existing_job.idempotency_key,
    existing_job.payload_json,
    existing_job.requested_by,
    false;
end;
$$;

create or replace function public.claim_automation_job_dispatch(target_job_id uuid)
returns table (claimed boolean, status text)
language plpgsql
security definer
set search_path = ''
as $$
declare
  current_status text;
begin
  if auth.role() <> 'service_role' then
    raise exception 'DISPATCH_RPC_INTERNAL_ONLY' using errcode = '42501';
  end if;

  update public.automation_jobs
  set status = 'dispatching'
  where automation_jobs.id = target_job_id
    and automation_jobs.status in ('queued', 'dispatch_failed')
  returning automation_jobs.status into current_status;

  if found then
    return query select true, current_status;
    return;
  end if;

  select automation_jobs.status into current_status
  from public.automation_jobs
  where automation_jobs.id = target_job_id;

  if current_status is null then
    raise exception 'JOB_NOT_FOUND' using errcode = 'P0002';
  end if;

  return query select false, current_status;
end;
$$;

create or replace function public.finish_automation_job_dispatch(
  target_job_id uuid,
  target_status text
)
returns table (status text)
language plpgsql
security definer
set search_path = ''
as $$
declare
  current_status text;
begin
  if auth.role() <> 'service_role' then
    raise exception 'DISPATCH_RPC_INTERNAL_ONLY' using errcode = '42501';
  end if;

  if target_status not in ('dispatched', 'dispatch_failed') then
    raise exception 'INVALID_DISPATCH_STATUS' using errcode = '22023';
  end if;

  update public.automation_jobs
  set status = target_status
  where automation_jobs.id = target_job_id
    and automation_jobs.status = 'dispatching'
  returning automation_jobs.status into current_status;

  if found then
    return query select current_status;
    return;
  end if;

  select automation_jobs.status into current_status
  from public.automation_jobs
  where automation_jobs.id = target_job_id;

  if current_status is null then
    raise exception 'JOB_NOT_FOUND' using errcode = 'P0002';
  end if;

  return query select current_status;
end;
$$;

revoke all on function public.enqueue_automation_job(uuid, text, text, jsonb, uuid)
  from public, anon, authenticated;
revoke all on function public.claim_automation_job_dispatch(uuid)
  from public, anon, authenticated;
revoke all on function public.finish_automation_job_dispatch(uuid, text)
  from public, anon, authenticated;

grant execute on function public.enqueue_automation_job(uuid, text, text, jsonb, uuid)
  to service_role;
grant execute on function public.claim_automation_job_dispatch(uuid)
  to service_role;
grant execute on function public.finish_automation_job_dispatch(uuid, text)
  to service_role;

grant select on public.automation_jobs to service_role;
