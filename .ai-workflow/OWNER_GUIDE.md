# Owner guide — mindx-review-bot v10

After the one-time local activation, each prepared task is started or safely resumed with one command: `npm run qq:auto`.
The bridge then runs the configured Gemini worker, deterministic gates, independent reviewer and bounded repair/senior escalation until it reaches READY_FOR_OWNER, WAITING_QUOTA, WAITING_CAPABILITY or BLOCKED_TECHNICAL.

When the candidate is technically ready, the wrapper pushes its feature branch to the guarded `Banhtalon/mindx-review-bot` GitHub target and creates or reuses a PR. It never merges; final merge stays an explicit Owner action.

One-time local setup uses Node 20+, Git, GitHub CLI, Gemini CLI logged in with the Google account, Codex CLI logged in with ChatGPT, and GitHub CLI logged in with GitHub. Run `npm run qq:setup` to create the ignored local bridge config and a stable exact-file write allowlist. Replace only the OpenAI model placeholders with model IDs verified on this account. Gemini CLI uses the `flash` alias; the doctor packet records the actually observed model.

Run `npm run qq:doctor` before any pilot. With a Lead-prepared frozen pilot task, run `npm run qq:pilot`, then `npm run qq:quota-drill`, then `npm run qq:activate`. Activation changes only the ignored local config to LOCAL_AUTO; it does not change GitHub code.

Do not change `write_paths` for each normal task: activation is bound to the exact config. The frozen `.workflow-local/task.json` provides task-specific scope while the activated allowlist is the outer write boundary. If a task needs a path outside that allowlist, stop and re-plan; widening the bound config requires a fresh pilot/quota-drill/activation cycle.

For normal tasks, a Lead prepares `.workflow-local/task.json`. Then `npm run qq:auto` is the only execution command. Re-running the same command safely resumes a preserved checkpoint when v10 permits it.

If the task is user-visible and its frozen contract requires browser evidence, the bridge may stop at WAITING_CAPABILITY for a local browser observation before Owner acceptance. This gate is intentionally not bypassed.
