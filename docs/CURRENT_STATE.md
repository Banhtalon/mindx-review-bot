# Current Project State

Last workflow baseline: `main` after CLI timeout hardening merge `1c13cb4f3bda8ec8d31da1ede25f2f2a0f1646c9`.

This file is a routing/status summary for agents. It does not replace the V4 master specification.

## Current approved work

`Agent Workflow Migration` only.

No product feature or Phase 6 implementation is currently approved by this file.

## Baseline health

- Latest merged CLI timeout hardening has a successful GitHub Actions CI run.
- Existing repository verification includes web lint/typecheck/tests/build, no-secret and no-live-write guards, local Supabase/RLS checks, and Python runner Ruff/Mypy/Pytest.
- Migration work must not weaken any existing gate.

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

Owner -> Sol High plan/spec -> GitHub artifact/state -> Gemini 3.8 Flash implementation/test/fix -> deterministic CI -> Terra xHigh fresh adversarial review -> Gemini fix if required -> final deterministic verification -> merge.

Superpowers remains the shared methodology.

`MAX_FIX_LOOPS = 2` before owner escalation.

No model may declare final `VERIFIED`.

## Current blockers / owner decisions

Product work that requires any of the following must use `blocked-owner` or `blocked-external` rather than guessing:

- live credentials or re-authentication;
- hosted deployment/secrets;
- business rule not present in the V4 spec/ADR;
- live Teaching/LMS selector behavior that differs from synthetic fixtures;
- scope exception/waiver;
- material architecture change;
- permission to enable a live write path.

## Next sequence

1. Complete and merge Agent Workflow Migration PR with CI green and fresh review.
2. Select exactly one small/medium real task as a manual pilot.
3. Run manual Sol -> Gemini -> CI -> Terra -> CI handoff.
4. Evaluate scope control, finding quality, time/token cost, and deterministic evidence.
5. Only then consider enabling Antigravity Scheduled Tasks/background handoff.

## Update rule

Update this file when any of these changes materially:

- baseline commit/CI health;
- phase closure state;
- approved current task;
- live/synthetic boundary;
- owner decision/blocker;
- workflow state machine.

Do not turn a historical/synthetic PASS into a live PASS by summary wording.