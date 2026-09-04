# Current Project State

Last workflow baseline on `main`: manual pilot merge `4edeb6e8e3f00fdf8915c00c03ff6268732bffae` (incorporating Agent Workflow Migration merge `f6dcaa9bd9e95fea69f63fdb868a385ac28aee7a` and CLI timeout hardening merge `1c13cb4f3bda8ec8d31da1ede25f2f2a0f1646c9`).

This file is a routing/status summary for agents. It does not replace the V4 master specification. Live GitHub issue/ruleset/CI state is authoritative for rapidly changing workflow-control fields.

## Current approved work

No product Phase 6 task is currently approved.

The Agent Workflow Migration (PR #6 / Issue #7) and the subsequent manual pilot (PR #9 / Issue #8) have both completed successfully and merged to `main`.

Any next product task requires a separate standalone GitHub issue with an Agent Control Block, specification/plan, and explicit Owner approval.

Recommended next engineering priority: Phase 2 hosted/off-PC closure and live-readiness prerequisites (followed by Phase 3 live Teaching reader and Phase 4 live LMS reader), rather than starting Phase 6 prematurely.

## Baseline health

- Latest merged baseline on `main` (`4edeb6e8e3f00fdf8915c00c03ff6268732bffae`) has successful GitHub Actions CI evidence.
- Existing repository verification includes web lint/typecheck/tests/build, no-secret and no-live-write guards, local Supabase/RLS checks, and Python runner Ruff/Mypy/Pytest.
- All deterministic gates remain enforced on `main`. Future work must not weaken any existing gate.

## Workflow-control readiness

Repository controls confirmed live on `main`:

- active ruleset `protect-main` targets the default branch;
- `main` is protected against direct push, deletion, and force-push (`non_fast_forward`);
- pull request is required before merge with `Required approvals = 0` (solo-owner repository constraint);
- required GitHub Actions status check is strictly `verify` (old Actions `review-gate` was removed during cutover);
- strict up-to-date branch policy is enabled (`strict_required_status_checks_policy = true`);
- conversation resolution is enabled and enforced before merge;
- bypass list is empty and current user cannot bypass;
- all nine canonical workflow-state labels exist.

Workflow control status:

- **Agent Workflow Migration**: Completed under Scope Revision 4 (PR #6 merged at `f6dcaa9bd9e95fea69f63fdb868a385ac28aee7a`, Issue #7 closed with state `done`).
- **Ruleset Cutover**: Completed. Owner removed the obsolete `review-gate` check from `protect-main`; `verify` is the sole enforced machine check.
- **Manual Pilot**: Completed successfully end-to-end (PR #9 merged at `4edeb6e8e3f00fdf8915c00c03ff6268732bffae`, Issue #8 closed with state `done`).
- **Unattended Automation Gate**: The development-agent workflow is no longer blocked specifically by the "no manual pilot yet" prerequisite. However, unattended/scheduled development automation is **not** automatically enabled and remains standing by until explicitly configured and approved by Owner for specific task scopes. Routine development continues via explicit task dispatch.

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

Owner decision remains open: keep, disable, or repair the pre-existing product schedule. This is a separate product/ops decision, not permission to bypass the manual development-agent pilot. Until Phase 2 hosted verification is resolved, do not convert cron failures into PASS by inference.

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

## Engineering workflow (post-migration)

Target pipeline:

Owner -> Sol High plan/spec -> GitHub issue control state -> controller transition -> Gemini 3.8 Flash implementation/test/fix -> deterministic CI -> Terra xHigh fresh adversarial review (when risk-routed) -> controller transition if needed -> Gemini fix -> final deterministic verification -> Controller declares merge-eligible -> Owner manual merge.

Superpowers remains the shared methodology.

`MAX_FIX_LOOPS = 2` means exactly two fix implementation re-entries are permitted for one unchanged `scope_revision`; the third attempted `needs-fix -> implementing` transition is blocked. The authoritative count lives in the linked GitHub issue Agent Control Block. Workers may not reset it; a reset requires a new `scope_revision` plus Owner-linked approval.

No model may declare final `VERIFIED`.

## Current blockers / owner decisions

Workflow status:

- Agent Workflow Migration (PR #6 / Issue #7) and Manual Pilot (PR #9 / Issue #8) are successfully completed and merged into `main`.
- The repository workflow is fully established and operational under Scope Revision 4 (manual trusted merge gate).

Product blockers / prerequisites:

- Phase 1 hosted Auth/workspace closure remains BLOCKED.
- Phase 2 hosted/off-PC closure remains BLOCKED (deployed migration/RPC, hosted Storage, cloud dispatch without PC).
- Phase 3 live Teaching reader remains BLOCKED (live selectors, session handling, production reconciliation).
- Phase 4 live LMS reader remains BLOCKED (live selectors, browser-state reuse, stable ID mapping).
- Phase 5C durable persistence, reload recovery, and review generation remain unverified against live systems.

Separate product/ops decision:

- decide whether to keep, temporarily disable, or repair the failing pre-existing `cron-dispatch` schedule.

Product work that requires any of the following must use `blocked-owner` or `blocked-external` rather than guessing:

- live credentials or re-authentication;
- hosted deployment/secrets;
- business rule not present in the V4 spec/ADR;
- live Teaching/LMS selector behavior that differs from synthetic fixtures;
- scope exception/waiver;
- material architecture change;
- permission to enable a live write path.

## Next sequence

1. Choose and approve the next product task with a dedicated standalone GitHub issue (Agent Control Block) and plan.
2. Address operational/hosted blockers in order of dependency:
   - **Phase 2 hosted/off-PC closure**: Deployed migration/RPC verification, hosted Storage, and cloud dispatch with PC off.
   - **Phase 3 Teaching live reader**: Selectors, authentication, read-only extraction, and production Supabase reconciliation.
   - **Phase 4 LMS live reader**: Selectors, session reuse, and deterministic stable-ID student mapping.
3. Proceed to later product phases (including Phase 6) only after earlier operational, hosted, and live-readiness prerequisites are satisfied.

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
