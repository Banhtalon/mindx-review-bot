# Current Project State

Last merged workflow baseline on `main`:

`255ccf9635aecc50474a0a88049355ef4c3638fc`

This file is a routing/status summary for agents. It does not replace the V4 master specification. Live GitHub issue/ruleset/CI state is authoritative for rapidly changing control fields.

## Current approved work

Issue #11 — **Phase 2 hosted/off-PC closure** — is the current Owner-approved product task.

Current implementation branch:

`codex/issue-11-phase2-hosted-closure`

Current branch head after the workflow simplification docs update:

`0ea7a2c4c068f68f5788406cd86d50063894ddf9`

Important: the latest branch-head changes after `3d61757cfec23772e03b23296d75b6f1fa47cebc` are documentation/process changes. The product implementation handoff recorded before this revision had already passed deterministic local/CI evidence. Hosted acceptance remains outstanding.

Issue #11 currently remains `blocked-owner` at the hosted configuration checkpoint. The new speed policy does not silently authorize hosted execution or secret handling.

No Phase 3, Phase 4, Phase 6, or live-write task is authorized by this update.

## Active workflow policy

The repository now uses risk-routed development instead of applying the heaviest workflow to every change.

Read:

1. `AGENTS.md`;
2. `docs/DEVELOPMENT_SPEED_POLICY.md`;
3. the active task plan.

Execution modes:

- **FAST** — low-risk/localized change: focused test + required CI;
- **STANDARD** — ordinary feature/bug: short plan + focused/subsystem tests + one review if useful;
- **STRICT** — migration/auth/session/live systems/privacy/identity/high-risk infrastructure: focused tests + runtime evidence + final CI + one fresh Terra review on the stable final head.

Superpowers remains available as methodology, but its full sequence is no longer mandatory for every task.

Full repository test suites must not be rerun after every small edit. Use the test ladder in `docs/DEVELOPMENT_SPEED_POLICY.md`.

## Active Phase 2 plan

Use:

`docs/superpowers/plans/2026-09-06-phase2-fast-closure.md`

This plan supersedes the earlier execution order in `2026-09-04-phase2-hosted-off-pc-closure.md` while preserving the same product/safety scope.

Phase 2 is now closed through six packets:

- **P2-A — Freeze local implementation**
- **P2-B — Hosted environment checkpoint**
- **P2-C — Hosted RPC + Storage proof**
- **P2-D — Edge dispatch + PC-off proof**
- **P2-E — Evidence reconciliation**
- **P2-F — One final verification + Terra review**

Finish one packet before opening another. Do not turn a packet failure into a phase-wide audit.

## Phase 2 starting evidence

Recorded implementation handoff before this process revision:

- product implementation head: `3d61757cfec23772e03b23296d75b6f1fa47cebc`;
- CI on that implementation head: PASS;
- local handoff: 130 web tests PASS;
- Python runner: 255 tests PASS;
- local pgTAP: 101 assertions PASS;
- lint/typecheck/build/security guards recorded PASS;
- hosted RPC/Storage acceptance: not yet proven;
- Edge dispatch/off-PC proof: not yet proven;
- cleanup proof: not yet proven;
- final fresh Terra exact-head review: not yet completed.

Agents must not rerun the whole local inventory unless new code changes make that evidence materially stale or final current-head CI is required for merge.

## Failure routing for Phase 2

Before making a fix, classify the failure:

### CONFIG

Examples: missing secret/variable, wrong project, deployment mismatch.

Action: correct provider configuration. Do not start a code-review loop.

### CODE-IN-SCOPE

The failure blocks P2-C/P2-D DONE or was caused by the branch.

Action: add/reuse one focused regression test, patch the defect, run focused + affected subsystem tests, then rerun only the failed hosted packet.

### UNRELATED

The issue does not block the current packet and was not caused by the branch.

Action: record separately. Do not fix under Issue #11.

### SAFETY

Could expose secrets/PII, affect real product jobs, weaken read-only behavior, or require CAPTCHA/OTP bypass.

Action: stop and route `blocked-owner`/`blocked-external` as appropriate.

## Verification/test policy

### During implementation/debugging

Run the smallest test that reproduces the issue.

### Before retrying a hosted packet after a code fix

Run affected subsystem tests plus relevant lint/type/static checks.

### Stable final candidate

Use required current-head `verify` CI as the primary full-repository deterministic gate. Run additional Supabase/hosted/runtime checks only when CI does not cover the required acceptance boundary.

Do not manually duplicate identical full-suite verification solely to produce a second copy of PASS evidence.

## Review policy

Phase 2 remains high-risk, therefore Terra xHigh is still mandatory before merge.

However:

- no Terra review after each intermediate edit;
- no fresh review for configuration-only changes;
- first stabilize implementation and hosted evidence;
- request Terra once on the final candidate head;
- request another exact-head review only if a material code commit changes the reviewed head.

Optional P2/P3 style findings do not automatically block Phase 2 unless they materially affect acceptance, correctness, safety, or maintainability.

## Baseline repository controls

Still required:

- protected `main`;
- PR before merge;
- required status check `verify`;
- strict up-to-date branch policy;
- conversation resolution;
- no bypass actors;
- no force push/delete;
- `Required approvals = 0` for the solo-owner repository;
- Owner manual final merge.

The workflow simplification does not weaken these controls.

## Product state summary

### Phase 1 — Auth / RLS / CI

- local/synthetic implementation: PASS;
- hosted closure: BLOCKED.

### Phase 2 — runner / lease / heartbeat / retry / scheduled dispatch

- local/synthetic implementation: PASS;
- hosted/off-PC closure: BLOCKED at Owner/provider configuration + hosted evidence;
- product cron stays disabled by default;
- current work is infrastructure closure only, not live Teaching/LMS readiness.

### Phase 3 — Teaching reader / reconciliation

- synthetic contracts: PASS where already delivered;
- live Teaching reader: BLOCKED/not authorized under Issue #11.

### Phase 4 — LMS reader / identity / manual mapping

- synthetic contracts: PASS where already delivered;
- live LMS reader/session reuse/stable-ID mapping: BLOCKED/not authorized under Issue #11.

### Later phases

Do not start Phase 5 expansion/Phase 6 automatically. They require separate Owner-approved tasks after earlier hosted/live prerequisites.

## Safety state

Still mandatory:

- Teaching/LMS read-only for MVP 1;
- no LMS Save/Submit/comment write path;
- no automatic Zalo send;
- no CAPTCHA/OTP/anti-bot bypass;
- no guessing class/session/student identity;
- no row-order mapping;
- sensitive identity/extraction deterministic;
- no student names/PII sent to Gemini or Browser Use LLM;
- no credential/cookie/token/PII in repo logs/evidence;
- no secret in frontend.

## Next sequence

1. **P2-B:** complete the isolated hosted configuration checkpoint. Do not change product code for missing configuration.
2. **P2-C:** run hosted RPC/Storage probe once and close only its defined acceptance points.
3. If P2-C exposes a real code defect, use focused regression + affected subsystem tests; rerun only P2-C.
4. **P2-D:** perform isolated Edge synthetic dispatch + PC-off proof; keep product cron disabled.
5. **P2-E:** reconcile Phase 2 evidence/status once after hosted packets complete.
6. **P2-F:** on stable final head, run required CI once, obtain one fresh Terra xHigh review, resolve material blockers, then Controller prompts Owner for manual merge.
7. Only after Phase 2 closure create separately approved Phase 3/4 tasks.

## Update rule

Update this file only when one of these materially changes:

- approved current task/scope;
- phase closure state;
- Owner/external blocker;
- active workflow/test policy;
- main baseline/ruleset;
- hosted/live evidence boundary.

Do not update it after every minor implementation edit, and do not turn historical/synthetic PASS into live PASS by summary wording.
