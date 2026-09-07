# Current Project State

Last merged baseline on `main`: `cf07aeb680c9c3b0e06813d2e1a66ceea6f9b427` (PR #13, QQ AI Workflow v9 adoption).

## Workflow authority

QQ AI Workflow v9 is now canonical and active on `main`.

- Issue #12 / PR #13: completed and merged.
- Current authoritative product task: Issue #11 / `TASK-11` — Phase 2 hosted/off-PC closure.
- Routing remains `MANUAL`; automatic model routing is not enabled.
- Superpowers may be used as a methodology, but `.ai-workflow/V9_CANONICAL_SPEC.md` and the external Controller are the workflow authority.
- Owner does not inspect code/CI/SQL/security controls; technical actions route to the Controller, Qualified Reviewer, or Technical Operator.

A fresh staging branch for TASK-11 was created from the exact post-v9 baseline:
`codex/task-11-v9-phase2-hosted-closure`.

This branch is **not yet an implementation attempt**. Under v9, attempt 1 starts only after the external Controller pins the frozen manifest/risk state and reserves a clean attempt from the approved base.

## Current approved work

Only Phase 2 hosted/off-PC closure is approved.

In scope:

- verify hosted Supabase migration/RPC state;
- establish an isolated synthetic Auth actor/workspace;
- prove hosted lease/heartbeat/retry behavior;
- prove encrypted synthetic browser-state persist/reuse/reset/cleanup;
- prove one isolated Edge dispatch completes in GitHub cloud execution with the Owner PC able to be off;
- reconcile Phase 2 evidence and run one final current-head CI + fresh Qualified Review.

Out of scope:

- Phase 3 live Teaching reader;
- Phase 4 live LMS reader;
- Phase 5/6 expansion;
- LMS Save/Submit/comment writes;
- automatic Zalo sending;
- CAPTCHA/OTP/anti-bot bypass;
- new schema/RLS redesign;
- automatic model routing.

## Phase 2 current checkpoint

Local/synthetic implementation evidence from the earlier Phase 2 work remains historical evidence and must not be promoted to hosted PASS.

Fresh hosted recheck on 2026-09-07:

- hosted Supabase project remains isolated and empty: 0 Auth users, 0 workspaces/members, 0 jobs/runs, 0 browser-state metadata/objects;
- the four committed migration bodies are present in remote migration records;
- remote history is still recorded under deployment timestamps `20260905...`, while migration names contain the committed versions `20260810...`, `20260812...`, `20260814...`;
- no direct edit of `supabase_migrations` has been performed;
- P2-C hosted probe has not run;
- P2-D Edge/cloud PC-off proof has not run.

P2-B is therefore `WAITING_FOR_OWNER` / external provider checkpoint.

### P2-B next action

Use the supported Supabase migration-history repair workflow (not direct SQL edits) to align remote history with the four committed migration versions. Then create a synthetic Auth user via Auth Admin, create its isolated workspace membership, and configure required GitHub/Supabase values privately. Product cron must remain absent/false.

No secret, JWT, cookie, browser state, or student PII may be pasted into issues, repository evidence, or chat.

## Active sequence

`P2-B -> P2-C -> P2-D -> P2-E -> P2-F`

- P2-B — hosted environment/history/actor/config checkpoint.
- P2-C — hosted RPC + encrypted Storage proof and cleanup.
- P2-D — isolated Edge dispatch + idempotency + PC-off GitHub execution proof.
- P2-E — evidence reconciliation with LOCAL/CI/HOSTED/LIVE boundaries.
- P2-F — stable-head required `verify` CI, one fresh Terra xHigh review, Controller readiness, then Owner manual merge.

During debugging use focused/affected tests only. Do not rerun full suites or request fresh review for configuration-only changes. Final broad CI/review happens once on the stable candidate head, unless a material code fix changes that head.

## Product phase order after Phase 2

1. Phase 2 hosted/off-PC closure.
2. Phase 3 live Teaching reader, still read-only.
3. Phase 4 live LMS reader with deterministic stable-ID mapping.
4. Later review-generation/durable UI/product phases only after prior hosted/live prerequisites are proven.

Do not start Phase 6 prematurely and do not infer LIVE/PRODUCTION readiness from synthetic or hosted-only evidence.
