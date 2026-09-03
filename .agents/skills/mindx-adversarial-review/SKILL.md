---
name: mindx-adversarial-review
description: Fresh-context adversarial review for risky MindX Review Bot changes, attacking edge cases, regressions, identity, auth/session, data integrity, privacy, and live-write safety.
---

# MindX Adversarial Review

## Independence rule

Start from fresh context.

Review package:

1. `AGENTS.md`
2. `docs/CURRENT_STATE.md`
3. linked GitHub issue Agent Control Block and current workflow-state label
4. task specification and acceptance criteria
5. PR diff
6. deterministic test/CI evidence from the current PR head
7. known limitations/blockers
8. relevant `docs/evidence/index.json` entries when any live/hosted readiness claim is made

Do not use implementer chain-of-thought or self-review as evidence.

If task control state is missing, malformed, conflicting, or ambiguous, return `BLOCKED`.

## Mandatory use

Use this skill for changes involving:

- Teaching/LMS;
- student identity or mapping;
- Supabase/RLS/migrations;
- auth/session/browser state;
- privacy/PII/model payloads;
- live-write safeguards;
- high-risk data or architecture changes.

## Attack checklist

Try to break the change through relevant dimensions:

- boundary/invalid inputs;
- retry/idempotency;
- timeout/cancellation/cleanup;
- race/concurrency/leases;
- partial failure and recovery;
- stale or expired authentication/session state;
- browser-state reuse/reset;
- wrong class/session/student identity;
- ambiguous/manual mapping;
- row-order identity leakage;
- DB/RLS authorization and data integrity;
- secret/PII leakage in logs/evidence/model payloads;
- accidental Save/Submit/comment mutation;
- hidden scope expansion;
- rollback/regression against existing behavior;
- mismatch between `docs/CURRENT_STATE.md` and claimed readiness;
- invalid issue `state`, `scope_revision`, `fix_reentries`, or workflow label;
- live/hosted claims unsupported by the evidence index.

When a finding depends on runtime behavior that cannot be proven from the diff, request the smallest deterministic/runtime evidence needed instead of guessing.

## Finding format

For each material finding include:

- severity: P0/P1/P2/P3;
- affected requirement or invariant;
- failure scenario/reproduction;
- evidence;
- expected behavior;
- recommended regression test/fix.

## Verdict

Return exactly one overall recommendation:

- `RECOMMEND_PASS`
- `NEEDS_FIX`
- `BLOCKED`

`RECOMMEND_PASS` is not `VERIFIED`.

The authoritative `fix_reentries` counter lives in the linked GitHub issue. At `fix_reentries >= 2`, another autonomous implementation re-entry is forbidden and requires `blocked-owner` escalation.
