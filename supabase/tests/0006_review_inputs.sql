begin;

select plan(35);

select has_table('public', 'review_sessions', 'review_sessions table exists');
select has_table('public', 'review_students', 'review_students table exists');
select has_table('public', 'review_inputs', 'review_inputs table exists');

select ok(
  (select relrowsecurity from pg_class where oid = 'public.review_sessions'::regclass),
  'review_sessions has RLS enabled'
);
select ok(
  (select relrowsecurity from pg_class where oid = 'public.review_students'::regclass),
  'review_students has RLS enabled'
);
select ok(
  (select relrowsecurity from pg_class where oid = 'public.review_inputs'::regclass),
  'review_inputs has RLS enabled'
);

select policies_are(
  'public',
  'review_sessions',
  array[
    'review_sessions_select_member',
    'review_sessions_insert_member',
    'review_sessions_update_member'
  ],
  'review_sessions policies are explicit'
);
select policies_are(
  'public',
  'review_students',
  array[
    'review_students_select_member',
    'review_students_insert_member',
    'review_students_update_member'
  ],
  'review_students policies are explicit'
);
select policies_are(
  'public',
  'review_inputs',
  array[
    'review_inputs_select_member',
    'review_inputs_insert_member',
    'review_inputs_update_member'
  ],
  'review_inputs policies are explicit'
);

select is(
  (select count(*) from information_schema.role_table_grants
   where table_schema = 'public'
     and table_name in ('review_sessions', 'review_students', 'review_inputs')
     and grantee = 'anon'),
  0::bigint,
  'anonymous role receives no review table grant'
);

select ok(
  exists (
    select 1
    from pg_trigger
    where tgrelid = 'public.review_sessions'::regclass
      and tgname = 'review_sessions_prepare_write'
      and not tgisinternal
  ),
  'review_sessions owns audit timestamps through a trigger'
);
select ok(
  exists (
    select 1
    from pg_trigger
    where tgrelid = 'public.review_students'::regclass
      and tgname = 'review_students_prepare_write'
      and not tgisinternal
  ),
  'review_students owns audit timestamps through a trigger'
);
select ok(
  exists (
    select 1
    from pg_trigger
    where tgrelid = 'public.review_inputs'::regclass
      and tgname = 'review_inputs_prepare_write'
      and not tgisinternal
  ),
  'review_inputs owns timestamps and revisions through a trigger'
);
select ok(
  exists (
    select 1
    from pg_trigger
    where tgrelid = 'public.review_sessions'::regclass
      and tgname = 'review_sessions_workspace_immutable'
      and not tgisinternal
  ),
  'review_sessions keeps workspace ownership immutable'
);
select ok(
  exists (
    select 1
    from pg_trigger
    where tgrelid = 'public.review_students'::regclass
      and tgname = 'review_students_workspace_immutable'
      and not tgisinternal
  ),
  'review_students keeps workspace ownership immutable'
);
select ok(
  exists (
    select 1
    from pg_trigger
    where tgrelid = 'public.review_inputs'::regclass
      and tgname = 'review_inputs_workspace_immutable'
      and not tgisinternal
  ),
  'review_inputs keeps workspace ownership immutable'
);

select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.review_inputs'::regclass
      and contype = 'f'
      and pg_get_constraintdef(oid) like '%(workspace_id, session_id)%'
      and pg_get_constraintdef(oid) like '%review_sessions%'
  ),
  'review_inputs session link includes workspace_id'
);
select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.review_inputs'::regclass
      and contype = 'f'
      and pg_get_constraintdef(oid) like '%(workspace_id, student_id)%'
      and pg_get_constraintdef(oid) like '%review_students%'
  ),
  'review_inputs student link includes workspace_id'
);

-- pgTAP 3.36 (the version used by Supabase CI) does not provide has_check.
-- Inspect the catalog directly so the assertion works across local/CI images.
select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.review_inputs'::regclass
      and conname = 'review_inputs_revision_check'
      and contype = 'c'
      and position('revision > 0' in pg_get_constraintdef(oid)) > 0
  ),
  'revision remains positive'
);

select ok(
  exists (
    select 1
    from pg_proc as procedure
    join pg_namespace as namespace on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname = 'update_review_input_if_revision_matches'
       and procedure.proargnames[1:7] = array[
        'target_workspace_id',
        'target_session_id',
        'target_student_id',
        'target_attendance',
        'target_learning_level',
        'target_note_draft',
        'target_expected_revision'
      ]::text[]
  ),
  'revision-checked review input RPC has the expected arguments'
);
select is(
  (select count(*)
   from information_schema.routine_privileges
   where specific_schema = 'public'
     and routine_name = 'update_review_input_if_revision_matches'
     and grantee = 'service_role'
     and privilege_type = 'EXECUTE'),
  1::bigint,
  'revision-checked review input RPC is service-role only'
);
select is(
  (select count(*)
   from information_schema.table_privileges
   where table_schema = 'public'
     and table_name = 'review_inputs'
     and grantee = 'authenticated'
     and privilege_type = 'UPDATE'),
  0::bigint,
  'authenticated clients cannot bypass the revision-checked RPC'
);

select lives_ok($$
  insert into public.workspaces (id, name)
  values
    ('00000000-0000-4000-8000-000000000061', 'Review Inputs Workspace A'),
    ('00000000-0000-4000-8000-000000000062', 'Review Inputs Workspace B');

  insert into public.review_sessions (id, workspace_id, external_session_key, context_hash)
  values ('00000000-0000-4000-8000-000000000063', '00000000-0000-4000-8000-000000000061', 'session-a', 'hash-a');

  insert into public.review_students (id, workspace_id, stable_key, display_label)
  values ('00000000-0000-4000-8000-000000000064', '00000000-0000-4000-8000-000000000062', 'student-b', 'Student B');
$$, 'synthetic review fixtures can be created');

select throws_ok($$
  insert into public.review_inputs (workspace_id, session_id, student_id)
  values (
    '00000000-0000-4000-8000-000000000061',
    '00000000-0000-4000-8000-000000000063',
    '00000000-0000-4000-8000-000000000064'
  )
$$, '23503', null, 'cross-workspace review input is rejected');

select lives_ok($$
  insert into public.review_students (id, workspace_id, stable_key, display_label)
  values ('00000000-0000-4000-8000-000000000065', '00000000-0000-4000-8000-000000000061', 'student-a', 'Student A');

  insert into public.review_inputs (workspace_id, session_id, student_id, revision)
  values (
    '00000000-0000-4000-8000-000000000061',
    '00000000-0000-4000-8000-000000000063',
    '00000000-0000-4000-8000-000000000065',
    900
  );
$$, 'same-workspace review input can be created');

select is(
  (select revision from public.review_inputs where session_id = '00000000-0000-4000-8000-000000000063' and student_id = '00000000-0000-4000-8000-000000000065'),
  1::bigint,
  'insert revision is normalized to one'
);

update public.review_inputs
set revision = 1, updated_at = '1970-01-01T00:00:00Z'::timestamptz
where session_id = '00000000-0000-4000-8000-000000000063'
  and student_id = '00000000-0000-4000-8000-000000000065';

select is(
  (select revision from public.review_inputs where session_id = '00000000-0000-4000-8000-000000000063' and student_id = '00000000-0000-4000-8000-000000000065'),
  2::bigint,
  'update revision advances exactly once'
);
select throws_ok($$
  update public.review_inputs
  set workspace_id = '00000000-0000-4000-8000-000000000062'
  where session_id = '00000000-0000-4000-8000-000000000063'
    and student_id = '00000000-0000-4000-8000-000000000065'
$$, '42501', 'REVIEW_WORKSPACE_IMMUTABLE', 'review input cannot move between workspaces');
select ok(
  (select updated_at > '1970-01-01T00:00:00Z'::timestamptz from public.review_inputs where session_id = '00000000-0000-4000-8000-000000000063' and student_id = '00000000-0000-4000-8000-000000000065'),
  'update timestamp is server managed'
);

select is(
  (select status
   from public.update_review_input_if_revision_matches(
     '00000000-0000-4000-8000-000000000061'::uuid,
     '00000000-0000-4000-8000-000000000063'::uuid,
     '00000000-0000-4000-8000-000000000065'::uuid,
     'present', 'developing', 'RPC update', 2)),
  'updated',
  'matching revision updates the review input'
);
select is(
  (select revision
   from public.review_inputs
   where session_id = '00000000-0000-4000-8000-000000000063'
     and student_id = '00000000-0000-4000-8000-000000000065'),
  3::bigint,
  'matching revision advances exactly once through the RPC'
);
select is(
  (select workspace_id
   from public.review_inputs
   where session_id = '00000000-0000-4000-8000-000000000063'
     and student_id = '00000000-0000-4000-8000-000000000065'),
  '00000000-0000-4000-8000-000000000061'::uuid,
  'RPC update preserves workspace ownership'
);
select is(
  (select status
   from public.update_review_input_if_revision_matches(
     '00000000-0000-4000-8000-000000000061'::uuid,
     '00000000-0000-4000-8000-000000000063'::uuid,
     '00000000-0000-4000-8000-000000000065'::uuid,
     'absent', 'strong', 'stale RPC update', 2)),
  'conflict',
  'stale revision returns a conflict'
);
select is(
  (select revision
   from public.review_inputs
   where session_id = '00000000-0000-4000-8000-000000000063'
     and student_id = '00000000-0000-4000-8000-000000000065'),
  3::bigint,
  'stale revision leaves the newer row unchanged'
);
select is(
  (select note_draft
   from public.review_inputs
   where session_id = '00000000-0000-4000-8000-000000000063'
     and student_id = '00000000-0000-4000-8000-000000000065'),
  'RPC update',
  'stale revision does not overwrite newer content'
);

select * from finish();
rollback;
