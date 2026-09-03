## Requirement

Link issue/task/spec:

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

## Review Package

- [ ] Requirement and acceptance criteria are available
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

Fix loop: `0 / 2`

## Known Limitations / Blockers

Use `blocked-owner` for missing business/scope/live-credential decisions and `blocked-external` for unavailable external prerequisites.

## Final Verification

- [ ] Required reviews resolved
- [ ] Required deterministic gates green on current diff
- [ ] No unresolved material findings
- [ ] No out-of-scope change
- [ ] Synthetic/local evidence is not mislabeled as live

> AI reviewer recommendations are not final verification. Only required deterministic evidence may produce `VERIFIED` / `done`.