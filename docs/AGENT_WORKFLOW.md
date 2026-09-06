# Agent Workflow

## Purpose

Define a fast, risk-routed handoff between Owner, planning/review models, implementation workers, GitHub, and deterministic verification.

This document changes development process only. Product safety and read-only boundaries remain unchanged.

Canonical speed policy: [`docs/DEVELOPMENT_SPEED_POLICY.md`](./DEVELOPMENT_SPEED_POLICY.md).

## Control plane

GitHub is the shared control plane:

- issue = scope + authoritative workflow state;
- task plan = DONE conditions;
- branch/PR = implementation diff;
- CI/runtime evidence = deterministic proof;
- labels/state = handoff signal.

Do not copy long model reasoning transcripts between agents. Agents should read the repository state and concise evidence instead.

## Three execution modes

### FAST

For low-risk localized work.

Flow:

`Owner/task -> implementation worker -> focused tests -> diff check -> required CI -> merge`

No mandatory Sol plan. Terra normally skipped.

### STANDARD

For normal features/non-trivial bugs that do not touch a high-risk boundary.

Flow:

`short plan -> implementation -> focused tests -> affected subsystem -> CI -> one review if useful -> merge`

Default is one review round, not a review after every small fix.

### STRICT

For migrations/RLS/schema, auth/session/browser state, live Teaching/LMS behavior, identity/mapping, privacy/PII, live-write safeguards, risky deployment/infrastructure, or material architecture/data-integrity changes.

Flow:

`plan/spec if needed -> implementation -> focused tests -> runtime/hosted evidence -> final CI -> fresh Terra on stable final head -> Owner merge`

Terra remains mandatory here, but should be called after the implementation is stable.

## Roles

### Owner

Owns product intent, business rules, scope/waiver decisions, provider credentials/configuration, high-risk merge approval, and blocked escalations.

### Sol High

Use for planning only when the task is medium/high-risk, ambiguous, or architectural. Sol should not remain in routine coding/fix loops.

### Implementation worker

Can be Codex/Gemini or equivalent. It owns scoped implementation, focused testing, debugging, CI fixes, and evidence preparation.

Worker must not invent business rules, broaden scope silently, weaken safety gates, or fix unrelated defects merely because they were noticed.

### Terra xHigh

Fresh adversarial review for STRICT/high-risk final candidate diffs. Terra reviews spec compliance, safety, regression, auth/session, retry/idempotency, data integrity, privacy/PII, identity/mapping, and live-write boundaries when relevant.

Terra returns `RECOMMEND_PASS`, `NEEDS_FIX`, or `BLOCKED`.

## Test economy

Use the test ladder from `docs/DEVELOPMENT_SPEED_POLICY.md`.

### During implementation

Run focused tests repeatedly.

### Before a subsystem is considered ready

Run affected-module tests and relevant static checks.

### Before merge

Use required current-head `verify` CI as the main full-repository deterministic gate. Manually rerun full suites only when CI does not cover the required check or when a risk-specific local/hosted gate is required.

Do not duplicate an identical full verification run when code/head has not changed.

## Failure classification before fixing

Every new failure must be classified before expanding work:

- `CONFIG` — provider secret/variable/project/deployment problem;
- `CODE-IN-SCOPE` — blocks current DONE condition or was caused by current diff;
- `UNRELATED` — real issue but not part of current DONE condition/current diff;
- `SAFETY` — security/privacy/read-only/real-job risk.

Routing:

- CONFIG: fix config, no code review loop;
- CODE-IN-SCOPE: focused regression + bounded patch;
- UNRELATED: record separate task, continue current closure;
- SAFETY: stop and block/escalate.

## Authoritative task state

Agent-driven tasks continue to use one linked GitHub issue with:

```text
state: <canonical state>
scope_revision: <positive integer>
fix_reentries: <0..2>
owner_scope_reset: <none | Owner approval link>
```

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

`MAX_FIX_LOOPS = 2` still limits material implementation re-entry for one unchanged scope revision.

Configuration changes, reruns, docs/evidence-only updates, and optional non-material review suggestions do not consume a code fix re-entry.

## Review economy

Request review late.

Why: exact-head review evidence becomes stale after product-code commits. Reviewing every intermediate patch creates avoidable cycles.

Rules:

- FAST: no Terra unless safety boundary unexpectedly appears;
- STANDARD: one review when useful/risk-routed;
- STRICT: one fresh Terra review on the stable final candidate head;
- another final-head review is necessary only after a material code commit changes the reviewed head;
- P2/P3 style/preferences do not automatically block closure.

## Verification authority

No model can declare final `VERIFIED` on opinion alone.

Merge authority uses:

- required current-head CI;
- required risk-specific runtime/hosted evidence;
- mandatory fresh Terra review for STRICT changes;
- resolved material review findings;
- protected `main`;
- Owner manual merge.

## Merge rules

- no direct feature/fix push to `main`;
- `verify` remains required on `main`;
- strict up-to-date branch policy remains enabled;
- unresolved material review conversations must be resolved;
- no bypass actors/force-push relaxation;
- `Required approvals = 0` remains correct for the solo-owner repository;
- Owner performs the final merge manually.

## Evidence package

Keep review/closure evidence concise:

1. issue/scope;
2. exact candidate head SHA;
3. changed files and explicit non-scope;
4. focused/subsystem test result;
5. final CI result;
6. runtime/hosted run link when required;
7. cleanup/blocker result;
8. Terra verdict when risk-routed.

Do not attach duplicate logs or model reasoning transcripts.

## Phase closure rule

A phase must be split into closure packets with explicit DONE conditions. Finish one packet before investigating another.

Current Phase 2 packet plan:

[`docs/superpowers/plans/2026-09-06-phase2-fast-closure.md`](./superpowers/plans/2026-09-06-phase2-fast-closure.md)

For Phase 2, do not reopen already-passing local work unless hosted evidence identifies a concrete in-scope code defect.
