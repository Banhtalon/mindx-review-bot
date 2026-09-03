# Agent Workflow

## Purpose

Define the repository handoff protocol between Owner, Sol High, Gemini 3.8 Flash, Terra xHigh, GitHub, and deterministic verification.

This is a development workflow document. It does not change product behavior.

## Control plane

GitHub is the shared control plane:

- issues/tasks hold scope and authoritative workflow state;
- specs/plans are committed artifacts;
- branches/worktrees isolate implementation;
- PRs carry diff and verification evidence;
- CI provides deterministic gates;
- labels/state communicate handoff without copying chat transcripts between models.

A workflow is not considered controlled until `main` is protected, the required CI check is enforced on the current PR head, and the workflow labels exist.

## Roles

### Owner

Owns:

- product intent;
- business-rule decisions;
- scope/waiver decisions;
- live credential/re-authentication steps;
- approval of scope-revision resets;
- approval of high-risk merges or blocked escalations.

Owner should not need to relay routine implementation/review messages manually once the GitHub handoff is established.

### Sol High

Primary use:

- clarify scope;
- write or refine specification;
- define acceptance criteria;
- make architecture decisions;
- write implementation plans for medium/high-risk work.

Exit condition:

- task is sufficiently specified and marked `ready-for-implementation`.

Sol does not remain in the coding/review loop unless escalation is needed.

### Gemini 3.8 Flash

Primary use:

- execute approved plan;
- TDD implementation;
- tests/debugging;
- scoped refactoring;
- CI fixes;
- review-finding fixes;
- PR/evidence preparation.

Gemini must stop instead of guessing when spec/business rules are ambiguous.

### Terra xHigh

Primary use:

- fresh-context spec-compliance review;
- adversarial/code-quality review;
- security/privacy/data-integrity/regression attack for risk-relevant changes.

Terra should receive the independent review package defined below, including `docs/CURRENT_STATE.md`.

Do not provide implementer chain-of-thought/reasoning transcript as review evidence.

### Machine verification

Final authority is deterministic evidence, not model opinion.

Required gates are task-scope dependent, but the repository baseline includes:

- lint;
- typecheck;
- web tests;
- build;
- no-secrets guard;
- no-live-write guard;
- Supabase reset/RLS tests where relevant;
- Python Ruff/Mypy/Pytest where relevant;
- browser/E2E/runtime evidence for authenticated live-web behavior when relevant.

## Authoritative task control state

Every agent-driven task must have exactly one linked GitHub issue that owns the control state.

The issue must contain an **Agent Control Block** with:

```text
state: <canonical workflow state>
scope_revision: <positive integer>
fix_reentries: <0..2>
owner_scope_reset: <none | link to explicit Owner approval record>
```

Rules:

- the GitHub issue is authoritative; the PR template is only a display/reference surface;
- exactly one primary workflow-state label must match `state`;
- implementation workers must have read access to issue state but must not be granted unattended issue/label administration permission;
- a controller/Owner updates the state and counter;
- every transition from `needs-fix` back into `implementing` increments `fix_reentries` by exactly 1 before implementation starts;
- every deterministic verification failure that requires code changes routes through `needs-fix`, so the next implementation re-entry also consumes one count;
- `fix_reentries >= 2` blocks another autonomous implementation re-entry and routes to `blocked-owner`;
- missing, malformed, conflicting, or ambiguous control state is fail-closed: scheduled/background workers must make no code change and return `BLOCKED`;
- a worker may not reset `fix_reentries` itself.

### Scope reset

A counter reset is allowed only when scope materially changes and Owner explicitly approves it.

Required sequence:

1. Owner creates an approval record/comment that states old scope revision, new scope revision, reason, and material scope change.
2. Controller increments `scope_revision`.
3. Controller records the approval link in `owner_scope_reset`.
4. Controller resets `fix_reentries` to `0`.
5. The updated specification/plan is linked before work resumes.

Without that Owner-linked record, changing scope does not reset the loop counter.

## State machine

```text
needs-plan
   |
   v
Sol High
   |
   v
ready-for-implementation
   |
   v
implementing
   |
   v
ready-for-review
   |
   +--> NEEDS_FIX --> needs-fix --(controller increments fix_reentries)--> implementing
   |
   +--> BLOCKED --> blocked-owner / blocked-external
   |
   +--> RECOMMEND_PASS
              |
              v
        ready-for-verify
              |
              v
       deterministic gates
          |          |
        FAIL        PASS
          |          |
          v          v
      needs-fix     done
```

## Bounded loop

For an unchanged task scope:

`MAX_FIX_LOOPS = 2`.

The authoritative count is `fix_reentries` in the linked GitHub issue control block, not a self-reported PR field.

After two implementation re-entries:

- stop autonomous iteration;
- move to `blocked-owner`;
- summarize unresolved findings and decision needed.

## Task sizing and routing

### Small / low risk

Examples: copy change, isolated CSS, trivial validation, mechanical test update.

Flow:

Gemini -> scoped tests -> deterministic verification -> merge.

Terra optional unless a safety boundary is touched.

### Medium

Examples: CRUD slice, import behavior, new page/API behavior, non-trivial auth-adjacent change.

Flow:

Sol plan -> Gemini -> tests/CI -> fresh spec review -> Terra if risk warrants -> final verification.

### High risk

Examples: migrations, student matching/identity, authentication/session, browser state, RLS, privacy boundary, live Teaching/LMS behavior, architecture change.

Flow:

Sol spec/architecture -> fresh plan critique -> Sol final plan -> Gemini implementation -> deterministic tests -> fresh spec review -> Terra adversarial review -> Gemini fix -> full verification.

## Review package

Every non-trivial fresh review must include:

1. `AGENTS.md`.
2. `docs/CURRENT_STATE.md`.
3. Linked GitHub issue Agent Control Block and current workflow-state label.
4. Requirement / issue link.
5. Specification / plan link.
6. Acceptance criteria.
7. PR diff.
8. Changed scope.
9. Explicitly not changed scope.
10. Tests added/updated.
11. Deterministic verification results from the current PR head.
12. Known limitations/blockers.
13. Relevant `docs/evidence/index.json` entries when a live/hosted readiness claim is made.

## Terra review protocol

### Pass 1 — spec compliance

Ask:

- Is every acceptance criterion implemented?
- Is any requirement silently omitted?
- Did implementation add behavior not requested?
- Did code change unrelated scope?
- Were tests weakened or rewritten to hide a regression?
- Does `CURRENT_STATE.md` contradict any claimed readiness or scope?
- If live/hosted readiness is claimed, does the evidence index actually support it?

### Pass 2 — adversarial attack

When relevant, attack:

- retries/idempotency;
- timeout/cancellation/cleanup;
- partial failure;
- race/concurrency;
- auth/session expiry;
- stale browser state;
- wrong student/class/session identity;
- mapping ambiguity;
- DB/RLS/data integrity;
- privacy/PII/model payloads;
- accidental LMS mutation/live-write path;
- rollback/recovery.

Reviewer output is one of:

- `RECOMMEND_PASS`;
- `NEEDS_FIX` with findings ordered by severity;
- `BLOCKED` with missing evidence/decision.

## Gemini fix protocol

For each accepted finding:

1. read the linked issue Agent Control Block;
2. fail closed if the issue state/counter/label is invalid or `fix_reentries >= 2`;
3. reproduce or prove the issue where practical;
4. add regression test first when behavior can be tested deterministically;
5. make smallest scoped fix;
6. run focused gates;
7. run required final gates before returning to review;
8. update PR evidence.

Do not perform unrelated cleanup while fixing a finding.

## Verification protocol

A model may say `RECOMMEND_PASS`, but a task reaches `done` only when required gates pass on the current PR head.

If review and CI disagree, CI/runtime evidence wins for final verification, while reviewer findings remain unresolved until explicitly fixed/waived.

No test result from an earlier commit may be reused as proof for a later changed diff unless the relevant gate reruns.

## Existing product scheduler versus development-agent automation

The repository already contains `.github/workflows/cron-dispatch.yml`. It is a pre-existing **read-only product-job scheduler** for Teaching/LMS dispatch and is not the new Sol/Gemini/Terra development-worker automation defined by this migration.

Important current state:

- the cron workflow predates this migration;
- recent scheduled execution has failed;
- hosted/off-PC Phase 2 closure is still BLOCKED;
- this migration neither treats that scheduler as pilot-approved nor uses its existence as evidence that unattended development workers are safe.

Owner must separately decide whether to keep, disable, or repair that pre-existing product schedule. That decision does not waive the manual pilot requirement for new development-agent automation.

## Background/scheduled development execution

**New unattended development-agent automation** is gated behind a successful manual pilot.

Before enabling Antigravity Scheduled Tasks or equivalent development workers, verify that:

- `main` is protected and direct worker pushes are blocked;
- required current-head CI is enforced before merge;
- workflow-state labels exist;
- the linked issue Agent Control Block is present and valid;
- agents cannot edit/reset the authoritative control counter unattended;
- blocked states stop execution;
- retry/review loops are bounded by the authoritative counter;
- secrets/permissions are scoped;
- one manual Sol -> Gemini -> Terra pipeline completed successfully.

After that, Antigravity Scheduled Tasks may be used as a Gemini worker trigger for unambiguous `ready-for-implementation` / `needs-fix` work, while review remains independently triggered for `ready-for-review`.

Scheduled workers must fail closed when:

- task issue is missing;
- Agent Control Block is missing/malformed;
- workflow label and `state` disagree;
- multiple primary state labels exist;
- `fix_reentries >= 2` for a `needs-fix` re-entry;
- a scope reset lacks Owner-linked approval;
- linked spec/plan is missing;
- task is `blocked-owner` or `blocked-external`.

## Owner escalation conditions

Move to `blocked-owner` when:

- business rule is missing/ambiguous;
- acceptance criteria conflict;
- material architecture change is required;
- authoritative fix re-entry counter reaches the limit;
- live credential/re-authentication is required;
- a safety rule would need an exception;
- a live write path would need enabling;
- merge risk is high and deterministic evidence is insufficient.

Move to `blocked-external` when a required external service/site/environment is unavailable or cannot be verified safely.
