# Current Project State

Updated: 2026-10-02 (Asia/Saigon). Verified product baseline on GitHub `main`:
`f02c4ad7135aeff23479e4e66fe60285d1d1b4d4`, merged through
[PR #31](https://github.com/Banhtalon/mindx-review-bot/pull/31).
Workflow authority is `.ai-workflow/V10_CANONICAL_SPEC.md`.

## Current completed scope

- PR #31 is merged. Reviewed candidate `505aad994b222edff3129f8579380cbc2462e1fb`
  and main have identical product tree `bbde830bcfa62a6c664fc0b764ae4921367fe7b2`.
- [Main verification](https://github.com/Banhtalon/mindx-review-bot/actions/runs/36980402733)
  completed successfully at the exact merged baseline. The completed implementation
  packet records 352 Python tests and independent PASS; those are previous checks,
  not a new test run during this documentation audit.
- [Teaching cloud pilot](https://github.com/Banhtalon/mindx-review-bot/actions/runs/36968042010)
  succeeded at candidate `505aad9`: VT-CSI02, session 6, 2026-09-27, 08:00–10:00.
  LMS steps were skipped. A fresh metadata-only SELECT confirms job/run succeeded,
  attempts 3/3, records_read 1, no error, and the expected GitHub runner.
- Completed fixes filter unrelated Teaching rows before date/time validation,
  wait for page readiness, and allow exact inspected test/dependency literals
  through the source review check while retaining credential safeguards.
- [Encrypted-state bootstrap](https://github.com/Banhtalon/mindx-review-bot/actions/runs/36967719095)
  succeeded. The temporary transport-secret name is absent from the fresh
  repository Actions secret inventory; no credential values were accessed.
- Owner acceptance and merge approval belong to the completed pilot. Its job
  `ddccd0a9-7f17-4ebd-a82d-a4cce27b796e` is complete at 3/3 attempts.
  Do not rerun/reset/replace it to extend that authorization.

`records_read=1` means one validated session was read. The live adapter returns
a count and the CLI stores run metadata; this does not prove durable Teaching
session/catalog reconciliation.

## Current approved work and next sequence

Owner requested necessary next work and explicitly selected Luna 6 max as
subagent. Current v10 packet: `TASK-STATE-HOSTED-AUDIT`, documentation reconciliation
and hosted metadata audit. No product code, new live pilot, migration, deployment,
scheduler activation, push or merge is approved by this packet.

1. Finish independent review of this documentation candidate; keep product main
   unchanged until a separate Owner merge decision.
2. Prepare trusted target configuration for manual hosted dispatch using synthetic
   data and a separate v10 contract. Current cron sends an empty payload; the live
   adapter needs a page and the dispatch guard rejects URL-bearing payloads.
   Preserve the guard and explicit class/session selection. Adding keys alone is
   insufficient; do not guess the target or reuse the exhausted job.
3. After a reviewed concrete implementation exists, obtain Owner's exact target
   and authorization for configuration/deployment and one bounded PC-off pilot.
   Lead performs technical checks; Owner supplies account-only actions and acceptance.
4. Prepare a separately authorized LMS read only after login and target exist.
5. Consider automatic scheduling only after hosted/live acceptance and a separate
   Owner decision; defer later product phases until prerequisites pass.

## Current product evidence boundary

| Area | Current evidence | Remaining gap |
| --- | --- | --- |
| Phase 1 | Prior local tests; five hosted infrastructure tables have row-level restrictions enabled | Hosted user/workspace acceptance and full role behavior |
| Phase 2 | Hosted Teaching run, persisted run metadata, required routines with restricted call permissions, private state bucket | Long-run heartbeat, contention/recovery, hosted reset/reuse lifecycle, end-to-end dispatch with PC off |
| Phase 3 | One exact Teaching class/session succeeds | Other targets, cold/warm metrics, durable reconciliation |
| Phase 4 | Prior local/synthetic contracts | Live LMS read, login/reuse, stable mapping, persistence and timing; zero active LMS states in pilot workspace |
| Phase 5–5C | Prior local/synthetic UI, draft recovery/export | Hosted drafts, live extraction/reconciliation and production review generation |

Infrastructure presence is not hosted functional acceptance. The fresh observations
and limits are in [the hosted readiness report](phase-reports/2026-10-02-hosted-readiness-audit.md).
Older phase reports/indexes remain historical evidence; blocked rows are not
automatically promoted to PASS.

The cron workflow has only `workflow_dispatch`, no schedule. Repository variable
`CRON_DISPATCH_ENABLED=false` is present but is not referenced by current source.
The successful pilot directly invoked `browser-runner`, not the Edge Function →
GitHub chain; the Owner's PC-off condition was not demonstrated.
`dispatch-job` is deployed, but deployed-source parity and invocation remain
unverified. Repository secret inventory lacks `CRON_DISPATCH_SECRET` and
`CRON_WORKSPACE_ID` used by the workflow; other account stores are not asserted.

The checked-in profile remains `ASSISTED`, `bridge_installed=false`, with unverified
bindings. The accepted pilot's separate local configuration does not activate this
profile or authorize future autonomous work. Retain one writer, frozen v10 contracts,
bounded repairs and genuine independent review. Historical v9 waiting states do not
apply to the completed pilot or this new task. This audit did not refresh rulesets.

Teaching/LMS remain read-only: no Save/Submit/comments, automatic Zalo send,
CAPTCHA/OTP bypass, guessed identity or row-order mapping. Keep student data,
browser state and credentials out of models/logs/commits. No new hosted writes.

Recovery: original handoffs/frozen pilot packets are untouched. Latest completed
pilot handoff is `.workflow-local/teaching-filter-completion/HANDOFF_2026-10-02_CONTINUED.md`.
The ignored root Owner status has a byte-preserving backup before refresh. Tracked
documentation is on a separate branch; main remains the accepted product baseline.

<details>
<summary>Historical snapshot below — superseded status and instructions</summary>

The following snapshot is retained for context only. Its baseline, waiting states,
v9 next-task instructions and ruleset assertions are historical, not current routing
or authorization. Use the current sections above and the canonical v10 contract.

Last workflow baseline on `main`: `255ccf9635aecc50474a0a88049355ef4c3638fc`. Issue #12 revision 1 exhausted attempt 4 with Qualified Review NEEDS_FIX. Owner authorized revision 2 to fix those findings; it starts from `519d4a1ae881c5a8a2960aa77ab2c01b6b54b57b` in a new worktree. The historical v9 task is not active on main; adopted tasks follow v10.

This file is a routing/status summary for agents. It does not replace the V4 master specification. Live GitHub issue/ruleset/CI state is authoritative for rapidly changing workflow-control fields.

## Current approved work

No product Phase 6 task is approved. Issue #12 changes workflow controls only and excludes product code, database, secrets, deployment, live write, automatic routing, and merge.

PR #6/Issue #7 and PR #9/Issue #8 remain historical workflow evidence. The current v10 rules supersede their actor/state/retry policy on this branch.

The next product task needs its own v10 task packet, frozen manifest, and explicit Owner scope approval.

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
- The local pilot branch now has an allowlisted read-only Teaching/LMS adapter, encrypted active browser-state loading, explicit login-path guards, and fail-closed missing-state handling. These are local contract changes only until an Owner-controlled account pilot verifies the real selectors and encrypted state activation.

### Pre-existing product cron scheduler

`.github/workflows/cron-dispatch.yml` is retained as a manual read-only dispatch entry point (`sync_teaching` / `read_lms_pending`). Its automatic schedule is disabled until hosted persistence and the live read-only pilot pass Owner acceptance. It is **not** Antigravity/Gemini development-agent automation.

Observed state:

- the last historical scheduled run on 2026-09-03 completed with `failure`;
- manual dispatch still uses configured secrets to dispatch read-only product jobs;
- Phase 2 hosted/off-PC closure remains BLOCKED;
- this migration does not claim the dispatcher is pilot-approved or evidence that unattended product jobs are safe.

Re-enabling the schedule is a separate product/ops decision after Phase 2 hosted verification. Do not convert historical cron failures into PASS by inference.

### Phase 3 — Teaching reader / reconciliation

- Synthetic parser/reconciliation contract: PASS.
- Live Teaching selectors/login/custom actions, owner-controlled live sample, cold/warm metrics and production Supabase reconciliation: BLOCKED.
- The adapter implementation is present, but the real site HTML/selector contract and a first owner-controlled login have not been verified. Do not set `MINDX_SITE_ADAPTER` for production jobs yet.

### Phase 4 — LMS reader / identity / manual mapping

- Synthetic context/manual-mapping contracts: PASS for delivered slices.
- Live LMS selectors, browser-state reuse, live smoke/timing and production persistence: BLOCKED.
- Active encrypted state is loaded only through the service-role runner client; no state means the run stops before browser startup. Initial login/state activation remains an Owner account action.
- Mapping must remain explicit/stable-ID based; row order is never identity.

### Phase 5 / 5A / 5B / 5C

- Delivered UI/curriculum/review-input/autosave slices are synthetic/local only.
- Phase 5C now persists the synthetic review draft in versioned browser storage and exports CSV/Markdown. Hosted durable persistence, live Teaching/LMS extraction, production reconciliation, review generation, Gemini production prompts, approval/export/delivery remain outside that local PASS. When hosted auth is configured, the UI stays in `WAITING_CAPABILITY` instead of exposing the synthetic fixture.

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

## Engineering workflow (v10)

Target pipeline:

Owner intent -> Controller task plus separate risk/complexity -> frozen manifest -> manually assigned clean attempt -> diff tripwire -> redacted gates -> exact-head Qualified Review when required -> Owner acceptance when applicable -> Controller readiness -> Owner manual merge.

Superpowers may remain a methodology; v10 is the workflow authority for adopted tasks.

The v10 bridge keeps one writer, bounded repairs, an independent review, and an explicit Owner merge decision. Missing account capability, quota, or evidence leaves the task waiting instead of declaring success.

No model opinion can declare deterministic PASS or final DONE.

## Current blockers / owner decisions

Workflow status:

- Historical Revision-4 and Issue #12 records remain audit evidence; they are not an activation receipt for v10.
- The current product changes must pass the v10 gates and Owner acceptance before manual merge.
- Automatic model routing is deliberately deferred to a separately approved future task.

Product blockers / prerequisites:

- Phase 1 hosted Auth/workspace closure remains BLOCKED.
- Phase 2 hosted/off-PC closure remains BLOCKED (deployed migration/RPC, hosted Storage, cloud dispatch without PC).
- Phase 3 live Teaching reader remains BLOCKED (live selectors, session handling, production reconciliation).
- Phase 4 live LMS reader remains BLOCKED (live selectors, browser-state reuse, stable ID mapping).
- Phase 5C durable persistence, reload recovery, and review generation remain unverified against live systems.

Separate product/ops decision:

- decide whether and when to re-enable the currently disabled `cron-dispatch` schedule after hosted acceptance.

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

</details>
