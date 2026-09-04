# Phase 2 Hosted/Off-PC Closure Design

**Date:** 2026-09-04

**Issue:** [#11 — `[agent] Phase 2 hosted/off-PC closure`](https://github.com/Banhtalon/mindx-review-bot/issues/11)

**Risk:** High — hosted Supabase, service-role RPCs, browser-state encryption, GitHub Actions, and auth/session boundaries

**Scope revision:** 1

**Status:** Ready for implementation after the Controller performs the issue transition

**Baseline inspected:** `main@255ccf9635aecc50474a0a88049355ef4c3638fc`

## Decision summary

Close the Phase 2 infrastructure boundary without implementing the Phase 3
Teaching adapter, the Phase 4 LMS adapter, any Phase 5/6 feature, or any LMS or
Zalo write path.

The closure is deliberately split into three independently evidenced surfaces:

1. hosted Supabase migration/RPC and private Storage behavior;
2. GitHub-hosted execution and off-PC continuity;
3. product cron operational state.

The pre-existing product schedule will default to **temporarily disabled** until
its required configuration is present and the hosted acceptance workflow has
passed. Manual verification remains available. This is a reversible, fail-closed
operations choice; it does not authorize live Teaching/LMS navigation.

Phase 2 may report hosted infrastructure PASS only when every Phase 2 acceptance
gate below has current redacted evidence. It must continue to report the actual
Teaching/LMS product runner as BLOCKED because `mindx-runner run` has no configured
site adapter. Phase 8's one-week/ten-session reliability gate also remains open.

## Current inventory

### Implemented and locally evidenced

| Surface | Current artifact | Current status |
|---|---|---|
| Edge dispatch | `supabase/functions/dispatch-job` plus shared dispatch adapters | Local synthetic tests cover auth, enqueue, dispatch claim, GitHub rejection, and safe errors. Hosted deployment is unverified. |
| Dispatch state | `20260810000001_spike0_dispatch.sql` | Local pgTAP covers idempotency and dispatch transitions. Hosted migration/RPC signatures are unverified. |
| Runner lease | `20260814000000_phase12_lease_retry.sql` | Local pgTAP covers runner ownership, ten-minute lease, heartbeat, expiry, finish, and three-attempt bound. Hosted behavior is unverified. |
| Runner client | `apps/browser-runner/src/mindx_runner/supabase_client.py` | Claim/heartbeat/finish and private Storage HTTP contracts have unit coverage. No hosted run exists. |
| Runtime lifecycle | `apps/browser-runner/src/mindx_runner/cli.py` | Local tests cover stable runner ID, heartbeat, hard timeout, bounded finalization, and browser cleanup. |
| Browser-state crypto | `browser_state.py` and `20260812000000_live_runner.sql` | AES-GCM, tamper rejection, key versioning, private bucket, activate/reset RPCs pass locally. Hosted reuse/reset is unverified. |
| Scheduled dispatch | `.github/workflows/cron-dispatch.yml` and `scripts/cron_dispatch.mjs` | Static/local contract passes. Hosted schedule is unhealthy. |
| Cloud runner | `.github/workflows/browser-runner.yml` | Workflow contract exists, but GitHub has no recorded run for it. |

### Current hosted facts observed on 2026-09-04

- `cron-dispatch` has 42 recorded runs and all 42 concluded `failure`.
- The first run (`32499129628`) and latest inspected run (`33821214878`) both
  failed with the safe code `CRON_CONFIG_INVALID`.
- GitHub repository Actions settings contain no repository secrets and no
  environment secrets. The scheduled workflow therefore cannot satisfy its
  required `SUPABASE_URL`, `CRON_DISPATCH_SECRET`, and `CRON_WORKSPACE_ID`
  inputs.
- `browser-runner.yml` has no hosted workflow run.
- `mindx-runner run` passes `adapter=None` and exits with
  `SITE_ADAPTER_NOT_CONFIGURED` before claiming a job. This is an intentional
  fail-closed boundary, not a Phase 2 hosted PASS.
- `BrowserStateLifecycle` keeps active-version metadata in process memory. The
  Supabase client exposes hosted object operations plus activate/reset RPCs, but
  no current runtime path composes them into a two-run hosted reuse/reset flow.
- Existing Phase 2 evidence correctly marks V4-P2-10 and the hosted/off-PC
  metrics as BLOCKED.

## Blocker classification

| Class | Blocker | Disposition |
|---|---|---|
| Code | Cron has no explicit disabled state and collapses all missing/malformed configuration into repeated failed runs. | Add a default-off gate and safe diagnostics under TDD. |
| Code | No hosted acceptance command composes the existing RPC, Storage, and crypto primitives. | Add a synthetic-only probe path; do not add a product job type or site adapter. |
| Code | Browser-state active-version metadata and object operations are not composed into a cross-process hosted reuse/reset check. | Add strictly validated client reads and a manual verification workflow. |
| Owner | Hosted Supabase deployment, synthetic workspace/actor, GitHub/Supabase secret stores, and PC-off attestation are unavailable to agents. | Perform only at the explicit Owner checkpoint; never transmit values through chat or evidence. |
| Owner | Temporarily pointing an otherwise active hosted Edge environment at a synthetic workflow could disrupt real traffic. | Use an isolated dev project/window or stop at `blocked-owner`. |
| External | Supabase project pause/outage or GitHub Actions/API queue/outage can invalidate a run. | Record `blocked-external`; retry only after external health is restored, without weakening timeouts. |
| Deferred | Teaching/LMS site adapters and credentials do not exist in the runtime path. | Leave BLOCKED for separately approved Phase 3/4 tasks. |

## Scope boundary

### In scope

- verify already-approved migrations and RPC signatures against one owner-linked
  hosted Supabase project;
- create a deterministic, manual-only Phase 2 hosted acceptance harness for
  synthetic control metadata and encrypted synthetic browser-state bytes;
- verify service-role-only claim/heartbeat/finish and active-state/reset behavior;
- prove GitHub-hosted execution continues after the Owner PC is off;
- add safe, non-secret diagnostics that distinguish disabled, missing-config,
  hosted-RPC, Storage, and GitHub-dispatch failures;
- stop the unhealthy product schedule from repeatedly dispatching until its
  configuration and prerequisites are explicitly enabled;
- update Phase 2 evidence without relabeling local/synthetic results as hosted.

### Explicitly out of scope

- live Teaching selectors, login automation, extraction, or reconciliation;
- live LMS selectors, session/student identity, roster extraction, or mapping;
- real Teaching/LMS credentials in the Phase 2 acceptance harness;
- any LMS Save/Submit/comment mutation or automatic Zalo send;
- CAPTCHA, OTP, anti-bot bypass, or challenge solving;
- schema/RLS redesign or a new product job type;
- Phase 3, Phase 4, Phase 5/5C expansion, Phase 6, or Phase 8 reliability closure;
- changing `protect-main`, weakening `verify`, or bypassing Terra review;
- copying secrets, raw encrypted state, cookies, tokens, student data, page
  content, screenshots, HAR, traces, or videos into logs/evidence.

## Architecture

### 1. Manual-only hosted acceptance workflow

Add a manually callable workflow for Phase 2 verification. It must have
`contents: read`, a bounded timeout, non-cancelling concurrency keyed by a
non-sensitive probe ID, no artifact upload, and no automatic trigger. Because
GitHub requires a manually dispatched workflow file to exist on the default
branch, the existing default-branch `spike0-dispatch-probe.yml` provides a
default-off manual bootstrap and calls the branch's reusable hosted workflow.
The existing Edge dispatch path omits that boolean input and therefore retains
its validation-only behavior.

The workflow invokes a dedicated acceptance command, not the product
`mindx-runner run` entrypoint. It operates only on an owner-created synthetic
workspace/actor and never opens Teaching or LMS.

The command returns one JSON summary containing only:

- run ID and current commit SHA;
- opaque synthetic job/probe UUIDs;
- step names and PASS/FAIL;
- job terminal status, attempt count, safe error code, and durations;
- encrypted-object byte count/hash, never object content;
- cleanup outcome.

Every unexpected response maps to an allowlisted safe error and a non-zero exit.

### 2. Hosted database/RPC probe

The probe must verify the deployed contract, not merely that HTTP returned 2xx:

- required relations/columns and exact RPC calls are available;
- anon/authenticated callers cannot invoke service-only runner RPCs;
- service-role claim succeeds once for a synthetic dispatched job;
- a second runner cannot claim, heartbeat, or finish an active lease;
- owner heartbeat extends the lease;
- finish records only bounded metrics and a safe terminal state;
- expired-lease recovery increments the attempt exactly once;
- the fourth claim is rejected after the three-attempt bound.

Use unique probe identifiers. Finish probe runs as `cancelled` or `failed` with
an explicit safe probe code; never record a synthetic probe as a successful
Teaching/LMS read. Clean up only rows created by that exact probe.

If hosted schema/RPC behavior differs from the committed migrations, stop with
`HOSTED_SCHEMA_DRIFT`. Do not generate or apply a new migration in Scope
Revision 1.

### 3. Hosted encrypted-state probe

Use deterministic synthetic JSON bytes containing no cookie, token, credential,
URL, class, session, or student field.

Pass A:

1. encrypt with AES-256-GCM and a fresh nonce;
2. upload to the private `browser-state` bucket under the existing scoped path;
3. activate its metadata through the existing service-only RPC;
4. record only version UUID, byte count, and SHA-256.

Pass B, in a separate GitHub-hosted process:

1. query the one active version for the same synthetic workspace/site;
2. download and decrypt it;
3. compare exact synthetic bytes and hash;
4. invoke reset;
5. delete the returned object path;
6. prove metadata is revoked, no active version remains, and the object returns
   not found.

This two-process sequence is the Phase 2 meaning of hosted state reuse/reset. It
does not claim a live website session or browser adapter.

The probe necessarily writes synthetic orchestration rows, encrypted synthetic
objects, and their terminal/cleanup metadata to the owner-selected hosted dev
project. Those are bounded verification records for existing Phase 2 contracts,
not live product writes. No Teaching/LMS/Zalo mutation, learner record, review,
or delivery data is written.

### 4. Off-PC proof

The Owner triggers the manual hosted acceptance sequence, records the GitHub run
URL and start time, and turns off/disconnects the local PC before the cloud steps
complete. After reconnecting from any device, the Owner records a short
attestation that the local PC was off during completion. Machine evidence must
show the GitHub-hosted runner, exact commit SHA, timestamps, and successful
hosted RPC/Storage checks.

The attestation proves infrastructure independence from the local PC. It does
not prove live Teaching/LMS accuracy and does not satisfy V4-P8 reliability
metrics.

### 5. Edge-to-GitHub dispatch proof

Use a dedicated verification window with the product cron gate disabled. Point
the hosted Edge dispatch configuration at the existing synthetic
`spike0-dispatch-probe.yml`, submit one empty-payload allowlisted job, and prove:

- Edge returns the same opaque job ID stored in Supabase;
- one matching GitHub workflow run starts on the expected `main` SHA;
- repeating the same idempotency key does not create a second job;
- the product `browser-runner.yml` is not invoked;
- the temporary workflow target is restored to `browser-runner.yml` after the
  proof and the restoration is verified without exposing the secret value.

This verifies the dispatch link without claiming a site adapter. If the hosted
project cannot be isolated safely for this temporary configuration, stop at
`blocked-owner`; do not repoint an active environment.

### 6. Cron policy

Add an explicit non-secret enable gate, default false when absent. Scheduled runs
must visibly report `disabled` and must not call the Edge Function unless all of
these are true:

- the enable variable is exactly `true`;
- required secret names are configured;
- the current Phase 2 hosted evidence is PASS;
- the configured downstream workflow is restored to `browser-runner.yml`;
- a later task has supplied the relevant live site adapter and credentials.

For Scope Revision 1 the expected final operational state is **temporarily
disabled**. Manual dispatch remains available only for the documented hosted
probe. Enabling the product schedule before Phase 3/4 adapter readiness is not
part of this issue.

## Acceptance criteria

1. Current Phase 2 inventory and the 42/42 cron failure history are recorded
   without secrets or speculative root-cause claims.
2. Missing/incorrect hosted configuration fails closed with a specific safe code;
   logs never reveal which secret value was supplied.
3. Committed migrations/RPCs are verified on hosted Supabase with service-only
   access and no schema/RLS change.
4. Hosted lease ownership, heartbeat, finish, expiry recovery, and three-attempt
   bound pass using synthetic probe rows.
5. Two separate GitHub-hosted processes prove encrypted synthetic state
   persist/reuse/reset and exact cleanup.
6. An Edge-to-GitHub synthetic dispatch proof completes once, with duplicate
   idempotency producing no duplicate job/run.
7. A current-SHA GitHub-hosted acceptance run completes while the Owner PC is off
   and has a separate Owner attestation.
8. Product cron is left fail-closed/temporarily disabled and no scheduled run can
   reach Teaching/LMS before later adapter readiness.
9. No real browser credential, cookie, token, student PII, page content, or
   external-system mutation appears in code, logs, or evidence.
10. All relevant web, Supabase, Python, security, and workflow-contract gates pass
    on the current PR head; fresh Terra review returns `RECOMMEND_PASS` with no
    P0/P1 and all material findings resolved.
11. `docs/evidence/phase-2/index.json`, metrics, Phase 2 report, and
    `docs/CURRENT_STATE.md` distinguish hosted infrastructure PASS from the still
    BLOCKED Teaching/LMS product adapters and Phase 8 reliability gate.

## Owner and external gates

Owner input is not required to start local implementation. The Controller may
move Issue #11 from `ready-for-implementation` to `implementing` with
`fix_reentries: 0`.

Before hosted execution, Owner must perform these secret/configuration actions
outside chat:

1. select or create the hosted dev Supabase project and a synthetic-only
   workspace/actor;
2. link/deploy the already-approved migrations and `dispatch-job` function;
3. add the required GitHub Actions and Supabase Edge secret names;
4. approve the temporary synthetic workflow-target verification window if the
   environment is otherwise active;
5. trigger and attest the PC-off run.

At that point the task transitions to `blocked-owner` if any required hosted
configuration or attestation is unavailable. No agent asks the Owner to paste a
secret into chat.

## Verification authority and review routing

This issue is high risk. Terra xHigh review is mandatory for the exact PR head,
with both spec-compliance and adversarial passes covering hosted auth, service
role, Storage cleanup, retries, idempotency, privacy, and no-live-write safety.

No model may declare `VERIFIED`. Deterministic evidence plus Controller checks
and Owner manual merge remain authoritative.
