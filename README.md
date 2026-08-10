# MindX Review Bot — Spike 0

Spike 0 is a synthetic-only foundation for the V4 MVP. It proves the local
identity, privacy and read-only guardrails without connecting to Teaching/LMS
or writing to either site.

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
