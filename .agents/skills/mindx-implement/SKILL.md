---
name: mindx-implement
description: Implements scoped MindX Review Bot tasks using FAST/STANDARD/STRICT routing, focused tests, and safety guards.
---

# MindX Implement

## Read first

1. `AGENTS.md`
2. `docs/CURRENT_STATE.md`
3. `docs/DEVELOPMENT_SPEED_POLICY.md`
4. current task scope and DONE condition

## Route by risk

Use the lightest workflow that is sufficient for the exact change:

- **FAST** — low-risk/localized bug, UI/CSS/text, parser/validation, mechanical refactor;
- **STANDARD** — ordinary feature or non-trivial bug without a high-risk boundary;
- **STRICT** — migrations/RLS/schema, auth/session/browser state, live Teaching/LMS, identity/mapping, privacy/PII, live-write safeguards, risky infrastructure, or material architecture/data-integrity change.

Do not escalate a task to STRICT merely because the repository contains high-risk code elsewhere.

## Work loop

1. Change the smallest set of files needed for the current DONE condition.
2. Run the smallest focused test that reproduces or covers the behavior.
3. For bug fixes, add/strengthen a regression test when practical; TDD/RED evidence is not mandatory when it adds no value.
4. When focused behavior is green, run affected-subsystem tests once.
5. Use required current-head CI as the broad final repository gate. Do not rerun the whole repository after every edit.

Superpowers techniques such as TDD, systematic debugging, brainstorming, or worktrees are optional tools. Use them when the problem actually benefits from them; they are not a mandatory checklist.

## Failure routing

Classify a new failure before doing more work:

- **CONFIG** — provider secret/variable/project/deployment issue: correct configuration; do not start a code-review loop.
- **CODE-IN-SCOPE** — blocks the current DONE condition or was caused by the current diff: focused regression + smallest patch.
- **UNRELATED** — real issue but unrelated to the current DONE/current diff: record separately and continue the current task.
- **SAFETY** — could expose secrets/PII, affect real jobs, weaken read-only behavior, or require CAPTCHA/OTP bypass: stop and escalate/block.

Do not turn one unrelated finding into a phase-wide audit.

## Review routing

- FAST: no Terra by default.
- STANDARD: one review when useful or risk-routed.
- STRICT: collect implementation + required runtime/hosted evidence first, then request one fresh Terra review on the stable final candidate head.

Do not request a fresh review after configuration-only changes. A new final-head review is needed only after a material code commit invalidates an exact-head review gate.

## Safety

Always preserve:

- Teaching/LMS read-only MVP boundary;
- no LMS Save/Submit/comment write path;
- no automatic Zalo send;
- no CAPTCHA/OTP/anti-bot bypass;
- no student mapping by row order;
- deterministic sensitive identity/extraction;
- no credential/cookie/token/PII in repo logs or evidence;
- no secret in frontend;
- no weakening of tests/guards/RLS/validation simply to obtain PASS.

## Handoff

Keep the handoff short:

- scope + DONE condition;
- changed files/behavior;
- focused/affected test result;
- runtime/hosted result if required;
- remaining blocker, if any;
- exact candidate head when requesting final review/merge.

Do not include chain-of-thought or duplicate full-suite logs.
