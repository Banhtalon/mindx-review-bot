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

A workflow is not considered controlled until `main` is protected, the required current-head CI check is enforced, current independent review cannot be bypassed, unresolved review threads block merge, and the workflow labels exist.

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

Gemini must stop instead of guessing when spec/business rules are ambiguous. Gemini implementation starts only after a controller has moved the authoritative task state to valid `implementing`.

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
- a controller/Owner updates state/counter before invoking implementation;
- initial implementation transition is `ready-for-implementation / fix_reentries=0 -> implementing / fix_reentries=0`;
- a fix re-entry is allowed only when current state is `needs-fix` and current `fix_reentries < MAX_FIX_LOOPS`;
- the fix transition is atomic: controller changes `state` and primary label to `implementing` and increments `fix_reentries` exactly once in the same control update;
- `needs-fix / 0 -> implementing / 1` authorizes fix re-entry #1;
- `needs-fix / 1 -> implementing / 2` authorizes fix re-entry #2;
- when a later fix re-entry is requested from `needs-fix` with current `fix_reentries >= 2`, that is the third attempt: do not increment, route to `blocked-owner`, and invoke no implementation;
- every deterministic verification failure that requires code changes routes through `needs-fix`, so the next implementation re-entry consumes one count under the same rule;
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
ready-for-implementation --(controller, counter stays 0)--> implementing
                                                        |
                                                        v
                                                ready-for-review
                                                        |
                         +------------------------------+------------------+
                         |                              |                  |
                         v                              v                  v
                    NEEDS_FIX                       BLOCKED         RECOMMEND_PASS
                         |                              |                  |
                         v                              v                  v
                     needs-fix               blocked-owner /       ready-for-verify
                         |                    blocked-external             |
                         |                                               v
                         |                                      deterministic gates
                         |                                         |            |
                         |                                       FAIL          PASS
                         |                                         |            |
                         +<------------------------------------ needs-fix        done
                         |
                         +-- if counter 0: atomic -> implementing / 1
                         +-- if counter 1: atomic -> implementing / 2
                         +-- if counter 2: blocked-owner; no third re-entry
```

## Bounded loop

For an unchanged task scope:

`MAX_FIX_LOOPS = 2`.

The authoritative count is `fix_reentries` in the linked GitHub issue control block, not a self-reported PR field.

Meaning:

- count `0`: zero fix re-entries consumed;
- count `1`: first fix re-entry is/was permitted;
- count `2`: second fix re-entry is/was permitted;
- a new third re-entry request while current count is `2` is blocked.

So **exactly two fix implementation re-entries are allowed; the third is blocked**.

## Task sizing and routing

### Small / low risk

Examples: copy change, isolated CSS, trivial validation, mechanical test update.

Flow:

controller -> Gemini -> scoped tests -> deterministic verification -> merge.

Terra optional unless a safety boundary is touched.

### Medium

Examples: CRUD slice, import behavior, new page/API behavior, non-trivial auth-adjacent change.

Flow:

Sol plan -> controller -> Gemini -> tests/CI -> fresh spec review -> Terra if risk warrants -> final verification.

### High risk

Examples: migrations, student matching/identity, authentication/session, browser state, RLS, privacy boundary, live Teaching/LMS behavior, architecture change.

Flow:

Sol spec/architecture -> fresh plan critique -> Sol final plan -> controller -> Gemini implementation -> deterministic tests -> fresh spec review -> Terra adversarial review -> controller -> Gemini fix -> full verification.

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
- Does the linked issue control block match exactly one primary workflow-state label?

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

## Independent review enforcement

A green `verify` check is necessary but not sufficient for merge.

The active `main` ruleset must also enforce:

- at least one current independent PR approval;
- stale approvals are dismissed when new commits are pushed;
- unresolved review conversations block merge;
- the PR author cannot use self-approval as independent review evidence.

For a personal repository, this means a second GitHub identity/app capable of valid independent approval is required if the PR is authored by the Owner account. If no such reviewer identity exists, merge remains blocked rather than weakening the review requirement.

## Gemini fix protocol

For each accepted finding:

1. read the linked issue Agent Control Block;
2. require the issue to be in valid `implementing` state before code changes;
3. for a fix re-entry, confirm the controller atomically transitioned from `needs-fix` and incremented the count exactly once;
4. accept resulting `fix_reentries=1` or `2` as valid permitted fix re-entry counts;
5. reproduce or prove the issue where practical;
6. add regression test first when behavior can be tested deterministically;
7. make smallest scoped fix;
8. run focused gates;
9. run required final gates before returning to review;
10. update PR evidence.

If the task is still `needs-fix` with current `fix_reentries >= 2`, do not perform a third autonomous fix; route `blocked-owner`.

Do not perform unrelated cleanup while fixing a finding.

## Solo-owner Terra review gate protocol

Because this is a solo-developer repository with a single human account, requiring a second GitHub human approval (`Required approvals >= 1`) blocks the repo owner from merging pull requests.

Under Scope Revision 2, the repository uses a deterministic machine-enforced gate:

1. **GitHub branch setting**: `Required approvals = 0`.
2. **Review gate workflow**: `.github/workflows/review-gate.yml` executes on every pull request event and comment.
3. **Head-SHA binding**: The gate validates a structured Terra attestation bound to the exact current PR head SHA:
   ```text
   <!-- TERRA_REVIEW_ATTESTATION_V1 -->
   reviewer_model: terra-xhigh
   control_issue: <linked control issue number>
   scope_revision: <matching scope revision>
   pr_number: <PR number>
   head_sha: <40-char current PR head SHA>
   verdict: RECOMMEND_PASS
   p0: 0
   p1: 0
   material_findings_resolved: true
   reviewed_at_utc: <ISO-8601 UTC timestamp>
   <!-- /TERRA_REVIEW_ATTESTATION_V1 -->
   ```
   Alternatively, ```terra-attestation or ```json:terra-attestation code blocks are accepted.
4. **Invalidation on push**: Any new commit pushed to the PR automatically changes `head_sha`, immediately invalidating any prior attestation and causing `review-gate` to fail closed until Terra reviews the new head.
5. **Later-attestation precedence**: When multiple attestations exist, later review submissions take precedence over earlier ones. Conflicting attestations within the same submission fail closed.
6. **No worker self-attestation**: Implementation workers (Gemini, Sol) may not post or modify Terra attestations.
7. **Thread resolution**: All review threads/conversations must be marked resolved before merge.

## Verification protocol

A model may say `RECOMMEND_PASS`, but a task reaches `done` only when all required status checks pass on the current PR head:

1. `verify`: deterministic machine gates (lint, typecheck, tests, build, security guards, Supabase RLS, Python runner);
2. `review-gate`: deterministic validation of the fresh Terra xHigh attestation bound to the current head SHA;
3. all review conversation threads are resolved.

If review and CI disagree, CI/runtime evidence wins for deterministic behavior verification, while reviewer findings remain unresolved until explicitly fixed/waived.

No test result or attestation from an earlier commit may be reused as proof for a later changed diff unless the relevant gate reruns.

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
- independent review controls are enforced by the ruleset;
- workflow-state labels exist;
- the linked issue Agent Control Block is present and valid;
- agents cannot edit/reset the authoritative control counter unattended;
- blocked states stop execution;
- retry/review loops are bounded by the authoritative counter;
- secrets/permissions are scoped;
- one manual Sol -> controller -> Gemini -> Terra pipeline completed successfully.

A scheduled controller may watch unambiguous `ready-for-implementation` / `needs-fix` tasks, perform the valid control transition, then invoke Gemini. The implementation worker itself starts only from `implementing`.

Scheduled workers/controllers must fail closed when:

- task issue is missing;
- Agent Control Block is missing/malformed;
- workflow label and `state` disagree;
- multiple primary state labels exist;
- a third fix re-entry would be attempted while current `fix_reentries >= 2`;
- a scope reset lacks Owner-linked approval;
- linked spec/plan is missing;
- task is `blocked-owner` or `blocked-external`.

## Owner escalation conditions

Move to `blocked-owner` when:

- business rule is missing/ambiguous;
- acceptance criteria conflict;
- material architecture change is required;
- a third fix implementation re-entry would be required for the same scope revision;
- independent GitHub approval cannot be obtained under the active ruleset;
- live credential/re-authentication is required;
- a safety rule would need an exception;
- a live write path would need enabling;
- merge risk is high and deterministic evidence is insufficient.

Move to `blocked-external` when a required external service/site/environment is unavailable or cannot be verified safely.
