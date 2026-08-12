# Teaching Reader and Reconciliation Design

## Goal

Implement the deterministic, synthetic-only core of Phase 3: parse a Teaching
schedule into validated structured records, normalize its identity fields, and
reconcile observations without guessing or mass-cancelling existing sessions.

This phase does not add live selectors, credentials, website calls, browser
login, Supabase writes, or any LMS/Teaching mutation.

## Architecture

`teaching_parser.py` owns semantic HTML extraction. It reads stable data
attributes and text, never CSS class names, and returns Pydantic models. The
parser computes a SHA-256 hash of the supplied page bytes and distinguishes a
real empty schedule from an authentication page or malformed page.

`teaching_reconcile.py` owns deterministic matching. It matches an observation
by source session ID first, then by an already verified internal source ID,
then by the exact class/session/type identity tuple. Zero candidates create a
new session, one candidate updates it, and multiple candidates are quarantined.
An empty or login page never causes mass cancellation.

## Output and safety contract

- Dates/times are parsed as explicit ISO values and retained as local wall-clock
  values; no timezone is inferred from browser content.
- Class codes and session types are normalized only by whitespace/case rules.
- `source_page_hash` is a digest, never raw HTML.
- Missing session type, unknown class code, duplicate candidates, and login
  pages fail closed or quarantine with safe codes.
- Synthetic fixtures contain no real credentials, student names, cookies, or
  production page bodies.

## Verification scope

The phase gate covers normal, empty, multi-class, rescheduled, makeup/repeat,
missing-type, duplicate-candidate, expired-login, CSS-class-change, empty-page
no-mass-cancellation, and idempotent-second-run fixtures. Live sample accuracy,
live browser timing, and production reconciliation remain BLOCKED until an
owner supplies verified selectors and explicitly authorizes a read-only smoke.
