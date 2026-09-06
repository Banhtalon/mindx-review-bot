---
name: mindx-plan
description: Creates short risk-routed plans for MindX Review Bot work only when planning is useful.
---

# MindX Plan

## Read first

1. `AGENTS.md`
2. `docs/CURRENT_STATE.md`
3. `docs/DEVELOPMENT_SPEED_POLICY.md`
4. relevant product spec/ADR only when the task depends on it

## When to plan

- **FAST:** normally do not create a separate plan. Define scope + DONE and implement.
- **STANDARD:** use a short plan when the change spans several related files or behavior is not obvious.
- **STRICT:** write a bounded plan when the change touches migrations/RLS/schema, auth/session/browser state, live systems, identity/mapping, privacy/PII, risky infrastructure, or material architecture/data integrity.

Do not use planning as a mandatory ceremony for localized work.

## Minimal plan format

A useful plan should answer only what the worker needs:

1. **Goal** — what outcome is required?
2. **In scope / out of scope** — what must not expand?
3. **DONE** — one observable completion condition or a small set of explicit closure packets.
4. **Risk mode** — FAST / STANDARD / STRICT and why.
5. **Verification** — smallest focused test; affected subsystem check; runtime/hosted proof only if required; final CI once on the stable candidate.

Add rollback/recovery only when a failure could affect data, auth, real jobs, or deployment state.

## Rules

- Do not create a large task list when one small DONE condition is enough.
- Do not require brainstorming/TDD/review artifacts by default.
- Do not reopen already-passing areas without concrete evidence they block the current DONE condition.
- Do not guess missing business rules, credentials, selectors, or identity mappings.
- Keep synthetic/local evidence distinct from live/hosted proof.
- Keep Teaching/LMS read-only unless Owner explicitly approves a different product scope.

## Output

Prefer a short issue section or compact task document. Repository plan files are mainly for STRICT work or a multi-step closure that another agent must continue later.

Use `blocked-owner` / `blocked-external` only for a real unresolved dependency, not merely because the task lacks a formal planning artifact.
