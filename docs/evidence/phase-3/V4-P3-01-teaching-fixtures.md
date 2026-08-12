# Evidence V4-P3-01 — Teaching fixture parser and reconciliation

- Date: 2026-08-12
- Branch: `codex/phase3-teaching-reader`
- Data class: synthetic fixture only
- Requirement: deterministic Teaching schedule extraction and reconciliation
  must normalize trusted identity fields, preserve source hashes, and stop on
  ambiguity. Page-provided internal IDs are not trusted as mappings.

## Verification

- PASS: focused parser/reconciliation suite — 33 tests.
- PASS: full Python suite — 125 tests.
- PASS: `uv run ruff check .`.
- PASS: `uv run mypy src`.
- PASS: `npm run lint`.
- PASS: `npm run typecheck`.
- PASS: `npm run test` — 11 files, 46 tests.
- PASS: `npm run build`.
- PASS: `npm run verify:no-secrets`.
- PASS: `npm run verify:no-live-write`.

## Contract results

- Semantic `data-*` attributes are parsed; generated CSS class names are not
  identity inputs.
- Class codes are normalized to uppercase and session types to lowercase.
- Dates and times are parsed as explicit ISO values; an end time that is not
  after the start time is rejected.
- The page body is represented in output only by a SHA-256 digest.
- Login pages fail with `TEACHING_LOGIN_REQUIRED` instead of becoming empty
  schedules.
- Empty schedules return a warning and never mass-cancel existing records.
- Source IDs are authoritative, followed by a previously verified internal
  mapping, then the exact class/session/type tuple. Page-provided internal ID
  claims are ignored unless a trusted mapping already exists. A late source ID
  attaches only to one previously unidentified tuple; conflicting IDs and
  multiple candidates are quarantined.
- Missing session type/number, duplicate source IDs, and malformed values fail
  closed.
- A repeated identical batch is `unchanged`; a verified reschedule is an
  `updated` record, not a duplicate.

## Explicit limitation

This evidence does **not** claim a live Teaching run. No production URL,
credential, cookie, browser state, roster, screenshot, or raw production page
was used. Verified live selectors, owner-controlled read-only smoke, cold/warm
timing, and production persistence remain BLOCKED. Browser login/custom
actions and Supabase reconciliation RPCs are deferred until those inputs are
reviewed.

## Privacy review

- [x] No credentials
- [x] No cookies/tokens
- [x] No student names or notes
- [x] No raw HTML in evidence
- [x] No screenshots, traces, video or HAR
- [x] No LMS Save/Submit/update-comment action
- [x] No live result represented as passed
