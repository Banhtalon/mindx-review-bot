# QQ Workflow v10 — local bridge for mindx-review-bot

## Architecture

GitHub stores code, PRs, CI and meaningful milestones. `.workflow-local/` stores mutable task/config/run packets and is ignored by Git. Subscription CLIs run on the Owner laptop; no API-key fallback is allowed.

Normal loop: Gemini Flash worker -> deterministic gates -> fresh Codex reviewer -> bounded repair. Two initial repair rounds are allowed, then at most one senior pass. The bridge stops for Owner, quota/capability, browser evidence, or a technical blocker.

## One-time activation

1. Install Node 20+, Git, Gemini CLI and Codex CLI on Windows.
2. Sign Gemini CLI in with the Google account and Codex CLI in with ChatGPT.
3. Copy `.ai-workflow/BRIDGE_CONFIG.example.json` to `.workflow-local/bridge-config.json`; keep billing SUBSCRIPTION_ONLY and replace only the probed OpenAI model IDs plus task-scoped write paths.
4. Run `npm run qq:doctor`.
5. Run a real supervised repair pilot with `npm run qq:pilot`.
6. Run `npm run qq:quota-drill` and then `npm run qq:activate`.

## Per task

The Lead creates/finalizes `.workflow-local/task.json`, including base SHA, acceptance criteria, gates, risk/complexity and GEMINI_FIRST_V1 execution fields, and narrows `write_paths` in the local config. Start or resume with:

    npm run qq:auto

When READY_FOR_OWNER appears, test the ordinary user actions supplied by the Lead. Merge remains separate and explicit.
