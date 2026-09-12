# QQ Workflow v10 — local bridge for mindx-review-bot

## Architecture

GitHub stores code, feature branches, PRs, CI and meaningful milestones. `.workflow-local/` stores mutable task/config/run/checkpoint packets and is ignored by Git. Subscription CLIs run on the Owner laptop; no API-key fallback is allowed.

Normal loop: Gemini Flash worker -> deterministic gates -> fresh Codex reviewer -> bounded repair. Two initial repair rounds are allowed, then at most one senior pass. The bridge stops for Owner, quota/capability, browser evidence, or a technical blocker.

When a normal run reaches `READY_FOR_OWNER` or `DONE`, the host wrapper pushes the current feature branch to the guarded `Banhtalon/mindx-review-bot` target and creates or reuses a PR. It never merges the PR.

## One-time activation

1. Install Node 20+, Git, GitHub CLI (`gh`), Gemini CLI and Codex CLI on Windows.
2. Sign Gemini CLI in with the Google account, Codex CLI in with ChatGPT, and `gh` in with the GitHub account.
3. Run `npm run qq:setup`. This creates `.workflow-local/bridge-config.json` and freezes a stable exact-file write allowlist from the currently tracked product source under `src/` and `apps/browser-runner/`, excluding tests/fixtures.
4. Replace only the OpenAI model placeholders with model IDs actually available on this account. Do not guess IDs.
5. Run `npm run qq:doctor`.
6. Have the Lead prepare a real frozen pilot task, then run `npm run qq:pilot` until the accepted pilot includes a real reviewer-to-worker repair using both subscription providers.
7. Run `npm run qq:quota-drill` and then `npm run qq:activate`.

Activation is bound to the exact bridge/config. **Do not narrow or expand `write_paths` per task after activation.** Changing the allowlist, account binding, model binding, or other bound config requires a fresh pilot/quota-drill/activation cycle. This makes one activation reusable across ordinary tasks that only touch files already in the stable allowlist.

A task that needs a new file, migration, deployment control, workflow/control file, test rewrite, or another path outside the activated allowlist must stop for Lead handling rather than silently broadening permissions.

## Per task

The Lead creates/finalizes `.workflow-local/task.json`, including base SHA, acceptance criteria, exact deterministic gates, risk/complexity and GEMINI_FIRST_V1 execution fields. The task contract is the per-task scope; the stable bridge allowlist is only the outer write boundary.

From an up-to-date clean `main`, start or resume the complete local execution loop with one command:

    npm run qq:auto

The wrapper creates a feature branch when needed, runs/resumes the v10 bridge, and when technically ready publishes the branch/PR to GitHub. Re-running the same command resumes only a safe preserved checkpoint; unknown in-flight operations remain blocked for Lead reconciliation.

When `READY_FOR_OWNER` appears, the Owner tests the ordinary user actions supplied by the Lead and decides the final merge. Merge is never automatic.
