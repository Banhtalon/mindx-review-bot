# Agent Workflow

## Purpose

Define the repository handoff protocol between Owner, Sol High, Gemini 3.8 Flash, Terra xHigh, GitHub, and deterministic verification.

This is a development workflow document. It does not change product behavior.

## Control plane

GitHub is the shared control plane:

- issues/tasks hold scope and state;
- specs/plans are committed artifacts;
- branches/worktrees isolate implementation;
- PRs carry diff and verification evidence;
- CI provides deterministic gates;
- labels/state communicate handoff without copying chat transcripts between models.

## Roles

### Owner

Owns:

- product intent;
- business-rule decisions;
- scope/waiver decisions;
- live credential/re-authentication steps;
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

Terra should receive only the minimum review package:

- `AGENTS.md`;
- linked spec/acceptance criteria;
- PR diff;
- deterministic test/CI evidence;
- known limitations.

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
implementing  <-------------------+
   |                               |
   v                               |
ready-for-review                    |
   |                               |
   +--> NEEDS_FIX --> needs-fix ----+
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

After two material review/fix loops:

- stop autonomous iteration;
- move to `blocked-owner`;
- summarize unresolved findings and decision needed.

A material spec/scope update may start a new bounded loop only after the artifact is updated.

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

Every non-trivial review should include:

1. Requirement / issue link.
2. Specification / plan link.
3. Acceptance criteria.
4. PR diff.
5. Changed scope.
6. Explicitly not changed scope.
7. Tests added/updated.
8. Deterministic verification results.
9. Known limitations/blockers.

## Terra review protocol

### Pass 1 — spec compliance

Ask:

- Is every acceptance criterion implemented?
- Is any requirement silently omitted?
- Did implementation add behavior not requested?
- Did code change unrelated scope?
- Were tests weakened or rewritten to hide a regression?

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

1. reproduce or prove the issue where practical;
2. add regression test first when behavior can be tested deterministically;
3. make smallest scoped fix;
4. run focused gates;
5. run required final gates before returning to review;
6. update PR evidence.

Do not perform unrelated cleanup while fixing a finding.

## Verification protocol

A model may say `RECOMMEND_PASS`, but a task reaches `done` only when required gates pass.

If review and CI disagree, CI/runtime evidence wins for final verification, while reviewer findings remain unresolved until explicitly fixed/waived.

No test result from an earlier commit may be reused as proof for a later changed diff unless the relevant gate reruns.

## Background/scheduled execution

Background automation is gated behind a successful manual pilot.

Before enabling scheduled agents, verify that:

- GitHub state labels/tasks are unambiguous;
- agents do not push directly to `main`;
- CI is required before merge;
- blocked states stop execution;
- retry/review loops are bounded;
- secrets/permissions are scoped;
- one manual Sol -> Gemini -> Terra pipeline completed successfully.

After that, Antigravity Scheduled Tasks may be used as a Gemini worker trigger for `ready-for-implementation` / `needs-fix` work, while review remains independently triggered for `ready-for-review`.

## Owner escalation conditions

Move to `blocked-owner` when:

- business rule is missing/ambiguous;
- acceptance criteria conflict;
- material architecture change is required;
- review loop hits the limit;
- live credential/re-authentication is required;
- a safety rule would need an exception;
- a live write path would need enabling;
- merge risk is high and deterministic evidence is insufficient.

Move to `blocked-external` when a required external service/site/environment is unavailable or cannot be verified safely.
