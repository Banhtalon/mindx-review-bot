# Phase 2 Hosted/Off-PC Closure Implementation Plan

> **For the implementation worker:** follow `AGENTS.md`, the linked Issue #11
> Agent Control Block, TDD, systematic debugging, review, and verification rules.
> Do not start until the Controller has changed the issue state/label to
> `implementing`. This plan does not authorize Phase 3, Phase 4, Phase 6, live
> Teaching/LMS navigation, or any external write path.

**Goal:** produce reproducible hosted infrastructure evidence for the existing
Phase 2 orchestration, lease, encrypted-state, and off-PC contracts while leaving
the product schedule fail-closed until later live adapters are ready.

**Design:** [Phase 2 Hosted/Off-PC Closure Design](../specs/2026-09-04-phase2-hosted-off-pc-closure-design.md)

**Issue:** [#11](https://github.com/Banhtalon/mindx-review-bot/issues/11)

**Risk:** high

**Expected review:** fresh Terra xHigh on exact PR head

## Global stop conditions

Immediately stop and route the issue as indicated when:

- issue state/label/control block is missing or inconsistent — `BLOCKED`;
- implementation requires a new product job type, migration, or RLS redesign —
  `blocked-owner` and a new scope revision;
- a real credential, cookie, token, PII, or raw page content would enter logs,
  fixtures, evidence, or chat — `blocked-owner`;
- hosted migration state differs from committed migrations —
  `blocked-external` or `blocked-owner`; do not repair schema in this scope;
- the only available Supabase environment is active and cannot safely be pointed
  at a synthetic probe workflow — `blocked-owner`;
- CAPTCHA/OTP/anti-bot or live site navigation becomes necessary —
  `blocked-owner`; do not bypass;
- any proposed change weakens `verify`, `protect-main`, no-secret, no-live-write,
  timeout, retry, or service-role boundaries — `BLOCKED`.

## Task 1: Freeze the current failure inventory in tests and evidence

**Files:**

- Modify: `test/cron-workflow.test.ts`
- Modify: `apps/browser-runner/tests/unit/test_workflow_contract.py`
- Create: `docs/evidence/phase-2/V4-P2-10-hosted-inventory.md`

- [ ] Add a regression fixture/assertion for the current safe error contract:
  missing cron configuration returns only `CRON_CONFIG_INVALID` and never an
  environment value.
- [ ] Add an assertion that no scheduled product dispatch can run when the new
  enable gate is absent or false.
- [ ] Record the 2026-09-04 inventory: main SHA, 42/42 cron failures, inspected
  first/latest `CRON_CONFIG_INVALID`, no repository/environment Actions secrets,
  zero browser-runner runs, and `SITE_ADAPTER_NOT_CONFIGURED` entrypoint.
- [ ] Run focused tests before implementation and preserve RED output in the PR
  evidence summary; do not commit raw logs containing environment values.

## Task 2: Make the cron scheduler explicitly fail-closed

**Files:**

- Modify: `.github/workflows/cron-dispatch.yml`
- Modify: `scripts/cron_dispatch.mjs`
- Modify: `scripts/cron_dispatch.d.mts`
- Modify: `test/cron-workflow.test.ts`
- Modify: `test/ci-contract.test.ts` if the workflow inventory changes

- [ ] Add a non-secret `CRON_DISPATCH_ENABLED` contract that accepts only the
  exact strings `true` or `false`; missing means disabled.
- [ ] Ensure scheduled runs with the gate disabled make no network request and
  produce a concise safe `disabled` summary.
- [ ] Keep manual validation possible, but require an explicit manual enable
  input and the same safe preflight.
- [ ] Preserve the job-type allowlist, empty payload, idempotency key, UTC
  schedule, `contents: read`, timeout, and non-cancelling concurrency.
- [ ] Add RED/GREEN tests for absent, false, malformed, and true gate values; no
  test may print a secret.

## Task 3: Add hosted probe client primitives without changing schema

**Files:**

- Modify: `apps/browser-runner/src/mindx_runner/supabase_client.py`
- Create: `apps/browser-runner/src/mindx_runner/hosted_probe.py`
- Modify: `apps/browser-runner/src/mindx_runner/cli.py`
- Modify: `apps/browser-runner/src/mindx_runner/live_runner.py`
- Create: `apps/browser-runner/tests/unit/test_hosted_probe.py`
- Modify: `apps/browser-runner/tests/unit/test_supabase_client.py`

- [ ] Add read methods for the one active browser-state metadata row and exact
  probe-row cleanup; validate every UUID, site, path, status, count, and hash.
- [ ] Keep keys out of `repr`, exceptions, summaries, and pytest diffs.
- [ ] Add a `phase2-hosted-probe` CLI distinct from `mindx-runner run`; it must
  never construct `ReadonlyBrowserSession` or open a URL.
- [ ] Implement `database`, `state-persist`, `state-reuse-reset`, and `cleanup`
  subcommands using only synthetic IDs/data.
- [ ] Finish synthetic lease runs as `cancelled`/safe-probe, never `succeeded` as
  if Teaching/LMS records were read.
- [ ] Test wrong role/runner, duplicate claim, heartbeat extension, expired lease,
  max attempts, tampered encrypted bytes, missing active version, repeated reset,
  partial failure, and cleanup retry.

## Task 4: Add the manual-only hosted workflow

**Files:**

- Create: `.github/workflows/phase2-hosted-verify.yml`
- Modify: `apps/browser-runner/tests/unit/test_workflow_contract.py`
- Modify: `test/ci-contract.test.ts`

- [ ] Use only `workflow_dispatch`; do not add `schedule`, `pull_request_target`,
  artifact upload, traces, screenshots, video, or HAR.
- [ ] Set `permissions: contents: read`, pinned actions, locked Python dependencies,
  a 15-minute job timeout, and concurrency keyed to a validated opaque probe ID.
- [ ] Split persist and reuse/reset into separate jobs/processes so reuse is not
  an in-memory artifact. Pass only opaque IDs and hashes between jobs.
- [ ] Add an always-run exact-probe cleanup job. Cleanup failure must fail the
  workflow and leave a safe remediation code, not silently pass.
- [ ] Emit a compact GitHub step summary with commit SHA, run URL, statuses,
  durations, counts, and hashes only.
- [ ] Add workflow-contract tests proving all safety properties.

## Task 5: Run complete local verification before requesting hosted inputs

From the repository root:

- [ ] `npm run lint`
- [ ] `npm run typecheck`
- [ ] `npm run test`
- [ ] `npm run build`
- [ ] `npm run verify:no-secrets`
- [ ] `npm run verify:no-live-write`
- [ ] `npx supabase db reset`
- [ ] `npm run test:rls`
- [ ] From `apps/browser-runner`: `uv run ruff check .`
- [ ] From `apps/browser-runner`: `uv run mypy src`
- [ ] From `apps/browser-runner`: `uv run pytest`

Record exact command, exit code, test/assertion count, commit SHA, and environment.
If a deterministic failure requires code changes, follow the authoritative
`needs-fix` re-entry rule; do not patch while the issue is in a non-implementation
state.

## Task 6: Owner-hosted configuration checkpoint

No agent receives secret values in chat. The Owner performs the following in the
provider dashboards or a private local shell:

- [ ] select/link a hosted dev Supabase project and synthetic workspace/actor;
- [ ] deploy the already-approved migrations and `dispatch-job` Edge Function;
- [ ] add GitHub Actions secrets needed by the hosted probe and cron dispatcher;
- [ ] add Supabase Edge secrets needed for the temporary synthetic dispatch
  target;
- [ ] keep `CRON_DISPATCH_ENABLED` absent/false;
- [ ] confirm the environment has no real queued/running product job before the
  temporary workflow-target test.

If any item is unavailable, Controller changes Issue #11 to `blocked-owner` or
`blocked-external` with `fix_reentries` unchanged.

## Task 7: Hosted migration, RPC, lease, and Storage acceptance

- [ ] Run the hosted probe on the exact current branch SHA.
- [ ] Verify required deployed migrations and RPC signatures; do not apply new
  SQL beyond the committed migration set.
- [ ] Verify anon/authenticated denial and service-role success.
- [ ] Exercise claim contention, wrong-runner heartbeat/finish denial, lease
  extension, expired recovery, and the three-attempt terminal bound.
- [ ] Run state persist, then state reuse/reset in a separate job.
- [ ] Verify private bucket access, AES-GCM integrity, active-version uniqueness,
  revocation, object deletion, and repeated reset behavior.
- [ ] Run exact-probe cleanup and prove no active state/object or running lease
  remains.
- [ ] Save only redacted metadata in
  `docs/evidence/phase-2/V4-P2-10-hosted-rpc-storage.md`.

## Task 8: Edge dispatch and off-PC acceptance

- [ ] Confirm product cron remains disabled.
- [ ] In an isolated verification window, point the hosted Edge Function's
  workflow target to `spike0-dispatch-probe.yml`.
- [ ] Submit one allowlisted, empty-payload synthetic dispatch and capture the
  returned opaque job ID.
- [ ] Repeat the same idempotency key and prove no duplicate job/workflow run.
- [ ] Confirm the matching GitHub run uses the expected `main` SHA and completes
  without invoking `browser-runner.yml`.
- [ ] Restore the Edge workflow target to `browser-runner.yml` and independently
  confirm the restored configuration name.
- [ ] Trigger the manual Phase 2 hosted workflow; Owner turns the PC off before
  completion and later records a short attestation with no sensitive data.
- [ ] Store redacted evidence in
  `docs/evidence/phase-2/V4-P2-10-off-pc-dispatch.md`.

Do not enable Teaching/LMS credentials or product cron in this task.

## Task 9: Reconcile reports and evidence honestly

**Files:**

- Modify: `docs/evidence/phase-2/index.json`
- Modify: `docs/evidence/phase-2/metrics.csv`
- Modify: `docs/evidence/phase-2/V4-P2-10.md`
- Modify: `docs/phase-reports/phase-2.md`
- Modify: `docs/CURRENT_STATE.md`

- [ ] Mark V4-P2-10 PASS only if Tasks 5, 7, and 8 all pass on current evidence.
- [ ] Describe the result as `hosted Phase 2 infrastructure`, not live
  Teaching/LMS or production readiness.
- [ ] Keep Phase 3, Phase 4, Phase 6, and Phase 8 reliability gates BLOCKED/not
  started as applicable.
- [ ] Keep cron state `temporarily disabled` with the exact future enable
  prerequisites.
- [ ] List any residual synthetic probe rows/objects as a blocker rather than
  hiding cleanup failure.

## Task 10: Review and final verification

- [ ] Re-run every Task 5 command on the final PR head.
- [ ] Confirm `git diff --name-only` and `git status --short` contain no
  out-of-scope file.
- [ ] Confirm no schema migration, RLS change, live selector, site adapter,
  credential, or Phase 3/4/6 behavior was introduced.
- [ ] Request fresh Terra xHigh two-pass review on the exact PR head with Issue
  #11, this design/plan, evidence indexes, diff, and current-head verification.
- [ ] Resolve all material review threads. Any new commit invalidates prior
  current-head review evidence.
- [ ] Controller may move to `ready-for-verify` only after Terra returns
  `RECOMMEND_PASS`, P0=0, P1=0, and all material findings are resolved.
- [ ] Controller independently checks CI, issue state/label, evidence, branch
  protection, and unresolved conversations before prompting Owner to merge.
- [ ] Owner performs the final merge manually. No agent merges this PR.

## Rollback and cleanup

- Product cron stays disabled by default, so rollback does not require a live
  dispatch.
- Revert the implementation commit(s) through a normal PR if the new manual
  workflow or client path is unsafe; do not reset `main`.
- Hosted probe cleanup targets only exact synthetic UUIDs created by the run.
- Restore `GITHUB_WORKFLOW_ID=browser-runner.yml` after the isolated dispatch
  proof even if the probe fails.
- Rotate only a secret suspected of exposure; never paste its old/new value into
  the issue or evidence.

## Required implementation report

Return:

- issue state/label/control snapshot;
- branch, PR number, and exact head SHA;
- changed files and explicit non-scope;
- RED evidence, GREEN evidence, and final deterministic gates;
- hosted Supabase project identifier in redacted form only;
- GitHub run URLs, safe statuses, and Owner PC-off attestation link;
- cleanup proof and remaining blockers;
- Terra verdict tied to exact head SHA;
- Owner action required next, if any;
- no claim of `VERIFIED` or merge completion.
