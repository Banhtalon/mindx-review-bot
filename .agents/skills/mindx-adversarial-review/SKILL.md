---
name: mindx-adversarial-review
description: Reviews stable final candidates for STRICT/high-risk MindX Review Bot changes, focusing on material correctness and safety findings.
---

# MindX Adversarial Review

## When to use

Use this skill for the stable final candidate of a **STRICT/high-risk** change, including:

- Teaching/LMS live behavior;
- student identity or mapping;
- Supabase/RLS/migrations/schema;
- auth/session/browser state;
- privacy/PII/model payload boundaries;
- live-write safeguards;
- risky deployment/infrastructure;
- material architecture or data-integrity changes.

Do not require this review for ordinary FAST work. Do not review every intermediate patch.

## Read

1. `AGENTS.md`
2. `docs/CURRENT_STATE.md`
3. current task scope + DONE condition
4. stable candidate diff/head SHA
5. current-head CI evidence
6. runtime/hosted evidence required by the task
7. relevant evidence index when a live/hosted readiness claim is made

Do not use implementer chain-of-thought as evidence.

## Review focus

Review only dimensions material to the current scope:

- missing or incorrect acceptance behavior;
- scope creep/regression caused by the diff;
- authorization/RLS/data integrity;
- retry/idempotency/race/timeout/cleanup when relevant;
- auth/session/browser-state expiry and reuse when relevant;
- student identity/mapping correctness;
- secret/PII leakage;
- accidental Save/Submit/live-write behavior;
- mismatch between claimed live/hosted readiness and actual runtime evidence.

Do not restart a repository-wide audit because an unrelated issue is noticed. Record unrelated findings separately.

When runtime behavior cannot be established from the diff, request the **smallest** missing deterministic/runtime proof instead of asking for a broad new test campaign.

## Severity and closure

- **P0/P1:** blocking.
- **P2:** blocking only when it materially affects acceptance, correctness, safety, data integrity, or maintainability of this task.
- **P3/style/preference:** non-blocking; do not create a fix/review cycle by default.

## Output

For each material finding provide:

- severity;
- affected requirement/invariant;
- concrete failure scenario/evidence;
- smallest required fix or proof.

End with exactly one verdict:

- `RECOMMEND_PASS`
- `NEEDS_FIX`
- `BLOCKED`

Also report the exact reviewed head SHA. `RECOMMEND_PASS` is a review recommendation, not final machine verification.

No special attestation template or long process transcript is required.
