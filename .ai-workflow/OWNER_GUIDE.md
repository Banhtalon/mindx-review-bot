# Owner guide — mindx-review-bot v10

After the one-time local activation, each prepared task is started with one command: `npm run qq:auto`.
The bridge then runs the configured Gemini worker, deterministic gates, independent reviewer and bounded repair/senior escalation until it reaches READY_FOR_OWNER, WAITING_QUOTA, WAITING_CAPABILITY or BLOCKED_TECHNICAL.

One-time local setup uses Node 20+, Git, Gemini CLI logged in with the Google account, and Codex CLI logged in with ChatGPT. Copy `.ai-workflow/BRIDGE_CONFIG.example.json` to `.workflow-local/bridge-config.json` and replace the OpenAI model placeholders with model IDs verified on this account. Gemini CLI supports the `flash` alias; the doctor packet records the actually observed model.

Use `npm run qq:doctor` before any pilot. Run `npm run qq:pilot` with a prepared frozen task, then `npm run qq:quota-drill`, then `npm run qq:activate`. Activation changes only the ignored local config to LOCAL_AUTO; it does not change GitHub code.

For normal tasks, a Lead prepares `.workflow-local/task.json` and task-scoped `write_paths` in the local bridge config. Then `npm run qq:auto` is the only execution command. Re-running the same command safely resumes a preserved checkpoint when v10 permits it.

If the task is user-visible and its frozen contract requires browser evidence, the bridge may stop at WAITING_CAPABILITY for a local browser observation before Owner acceptance. This gate is intentionally not bypassed.
