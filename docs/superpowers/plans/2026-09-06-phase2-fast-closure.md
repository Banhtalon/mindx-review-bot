# Phase 2 Fast Closure Plan

Date: 2026-09-06
Issue: #11 — Phase 2 hosted/off-PC closure
Active v9 staging branch: `codex/task-11-v9-phase2-hosted-closure`
Approved base: `cf07aeb680c9c3b0e06813d2e1a66ceea6f9b427`

QQ AI Workflow v9 is the workflow authority. This document only defines the product execution order and fast test cadence. The historical branch `codex/issue-11-phase2-hosted-closure` is source material only; it is not an active v9 attempt and must not be merged wholesale over the post-v9 baseline.

## Goal

Close only the remaining hosted/off-PC Phase 2 gaps with the fewest necessary iterations.

Do not re-audit local behavior that already has passing evidence unless a hosted failure points directly to an in-scope code defect.

## Non-negotiable boundaries

- Teaching/LMS remain read-only.
- No LMS Save/Submit/comment write path.
- No automatic Zalo send.
- No CAPTCHA/OTP/anti-bot bypass.
- No new schema/RLS redesign in this closure task.
- No credential/cookie/token/PII in repo logs, evidence, issues, or chat.
- Product cron remains disabled by default.
- Synthetic hosted probe data stays isolated from real product jobs.
- Model routing remains manual.

## P2-B — Hosted environment checkpoint

Confirm:

1. isolated hosted development Supabase project;
2. synthetic-only Auth actor/workspace;
3. remote migration history aligns with the four committed versions using the supported Supabase migration-history workflow;
4. required GitHub/Supabase secrets and variables are configured privately;
5. no real queued/running jobs or active browser sessions can be affected;
6. `CRON_DISPATCH_ENABLED` remains absent/false.

Configuration/history mismatch is a CONFIG/Technical-Operator blocker, not a reason to alter product schema or bypass safety controls.

DONE when all six are confirmed.

## P2-C — Hosted RPC + Storage proof

Run the manual hosted probe once and verify:

1. expected RPC access boundary;
2. lease claim/heartbeat/expiry/retry behavior;
3. encrypted synthetic state persist;
4. separate-process reuse/reset;
5. exact synthetic cleanup.

On failure classify first: CONFIG, CODE-IN-SCOPE, UNRELATED, or SAFETY. Only CODE-IN-SCOPE permits the smallest product patch plus focused/affected tests.

## P2-D — Edge dispatch + PC-off proof

Verify:

1. product cron still disabled;
2. one isolated synthetic dispatch is accepted;
3. repeated idempotency key creates no duplicate;
4. matching GitHub workflow completes in cloud execution;
5. Owner PC can be off before completion;
6. temporary Edge workflow target is restored after the probe.

No live Teaching/LMS reader is required.

## P2-E — Evidence reconciliation

Update minimum evidence once after hosted packets complete and clearly distinguish:

- LOCAL_HERMETIC PASS;
- CI PASS;
- HOSTED Phase 2 infrastructure PASS;
- LIVE Teaching/LMS readiness still unproven.

Keep product cron temporarily disabled.

## P2-F — Stable final verification

On the stable final candidate:

1. stop code changes;
2. run the frozen v9 manifest / required current-head `verify` CI;
3. run only risk-specific checks not already covered;
4. obtain one fresh Terra xHigh review on the exact head;
5. Controller checks current Issue #11 state, frozen digest, hosted evidence, review findings, branch protection, and unresolved conversations;
6. Owner merges manually.

A material code fix after review requires affected checks + current-head CI + a new exact-head review.

## Test cadence

During code work: focused tests only.

Before rerunning a failed hosted packet after a code fix: affected subsystem tests once plus relevant static checks.

Stable final head: use the current-head GitHub `verify` and frozen v9 manifest as the broad deterministic gate; do not duplicate the same full-suite run without a head change.

## Exit statement

When P2-B through P2-F are complete, report only:

`hosted/off-PC infrastructure closure PASS`

Do not claim live Teaching/LMS reader PASS, product cron enabled, or production/live-write readiness.
