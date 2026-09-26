# MindX Review Bot

The current product slice is deliberately read-only. It proves the identity,
privacy and workflow guardrails with synthetic data, keeps review drafts in the
current browser, and exports CSV/Markdown without writing to Teaching or LMS.
Live Teaching/LMS adapters remain disabled until an Owner-controlled account
pilot supplies a configured `MINDX_SITE_ADAPTER`.
When Supabase authentication is configured, the shell intentionally shows a
blocked hosted state until the durable review store and live read-only sources
have been verified; it never presents the synthetic fixture as real data.

`MINDX_SITE_ADAPTER` is a non-secret GitHub repository variable containing an
async adapter path in the form `mindx_runner.<module>:<callable>`. The module
must be present in the runner image and must implement the approved read-only
Teaching/LMS contract before a live pilot is allowed. If it is missing or
invalid, the runner stops before claiming a job or opening a browser.

## Checks

```text
npm run lint
npm run typecheck
npm run test
npm run build
npm run verify:no-secrets
npm run verify:no-live-write

cd apps/browser-runner
uv run ruff check .
uv run mypy src
uv run pytest
```

The Supabase pgTAP suite is available with `npm run test:rls`; it requires the
local Supabase stack/Docker to be running. Spike 0 does not include Edge
Functions or browser E2E scripts yet.

## Safety boundary

- Browser Use may navigate only allowlisted non-roster pages.
- Student rows are parsed deterministically from synthetic HTML.
- Stable student IDs/discriminators are required; row order is never identity.
- Model payloads use aliases and redact known personal values.
- Log metadata uses a fail-closed allowlist.
- `MVP_LMS_WRITE_ENABLED` is rejected when enabled.
- No credentials, cookies, real student data or live screenshots belong in the repo.

## Workflow file handoffs

QQ AI Workflow v10 uses local task packets, bounded repair and independent
review so the Owner does not need to inspect code, CI, SQL or logs. Read the
`.ai-workflow` documents for the exact handoff and activation rules. Final
product acceptance and production merge remain explicit Owner actions.
