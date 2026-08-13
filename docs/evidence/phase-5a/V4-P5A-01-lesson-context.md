# Evidence V4-P5A-01 — Deterministic Teaching/LMS lesson context

- Implementation scope: synthetic Python resolver and validated models only.
- Design/plan commit: 5c66ada
- Teaching metadata commit: f86da56
- LMS model commit: 8faebc5
- Resolver commit: 8cf034e

## Command/steps

- Added deterministic Teaching block and special_event extraction.
- Added immutable LMS class schedule and per-session curriculum models.
- Added exact class/session/date/time reconciliation.
- Added session-number curriculum lookup and actual-date/time next-event scan.
- Added explicit mismatch, ambiguity, missing-curriculum, and no-next-session
  result codes.
- Used synthetic class codes, lesson titles, homework titles, and identifiers
  only in automated tests.

## RED evidence

- Teaching parser test failed before the model/parser change because the new
  fields were absent.
- LMS model tests failed during collection before the new module existed.
- Resolver tests failed during collection before the resolver module existed.

## Actual verification

- Focused Teaching parser: 14 tests passed.
- Focused LMS model contract: 6 tests passed.
- Focused lesson-context resolver: 10 tests passed.
- Full Python runner suite: 209 tests passed.
- Python Ruff: passed.
- Python mypy: passed for 22 source files.
- Web lint: passed.
- Web typecheck: passed.
- Web Vitest suite: 57 tests passed.
- Web production build: passed.
- No-secrets check: passed.
- No-live-write check: passed.
- Supabase local database reset: passed.
- Supabase RLS suite: 67 tests passed.

## Result

PASS — synthetic Phase 5A lesson-context contract and verification gates.

## Privacy and safety review

- No credential, cookie, token, real student name, raw HTML, screenshot, or
  production URL is stored in this evidence.
- No browser action, network client, Supabase write, LMS Save/Submit action,
  comment mutation, or student mapping was added.
- Missing curriculum remains an explicit status; no title or homework is
  fabricated.
- Next-session selection uses actual later schedule date/time and preserves
  special-event metadata; it does not use array order or session-number
  incrementing.

## Known limitations

- Live selectors and live parser integration are not part of this phase.
- Live smoke was used only to verify the observed field shape in read-only mode.
- Supabase persistence, curriculum storage, and review generation remain
  deferred.
- A future live adapter must provide the normalized LMS class record before
  this resolver can be used with production observations.
