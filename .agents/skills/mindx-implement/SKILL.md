---
name: mindx-implement
description: Implements approved MindX Review Bot tasks with TDD, scoped changes, deterministic verification, and safety guards. Use when coding, debugging, fixing CI, or addressing accepted review findings.
---

# MindX Implement

## Read first

1. `AGENTS.md`
2. `docs/CURRENT_STATE.md`
3. linked specification/acceptance criteria
4. linked implementation plan
5. current task/PR state

## Entry condition

Start implementation only when the task is explicitly approved or marked `ready-for-implementation` / `needs-fix`.

If the specification is ambiguous, conflicts with an ADR, or requires a new business rule, stop with `BLOCKED` rather than inventing behavior.

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

- requirement/spec link;
- acceptance criteria status;
- changed files/behavior;
- explicitly not changed scope;
- tests added/updated;
- verification results from current diff;
- known limitations/blockers.

Do not provide chain-of-thought as review evidence.

## Review fixes

For each accepted Terra finding:

1. reproduce/prove where practical;
2. add regression coverage;
3. apply smallest fix;
4. rerun focused gates;
5. rerun required final gates;
6. update PR evidence.

The same scope may complete at most `MAX_FIX_LOOPS = 2` before owner escalation.

Never output final `VERIFIED`; deterministic gates own that state.