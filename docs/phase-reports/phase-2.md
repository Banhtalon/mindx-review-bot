# Phase 2 report — Runner lease, heartbeat, retry and scheduled dispatch

- Commit: `a510555`
- Branch: `codex/phase1-2-closure`
- Result: local/synthetic implementation PASS; hosted/off-PC closure BLOCKED.

## Scope completed

- Added service-only runner-owned claim, heartbeat and finish RPCs.
- Added a ten-minute lease, explicit runner IDs, bounded duration metrics and a
  maximum of three attempts with safe expired-lease recovery.
- Updated the Python runner to require a safe `RUNNER_ID`, send exact RPC
  contracts, heartbeat during long reads, enforce a twelve-minute application
  deadline and close the browser in `finally` with bounded cleanup.
- Added a deterministic GitHub Cron dispatch contract for the two read-only job
  types and the three requested UTC schedules; Teaching uses the workspace local
  date and LMS uses distinct UTC time windows for the primary/retry schedules.
- Kept browser-state storage private and LMS behavior read-only.

## Fresh local gates

- PASS: `uv run --project apps/browser-runner ruff check .`.
- PASS: `uv run mypy src` from `apps/browser-runner`.
- PASS: `uv run pytest` from `apps/browser-runner` — 218 tests.
- PASS: `npx supabase db reset`.
- PASS: `npm run test:rls` — 101 assertions.
- PASS: `npm exec vitest run test/cron-workflow.test.ts` — 6 tests.

## Exit boundary

- BLOCKED: deployed Supabase migration/RPC verification.
- BLOCKED: hosted Storage reuse/reset and live Teaching/LMS read-only smoke.
- BLOCKED: cloud dispatch with the PC off and redacted owner evidence.
- PASS: final review round addressed the four implementation blockers; the
  follow-up scoped review completed with no P0/P1 findings.

## Privacy review

No credentials, browser state, cookies, tokens, student names, notes, screenshots
or raw production responses were used. The Cron body is empty payload and the
runner has no LMS Save/Submit/comment action.

## Owner handoff

Qq must review the branch, deploy/link migrations and the Edge Function, set
secrets outside chat, perform one read-only cloud dispatch with the PC off, and
record only redacted job/status metadata. Do not treat local PASS as hosted PASS.
