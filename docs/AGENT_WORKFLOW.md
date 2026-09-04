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

A workflow is not considered controlled until `main` is protected, the required current-head CI checks are enforced, current independent Terra review cannot be bypassed, unresolved review threads block merge, and the workflow labels exist.

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

For this solo-owner repository, the required merge authority is:

- current-head `verify`;
- current-head `terra-review-gate` check produced via GitHub Checks API by the dedicated GitHub App (`apps/review-gate-worker/`), validating a fresh Terra xHigh attestation authored by the authorized Owner identity (`Banhtalon`, ID `105797112`, `author_association: OWNER`) and bound to the exact re-fetched PR head SHA;
- bootstrap GitHub Actions `review-gate` retained for offline/PR self-test only;
- required conversation resolution;
- protected `main` with no bypass actors and no force pushes;
- `Required approvals = 0` because there is only one GitHub account.

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
                         |                                    verify + review-gate
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

Ask whether the exact current diff satisfies the requirement/spec/acceptance criteria without scope creep.

### Pass 2 — adversarial review

Attack failure modes, trust boundaries, stale-state handling, race/idempotency/retry behavior, auth/session state, PII/privacy, live-write safety, and regressions relevant to the change.

Terra returns findings with P0/P1/P2/P3 severity and exactly one verdict:

- `RECOMMEND_PASS`
- `NEEDS_FIX`
- `BLOCKED`

Terra never declares final `VERIFIED`.

For solo-owner merge authority, a Terra `RECOMMEND_PASS` must be posted by the authorized Owner identity (`Banhtalon`, user ID `105797112`, `author_association: OWNER`) as a structured `TERRA_REVIEW_ATTESTATION_V1` block in top-level PR comments, and verified by the dedicated GitHub App check `terra-review-gate`. Any new push changes the PR head SHA and invalidates the prior attestation automatically.

## Merge authority

A PR may merge only when all applicable conditions are true on the exact current head:

- `verify` passes;
- `terra-review-gate` passes from the dedicated GitHub App when Terra review is required;
- required conversation/review threads are resolved;
- the linked control issue is in a valid verification state (`ready-for-review` or `ready-for-verify`) and its label matches the unique Agent Control Block;
- there are no unresolved P0/P1 findings;
- required live/runtime evidence exists for claims that depend on authenticated live-web behavior.

No model may declare `VERIFIED`; deterministic machine evidence is the final authority.
