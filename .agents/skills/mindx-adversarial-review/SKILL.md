---
name: mindx-adversarial-review
description: Performs fresh-context adversarial review for risky MindX Review Bot changes, attacking edge cases, regressions, identity, auth/session, data integrity, privacy, and live-write safety. Use after spec compliance on medium/high-risk changes.
---

# MindX Adversarial Review

## Independence rule

Start from fresh context.

Review package:

1. `AGENTS.md`
2. task specification and acceptance criteria
3. PR diff
4. deterministic test/CI evidence
5. known limitations/blockers

Do not use implementer chain-of-thought or self-review as evidence.

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
- rollback/regression against existing behavior.

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

The same unchanged task scope is limited to `MAX_FIX_LOOPS = 2`. After that, unresolved material findings require `blocked-owner` escalation.