begin;

select plan(16);

insert into auth.users (id, aud, role, email, encrypted_password, email_confirmed_at)
values (
  '33333333-3333-4333-8333-333333333333',
  'authenticated',
  'authenticated',
  'outsider@example.invalid',
  'synthetic',
  now()
)
on conflict (id) do update
set email = excluded.email;

select is(
  (select email from auth.users where id = '11111111-1111-4111-8111-111111111111'),
  'owner@example.invalid',
  'seed owner email is deterministic and synthetic'
);
select ok(
  exists(select 1 from public.workspaces where id = '22222222-2222-4222-8222-222222222222'),
  'seed workspace exists'
);
select ok(
  exists(
    select 1
    from public.workspace_members
    where workspace_id = '22222222-2222-4222-8222-222222222222'
      and user_id = '11111111-1111-4111-8111-111111111111'
      and role = 'owner'
  ),
  'seed owner membership keeps the owner role'
);

set local role anon;
select set_config('request.jwt.claim.role', 'anon', true);
select set_config('request.jwt.claim.sub', '', true);
select is(
  (select count(*) from public.workspaces where id = '22222222-2222-4222-8222-222222222222'),
  0::bigint,
  'anonymous cannot read the seeded workspace'
);
select is(
  (select count(*) from public.workspace_members where workspace_id = '22222222-2222-4222-8222-222222222222'),
  0::bigint,
  'anonymous cannot read seeded workspace members'
);

set local role authenticated;
select set_config('request.jwt.claim.role', 'authenticated', true);
select set_config('request.jwt.claim.sub', '11111111-1111-4111-8111-111111111111', true);
select is(
  (select count(*) from public.workspaces where id = '22222222-2222-4222-8222-222222222222'),
  1::bigint,
  'seed owner can read the seeded workspace'
);
select is(
  (select count(*)
   from public.workspace_members
   where workspace_id = '22222222-2222-4222-8222-222222222222'
     and user_id = '11111111-1111-4111-8111-111111111111'),
  1::bigint,
  'seed owner can read their own membership row'
);
select is(
  (select role
   from public.workspace_members
   where workspace_id = '22222222-2222-4222-8222-222222222222'
     and user_id = '11111111-1111-4111-8111-111111111111'),
  'owner',
  'seed owner reads the owner role through RLS'
);
select ok(
  public.is_workspace_member('22222222-2222-4222-8222-222222222222'),
  'seed owner is recognized as a workspace member'
);
select ok(
  public.has_workspace_role('22222222-2222-4222-8222-222222222222', array['owner']),
  'seed owner is recognized as an owner'
);
select ok(
  not public.has_workspace_role('22222222-2222-4222-8222-222222222222', array['reviewer']),
  'seed owner is not misclassified as a reviewer'
);

select set_config('request.jwt.claim.sub', '33333333-3333-4333-8333-333333333333', true);
select is(
  (select count(*) from public.workspaces where id = '22222222-2222-4222-8222-222222222222'),
  0::bigint,
  'non-member cannot read the seeded workspace'
);
select is(
  (select count(*) from public.workspace_members where workspace_id = '22222222-2222-4222-8222-222222222222'),
  0::bigint,
  'non-member cannot read the seeded membership rows'
);

reset role;
select throws_ok(
  $$insert into public.workspace_members (workspace_id, user_id, role)
    values (
      '22222222-2222-4222-8222-222222222222',
      '33333333-3333-4333-8333-333333333333',
      'student'
    )$$,
  '23514',
  null,
  'workspace member role constraint rejects unsupported roles'
);
select is(
  (select array_to_string(coalesce(proconfig, array[]::text[]), ',')
   from pg_proc
   where oid = 'public.is_workspace_member(uuid)'::regprocedure),
  'search_path=',
  'is_workspace_member keeps a fixed empty search_path'
);
select is(
  (select array_to_string(coalesce(proconfig, array[]::text[]), ',')
   from pg_proc
   where oid = 'public.has_workspace_role(uuid,text[])'::regprocedure),
  'search_path=',
  'has_workspace_role keeps a fixed empty search_path'
);

select * from finish();
rollback;
