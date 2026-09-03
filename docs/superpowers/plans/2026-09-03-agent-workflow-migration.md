# Agent Workflow Migration Plan

## Goal

Migrate the repository development workflow to a bounded, evidence-driven multi-model pipeline without changing product behavior.

Target roles:

- **Sol High**: requirements, architecture, acceptance criteria, planning, owner-decision analysis.
- **Gemini 3.8 Flash**: implementation, tests, debugging, scoped refactoring, CI fixes, review fixes.
- **Terra xHigh**: fresh-context spec compliance and adversarial review.
- **GitHub Actions / deterministic commands**: final verification authority.

Superpowers remains the engineering methodology underneath the role-specific workflow.

## Non-goals

This migration does not:

- implement a new product feature;
- change Teaching/LMS behavior;
- enable LMS writes or Zalo delivery;
- change Supabase schemas, migrations, RLS, auth, browser runtime, or application code;
- waive any existing safety or privacy rule;
- start Phase 6;
- enable unattended scheduled agents before one manual pilot succeeds.

## Source of truth

Agents must read in this order:

1. `AGENTS.md` — durable engineering and safety rules.
2. `docs/CURRENT_STATE.md` — current verified project state and blockers.
3. the linked requirement/specification for the task.
4. the linked implementation plan for the task.

The V4 master specification remains the product requirements source. `CURRENT_STATE.md` is a routing/status document and must not silently override the master specification.

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

### Gemini 3.8 Flash

Allowed:

- inspect the repo within task scope;
- implement from an approved plan;
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
- declaring final verification.

### Terra xHigh

Review starts from fresh context. Terra receives the specification, acceptance criteria, PR diff, test/CI evidence, and `AGENTS.md`; it should not depend on the implementer's chain of reasoning.

Review occurs in two passes:

1. **Spec compliance** — missing requirements, extra behavior, acceptance-criteria gaps.
2. **Adversarial review** — edge cases, regression, data integrity, auth/session, idempotency, partial failure, privacy/PII, student identity/mapping, and live-write safety where relevant.

Terra returns only `RECOMMEND_PASS`, `NEEDS_FIX`, or `BLOCKED`.

## Verification authority

No model may mark a task `VERIFIED` based on reasoning or self-review.

A task becomes verified only when all required deterministic gates for its scope pass. Current repository gates include:

- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `npm run verify:no-secrets`
- `npm run verify:no-live-write`
- local Supabase reset/RLS tests where required
- browser-runner Ruff, Mypy, and Pytest where required
- relevant browser/E2E evidence when the task touches authenticated live web behavior

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

`needs-plan -> ready-for-implementation -> implementing -> ready-for-review`

From review:

- `NEEDS_FIX -> needs-fix -> implementing -> ready-for-review`
- `RECOMMEND_PASS -> ready-for-verify -> deterministic verification -> done`
- missing owner decision -> `blocked-owner`
- unavailable external prerequisite -> `blocked-external`

## Bounded review/fix loop

`MAX_FIX_LOOPS = 2` for the same unchanged task scope.

After two review/fix loops, unresolved material findings must move to `blocked-owner` for scope/architecture/business-rule decision instead of continuing indefinitely.

A new material scope decision resets the loop only after the specification/plan is updated.

## Risk-based routing

### Small / low risk

Gemini -> scoped tests -> optional fresh Flash spec check -> deterministic verification.

Terra is not mandatory for text/CSS/trivial mechanical changes unless they touch a safety boundary.

### Medium

Sol plan -> Gemini implementation -> deterministic tests -> fresh spec review -> Terra when risk warrants -> verification.

### High risk

Sol specification/architecture -> fresh plan critique -> Sol final plan -> Gemini implementation -> deterministic tests -> fresh spec review -> Terra adversarial review -> Gemini fixes -> full verification.

Terra is mandatory for Teaching/LMS, student identity/mapping, Supabase/RLS, auth/session/browser state, migrations, privacy/PII, model payload boundaries, and live-write safeguards.

## Migration deliverables

This PR will add/update only workflow artifacts:

- `AGENTS.md`
- `docs/CURRENT_STATE.md`
- `docs/AGENT_WORKFLOW.md`
- `.agents/skills/mindx-plan/SKILL.md`
- `.agents/skills/mindx-implement/SKILL.md`
- `.agents/skills/mindx-spec-review/SKILL.md`
- `.agents/skills/mindx-adversarial-review/SKILL.md`
- `.agents/skills/mindx-verify/SKILL.md`
- `.github/PULL_REQUEST_TEMPLATE.md`

No application behavior file should change.

## Acceptance criteria

- AC1: Existing safety/privacy rules remain intact and are not weakened.
- AC2: Sol, Gemini, Terra, and machine-verification responsibilities are explicit and non-overlapping.
- AC3: No model can declare final `VERIFIED` status.
- AC4: The review/fix loop is bounded at two iterations before owner escalation.
- AC5: Fresh-context Terra review does not depend on Gemini's reasoning transcript.
- AC6: `CURRENT_STATE.md` clearly separates verified, synthetic/local-only, live-blocked, and owner-decision states.
- AC7: PR template requires requirement, acceptance criteria, changed/not-changed scope, tests, verification, and limitations.
- AC8: Migration changes no product source, browser runtime, schema, migration, or business behavior.
- AC9: Existing CI remains green.
- AC10: Scheduled/unattended agents stay disabled until one manual pilot completes successfully.

## Pilot after merge

Choose one small or medium real task. Run the complete manual handoff:

Owner -> Sol plan -> Gemini 3.8 Flash implement -> CI -> Terra fresh review -> Gemini fix if needed -> final CI -> merge.

Only after this pilot demonstrates bounded scope, independent review, and deterministic verification should scheduled/background handoff be enabled.
