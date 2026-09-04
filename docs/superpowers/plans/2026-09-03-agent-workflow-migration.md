# Agent Workflow Migration Plan

## Goal

Migrate the repository development workflow to a bounded, evidence-driven multi-model pipeline without changing product behavior.

Target roles:

- **Sol High**: requirements, architecture, acceptance criteria, planning, owner-decision analysis.
- **Gemini 3.8 Flash**: implementation, tests, debugging, scoped refactoring, CI fixes, review fixes.
- **Terra xHigh**: fresh-context spec compliance and adversarial review.
- **GitHub issue/ruleset/CI**: authoritative workflow state, independent merge controls, and deterministic verification evidence.

Superpowers remains the engineering methodology underneath the role-specific workflow.

## Non-goals

This migration does not:

- implement a new product feature;
- change Teaching/LMS behavior;
- enable LMS writes or Zalo delivery;
- change Supabase schemas, migrations, RLS, auth, browser runtime, or application code;
- waive any existing safety or privacy rule;
- start Phase 6;
- enable unattended scheduled development agents before one manual pilot succeeds.

## Source of truth

Agents must read in this order:

1. `AGENTS.md` — durable engineering and safety rules.
2. `docs/CURRENT_STATE.md` — current verified project state and blockers.
3. linked standalone GitHub issue Agent Control Block + exactly one matching workflow-state label.
4. the linked requirement/specification and implementation plan for the task.

The V4 master specification remains the product requirements source. `CURRENT_STATE.md` is a routing/status document and must not silently override the master specification. Live GitHub issue/ruleset/CI state is authoritative for fast-changing control data.

## Role boundaries

### Sol High

Allowed:

- clarify requirements;
- define acceptance criteria;
- make or propose architecture decisions;
- decompose medium/high-risk work;
- identify owner decisions and blockers.

Normally prohibited:

- routine implementation;
- routine bug fixing;
- acting as a message broker between workers/reviewers;
- declaring final verification.

Sol exits the loop after a task is `ready-for-implementation` unless the task becomes `blocked-owner`, `blocked-external`, or requires a material architecture/spec change.

### Controller / Owner control plane

A controller (manual during the pilot) owns authoritative issue state transitions and labels. The implementation worker does not edit/reset its own counter unattended.

Initial implementation transition:

`ready-for-implementation / fix_reentries=0 -> implementing / fix_reentries=0`.

Fix transition is atomic and permitted only while current `fix_reentries < 2`:

- `needs-fix / 0 -> implementing / 1`: fix re-entry #1 allowed;
- `needs-fix / 1 -> implementing / 2`: fix re-entry #2 allowed;
- new attempted transition from `needs-fix / 2`: third re-entry blocked; route `blocked-owner` without incrementing or invoking code.

### Gemini 3.8 Flash

Allowed:

- inspect the repo within task scope;
- implement from an approved plan after the task is already in valid `implementing` state;
- write and update tests;
- debug failures;
- make scoped refactors required by the task;
- fix review findings;
- prepare verification evidence and PR summaries.

Prohibited:

- inventing business rules;
- silently changing architecture;
- weakening tests/safety gates to get green;
- waiving acceptance criteria;
- expanding scope without escalation;
- editing/resetting authoritative issue state/counter unattended;
- declaring final verification.

### Terra xHigh

Review starts from fresh context. Terra receives:

- `AGENTS.md`;
- `docs/CURRENT_STATE.md`;
- linked standalone issue Agent Control Block + workflow-state label;
- specification and acceptance criteria;
- PR diff;
- current-head test/CI evidence;
- relevant evidence-index entries for any live/hosted readiness claim.

Terra should not depend on the implementer's chain of reasoning.

Review occurs in two passes:

1. **Spec compliance** — missing requirements, extra behavior, acceptance-criteria gaps, state/readiness contradictions.
2. **Adversarial review** — edge cases, regression, data integrity, auth/session, idempotency, partial failure, privacy/PII, student identity/mapping, and live-write safety where relevant.

Terra returns only `RECOMMEND_PASS`, `NEEDS_FIX`, or `BLOCKED`.

## Verification and merge authority

No model may mark a task `VERIFIED` based on reasoning or self-review.

A task becomes merge-ready only when all required deterministic gates for its scope pass on the current PR head **and** enforced independent-review controls are satisfied.

Current repository gates include:

- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `npm run verify:no-secrets`
- `npm run verify:no-live-write`
- local Supabase reset/RLS tests where required
- browser-runner Ruff, Mypy, and Pytest where required
- relevant browser/E2E evidence when the task touches authenticated live web behavior

The active `main` ruleset must enforce:

- PR required;
- `Required approvals = 0` (solo-owner repository model);
- current-head `verify` required with branch up to date;
- current-head `review-gate` required;
- no bypass/direct worker merge;
- fresh Terra attestation bound to exact current head SHA (push automatically invalidates previous attestation);
- material review conversations resolved before merge.

A green `verify` CI result alone is not sufficient; both `verify` and `review-gate` must pass.

## Task state machine

Canonical states:

- `needs-plan`
- `ready-for-implementation`
- `implementing`
- `ready-for-review`
- `needs-fix`
- `ready-for-verify`
- `done`
- `blocked-owner`
- `blocked-external`

Transitions:

- `needs-plan -> ready-for-implementation` after Sol/spec completion;
- controller: `ready-for-implementation/0 -> implementing/0`;
- worker: `implementing -> ready-for-review` after scoped implementation/evidence;
- review `NEEDS_FIX -> needs-fix`;
- controller permits `needs-fix/0 -> implementing/1` and `needs-fix/1 -> implementing/2`;
- a new third re-entry request from `needs-fix/2` routes `blocked-owner`;
- `RECOMMEND_PASS -> ready-for-verify -> deterministic verification -> done` only when review and merge controls are also satisfied;
- missing owner decision -> `blocked-owner`;
- unavailable external prerequisite -> `blocked-external`.

## Bounded review/fix loop

`MAX_FIX_LOOPS = 2` for the same unchanged task scope.

This means **exactly two fix implementation re-entries are permitted; the third attempted re-entry is blocked**.

The authoritative count lives in the linked standalone GitHub issue. PR text is only a snapshot/reference.

A material scope decision may reset the count only after:

1. Owner explicitly approves the material scope revision;
2. `scope_revision` increments;
3. approval link is recorded in `owner_scope_reset`;
4. counter resets to `0`;
5. updated spec/plan is linked.

## Risk-based routing

### Small / low risk

Controller -> Gemini -> scoped tests -> optional fresh spec check -> deterministic verification.

Terra is not mandatory for text/CSS/trivial mechanical changes unless they touch a safety boundary.

### Medium

Sol plan -> controller -> Gemini implementation -> deterministic tests -> fresh spec review -> Terra when risk warrants -> verification.

### High risk

Sol specification/architecture -> fresh plan critique -> Sol final plan -> controller -> Gemini implementation -> deterministic tests -> fresh spec review -> Terra adversarial review -> controller/Gemini fixes -> full verification.

Terra is mandatory for Teaching/LMS, student identity/mapping, Supabase/RLS, auth/session/browser state, migrations, privacy/PII, model payload boundaries, and live-write safeguards.

## Migration deliverables

This PR adds/updates only workflow artifacts:

- `AGENTS.md`
- `docs/CURRENT_STATE.md`
- `docs/AGENT_WORKFLOW.md`
- `docs/AGENT_WORKFLOW_OWNER_SETUP.md`
- `.agents/skills/mindx-plan/SKILL.md`
- `.agents/skills/mindx-implement/SKILL.md`
- `.agents/skills/mindx-spec-review/SKILL.md`
- `.agents/skills/mindx-adversarial-review/SKILL.md`
- `.agents/skills/mindx-verify/SKILL.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/ISSUE_TEMPLATE/agent-task.yml`

The migration itself has standalone authoritative control issue #7.

No application behavior file should change.

## Acceptance criteria

- AC1: Existing safety/privacy rules remain intact and are not weakened.
- AC2: Sol, controller, Gemini, Terra, and machine-verification responsibilities are explicit and non-overlapping.
- AC3: No model can declare final `VERIFIED` status.
- AC4: Exactly two fix implementation re-entries are permitted for unchanged scope; the third is blocked by authoritative issue state.
- AC5: Fresh-context Terra review does not depend on Gemini's reasoning transcript and includes current state/control evidence.
- AC6: `CURRENT_STATE.md` clearly separates verified, synthetic/local-only, live-blocked, and owner-decision states and matches live repository controls.
- AC7: PR/issue templates require authoritative control linkage, acceptance criteria, scope, tests, verification, limitations, and current independent review evidence.
- AC8: Migration changes no product source, browser runtime, schema, migration, or business behavior.
- AC9: Current-head CI remains green after final migration changes.
- AC10: Active `main` rules enforce `Required approvals = 0`, dual required status checks (`verify` and `review-gate`), stale-attestation invalidation by head SHA, and review-thread resolution before merge.
- AC11: Scheduled/unattended development agents stay disabled until one manual pilot completes successfully.

## Pilot after merge

Choose one small or medium real task. Run the complete manual handoff:

Owner -> Sol plan -> controller state transition -> Gemini 3.8 Flash implement -> CI -> Terra fresh review -> controller fix transition if needed -> Gemini fix -> final CI -> Terra attestation + review-gate pass / thread resolution -> merge.

Only after this pilot demonstrates bounded scope, independent review, and deterministic verification should scheduled/background development-agent handoff be enabled.
