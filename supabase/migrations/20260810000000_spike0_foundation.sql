create extension if not exists pgcrypto;

create table public.workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  timezone text not null default 'Asia/Ho_Chi_Minh',
  created_at timestamptz not null default now()
);

create table public.workspace_members (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner', 'reviewer')),
  created_at timestamptz not null default now(),
  primary key (workspace_id, user_id)
);

create table public.automation_jobs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  type text not null check (type in ('sync_teaching', 'read_lms_pending')),
  status text not null default 'queued'
    check (status in (
      'queued', 'dispatching', 'dispatched', 'running', 'succeeded',
      'partial', 'dispatch_failed', 'failed', 'cancelled'
    )),
  idempotency_key text not null,
  requested_by uuid not null references auth.users(id),
  payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (workspace_id, idempotency_key)
);

create table public.automation_runs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  job_id uuid not null references public.automation_jobs(id) on delete cascade,
  attempt integer not null check (attempt > 0),
  status text not null,
  records_read integer not null default 0 check (records_read >= 0),
  error_code text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  unique (job_id, attempt)
);

create or replace function public.is_workspace_member(target_workspace uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.workspace_members member
    where member.workspace_id = target_workspace
      and member.user_id = auth.uid()
  );
$$;

create or replace function public.has_workspace_role(
  target_workspace uuid,
  allowed_roles text[]
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.workspace_members member
    where member.workspace_id = target_workspace
      and member.user_id = auth.uid()
      and member.role = any(allowed_roles)
  );
$$;

revoke all on function public.is_workspace_member(uuid) from public;
revoke all on function public.has_workspace_role(uuid, text[]) from public;
grant execute on function public.is_workspace_member(uuid) to authenticated;
grant execute on function public.has_workspace_role(uuid, text[]) to authenticated;

alter table public.workspaces enable row level security;
alter table public.workspace_members enable row level security;
alter table public.automation_jobs enable row level security;
alter table public.automation_runs enable row level security;

grant select on public.workspaces, public.workspace_members,
  public.automation_jobs, public.automation_runs to anon, authenticated;
grant insert on public.automation_jobs to authenticated;

create policy workspaces_select_member
on public.workspaces
for select to authenticated
using (public.is_workspace_member(id));

create policy workspace_members_select_member
on public.workspace_members
for select to authenticated
using (public.is_workspace_member(workspace_id));

create policy automation_jobs_select_member
on public.automation_jobs
for select to authenticated
using (public.is_workspace_member(workspace_id));

create policy automation_jobs_insert_owner
on public.automation_jobs
for insert to authenticated
with check (
  public.has_workspace_role(workspace_id, array['owner'])
  and requested_by = auth.uid()
);

create policy automation_runs_select_member
on public.automation_runs
for select to authenticated
using (public.is_workspace_member(workspace_id));
