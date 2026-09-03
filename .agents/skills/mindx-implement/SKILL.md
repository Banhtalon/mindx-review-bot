---
name: mindx-implement
description: Implements approved MindX Review Bot tasks with TDD, scoped changes, deterministic verification, authoritative task-state checks, and safety guards.
---

# MindX Implement

## Read first

1. `AGENTS.md`
2. `docs/CURRENT_STATE.md`
3. linked GitHub issue Agent Control Block and current workflow-state label
4. linked specification/acceptance criteria
5. linked implementation plan
6. current PR state

## Entry condition

Start implementation only when the linked issue control state is valid and is explicitly `ready-for-implementation` or `needs-fix`.

Before any `needs-fix` re-entry, a controller must already have incremented authoritative `fix_reentries` by exactly 1. If `fix_reentries >= 2`, do not start another autonomous fix; return `BLOCKED` / `blocked-owner`.

Fail closed and make no code change if:

- linked issue is missing;
- Agent Control Block is missing/malformed;
- multiple primary workflow-state labels exist;
- issue `state` and label disagree;
- `scope_revision` is invalid;
- `fix_reentries` is invalid/out of range;
- a counter reset lacks an Owner-linked scope-reset record;
- specification/plan is ambiguous or conflicts with an ADR.

Workers must not edit/reset the authoritative issue counter or workflow labels unattended.

## Method

Use Superpowers:

- `test-driven-development`;
- `systematic-debugging`;
- `using-git-worktrees` where appropriate;
- `verification-before-completion`.

Work cycle:

`RED -> GREEN -> REFACTOR -> VERIFY`.

For a bug fix, create or strengthen a regression test before the final fix when deterministic reproduction is practical.

## Scope discipline

- Change the smallest set of files needed.
- Do not perform unrelated cleanup/refactoring.
- Do not change business rules or architecture silently.
- Do not weaken tests, guards, typing, RLS, or validation to make CI green.
- Preserve read-only LMS/Teaching boundaries.
- Preserve deterministic identity/mapping rules.

## Verification

Run focused tests during development, then all required gates for the changed scope.

Typical web gates:

- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `npm run verify:no-secrets`
- `npm run verify:no-live-write`

For Supabase changes:

- `npx supabase db reset`
- `npm run test:rls`

For browser-runner changes from `apps/browser-runner`:

- `uv run ruff check .`
- `uv run mypy src`
- `uv run pytest`

Authenticated live-web behavior needs appropriate runtime/browser evidence when available; unit tests alone are not sufficient proof.

## PR handoff

Before `ready-for-review`, provide:

- linked issue and Agent Control Block state;
- requirement/spec link;
- acceptance criteria status;
- changed files/behavior;
- explicitly not changed scope;
- tests added/updated;
- verification results from current PR head;
- known limitations/blockers.

Do not provide chain-of-thought as review evidence.

## Review fixes

For each accepted Terra finding:

1. confirm the controller has routed the issue to `needs-fix`;
2. confirm authoritative `fix_reentries` was incremented before re-entry;
3. fail closed if the counter/state is invalid or at the limit;
4. reproduce/prove where practical;
5. add regression coverage;
6. apply smallest fix;
7. rerun focused gates;
8. rerun required final gates;
9. update PR evidence.

`MAX_FIX_LOOPS = 2` is controlled by the linked issue `fix_reentries` value, not a PR self-report field.

Never output final `VERIFIED`; deterministic gates own that state.
