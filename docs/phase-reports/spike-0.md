# Phase Spike 0 result

- Implementation commits: `dc6dc3b`, `80ae593`, `0dbf585`, `8e7aa1b`,
  `5de0d93`, `1810450`, `3200bca`, `b600122`, `d2ec5cb`, `a048875`,
  `8f7abf3`, `ba4951f`, `974b81b`

## Scope completed

- Bootstrapped the React/Vite shell with explicit synthetic-only copy.
- Added deterministic TypeScript and Python identity/roster parsing fixtures.
- Added allowlisted-domain, kill-switch and LMS read-only guards.
- Added model redaction, fail-closed log metadata and repository safety scans.
- Added the initial Supabase workspace/job/run schema, RLS policies and pgTAP
  assertions, including duplicate idempotency-key coverage.
- Added the synthetic Edge dispatch path: owner/Cron authorization, idempotent
  enqueue and atomic dispatch claim RPCs, mocked GitHub adapters, and a
  read-only workflow contract.
- Added ADRs, evidence index, synthetic metrics and this phase report.

## Tests

Fresh verification results:

- PASS `npm run lint`
- PASS `npm run typecheck`
- PASS `npm run test` — 9 files, 39 tests
- PASS `npm run build`
- PASS `npm run verify:no-secrets`
- PASS `npm run verify:no-live-write`
- PASS `cd apps/browser-runner && uv run ruff check .`
- PASS `cd apps/browser-runner && uv run mypy src`
- PASS `cd apps/browser-runner && uv run pytest` — 19 tests
- PASS focused dispatch/adapter/workflow suite — 3 files, 16 tests
- PASS `npm run test:rls` — 2 SQL files, 38 tests, 0 failures after remapping
  local Supabase ports outside the Windows excluded range.

Synthetic web and Python suite counts are recorded in
`docs/evidence/spike-0/metrics.csv`.

## Evidence IDs

- Synthetic PASS: `V4-S0-01`, `V4-S0-02`, `V4-S0-04`, `V4-S0-07`, `V4-S0-08`,
  `V4-S0-10`, plus the mocked Edge dispatch tests in `V4-S0-03`.
- Infrastructure/live BLOCKED: `V4-S0-03` remains blocked for real cloud
  dispatch, plus `V4-S0-05`, `V4-S0-06`, `V4-S0-09`, and `V4-S0-11`.

## Security/privacy review

- No credential, cookie, token or real PII was added.
- `.env.example` contains placeholders only.
- No LMS Save/Submit action exists in the current source.
- GitHub dispatch is reachable only through the server-side Edge adapter and
  the workflow is synthetic/read-only; tests use mocked GitHub responses.
- No Browser Use live telemetry audit was attempted.
- Evidence and fixtures are synthetic/redacted.
- The earlier bootstrap range had a read-only review after the privacy,
  logging, identity, parser, scanner and RLS-attribution fixes; the dispatch
  range still requires the review recorded for this continuation.

## Deviations/ADR

- Browser Use is constrained to the hybrid navigation/parser boundary in
  `docs/adr/001-spike0-browser-use-privacy-boundary.md`.
- Real Edge/GitHub cloud dispatch, encrypted browser state and live site probes
  remain outside this synthetic implementation and are explicitly not
  represented as passed.
- Superpowers version is recorded in
  `docs/adr/000-superpowers-version.md`.

## Known limitations

- The Deno CLI was not installed, so no local Edge runtime smoke test was
  possible; the mocked Edge adapter suite remains green.
- Teaching/LMS cold/warm runs, CAPTCHA/anti-bot observation, browser telemetry
  capture and GitHub billed-minute measurement are not available without
  owner-controlled infrastructure and credentials.
- Browser-state encryption and live cloud wiring remain before any production
  job can run.

## Exit gate

BLOCKED — the synthetic foundation is testable, but Spike 0 GO criteria cannot
pass until the blocked live/cloud evidence is collected by the owner under the
read-only and privacy constraints.
