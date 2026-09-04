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

However the workflow is **not yet fully controlled for merge/unattended development** because the solo-owner trusted review gate setup is completing under Scope Revision 3:

- active ruleset `protect-main` currently has `Required approvals = 0`, requires `verify` and Actions `review-gate`, strict up-to-date policy, conversation resolution already enabled, and no bypass;
- the review authority is being transitioned from PR-controlled GitHub Actions code to a dedicated GitHub App check named `terra-review-gate` (`apps/review-gate-worker/`);
- `.github/workflows/review-gate.yml` is retained only as a bootstrap/self-test artifact and is not final merge authority;
- after Terra reviews and approves the implementation, Owner will create/install the dedicated GitHub App, deploy the reviewed worker, and update `protect-main` required status checks to replace Actions `review-gate` with `terra-review-gate` (expected source: dedicated GitHub App);
- any new commit pushed to the PR automatically changes `head_sha`, invalidating prior attestations.

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

Owner -> Sol High plan/spec -> GitHub issue control state -> controller transition -> Gemini 3.8 Flash implementation/test/fix -> deterministic CI -> Terra xHigh fresh adversarial review -> controller transition if needed -> Gemini fix -> final deterministic verification -> Terra attestation + review-gate pass / thread resolution -> merge.

Superpowers remains the shared methodology.

`MAX_FIX_LOOPS = 2` means exactly two fix implementation re-entries are permitted for one unchanged `scope_revision`; the third attempted `needs-fix -> implementing` transition is blocked. The authoritative count lives in the linked GitHub issue Agent Control Block. Workers may not reset it; a reset requires a new `scope_revision` plus Owner-linked approval.

No model may declare final `VERIFIED`.

## Current blockers / owner decisions

Workflow migration status:

- Scope Revision 3 fix re-entry #1 implemented: dedicated GitHub App review gate worker under `apps/review-gate-worker/` (pure validator, non-PR-controlled trusted configuration, strict Owner provenance checks requiring `author_association: OWNER`, strict `owner_scope_reset` URL checks, exhaustive comment pagination with fail-closed safety cap, `issues` event webhook handler to recompute when control issue changes, canonical Terra carrier only with duplicate/fenced block rejection and strict key validation, same-head check run dedup/update via PATCH, HMAC verification, strict calendar UTC date validation, AGENT_CONTROL_BLOCK_V1 and OWNER_SCOPE_RESET_V1 validation, GitHub Checks API adapter);
- Issue #7 at `state: implementing`, `scope_revision: 3`, `fix_reentries: 1`, linked to Owner approval record #5534707230;
- `.github/workflows/review-gate.yml` retained as bootstrap/self-test only;
- Future Owner action items after Terra review approval: create/install the dedicated GitHub App, deploy the reviewed worker, and update `protect-main` ruleset to replace Actions `review-gate` with `terra-review-gate` (expected source: dedicated GitHub App). Note: `protect-main` already has conversation resolution enabled, `Required approvals = 0`, `verify`, and strict up-to-date.

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

1. Complete Scope Revision 3 implementation and verify all deterministic gates pass.
2. Push commit to PR #6 (`chore/agent-workflow-migration`).
3. Controller moves Issue #7 to `ready-for-review`.
4. Terra xHigh performs fresh-context review of the exact current PR head diff.
5. If Terra returns `NEEDS_FIX`, fix loop routes through controller (at most 2 fix re-entries).
6. Upon Terra `RECOMMEND_PASS`, Owner installs the dedicated GitHub App and deploys the reviewed worker.
7. Worker evaluates PR #6 and emits `terra-review-gate` on the current PR head.
8. Owner updates `protect-main` ruleset to replace Actions `review-gate` with `terra-review-gate` (from the GitHub App source).
9. Controller posts the authorized Owner-carried Terra attestation for the current head; `terra-review-gate` passes.
10. Merge PR #6 when both checks pass and required conversations are resolved.
11. Run manual pilot on one small task before unattended automation.

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
