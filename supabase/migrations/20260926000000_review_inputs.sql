create table public.review_sessions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  external_session_key text not null check (btrim(external_session_key) <> ''),
  context_json jsonb not null default '{}'::jsonb,
  context_hash text not null check (btrim(context_hash) <> ''),
  status text not null default 'draft'
    check (status in ('draft', 'ready', 'exported', 'blocked')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, external_session_key),
  unique (workspace_id, id)
);

create table public.review_students (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  stable_key text not null check (btrim(stable_key) <> ''),
  display_label text not null check (btrim(display_label) <> ''),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, stable_key),
  unique (workspace_id, id)
);

create table public.review_inputs (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  session_id uuid not null,
  student_id uuid not null,
  attendance text not null default 'unknown'
    check (attendance in ('present', 'absent', 'unknown')),
  learning_level text not null default 'unknown'
    check (learning_level in ('strong', 'developing', 'needs_support', 'unknown')),
  note_draft text not null default '' check (char_length(note_draft) <= 10000),
  revision bigint not null default 1,
  updated_at timestamptz not null default now(),
  primary key (session_id, student_id),
  constraint review_inputs_revision_check check (revision > 0),
  foreign key (workspace_id, session_id)
    references public.review_sessions(workspace_id, id) on delete cascade,
  foreign key (workspace_id, student_id)
    references public.review_students(workspace_id, id) on delete cascade
);

-- Keep audit timestamps and optimistic-concurrency revisions owned by the
-- database.  Clients may submit a draft, but they cannot forge an older
-- timestamp or reuse a revision while retrying the same update.
create or replace function public.prepare_review_timestamp_write()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    new.created_at := statement_timestamp();
  end if;
  new.updated_at := statement_timestamp();
  return new;
end;
$$;

create or replace function public.prepare_review_input_write()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := statement_timestamp();
  if tg_op = 'INSERT' then
    new.revision := 1;
  else
    -- Always advance exactly once per committed update.  This makes retries
    -- observable and prevents a caller from moving the counter backwards.
    new.revision := old.revision + 1;
  end if;
  return new;
end;
$$;

create or replace function public.prevent_review_workspace_move()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' and new.workspace_id is distinct from old.workspace_id then
    raise exception 'REVIEW_WORKSPACE_IMMUTABLE' using errcode = '42501';
  end if;
  return new;
end;
$$;

create trigger review_sessions_prepare_write
before insert or update on public.review_sessions
for each row execute function public.prepare_review_timestamp_write();

create trigger review_students_prepare_write
before insert or update on public.review_students
for each row execute function public.prepare_review_timestamp_write();

create trigger review_inputs_prepare_write
before insert or update on public.review_inputs
for each row execute function public.prepare_review_input_write();

create trigger review_sessions_workspace_immutable
before update on public.review_sessions
for each row execute function public.prevent_review_workspace_move();

create trigger review_students_workspace_immutable
before update on public.review_students
for each row execute function public.prevent_review_workspace_move();

create trigger review_inputs_workspace_immutable
before update on public.review_inputs
for each row execute function public.prevent_review_workspace_move();

-- Update one draft only when the caller still owns the revision it read.  The
-- trigger above assigns the next revision, so retries with an old revision
-- cannot overwrite a newer draft.
create or replace function public.update_review_input_if_revision_matches(
  target_workspace_id uuid,
  target_session_id uuid,
  target_student_id uuid,
  target_attendance text,
  target_learning_level text,
  target_note_draft text,
  target_expected_revision bigint
)
returns table (
  status text,
  workspace_id uuid,
  session_id uuid,
  student_id uuid,
  attendance text,
  learning_level text,
  note_draft text,
  revision bigint
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  current_input public.review_inputs;
begin
  if target_expected_revision is null or target_expected_revision < 1
     or target_note_draft is null or char_length(target_note_draft) > 10000
     or target_attendance not in ('present', 'absent', 'unknown')
     or target_learning_level not in ('strong', 'developing', 'needs_support', 'unknown') then
    raise exception 'REVIEW_INPUT_INVALID' using errcode = '22023';
  end if;

  update public.review_inputs
  set attendance = target_attendance,
      learning_level = target_learning_level,
      note_draft = target_note_draft
  where public.review_inputs.workspace_id = target_workspace_id
    and public.review_inputs.session_id = target_session_id
    and public.review_inputs.student_id = target_student_id
    and public.review_inputs.revision = target_expected_revision
  returning * into current_input;

  if found then
    return query select
      'updated'::text,
      current_input.workspace_id,
      current_input.session_id,
      current_input.student_id,
      current_input.attendance,
      current_input.learning_level,
      current_input.note_draft,
      current_input.revision;
    return;
  end if;

  select * into current_input
  from public.review_inputs
  where public.review_inputs.workspace_id = target_workspace_id
    and public.review_inputs.session_id = target_session_id
    and public.review_inputs.student_id = target_student_id;

  if found then
    return query select
      'conflict'::text,
      current_input.workspace_id,
      current_input.session_id,
      current_input.student_id,
      current_input.attendance,
      current_input.learning_level,
      current_input.note_draft,
      current_input.revision;
  else
    return query select
      'missing'::text,
      null::uuid,
      null::uuid,
      null::uuid,
      null::text,
      null::text,
      null::text,
      null::bigint;
  end if;
end;
$$;

revoke all on function public.prepare_review_timestamp_write() from public;
revoke all on function public.prepare_review_input_write() from public;
revoke all on function public.prevent_review_workspace_move() from public;
revoke all on function public.update_review_input_if_revision_matches(uuid, uuid, uuid, text, text, text, bigint)
  from public, anon, authenticated;
grant execute on function public.update_review_input_if_revision_matches(uuid, uuid, uuid, text, text, text, bigint)
  to service_role;

alter table public.review_sessions enable row level security;
alter table public.review_students enable row level security;
alter table public.review_inputs enable row level security;

-- Supabase's local bootstrap can expose newly created tables to anon through
-- inherited/default grants.  Remove those grants explicitly before granting
-- the intended authenticated and service roles.
revoke all on public.review_sessions, public.review_students, public.review_inputs
  from anon, public;

grant select, insert, update
  on public.review_sessions, public.review_students, public.review_inputs
  to authenticated;
revoke update on public.review_inputs from authenticated;
grant select, update on public.review_inputs to service_role;

create policy review_sessions_select_member
on public.review_sessions
for select to authenticated
using (public.is_workspace_member(workspace_id));

create policy review_sessions_insert_member
on public.review_sessions
for insert to authenticated
with check (public.is_workspace_member(workspace_id));

create policy review_sessions_update_member
on public.review_sessions
for update to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy review_students_select_member
on public.review_students
for select to authenticated
using (public.is_workspace_member(workspace_id));

create policy review_students_insert_member
on public.review_students
for insert to authenticated
with check (public.is_workspace_member(workspace_id));

create policy review_students_update_member
on public.review_students
for update to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));

create policy review_inputs_select_member
on public.review_inputs
for select to authenticated
using (public.is_workspace_member(workspace_id));

create policy review_inputs_insert_member
on public.review_inputs
for insert to authenticated
with check (public.is_workspace_member(workspace_id));

create policy review_inputs_update_member
on public.review_inputs
for update to authenticated
using (public.is_workspace_member(workspace_id))
with check (public.is_workspace_member(workspace_id));
