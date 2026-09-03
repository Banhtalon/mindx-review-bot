# Agent Workflow — Owner Setup Checklist

This checklist covers repository settings that are outside the committed workflow artifacts.

Do not enable unattended product work until these items and the manual pilot are complete.

## 1. Main branch protection

Configure `main` so routine agents cannot bypass verification:

- require a pull request before merge;
- require the repository CI/verify check to pass;
- require the branch to be up to date before merge when practical;
- disallow direct feature/fix pushes to `main`;
- do not allow bypass for unattended agents.

For this personal/small-team project, no enterprise approval matrix is required.

## 2. Workflow state labels

Create these labels if they do not already exist:

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

## 3. Permissions

Gemini/Antigravity worker permissions should allow normal scoped development commands but must not grant unattended access to secrets or destructive/live operations.

Safe routine examples include:

- read/write files in the task branch/worktree;
- run tests, lint, typecheck, build;
- Git status/diff/add/commit/push on the task branch.

Keep explicit approval for:

- destructive filesystem/database commands;
- production migration/deploy;
- secret access;
- enabling LMS/live-write behavior;
- actions requiring credential/OTP/CAPTCHA handling.

## 4. Manual pilot gate

Before Scheduled Tasks/background handoff:

1. choose exactly one small/medium real task;
2. Sol writes/approves plan and acceptance criteria;
3. Gemini 3.8 Flash implements using repository skills;
4. deterministic CI passes;
5. Terra reviews from fresh context;
6. Gemini fixes accepted findings if needed;
7. final deterministic CI passes;
8. Owner reviews pilot outcome.

Pilot success criteria:

- no scope creep;
- no safety-rule bypass;
- GitHub handoff is understandable without chat-copying;
- Terra review is independent/useful;
- fix loop stays bounded;
- current-diff CI evidence is sufficient;
- token/time cost is acceptable.

## 5. Scheduled automation gate

Only after the pilot succeeds should Owner configure Antigravity Scheduled Tasks to pick up unambiguous `ready-for-implementation` / `needs-fix` work.

Scheduled workers must stop on:

- `blocked-owner`;
- `blocked-external`;
- ambiguous/multiple eligible tasks unless a deterministic selection rule exists;
- missing linked spec/plan;
- failed required safety gate.

Do not configure a scheduled worker to merge directly to `main`.