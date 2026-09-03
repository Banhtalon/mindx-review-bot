# Agent Workflow — Owner Setup Checklist

This checklist covers repository settings that are outside committed workflow artifacts.

The workflow must **not** be treated as controlled, and PR #6 should not be merged, until Sections 1 and 2 are complete and re-reviewed.

Do not enable new unattended development-agent work until these controls and the manual pilot are complete.

## 1. Main branch protection — required before migration merge

Current observed state on 2026-09-03: `main` reports `protected: false`.

Configure `main` so routine agents cannot bypass verification:

- require a pull request before merge;
- require the repository `verify` CI check to pass on the current PR head;
- require the branch to be up to date before merge when practical;
- disallow direct feature/fix pushes to `main`;
- do not allow bypass for unattended workers;
- keep worker credentials scoped to task branches/PRs, not protection administration.

After configuration, confirm through repository branch/ruleset state that protection is actually active. Documentation alone is not sufficient proof.

For this personal/small-team project, no enterprise approval matrix is required.

## 2. Workflow state labels — required before migration merge

Create and confirm these labels:

- `needs-plan`
- `ready-for-implementation`
- `implementing`
- `ready-for-review`
- `needs-fix`
- `ready-for-verify`
- `done`
- `blocked-owner`
- `blocked-external`

Use exactly one primary workflow-state label on a task/PR whenever possible.

A scheduled/background worker must fail closed if zero or multiple primary state labels exist, or if the label conflicts with the linked issue Agent Control Block.

## 3. Authoritative Agent Control Block

Every agent-driven task must have exactly one linked GitHub issue containing:

```text
state: <canonical state>
scope_revision: <positive integer>
fix_reentries: <0..2>
owner_scope_reset: <none | Owner approval link>
```

Rules:

- issue state is authoritative; PR body is only a snapshot/reference;
- worker may read but must not have unattended permission to edit/reset task state, labels, or counter;
- controller increments `fix_reentries` before every `needs-fix` -> `implementing` re-entry;
- deterministic verification failure needing code changes also routes through `needs-fix` and consumes the next re-entry;
- `fix_reentries >= 2` routes to `blocked-owner`;
- a counter reset requires a new `scope_revision` and an Owner-linked scope-reset approval record.

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

Whichever choice is made, record it in `docs/CURRENT_STATE.md`. The existence of this cron does not satisfy the development-agent manual pilot gate.

## 6. Manual pilot gate

Before Scheduled Tasks/background **development-agent** handoff:

1. choose exactly one small/medium real task;
2. create/link its Agent Control Block;
3. Sol writes/approves plan and acceptance criteria;
4. Gemini 3.8 Flash implements using repository skills;
5. deterministic CI passes;
6. Terra reviews from fresh context;
7. controller routes accepted findings through authoritative `needs-fix`/counter state;
8. Gemini fixes if the counter allows re-entry;
9. final deterministic CI passes;
10. Owner reviews pilot outcome.

Pilot success criteria:

- no scope creep;
- no safety-rule bypass;
- GitHub handoff is understandable without chat-copying;
- Terra review is independent/useful;
- fix loop stays bounded by authoritative state;
- current-head CI evidence is sufficient;
- token/time cost is acceptable.

## 7. Scheduled development automation gate

Only after the pilot succeeds should Owner configure Antigravity Scheduled Tasks to pick up unambiguous `ready-for-implementation` / `needs-fix` work.

Scheduled development workers must stop and make no code change on:

- `blocked-owner`;
- `blocked-external`;
- ambiguous/multiple eligible tasks unless a deterministic selection rule exists;
- missing linked issue;
- missing/malformed Agent Control Block;
- workflow label/state mismatch;
- `fix_reentries >= 2` on a fix re-entry;
- scope-reset counter reset without Owner-linked approval;
- missing linked spec/plan;
- failed required safety gate.

Do not configure a scheduled worker to merge directly to `main`.
