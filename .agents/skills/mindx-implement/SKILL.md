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

Implementation code may start only when the linked issue is already in valid `implementing` state and exactly one `implementing` workflow label matches it.

The controller transition is separate from the implementation worker:

- initial implementation: `ready-for-implementation / fix_reentries=0 -> implementing / fix_reentries=0`;
- fix re-entry: if current state is `needs-fix` and current `fix_reentries < MAX_FIX_LOOPS`, the controller atomically sets `state=implementing`, increments `fix_reentries` by exactly 1, and replaces the primary label with `implementing`;
- `fix_reentries=1` authorizes the first fix re-entry;
- `fix_reentries=2` authorizes the second fix re-entry;
- if a new fix re-entry is requested while current `fix_reentries >= MAX_FIX_LOOPS` (2), the controller must not increment or invoke implementation; it routes to `blocked-owner` instead.

Therefore exactly two `needs-fix -> implementing` re-entries are permitted for one unchanged scope revision; the third attempt is blocked.

Fail closed and make no code change if:

- linked issue is missing;
- Agent Control Block is missing/malformed;
- state is not `implementing` when the worker is invoked;
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
2. confirm the controller performed the atomic transition to `implementing` and incremented the counter exactly once;
3. confirm the resulting `fix_reentries` is `1` or `2` and the issue/label both say `implementing`;
4. reproduce/prove where practical;
5. add regression coverage;
6. apply smallest fix;
7. rerun focused gates;
8. rerun required final gates;
9. update PR evidence.

If the issue is still `needs-fix` with `fix_reentries >= 2`, no third autonomous fix is allowed; return `BLOCKED` / `blocked-owner` without changing code.

`MAX_FIX_LOOPS = 2` is controlled by the linked issue `fix_reentries` value, not a PR self-report field.

Never output final `VERIFIED`; deterministic gates own that state.
