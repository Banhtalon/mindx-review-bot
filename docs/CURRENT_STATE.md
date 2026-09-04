# Current Project State

Last workflow baseline on `main`: CLI timeout hardening merge `1c13cb4f3bda8ec8d31da1ede25f2f2a0f1646c9`.

This file is a routing/status summary for agents. It does not replace the V4 master specification. Live GitHub issue/ruleset/CI state is authoritative for rapidly changing workflow-control fields.

## Current approved work

`Agent Workflow Migration` only.

No product feature or Phase 6 implementation is currently approved by this file.

Migration control record: GitHub issue #7 (`[agent] Agent Workflow Migration control record`). Read its live Agent Control Block and primary workflow label before acting; do not copy a stale counter snapshot from this file.

## Baseline health

- Latest merged CLI timeout hardening on `main` has successful GitHub Actions evidence.
- Existing repository verification includes web lint/typecheck/tests/build, no-secret and no-live-write guards, local Supabase/RLS checks, and Python runner Ruff/Mypy/Pytest.
- Migration PR #6 had a full current-head `verify` PASS at `ff8283109327662dbf52d0c65d60846a291da303` before the second Terra-finding fix pass.
- Any later migration commit invalidates that cached CI evidence; the live current PR head must rerun `verify` before merge.
- Migration work must not weaken any existing gate.

## Workflow-control readiness

Repository controls now confirmed live on 2026-09-03:

- active ruleset `protect-main` targets the default branch;
- `main` is protected;
- pull request is required before merge with `Required approvals = 0`;
- required GitHub Actions check is `verify` and Actions `review-gate`;
- strict up-to-date policy is enabled;
- conversation resolution is already enabled;
- bypass list is empty and current user cannot bypass;
- deletion and non-fast-forward/force-push protection are active;
- all nine canonical workflow-state labels exist.

However the workflow is **not yet fully controlled for merge/unattended development** because the solo-owner trusted review gate setup is completing under Scope Revision 4 (GitHub-native manual trusted merge gate):

- active ruleset `protect-main` currently has `Required approvals = 0`, requires `verify` and Actions `review-gate`, strict up-to-date policy, conversation resolution enabled, and no bypass;
- under Scope Revision 4, external review-gate infrastructure (`apps/review-gate-worker/`, Cloudflare Workers, dedicated GitHub App) and PR-controlled Actions review gate (`.github/workflows/review-gate.yml`, `.github/scripts/validate_terra_attestation.*`, `test/review-gate.test.ts`) are retired and deleted;
- ruleset cutover and merge authority follow the unified 4-step sequence:
  - **STEP A — BEFORE OWNER CUTOVER**: Implementation complete, current-head `verify` PASS, fresh Terra exact-head review acceptable (`RECOMMEND_PASS`, P0=0, P1=0, material findings resolved), Controller confirms code/review evidence is ready for cutover. PR is NOT yet merge-eligible because `protect-main` still requires obsolete `review-gate`.
  - **STEP B — OWNER CUTOVER**: Owner edits `protect-main` to remove required status check `review-gate`, keeping `verify`, strict up-to-date, conversation resolution, `Required approvals = 0`, and no-bypass protections.
  - **STEP C — CONTROLLER RECHECK**: Controller re-fetches live ruleset and verifies required checks include `verify` and not `review-gate`, with all protections intact. Only AFTER this post-change recheck plus all other gates can Controller declare PR `merge-eligible`.
  - **STEP D — OWNER MERGE**: Owner performs final Merge action on PR #6 when explicitly prompted.
- any new commit pushed to the PR automatically changes `head_sha`, invalidating prior attestations/review.

New unattended development-agent automation remains blocked until the migration is merged and one manual pilot succeeds.

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

## Current engineering workflow migration

Target pipeline:

Owner -> Sol High plan/spec -> GitHub issue control state -> controller transition -> Gemini 3.8 Flash implementation/test/fix -> deterministic CI -> Terra xHigh fresh adversarial review -> controller transition if needed -> Gemini fix -> final deterministic verification -> Controller declares merge-eligible -> Owner manual merge.

Superpowers remains the shared methodology.

`MAX_FIX_LOOPS = 2` means exactly two fix implementation re-entries are permitted for one unchanged `scope_revision`; the third attempted `needs-fix -> implementing` transition is blocked. The authoritative count lives in the linked GitHub issue Agent Control Block. Workers may not reset it; a reset requires a new `scope_revision` plus Owner-linked approval.

No model may declare final `VERIFIED`.

## Current blockers / owner decisions

Workflow migration status:

- Scope Revision 4 implemented: GitHub-native manual trusted merge gate replacing external review-gate infrastructure;
- `apps/review-gate-worker/`, `.github/workflows/review-gate.yml`, `.github/scripts/validate_terra_attestation.*`, and `test/review-gate.test.ts` retired and deleted;
- Authoritative task control: live GitHub Issue #7 Agent Control Block and its single matching primary workflow-state label are authoritative for current state, scope revision, and fix re-entries (approved under scope revision 4 via Owner record #5535792176). Transient state/counter values are not copied here to prevent stale snapshots;
- No external Cloudflare, Durable Object, or GitHub App deployment required;
- Expected Owner action at this stage: NONE (Owner ruleset cutover of `protect-main` occurs only in STEP B after Terra approval and verify CI pass).

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

1. Complete Scope Revision 4 fix implementation and verify all deterministic gates pass.
2. Push commit to PR #6 (`chore/agent-workflow-migration`).
3. Controller moves Issue #7 to `ready-for-review`.
4. Terra xHigh performs fresh-context review of the exact current PR head diff.
5. If Terra returns `NEEDS_FIX`, fix loop routes through controller (at most 2 fix re-entries permitted).
6. Execute unified ruleset cutover and merge sequence:
   - **STEP A — BEFORE OWNER CUTOVER**: Implementation complete, current-head `verify` PASS, fresh Terra exact-head review acceptable (`RECOMMEND_PASS`, P0=0, P1=0, material findings resolved), Controller confirms code/review evidence is ready for ruleset cutover. PR is NOT yet merge-eligible because `protect-main` still requires obsolete `review-gate`.
   - **STEP B — OWNER CUTOVER**: Owner performs exactly one manual repository-settings action: edit `protect-main`, remove required status check `review-gate`, keep required `verify`, keep strict up-to-date, keep conversation resolution, keep `Required approvals = 0`, keep no bypass / force-push protections.
   - **STEP C — CONTROLLER RECHECK**: Controller re-fetches live ruleset and verifies: required checks exactly include `verify`, old `review-gate` no longer required, strict up-to-date remains true, conversation resolution remains true, `Required approvals = 0`, bypass remains empty, force-push/deletion protections remain active. Only AFTER this post-change recheck plus all other gates can Controller declare PR `merge-eligible`.
   - **STEP D — OWNER MERGE**: Owner performs final Merge action on PR #6 when explicitly prompted.
7. Run manual pilot on one small task before unattended automation.

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
