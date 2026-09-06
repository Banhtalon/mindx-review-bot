# Phase 2 Fast Closure Plan

Date: 2026-09-06

Issue: #11 — Phase 2 hosted/off-PC closure

Branch: `codex/issue-11-phase2-hosted-closure`

This is the active execution plan for closing Phase 2. It supersedes the earlier step-by-step execution order in `2026-09-04-phase2-hosted-off-pc-closure.md` while preserving the same product scope and safety boundaries.

The earlier plan remains historical design/evidence context. This revision changes process and test cadence only; it does not authorize Phase 3/4/6 or live-write behavior.

## Goal

Close only the remaining hosted/off-PC Phase 2 gaps with the fewest necessary iterations.

Do not re-audit local behavior that already has passing evidence unless a hosted failure points directly to it.

## Current starting point

Existing branch implementation already contains the local Phase 2 closure work, including the default-off cron gate and hosted probe bootstrap.

Recorded handoff before this process revision:

- implementation head: `3d61757cfec23772e03b23296d75b6f1fa47cebc`;
- CI for that implementation head passed;
- local handoff recorded 130 web tests, 255 Python tests, and 101 local pgTAP assertions passing;
- hosted RPC/Storage acceptance, Edge dispatch proof, cleanup proof, PC-off attestation, and final fresh Terra review were still outstanding.

The documentation-only commits created by this workflow revision do not invalidate the fact that product code had already passed those local checks. Final merge eligibility will still require current-head CI/review as defined below.

## Non-negotiable boundaries

- Teaching/LMS remain read-only.
- No LMS Save/Submit/comment write path.
- No automatic Zalo send.
- No CAPTCHA/OTP/anti-bot bypass.
- No new schema/RLS redesign in this closure task.
- No credential/cookie/token/PII in repo logs, evidence, or chat.
- Product cron remains disabled by default.
- Synthetic hosted probe data must remain isolated from real product jobs.

## DONE model

Phase 2 closes through six small packets. A packet is finished once its explicit DONE condition is met. Do not continue debugging beyond that condition.

### P2-A — Freeze local implementation

Purpose: stop repeated local rework.

Actions:

1. Treat existing implementation as the candidate unless hosted evidence proves a code defect.
2. Do not rerun every local suite merely because documentation or evidence changed.
3. If code must change, run only the focused test that reproduces the defect plus the affected subsystem tests.

DONE when:

- no known local code blocker prevents the hosted probe;
- current product cron remains default-off;
- no new product-code change is required before hosted execution.

No Terra review at this point.

### P2-B — Hosted environment checkpoint

Purpose: prove the target environment is safe and configured, without changing product code.

Owner/provider checks:

1. isolated hosted development Supabase project selected;
2. synthetic-only workspace/actor available;
3. deployed migrations match the committed set;
4. required GitHub/Supabase secrets and variables are configured privately;
5. no real queued/running jobs or active browser sessions can be affected;
6. `CRON_DISPATCH_ENABLED` remains absent/false.

DONE when:

- all six checks are confirmed, or a single concrete external blocker is recorded.

If blocked by missing configuration, remain `blocked-owner`/`blocked-external`. Do not edit code to compensate for missing secrets/configuration.

### P2-C — Hosted RPC + Storage proof

Purpose: verify the hosted orchestration/state contracts once.

Run the manual hosted probe and verify only these acceptance points:

1. expected RPC access boundary works;
2. lease claim/heartbeat/expiry/retry behavior works;
3. encrypted synthetic browser-state persist works;
4. separate-process reuse/reset works;
5. exact synthetic cleanup removes probe rows/objects.

DONE when:

- the hosted probe passes these five points;
- cleanup leaves no active synthetic state or running lease.

If it fails:

- first classify as configuration/environment vs code;
- configuration/environment failure does not trigger a code review loop;
- for a real code defect, add/reuse one focused regression test, patch once, run focused + affected subsystem tests, then rerun only the failed hosted packet.

Do not restart P2-A or perform a repository-wide audit.

### P2-D — Edge dispatch + PC-off proof

Purpose: prove cloud execution does not depend on the Owner PC.

Acceptance:

1. product cron still disabled;
2. one isolated synthetic dispatch is accepted;
3. repeated idempotency key does not create a duplicate;
4. matching GitHub workflow completes in cloud execution;
5. Owner PC can be off before completion;
6. temporary Edge workflow target is restored after the probe.

DONE when all six conditions are evidenced with safe metadata/run links only.

No Teaching/LMS live reader is required for this packet.

### P2-E — Evidence reconciliation

Purpose: update status once, not after every intermediate action.

Update only the Phase 2 evidence/status documents needed to show:

- hosted RPC/Storage result;
- off-PC dispatch result;
- cleanup result;
- cron remains temporarily disabled;
- live Teaching/LMS readiness is not claimed.

DONE when Phase 2 documentation accurately distinguishes:

- local/synthetic PASS;
- hosted Phase 2 infrastructure PASS;
- still-not-proven live product readiness.

### P2-F — One final verification and review

Purpose: pay the expensive verification cost once on the stable final head.

Sequence:

1. stop code changes;
2. run/obtain required current-head `verify` CI;
3. run only additional risk-specific checks not already covered by CI;
4. request one fresh Terra xHigh review on the exact stable PR head;
5. fix only P0/P1 or material acceptance/safety findings;
6. if code changes, run focused affected tests plus final required CI again;
7. request a new Terra final-head review only because the exact-head gate became stale after that material code change;
8. Controller checks Issue state/label, CI, hosted evidence, review verdict, branch protection, and unresolved conversations;
9. Owner merges manually.

DONE when:

- final-head CI passes;
- hosted P2-C and P2-D evidence passes;
- cleanup passes;
- Terra returns `RECOMMEND_PASS` with P0=0 and P1=0 on the exact final head;
- no material blocker remains.

## Simplified test cadence

### While editing code

Run Level 1 focused tests repeatedly.

Examples:

```bash
npx vitest run test/cron-workflow.test.ts
```

```bash
cd apps/browser-runner
uv run pytest tests/unit/test_hosted_probe.py
```

### Before rerunning a failed hosted packet

Run only the affected subsystem.

Examples:

```bash
npx vitest run test/cron-workflow.test.ts test/ci-contract.test.ts
```

```bash
cd apps/browser-runner
uv run pytest tests/unit/test_hosted_probe.py tests/unit/test_supabase_client.py tests/unit/test_workflow_contract.py
```

Add Ruff/Mypy or lint/typecheck when the touched code warrants them.

### At final stable head

Use required CI as the primary full-repository gate. Do not manually duplicate every full command if CI already runs the same deterministic check and its evidence is available on the exact head.

Run Supabase reset/RLS or hosted/runtime checks separately only when they are not represented by current-head CI and are required by the Phase 2 acceptance boundary.

## Bug routing rule

When any failure appears, classify it before doing work:

- **CONFIG** — secret/variable/project/deployment mismatch: fix configuration, no code loop;
- **CODE-IN-SCOPE** — prevents P2-C/P2-D DONE or was caused by this branch: focused regression + patch;
- **UNRELATED** — does not block the packet and was not caused by the branch: record separately, do not fix here;
- **SAFETY** — could expose secrets/PII, affect real jobs, or weaken read-only boundaries: stop and block.

This classification is mandatory to prevent endless scope expansion.

## Review routing

Phase 2 is high-risk overall, so Terra remains mandatory before merge.

However:

- do not ask Terra to review intermediate local edits;
- do not request a fresh full review after configuration-only changes;
- collect implementation + hosted evidence first;
- request Terra once on the stable candidate head;
- another fresh review is needed only after a material code commit changes that head.

## Exit statement

When P2-A through P2-F are complete, report Phase 2 as:

`hosted/off-PC infrastructure closure PASS`

Do not report:

- live Teaching reader PASS;
- live LMS reader PASS;
- product cron enabled;
- production/live-write readiness.

Those remain separate future tasks.
