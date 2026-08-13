# Phase 5A Lesson Context Resolver Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

Goal: Build a pure, deterministic resolver that joins a selected Teaching session to the exact LMS schedule and curriculum entry and exposes the next actual Teaching event.

Architecture: Extend the existing semantic Teaching extract with block and special_event. Add immutable Pydantic models for an LMS class schedule/curriculum catalog and a pure resolver that performs exact context checks, session-keyed curriculum lookup, and date/time-based next-event selection. No browser, network, Supabase, or LMS mutation code changes.

Tech Stack: Python 3.12, Pydantic 2, pytest, Ruff, mypy, existing browser-runner package.

## Global Constraints

- MVP 1 only reads Teaching and LMS.
- No LMS Save/Submit action exists.
- No CAPTCHA, OTP, anti-bot bypass, credential, cookie, token, raw HTML, production URL, or student PII in fixtures/evidence.
- Session identity uses exact stable fields and explicit session numbers; array order, fuzzy matching, and guessed curriculum are forbidden.
- Context mismatch, ambiguity, and missing curriculum fail closed with stable reason codes.
- Live smoke observations are field-shape evidence only; this plan adds no live adapter.

---

### Task 1: Extend the Teaching semantic record with observed metadata

Files:
- Modify: apps/browser-runner/src/mindx_runner/teaching_models.py
- Modify: apps/browser-runner/src/mindx_runner/teaching_parser.py
- Create: apps/browser-runner/tests/fixtures/teaching/special-event.html
- Modify: apps/browser-runner/tests/unit/test_teaching_parser.py

Interfaces:
- TeachingSessionExtract.block: str | None
- TeachingSessionExtract.special_event: str | None
- parse_teaching_schedule() reads data-block and data-special-event from semantic session attributes.

- [ ] Step 1: Write the failing parser test

Add a synthetic fixture with one data-teaching-session="true" record containing data-block="Coding" and data-special-event="SYN-EVENT-01", then assert the parsed record preserves both normalized values.

- [ ] Step 2: Run the focused test to verify RED

Run: uv run --project apps/browser-runner pytest apps/browser-runner/tests/unit/test_teaching_parser.py::test_parser_preserves_block_and_special_event -q

Expected: FAIL because the current model/parser discard the two attributes.

- [ ] Step 3: Implement the minimal model/parser change

Add optional normalized fields to TeachingSessionExtract and include block and special-event in the parser semantic attribute allow-list and model construction. Existing fixtures without those attributes must continue to parse as None.

- [ ] Step 4: Run the focused test to verify GREEN

Run the same focused pytest command and require one passing test.

- [ ] Step 5: Run the existing Teaching parser tests

Run: uv run --project apps/browser-runner pytest apps/browser-runner/tests/unit/test_teaching_parser.py -q

Expected: all Teaching parser tests pass.

- [ ] Step 6: Commit the isolated parser change

~~~powershell
git add apps/browser-runner/src/mindx_runner/teaching_models.py apps/browser-runner/src/mindx_runner/teaching_parser.py apps/browser-runner/tests/fixtures/teaching/special-event.html apps/browser-runner/tests/unit/test_teaching_parser.py
git commit -m "feat: retain teaching block and special event"
~~~

### Task 2: Add immutable LMS schedule and curriculum models

Files:
- Create: apps/browser-runner/src/mindx_runner/lesson_context_models.py
- Create: apps/browser-runner/tests/unit/test_lesson_context_models.py

Interfaces:
- LmsScheduleEntry(session_number, scheduled_date, start_time, end_time)
- LmsCurriculumEntry(session_number, lesson_title, homework_title=None)
- LmsClassExtract(class_code, course_code, course_name, total_sessions, scheduled_sessions, curriculum, operation_mode=None)

- [ ] Step 1: Write failing validation tests

Cover normalized text, end-time-after-start-time, duplicate schedule session numbers, duplicate curriculum session numbers, and a blank curriculum title being rejected when a populated title is expected by the model.

- [ ] Step 2: Run the focused model tests to verify RED

Run: uv run --project apps/browser-runner pytest apps/browser-runner/tests/unit/test_lesson_context_models.py -q

Expected: FAIL because the module and models do not exist.

- [ ] Step 3: Implement minimal frozen Pydantic models

Use ConfigDict(frozen=True, extra="forbid"), normalize Unicode/whitespace, enforce positive session numbers and total sessions, enforce valid time ranges, and reject duplicate explicit session keys. Keep homework_title optional but require lesson_title to be non-blank.

- [ ] Step 4: Run the focused model tests to verify GREEN

Run the same pytest command and require all model tests to pass.

- [ ] Step 5: Commit the model contract

~~~powershell
git add apps/browser-runner/src/mindx_runner/lesson_context_models.py apps/browser-runner/tests/unit/test_lesson_context_models.py
git commit -m "feat: add lms schedule and curriculum models"
~~~

### Task 3: Implement exact lesson-context resolution

Files:
- Create: apps/browser-runner/src/mindx_runner/lesson_context.py
- Create: apps/browser-runner/tests/unit/test_lesson_context.py

Interfaces:
- LessonContextResolution(status, reason_code, current, next_session)
- resolve_lesson_context(teaching_session, teaching_schedule, lms_class) -> LessonContextResolution

- [ ] Step 1: Write the failing resolver tests

Add tests for exact match, similar class rejection, LMS session not found, duplicate LMS session ambiguity, schedule date/time mismatch, missing curriculum, out-of-order curriculum lookup, non-consecutive next session selection, special-event preservation, duplicate next timestamp ambiguity, and no-next-session warning.

- [ ] Step 2: Run the focused resolver tests to verify RED

Run: uv run --project apps/browser-runner pytest apps/browser-runner/tests/unit/test_lesson_context.py -q

Expected: FAIL during collection because the resolver module and public function do not exist.

- [ ] Step 3: Implement exact reconciliation and next-event scan

Require a Teaching session number. Normalize and compare the class code exactly. Match the LMS schedule by session number, reject zero or multiple matches, compare date/start/end exactly, then look up the curriculum by session number. Scan same-class Teaching entries whose scheduled start is later than the selected session, sort by date/start/end/session number, reject equal earliest timestamps, and return the selected event including block and special_event. Return stable status/reason-code pairs from the design; never invent a title or use session_number + 1.

- [ ] Step 4: Run the focused resolver tests to verify GREEN

Run the same focused pytest command and require all resolver tests to pass.

- [ ] Step 5: Refactor only after green

Extract small pure helpers for normalized class comparison, exact schedule lookup, curriculum lookup, and next-event selection only if the tests stay green. Keep all output models immutable and safe-code based.

- [ ] Step 6: Commit the resolver

~~~powershell
git add apps/browser-runner/src/mindx_runner/lesson_context.py apps/browser-runner/tests/unit/test_lesson_context.py
git commit -m "feat: resolve exact teaching lms lesson context"
~~~

### Task 4: Add redacted Phase 5A evidence and report

Files:
- Create: docs/evidence/phase-5a/V4-P5A-01-lesson-context.md
- Create: docs/evidence/phase-5a/index.json
- Create: docs/evidence/phase-5a/metrics.csv
- Create: docs/phase-reports/phase-5a.md

Interfaces:
- Evidence contains synthetic counts, test totals, status/reason codes, and verification commands only.
- The report explicitly records live field-shape smoke as read-only validation and keeps live execution/persistence outside scope.

- [ ] Step 1: Write evidence after implementation tests pass

Record the RED test observation, exact-match PASS, mismatch/ambiguity PASS, curriculum-missing PASS, next-event PASS, special-event preservation PASS, no-next-session PASS, privacy boundary, and known limitations. Do not include real names, credentials, cookies, tokens, raw HTML, screenshots, or production URLs.

- [ ] Step 2: Run the complete verification gate

~~~powershell
npm run lint
npm run typecheck
npm run test
npm run build
npm run verify:no-secrets
npm run verify:no-live-write
uv run --project apps/browser-runner ruff check apps/browser-runner
uv run --project apps/browser-runner mypy apps/browser-runner/src
uv run --project apps/browser-runner pytest apps/browser-runner/tests -q
~~~

Expected: every command exits 0; evidence contains no prohibited data.

- [ ] Step 3: Review the diff and commit evidence

~~~powershell
git diff --check
git status --short
git add docs/evidence/phase-5a docs/phase-reports/phase-5a.md
git commit -m "docs: record phase 5a lesson context evidence"
~~~

## Verification checklist

- [ ] RED was observed for each new behavior before its implementation.
- [ ] All focused and full Python tests pass.
- [ ] Web lint, typecheck, tests, build, no-secrets, and no-live-write pass.
- [ ] Ruff and mypy pass for the Python runner.
- [ ] Evidence has no credential, cookie, token, raw HTML, production URL, or real PII.
- [ ] No browser action, network call, Supabase write, LMS Save/Submit, or comment mutation was added.
- [ ] Branch remains isolated from main until review and integration decision.
