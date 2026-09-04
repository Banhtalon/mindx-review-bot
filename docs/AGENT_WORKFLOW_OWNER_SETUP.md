# Agent Workflow — Owner Setup Checklist

This checklist covers repository settings that are outside committed workflow artifacts.

Do not enable new unattended development-agent work until these controls and the manual pilot are complete.

## 1. Main branch protection — migration merge gate

Confirmed live on 2026-09-03:

- ruleset `protect-main` is **Active** on the default branch;
- pull request is required before merge;
- required GitHub Actions check is `verify`;
- strict branch-up-to-date policy is enabled;
- bypass list is empty and current user cannot bypass;
- deletion protection is enabled;
- non-fast-forward/force-push protection is enabled.

Solo-owner review gate configuration (Scope Revision 4 — manual trusted merge gate):

Scope Revision 4 replaces external infrastructure (Cloudflare Worker, Durable Object, dedicated GitHub App, RS256 private keys, webhook secrets) with a GitHub-native manual trusted merge gate:

- keep **Required approvals** at `0` (solo-owner repository: requiring human approvals blocks the solo owner from merging);
- require the repository deterministic `verify` CI check to pass on the current PR head;
- require fresh Terra xHigh adversarial review on the exact current PR head SHA (`RECOMMEND_PASS`, P0=0, P1=0, material findings resolved);
- keep **Require conversation resolution before merging** active (already enabled on live protect-main ruleset);
- any new commit changes `head_sha`, automatically invalidating any prior review;

Ruleset cutover and merge sequence:
- **STEP A — BEFORE OWNER CUTOVER**: Implementation complete, current-head `verify` PASS, fresh Terra exact-head review acceptable (`RECOMMEND_PASS`, P0=0, P1=0, material findings resolved), Controller confirms code/review evidence is ready for cutover. PR is NOT yet merge-eligible because `protect-main` still requires obsolete `review-gate`.
- **STEP B — OWNER CUTOVER**: Owner edits `protect-main` to remove required status check `review-gate`, keeping `verify`, strict up-to-date, conversation resolution, `Required approvals = 0`, and no-bypass protections.
- **STEP C — CONTROLLER RECHECK**: Controller re-fetches live ruleset and verifies required checks include `verify` and not `review-gate`, with all protections intact. Only AFTER this post-change recheck plus all other gates can Controller declare PR `merge-eligible`.
- **STEP D — OWNER MERGE**: Owner performs final Merge action on PR #6 when explicitly prompted.

At the current implementation stage, expected Owner action is **NONE**.

## 2. Workflow state labels — complete

Confirmed created:

- `needs-plan`
- `ready-for-implementation`
- `implementing`
- `ready-for-review`
- `needs-fix`
- `ready-for-verify`
- `done`
- `blocked-owner`
- `blocked-external`

Use exactly one primary workflow-state label on the authoritative task issue. PR state labels should mirror the task when used for routing.

A scheduled/background controller must fail closed if zero or multiple primary state labels exist, or if the label conflicts with the linked issue Agent Control Block.

## 3. Authoritative Agent Control Block

Every agent-driven task must have exactly one linked standalone GitHub issue containing:

```text
state: <canonical state>
scope_revision: <positive integer>
fix_reentries: <0..2>
owner_scope_reset: <none | Owner approval link>
```

PR #6 migration control issue: **#7**.

Rules:

- issue state is authoritative; PR body is only a snapshot/reference;
- worker may read but must not have unattended permission to edit/reset task state, labels, or counter;
- implementation begins only after a controller has moved the issue to `implementing` with matching label;
- initial transition: `ready-for-implementation / 0 -> implementing / 0`;
- for a fix re-entry, if current `fix_reentries < 2`, controller atomically changes `needs-fix -> implementing` and increments exactly once;
- `needs-fix / 0 -> implementing / 1` is permitted fix re-entry #1;
- `needs-fix / 1 -> implementing / 2` is permitted fix re-entry #2;
- if another re-entry is requested while task is `needs-fix` and current `fix_reentries >= 2`, do not increment or run code; route to `blocked-owner`;
- a counter reset requires a new `scope_revision` and an Owner-linked scope-reset approval record.

`MAX_FIX_LOOPS = 2` therefore means exactly two fix implementation re-entries are allowed; the third is blocked.

## 4. Permissions

Gemini/Antigravity worker permissions should allow normal scoped development commands but must not grant unattended access to secrets, issue-state administration, branch-protection administration, or destructive/live operations.

Safe routine examples include:

- read/write files in the task branch/worktree;
- run tests, lint, typecheck, build;
- Git status/diff/add/commit/push on the task branch;
- read linked issue/PR state.

Keep explicit approval for:

- editing authoritative issue control state/labels;
- destructive filesystem/database commands;
- production migration/deploy;
- secret access;
- enabling LMS/live-write behavior;
- actions requiring credential/OTP/CAPTCHA handling.

## 5. Pre-existing product cron decision

`.github/workflows/cron-dispatch.yml` predates this migration. It is a read-only product-job scheduler, not new development-agent automation.

Observed on 2026-09-03:

- recent scheduled execution failed;
- Phase 2 hosted/off-PC closure remains BLOCKED.

Owner must explicitly choose one of:

- keep it enabled while its failure remains tracked;
- disable the schedule temporarily and retain manual dispatch;
- repair it under a separately approved product task.

Whichever choice is made, record it in `docs/CURRENT_STATE.md`. The existence of this cron does not satisfy the development-agent manual pilot gate and is not permission for unattended coding.

## 6. Manual pilot gate

Before Scheduled Tasks/background **development-agent** handoff:

1. choose exactly one small/medium real task;
2. create/link its standalone Agent Control Block issue;
3. Sol writes/approves plan and acceptance criteria;
4. controller moves the task to valid `implementing` state;
5. Gemini 3.8 Flash implements using repository skills;
6. deterministic CI passes;
7. Terra reviews from fresh context;
8. controller routes accepted findings through authoritative `needs-fix` and atomic re-entry transition if the counter permits;
9. Gemini fixes only from valid `implementing` state;
10. final deterministic CI `verify` passes;
11. fresh Terra xHigh adversarial review recommends pass (P0=0, P1=0, material findings resolved) and material review threads are resolved (STEP A);
12. Owner performs ruleset cutover to remove old `review-gate` (STEP B) when prompted by Controller;
13. Controller re-fetches live ruleset, confirms all protections, and declares PR `merge-eligible` (STEP C);
14. Owner performs manual Merge on PR (STEP D);
15. Owner reviews pilot outcome.

Pilot success criteria:

- no scope creep;
- no safety-rule bypass;
- GitHub handoff is understandable without chat-copying;
- Terra review is independent/useful;
- fix loop permits exactly two re-entries and blocks the third;
- current-head CI evidence is sufficient;
- token/time cost is acceptable.

## 7. Scheduled development automation gate

Only after the pilot succeeds should Owner configure Antigravity Scheduled Tasks to pick up unambiguous `ready-for-implementation` / `needs-fix` work.

A scheduled controller may select the task and perform the valid control transition. The Gemini implementation worker itself must start only after the issue is already `implementing` with a matching label.

Scheduled development workers/controllers must stop and make no code change on:

- `blocked-owner`;
- `blocked-external`;
- ambiguous/multiple eligible tasks unless a deterministic selection rule exists;
- missing linked issue;
- missing/malformed Agent Control Block;
- workflow label/state mismatch;
- a third fix re-entry attempt when current `fix_reentries >= 2`;
- scope-reset counter reset without Owner-linked approval;
- missing linked spec/plan;
- failed required safety gate.

Do not configure a scheduled worker to merge directly to `main`.
