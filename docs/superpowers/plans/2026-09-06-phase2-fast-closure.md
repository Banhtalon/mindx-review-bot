# Phase 2 Fast Closure Plan

Date: 2026-09-06

Issue: #11 — Phase 2 hosted/off-PC closure

Branch: `codex/issue-11-phase2-hosted-closure`

This is the **only active execution plan** for closing Phase 2. Older heavy execution checklists are retired and must not be used for routing. This plan preserves the approved product scope and safety boundaries while minimizing repeated testing/review work.

## Goal

Close only the remaining hosted/off-PC Phase 2 gaps with the fewest necessary iterations.

Do not re-audit local behavior that already has passing evidence unless a hosted failure points directly to an in-scope code defect.

## Non-negotiable boundaries

- Teaching/LMS remain read-only.
- No LMS Save/Submit/comment write path.
- No automatic Zalo send.
- No CAPTCHA/OTP/anti-bot bypass.
- No new schema/RLS redesign in this closure task.
- No credential/cookie/token/PII in repo logs, evidence, or chat.
- Product cron remains disabled by default.
- Synthetic hosted probe data stays isolated from real product jobs.

## Closure packets

### P2-A — Freeze local implementation

Treat the existing product implementation as the candidate unless hosted evidence proves a code defect.

DONE when:

- no known local blocker prevents hosted execution;
- product cron remains default-off;
- no product-code change is required before the hosted checkpoint.

Do not rerun full local suites merely because docs/evidence changed. No Terra review here.

### P2-B — Hosted environment checkpoint

Confirm only:

1. isolated hosted development Supabase project;
2. synthetic-only workspace/actor;
3. deployed migrations match the committed set;
4. required GitHub/Supabase secrets and variables are configured privately;
5. no real queued/running jobs or active browser sessions can be affected;
6. `CRON_DISPATCH_ENABLED` remains absent/false.

DONE when all six are confirmed, or one concrete external blocker is recorded.

Missing configuration is a CONFIG blocker, not a reason to edit product code.

### P2-C — Hosted RPC + Storage proof

Run the manual hosted probe once and verify:

1. expected RPC access boundary;
2. lease claim/heartbeat/expiry/retry behavior;
3. encrypted synthetic state persist;
4. separate-process reuse/reset;
5. exact synthetic cleanup.

DONE when those five points pass and no active synthetic state or running lease remains.

On failure, classify first:

- CONFIG → correct configuration and rerun P2-C;
- CODE-IN-SCOPE → focused regression + smallest patch + affected-subsystem tests, then rerun only P2-C;
- UNRELATED → record separately;
- SAFETY → stop/escalate.

Do not restart P2-A or audit the whole phase.

### P2-D — Edge dispatch + PC-off proof

Verify:

1. product cron still disabled;
2. one isolated synthetic dispatch is accepted;
3. repeated idempotency key creates no duplicate;
4. matching GitHub workflow completes in cloud execution;
5. Owner PC can be off before completion;
6. temporary Edge workflow target is restored after the probe.

DONE when all six are evidenced with safe metadata/run links only.

No live Teaching/LMS reader is required.

### P2-E — Evidence reconciliation

Update the minimum Phase 2 evidence/status documents once after hosted packets complete.

Evidence must distinguish:

- local/synthetic PASS;
- hosted Phase 2 infrastructure PASS;
- live Teaching/LMS readiness still not proven.

Keep product cron status `temporarily disabled`.

### P2-F — One final verification + review

On the stable final candidate:

1. stop code changes;
2. use required current-head `verify` CI as the broad deterministic gate;
3. run only additional risk-specific checks not covered by CI;
4. request one fresh Terra xHigh review on that stable head;
5. fix only P0/P1 or material acceptance/safety findings;
6. after a material code fix, rerun focused/affected tests + required CI and obtain a new final-head review because the reviewed SHA changed;
7. Controller checks current issue state, CI, hosted evidence, material review findings, branch protection, and unresolved conversations;
8. Owner merges manually.

DONE when:

- final-head CI passes;
- P2-C and P2-D hosted evidence passes;
- cleanup passes;
- Terra returns `RECOMMEND_PASS` with no P0/P1 or material blocker;
- no safety/scope blocker remains.

## Test cadence

### While editing code

Run Level 1 focused tests only.

Examples:

```bash
npx vitest run test/cron-workflow.test.ts
```

```bash
cd apps/browser-runner
uv run pytest tests/unit/test_hosted_probe.py
```

### Before rerunning a failed hosted packet after a code fix

Run the affected subsystem once, plus relevant static checks.

Examples:

```bash
npx vitest run test/cron-workflow.test.ts test/ci-contract.test.ts
```

```bash
cd apps/browser-runner
uv run pytest tests/unit/test_hosted_probe.py tests/unit/test_supabase_client.py tests/unit/test_workflow_contract.py
```

### Stable final head

Use current-head GitHub `verify` as the main full-repository gate. Do not manually duplicate the same full-suite run when code/head has not changed.

## Exit statement

When P2-A through P2-F are complete, report only:

`hosted/off-PC infrastructure closure PASS`

Do not claim live Teaching/LMS reader PASS, product cron enabled, or production/live-write readiness.
