# Evidence V4-S0-05 — Guarded live runner contract

- Date: 2026-08-12
- Branch: `codex/live-readonly-runner`
- Data class: synthetic/redacted-live-metadata only
- Requirement: owner-authorized Teaching/LMS read-only jobs have a fail-closed
  runner boundary before any live site adapter is enabled.

## Verification

- PASS: `uv run pytest` — 92 Python tests.
- PASS: `uv run ruff check .`.
- PASS: `uv run mypy src`.
- PASS: `npm run lint`.
- PASS: `npm run typecheck`.
- PASS: `npm run test` — 11 files, 46 tests.
- PASS: `npm run build`.
- PASS: `npm run verify:no-secrets`.
- PASS: `npm run verify:no-live-write`.
- PASS: `npm run test:rls` — 3 SQL files, 67 tests.
- PASS: local Browser Use Chromium startup and target-creation smoke; no live
  site, credentials or browser state were used.

## Contract results

- Configuration requires `AUTOMATION_ENABLED=true` and
  `MVP_LMS_WRITE_ENABLED=false`, an exact UUID job id, an HTTPS Supabase host,
  and a 32-byte browser-state key.
- Browser Use starts headless with exactly the two production hosts allowlisted;
  default extensions, CAPTCHA solver, keep-alive, traces, video and HAR output
  are disabled.
- CDP Fetch pauses page requests. GET/HEAD/OPTIONS reads continue; only
  explicitly allowlisted login POST paths can continue; mutation methods,
  mutation paths and mutation-like bodies fail with `BlockedByClient`.
- Runner lifecycle uses service-only claim/finish RPCs. Results contain only
  numeric `records_read` and a safe error code.
- Browser state is represented by encrypted envelopes and private-bucket
  metadata. Raw browser state is not placed in Postgres metadata or evidence.
- The GitHub workflow is manual, has `contents: read`, a 15-minute timeout,
  non-cancelling job concurrency, immutable action references and no artifact or
  browser recording upload.

## Explicit limitation

This evidence does **not** claim a live Teaching or LMS run. The CLI currently
stops with `SITE_ADAPTER_NOT_CONFIGURED` before claiming a job because verified
site selectors and deterministic Teaching/LMS adapters have not been supplied.
Local Chromium startup and target-creation smoke passed, including the guarded
target attach path, but no live site navigation or request probe was performed.
The required five cold and five warm runs per site, identity assertions,
privacy probe and billed-minute measurement remain BLOCKED. No real credential,
cookie, token, student name or page body was used.

## Privacy review

- [x] No credentials
- [x] No cookies/tokens
- [x] No student names/notes
- [x] No screenshots, traces, video or HAR
- [x] No LMS Save/Submit/update-comment action
- [x] No live site result represented as passed
