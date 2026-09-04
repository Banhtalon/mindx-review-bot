---
name: mindx-verify
description: Verifies MindX Review Bot changes using current-head deterministic gates, current project state, authoritative task control, independent review controls, and runtime/browser proof when required.
---

# MindX Verify

## Principle

Evidence over claims.

No model opinion, self-review, or old test result can create final `VERIFIED` status.

## Read first

1. `AGENTS.md`
2. `docs/CURRENT_STATE.md`
3. linked GitHub issue Agent Control Block and current workflow-state label
4. task acceptance criteria
5. PR diff
6. current verification evidence
7. current PR review-gate/attestation state and unresolved review threads
8. relevant `docs/evidence/index.json` entries when a live/hosted readiness claim is made

If control state is missing, malformed, conflicting, or ambiguous, verification is `BLOCKED`.

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

## Current-head rule

Verification evidence must correspond to the current PR head/diff. If code changes after a gate ran, rerun every gate whose result could be invalidated by that change.

A prior Terra attestation that is invalidated by a new commit (head SHA mismatch) is not current review evidence.

## Task-control checks

Before moving to `done`, verify:

- exactly one linked task issue owns the Agent Control Block;
- exactly one primary workflow-state label exists and matches issue `state`;
- `scope_revision` is valid;
- `fix_reentries` is valid and has not been self-reset by a worker;
- any scope-reset counter reset has an Owner-linked approval record;
- no blocked state is being bypassed.

`MAX_FIX_LOOPS = 2` means `fix_reentries=1` and `fix_reentries=2` are both valid consumed/permitted fix re-entry counts. A third fix implementation attempt is blocked only when a new `needs-fix -> implementing` transition is requested while the current count is already `2`.

A failed deterministic gate that requires implementation changes must route to `needs-fix`; the next implementation re-entry follows that atomic controller rule.

## Independent review checks (solo-owner review gate)

Before merge/`done`, verify:

- `protect-main` ruleset requires `verify` and `review-gate` with `Required approvals = 0`;
- `review-gate` check is PASS for the exact current PR head SHA;
- valid Terra xHigh attestation exists matching PR number, control issue, scope revision, with `RECOMMEND_PASS`, P0=0, P1=0, and material findings resolved;
- any new push invalidates earlier attestations via head-SHA mismatch;
- all material review conversations/threads are resolved;
- no unresolved P0/P1 finding remains.

A green `verify` check alone is not sufficient if `review-gate` fails or review conversations remain open.

## Completion checklist

Before moving to `done`, confirm:

- acceptance criteria satisfied;
- required review completed according to risk routing;
- required independent review-gate check is current and passing;
- material review threads are resolved;
- no unresolved material finding;
- no out-of-scope diff;
- required deterministic gates PASS on current PR head;
- safety/privacy guards PASS;
- known limitations accurately documented;
- `docs/CURRENT_STATE.md` does not contradict the claimed result;
- no synthetic/local evidence is mislabeled live;
- any live/hosted claim is supported by the relevant evidence index;
- repository branch protection/required CI/review prerequisites are active when this workflow is being treated as controlled.

## Output

Report gate-by-gate PASS/FAIL/BLOCKED evidence.

Only when all required deterministic gates, control-state checks, and enforced independent-review checks are PASS may the workflow set `VERIFIED` / `done`.

Do not manufacture or infer missing command or review results.
