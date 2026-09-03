---
name: mindx-verify
description: Verifies MindX Review Bot changes using current-diff deterministic gates, evidence, scope checks, and runtime/browser proof when required. Use before declaring a task done or merge-ready.
---

# MindX Verify

## Principle

Evidence over claims.

No model opinion, self-review, or old test result can create final `VERIFIED` status.

## Read first

1. `AGENTS.md`
2. task acceptance criteria
3. PR diff
4. current verification evidence

## Required checks

Select every gate relevant to the changed scope.

### Web baseline

- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `npm run verify:no-secrets`
- `npm run verify:no-live-write`

### Supabase-related changes

- start local Supabase when required
- `npx supabase db reset`
- `npm run test:rls`

### Browser-runner changes

From `apps/browser-runner`:

- `uv run ruff check .`
- `uv run mypy src`
- `uv run pytest`

### Authenticated live-web changes

Require appropriate browser/E2E/runtime evidence for the changed behavior when the environment is available. Static review or unit tests alone cannot prove session redirects, DOM changes, browser-state reuse, live selectors, or no-mutation behavior.

If a required live prerequisite is unavailable, use `blocked-owner` or `blocked-external`; do not infer PASS.

## Current-diff rule

Verification evidence must correspond to the current PR head/diff. If code changes after a gate ran, rerun every gate whose result could be invalidated by that change.

## Completion checklist

Before moving to `done`, confirm:

- acceptance criteria satisfied;
- required review completed according to risk routing;
- no unresolved material finding;
- no out-of-scope diff;
- required deterministic gates PASS;
- safety/privacy guards PASS;
- known limitations accurately documented;
- no synthetic/local evidence is mislabeled live.

## Output

Report gate-by-gate PASS/FAIL/BLOCKED evidence.

Only when all required deterministic gates for the task are PASS may the workflow set `VERIFIED` / `done`.

Do not manufacture or infer missing command results.