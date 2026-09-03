# Current Project State

Last workflow baseline: `main` after CLI timeout hardening merge `1c13cb4f3bda8ec8d31da1ede25f2f2a0f1646c9`.

This file is a routing/status summary for agents. It does not replace the V4 master specification.

## Current approved work

`Agent Workflow Migration` only.

No product feature or Phase 6 implementation is currently approved by this file.

## Baseline health

- Latest merged CLI timeout hardening has a successful GitHub Actions CI run.
- Existing repository verification includes web lint/typecheck/tests/build, no-secret and no-live-write guards, local Supabase/RLS checks, and Python runner Ruff/Mypy/Pytest.
- Migration PR #6 current-head CI is GREEN as of the first migration review round.
- Migration work must not weaken any existing gate.

## Workflow-control readiness

The development-agent workflow is **not yet controlled/ready for unattended execution** because repository-level prerequisites remain incomplete:

- `main` is currently unprotected (`protected: false` observed on 2026-09-03);
- required current-head CI is therefore not yet enforced by branch protection/ruleset;
- canonical workflow-state labels are not yet confirmed/created;
- these settings require Owner repository configuration before the workflow may be treated as controlled.

Do not enable new unattended development agents while any item above remains open.

## Product state summary

The repository contains implementation/report slices from Spike 0 through Phase 5C. Many slices are intentionally synthetic/local and must not be treated as live production readiness.

### Phase 1 — Auth / RLS / CI

- Local/synthetic implementation: PASS.
- Hosted closure: BLOCKED.
- Hosted Auth user/workspace membership and owner-controlled smoke remain external/owner prerequisites.

### Phase 2 — runner / lease / heartbeat / retry / scheduled dispatch

- Local/synthetic implementation: PASS.
- Hosted/off-PC closure: BLOCKED.
- Deployed migration/RPC verification, hosted Storage reuse/reset, live Teaching/LMS smoke and cloud dispatch with the PC off remain open.
- CLI timeout/finalization/cleanup logic received additional hardening on 2026-09-03 and merged to `main`.

### Pre-existing product cron scheduler

`.github/workflows/cron-dispatch.yml` already schedules read-only product jobs (`sync_teaching` / `read_lms_pending`) three times daily. It predates the Agent Workflow Migration and is **not** Antigravity/Gemini development-agent automation.

Observed state:

- a scheduled `cron-dispatch` run on 2026-09-03 completed with `failure`;
- the scheduler uses configured secrets to dispatch read-only product jobs;
- Phase 2 hosted/off-PC closure remains BLOCKED;
- this migration does not claim the scheduler is healthy, pilot-approved, or evidence that unattended development agents are safe.

Owner decision remains open: keep, disable, or repair the pre-existing product schedule. Until that decision and Phase 2 hosted verification are resolved, do not convert cron failures into PASS by inference.

### Phase 3 — Teaching reader / reconciliation

- Synthetic parser/reconciliation contract: PASS.
- Live Teaching selectors/login/custom actions, owner-controlled live sample, cold/warm metrics and production Supabase reconciliation: BLOCKED.

### Phase 4 — LMS reader / identity / manual mapping

- Synthetic context/manual-mapping contracts: PASS for delivered slices.
- Live LMS selectors, browser-state reuse, live smoke/timing and production persistence: BLOCKED.
- Mapping must remain explicit/stable-ID based; row order is never identity.

### Phase 5 / 5A / 5B / 5C

- Delivered UI/curriculum/review-input/autosave slices are synthetic/local only.
- Phase 5C local in-memory autosave/conflict behavior has verification evidence, but durable persistence, reload recovery, live Teaching/LMS extraction, production reconciliation, review generation, Gemini production prompts, approval/export/delivery remain outside that synthetic PASS.

## Spike 0 evidence boundary

Current evidence index still contains BLOCKED live/operational gates including:

- Teaching cold/warm metrics;
- LMS cold/warm metrics;
- pinned dependency/minute estimate;
- guarded live runner contract;
- owner-controlled read-only browser smoke as a full closure gate.

Exact identity/no-mutation/privacy lifecycle evidence contains PASS items, but those PASS items do not implicitly close the blocked live gates.

## Safety state

Still mandatory:

- MVP 1 Teaching/LMS is read-only.
- No LMS Save/Submit/comment write path.
- No automatic Zalo send.
- No CAPTCHA/OTP/anti-bot bypass.
- No guessing class/session/student identity.
- No student mapping by row order.
- Sensitive identity/extraction stays deterministic.
- Student names/PII are not sent to Gemini or Browser Use LLM.
- No credential/cookie/token/PII in repo logs/evidence.
- No secret in frontend.

## Current engineering workflow migration

Target pipeline:

Owner -> Sol High plan/spec -> GitHub issue control state/artifact -> Gemini 3.8 Flash implementation/test/fix -> deterministic CI -> Terra xHigh fresh adversarial review -> Gemini fix if required -> final deterministic verification -> merge.

Superpowers remains the shared methodology.

`MAX_FIX_LOOPS = 2`, enforced by the authoritative per-task `fix_reentries` value in the linked GitHub issue Agent Control Block. Workers may not reset that counter; a reset requires a new `scope_revision` plus Owner-linked approval.

No model may declare final `VERIFIED`.

## Current blockers / owner decisions

Workflow migration blockers:

- protect `main` / require PR and current-head CI;
- create/confirm canonical workflow-state labels;
- decide treatment of the failing pre-existing `cron-dispatch` schedule.

Product work that requires any of the following must use `blocked-owner` or `blocked-external` rather than guessing:

- live credentials or re-authentication;
- hosted deployment/secrets;
- business rule not present in the V4 spec/ADR;
- live Teaching/LMS selector behavior that differs from synthetic fixtures;
- scope exception/waiver;
- material architecture change;
- permission to enable a live write path.

## Next sequence

1. Resolve migration review findings and rerun current-head CI.
2. Owner protects `main`, requires current-head CI, and creates/validates workflow-state labels.
3. Fresh Terra re-review confirms no P0/P1 workflow-control blocker remains.
4. Merge Agent Workflow Migration PR.
5. Select exactly one small/medium real task as a manual pilot.
6. Run manual Sol -> Gemini -> CI -> Terra -> CI handoff using a linked Agent Control Block.
7. Evaluate scope control, finding quality, time/token cost, and deterministic evidence.
8. Only then consider enabling Antigravity Scheduled Tasks/background development-agent handoff.

## Update rule

Update this file when any of these changes materially:

- baseline commit/CI health;
- branch protection/workflow-control readiness;
- phase closure state;
- approved current task;
- live/synthetic boundary;
- product cron scheduler health/Owner decision;
- owner decision/blocker;
- workflow state machine.

Do not turn a historical/synthetic PASS into a live PASS by summary wording.
