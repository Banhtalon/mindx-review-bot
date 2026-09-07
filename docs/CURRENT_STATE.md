# Current Project State

Last workflow baseline on `main`: `255ccf9635aecc50474a0a88049355ef4c3638fc`. Issue #12 revision 1 exhausted attempt 4 with Qualified Review NEEDS_FIX. Owner authorized revision 2 to fix those findings; it starts from `519d4a1ae881c5a8a2960aa77ab2c01b6b54b57b` in a new worktree. v9 is not active on main until review and merge.

This file is a routing/status summary for agents. It does not replace the V4 master specification. Live GitHub issue/ruleset/CI state is authoritative for rapidly changing workflow-control fields.

## Current approved work

No product Phase 6 task is approved. Issue #12 changes workflow controls only and excludes product code, database, secrets, deployment, live write, automatic routing, and merge.

PR #6/Issue #7 and PR #9/Issue #8 remain historical workflow evidence. v9 supersedes their actor/state/retry policy on this branch.

The next product task needs its own issue, v9 record, frozen manifest, and explicit Owner scope approval.

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

- **Revision-4 baseline**: Historical workflow completed through PR #6 and PR #9.
- **v9 task**: Issue #12, scope revision 2, attempt 1 hardens external authority, candidate binding, risk, attempt reservations, glob handling and bounded redaction. Revision 1 evidence remains historical.
- **Verification**: Required `verify` CI remains unchanged; v9 adds frozen task gates and redacted evidence without weakening product checks.
- **Routing**: `MANUAL`; no scheduled development router or automatic retry is enabled.

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

## Engineering workflow (v9 candidate)

Target pipeline:

Owner intent -> Controller task plus separate risk/complexity -> frozen manifest -> manually assigned clean attempt -> diff tripwire -> redacted gates -> exact-head Qualified Review when required -> Owner acceptance when applicable -> Controller readiness -> Owner manual merge.

Superpowers may remain a methodology; v9 is the workflow authority.

v9 allows four attempts at most: two default, one senior, and one final escalation. Each starts at the same base in a new worktree. Any next code-changing failure stops for Technical Operator.

No model opinion can declare deterministic PASS or final DONE.

## Current blockers / owner decisions

Workflow status:

- Revision-4 remains active on `main` until v9 is merged.
- Issue #12 revision 2 must pass its newly frozen manifest, CI and fresh Qualified Review before readiness and Owner manual merge.
- Automatic model routing is deliberately deferred to a separately approved future task.

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

1. Complete Issue #12 gates, Qualified Review, PR CI, and manual merge without enabling routing.
2. Create the next product task with a v9 record and frozen manifest.
3. Address operational/hosted blockers in order of dependency:
   - **Phase 2 hosted/off-PC closure**: Deployed migration/RPC verification, hosted Storage, and cloud dispatch with PC off.
   - **Phase 3 Teaching live reader**: Selectors, authentication, read-only extraction, and production Supabase reconciliation.
   - **Phase 4 LMS live reader**: Selectors, session reuse, and deterministic stable-ID student mapping.
4. Proceed to later product phases only after prior hosted/live prerequisites are satisfied.

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
