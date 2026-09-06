# Current Project State

This file is the concise routing/status summary for agents. It does not replace the V4 product specification. Live GitHub issue/CI/ruleset state is authoritative for rapidly changing fields such as branch head, labels, and run status.

## Current approved work

Issue #11 — **Phase 2 hosted/off-PC closure** — is the current Owner-approved product task.

Branch:

`codex/issue-11-phase2-hosted-closure`

Current control state: `blocked-owner` at **P2-B — Hosted environment checkpoint**.

No Phase 3, Phase 4, Phase 6, or live-write work is authorized by Issue #11.

## Active development workflow

Read in this order:

1. `AGENTS.md`
2. `docs/DEVELOPMENT_SPEED_POLICY.md`
3. current task/issue + DONE condition
4. active task plan only when one is needed

Execution modes:

- **FAST** — localized low-risk work: implement → focused test → required CI.
- **STANDARD** — ordinary feature/bug: short plan if useful → focused/affected tests → CI → one review if useful.
- **STRICT** — migration/auth/session/live systems/privacy/identity/risky infrastructure: focused tests → required runtime/hosted evidence → final CI → one fresh Terra review on the stable final head.

Superpowers techniques are optional tools, not a mandatory sequence.

Do not rerun full repository suites after every edit. Do not request fresh review after every intermediate commit.

## Active Phase 2 plan

The only active Phase 2 execution plan is:

`docs/superpowers/plans/2026-09-06-phase2-fast-closure.md`

Older heavy execution checklists are retired and must not be used for routing.

Phase 2 closure packets:

- **P2-A — Freeze local implementation** — done for routing purposes unless hosted evidence proves a new in-scope code defect.
- **P2-B — Hosted environment checkpoint** — current step.
- **P2-C — Hosted RPC + Storage proof**.
- **P2-D — Edge dispatch + PC-off proof**.
- **P2-E — Evidence reconciliation**.
- **P2-F — One final CI + Terra review**.

Finish one packet before opening another. A packet failure must not become a phase-wide audit.

## Existing Phase 2 evidence

Recorded product implementation handoff before workflow cleanup:

- product implementation candidate: `3d61757cfec23772e03b23296d75b6f1fa47cebc`;
- CI on that implementation candidate: PASS;
- 130 web tests PASS;
- 255 Python tests PASS;
- 101 local pgTAP assertions PASS;
- lint/typecheck/build/security guards recorded PASS.

Still outstanding:

- hosted RPC/Storage acceptance;
- Edge synthetic dispatch/off-PC proof;
- exact hosted cleanup proof;
- final stable-head CI/review before merge.

Do not rerun the entire local inventory unless a product-code change materially invalidates it or final current-head CI is required.

## Failure routing

Classify every new failure before changing code:

- **CONFIG** — secret/variable/project/deployment mismatch: correct configuration; no code-review loop.
- **CODE-IN-SCOPE** — blocks the current DONE condition or was caused by current diff: focused regression + smallest patch + affected-subsystem check.
- **UNRELATED** — does not block current DONE/current diff: record separately and continue.
- **SAFETY** — could expose secrets/PII, affect real jobs, weaken read-only behavior, or require CAPTCHA/OTP bypass: stop and escalate/block.

## Current next sequence

1. **P2-B:** confirm isolated hosted Supabase project, synthetic actor/workspace, committed migrations, private provider configuration, no real running jobs/sessions, and cron absent/false.
2. **P2-C:** run hosted RPC/Storage probe once.
3. If P2-C exposes a real code defect, run focused + affected tests and rerun only P2-C.
4. **P2-D:** run isolated Edge synthetic dispatch + PC-off proof; keep product cron disabled.
5. **P2-E:** reconcile Phase 2 evidence/status once.
6. **P2-F:** on stable final head, use required `verify` CI, obtain one fresh Terra review, resolve only material blockers, then Owner manually merges.
7. Create separate Owner-approved Phase 3/4 tasks only after Phase 2 closure.

## Repository controls that remain active

These are safety/merge controls, not obsolete workflow ceremony:

- protected `main`;
- PR before merge;
- required `verify` status check;
- strict up-to-date branch policy;
- conversation resolution;
- no bypass actors;
- no force push/delete;
- `Required approvals = 0` for the solo-owner repository;
- Owner manual final merge.

## Product safety boundaries

Still mandatory:

- Teaching/LMS read-only for MVP 1;
- no LMS Save/Submit/comment write path;
- no automatic Zalo send;
- no CAPTCHA/OTP/anti-bot bypass;
- no guessing class/session/student identity;
- no student mapping by row order;
- sensitive identity/extraction remains deterministic;
- no student names/PII sent to Gemini or Browser Use LLM;
- no credential/cookie/token/PII in repo logs/evidence;
- no secret in frontend.

## Update rule

Update this file only when current scope, phase status, blocker, active workflow, repository controls, or hosted/live evidence boundary materially changes.

Do not turn historical/synthetic PASS into live PASS by wording, and do not add per-edit process logs here.
