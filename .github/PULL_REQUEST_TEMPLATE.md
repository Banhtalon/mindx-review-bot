## Requirement

Link issue/task/spec:

## Authoritative Task Control

Linked standalone GitHub issue:

Current control snapshot (reference only; issue is authoritative):

- state:
- scope_revision:
- fix_reentries:
- owner_scope_reset:

> Do not edit/reset authoritative task state through this PR body. Workflow state/counter live in the linked GitHub issue and must match exactly one primary workflow-state label.

## Specification / Plan

- Spec:
- Plan:

## Acceptance Criteria

- [ ] AC1:
- [ ] AC2:

## Changed

Describe only behavior/files intentionally changed.

## Explicitly Not Changed

List adjacent behavior/scope that this PR deliberately leaves unchanged.

## Tests Added / Updated

- [ ] Regression/acceptance coverage added where applicable
- [ ] Existing relevant tests preserved

## Deterministic Verification

Record results from the **current PR head** only.

### Web

- [ ] `npm run lint`
- [ ] `npm run typecheck`
- [ ] `npm run test`
- [ ] `npm run build`
- [ ] `npm run verify:no-secrets`
- [ ] `npm run verify:no-live-write`

### Supabase — when relevant

- [ ] `npx supabase db reset`
- [ ] `npm run test:rls`

### Browser runner — when relevant

- [ ] `uv run ruff check .`
- [ ] `uv run mypy src`
- [ ] `uv run pytest`

### Live browser/E2E — when relevant

- [ ] Runtime/browser evidence recorded without secrets/PII
- [ ] Read-only/no-mutation boundary verified
- [ ] Relevant `docs/evidence/index.json` entries support any live/hosted readiness claim

## Review Package

- [ ] `AGENTS.md` available
- [ ] `docs/CURRENT_STATE.md` reviewed
- [ ] Linked standalone issue Agent Control Block + workflow label checked
- [ ] Requirement and acceptance criteria available
- [ ] Diff is scoped
- [ ] Deterministic evidence is attached/current
- [ ] Known limitations/blockers are stated
- [ ] Implementer reasoning transcript is **not** being used as review evidence

## Risk / Reviewer Routing

Risk: `small | medium | high`

Terra fresh adversarial review required? `yes | no`

If yes, reason:

## Review Status

`READY_FOR_REVIEW | NEEDS_FIX | BLOCKED`

Authoritative fix-loop state: see linked issue `fix_reentries`.

`MAX_FIX_LOOPS = 2` means fix re-entry counts `1` and `2` are both permitted; a new third re-entry request from `needs-fix` while the current count is already `2` is blocked.

## Known Limitations / Blockers

Use `blocked-owner` for missing business/scope/live-credential/reviewer decisions and `blocked-external` for unavailable external prerequisites.

## Independent Merge Review

- [ ] At least one current independent GitHub approval exists
- [ ] Approval is not self-approval by the PR author
- [ ] Approval was not invalidated by a later commit
- [ ] All material review conversations are resolved

> The active `main` ruleset is expected to enforce these conditions. A green `verify` check alone is not sufficient to merge.

## Final Verification

- [ ] Required reviews resolved
- [ ] Required deterministic gates green on current PR head
- [ ] Linked issue control state is valid and consistent with its workflow label
- [ ] No unresolved material findings
- [ ] No out-of-scope change
- [ ] `docs/CURRENT_STATE.md` does not contradict the result
- [ ] Synthetic/local evidence is not mislabeled as live

> AI reviewer recommendations are not final verification. Only required deterministic evidence, valid control state, and current enforced independent review may produce `VERIFIED` / `done`.
