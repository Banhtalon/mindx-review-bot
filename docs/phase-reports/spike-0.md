# Phase Spike 0 result

- Implementation commit: `dc6dc3b`

## Scope completed

- Bootstrapped the React/Vite shell with explicit synthetic-only copy.
- Added deterministic TypeScript and Python identity/roster parsing fixtures.
- Added allowlisted-domain, kill-switch and LMS read-only guards.
- Added model redaction, fail-closed log metadata and repository safety scans.
- Added the initial Supabase workspace/job/run schema, RLS policies and pgTAP
  assertions, including duplicate idempotency-key coverage.
- Added ADRs, evidence index, synthetic metrics and this phase report.

## Tests

Fresh verification results:

- PASS `npm run lint`
- PASS `npm run typecheck`
- PASS `npm run test` — 6 files, 17 tests
- PASS `npm run build`
- PASS `npm run verify:no-secrets`
- PASS `npm run verify:no-live-write`
- PASS `cd apps/browser-runner && uv run ruff check .`
- PASS `cd apps/browser-runner && uv run mypy src`
- PASS `cd apps/browser-runner && uv run pytest` — 12 tests
- BLOCKED `npm run test:rls` — local Postgres `127.0.0.1:54322` refused the
  connection because Docker was unavailable.

Synthetic web and Python suite counts are recorded in
`docs/evidence/spike-0/metrics.csv`.

## Evidence IDs

- Synthetic PASS: `V4-S0-07`, `V4-S0-08`, `V4-S0-10`.
- Infrastructure/live BLOCKED: `V4-S0-01` through `V4-S0-06`, `V4-S0-09`,
  `V4-S0-11`.

## Security/privacy review

- No credential, cookie, token or real PII was added.
- `.env.example` contains placeholders only.
- No LMS Save/Submit action exists in the current source.
- No Browser Use live telemetry audit was attempted.
- Evidence and fixtures are synthetic/redacted.

## Deviations/ADR

- Browser Use is constrained to the hybrid navigation/parser boundary in
  `docs/adr/001-spike0-browser-use-privacy-boundary.md`.
- Edge Functions, GitHub dispatch, encrypted browser state and live site probes
  remain outside this bootstrap and are explicitly not represented as passed.
- Superpowers version is recorded in
  `docs/adr/000-superpowers-version.md`.

## Known limitations

- Supabase pgTAP assertions have not executed in this environment because the
  local Postgres endpoint was unavailable.
- Teaching/LMS cold/warm runs, CAPTCHA/anti-bot observation, browser telemetry
  capture and GitHub billed-minute measurement are not available without
  owner-controlled infrastructure and credentials.
- Browser-state encryption and Edge dispatch must be implemented in later
  phases before any cloud job can run.

## Exit gate

BLOCKED — the synthetic foundation is testable, but Spike 0 GO criteria cannot
pass until the blocked live/cloud evidence is collected by the owner under the
read-only and privacy constraints.
