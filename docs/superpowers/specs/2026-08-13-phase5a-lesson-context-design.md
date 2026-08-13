# Phase 5A — Deterministic lesson context resolver

## Status

Approved design based on an owner-controlled, read-only smoke of Teaching and
LMS. The smoke verified the field shape needed for this phase; it does not
authorize live persistence, credential handling, or browser automation changes.

## Goal

Resolve one lesson context from normalized Teaching and LMS observations without
guessing: exact class/session/date/time must match, the current curriculum entry
must exist, and the next actual Teaching event must be returned when available.

## Scope

This phase includes:

- optional deterministic extraction of Teaching 'block' and 'special_event';
- validated LMS class schedule and per-session curriculum models;
- exact Teaching–LMS context reconciliation;
- current lesson/homework lookup by explicit session number;
- next-event lookup by the actual future schedule, preserving special events;
- explicit safe statuses for mismatch, missing curriculum, ambiguous schedule,
  and no next session;
- synthetic fixtures, unit tests, redacted evidence, and phase report.

This phase does not include:

- live selectors, login, credentials, cookies, browser-state loading, or
  production URLs;
- Supabase persistence or migrations;
- Gemini prompts or review generation;
- LMS Save, Submit, comment editing, Zalo delivery, or any mutation;
- student roster parsing or row-order mapping;
- inventing a lesson title, homework, session number, or next lesson.

## Architecture

teaching_models.py and teaching_parser.py retain the existing semantic Teaching
parser and add the two observed, non-identity metadata fields: block and
special_event. New lesson_context_models.py contains immutable Pydantic models
for an LMS class schedule and curriculum catalog. New lesson_context.py
contains the pure resolver and no I/O.

The resolver accepts one selected Teaching session, the complete Teaching
schedule for the class, and one normalized LMS class record. It first asserts
the exact class/session/date/time against the LMS schedule, then looks up the
curriculum by session number, then scans actual later Teaching events for the
next session. It never derives the next event from current_session + 1 and
never uses array position as identity.

## Data contract

    TeachingSessionExtract(
        class_code,
        session_number,
        scheduled_date,
        start_time,
        end_time,
        block=None,
        special_event=None,
    )

    LmsClassExtract(
        class_code,
        course_code,
        course_name,
        total_sessions,
        scheduled_sessions=(LmsScheduleEntry(...), ...),
        curriculum=(LmsCurriculumEntry(...), ...),
        operation_mode=None,
    )

LmsScheduleEntry.session_number and LmsCurriculumEntry.session_number are the
only lookup keys within their respective collections. Duplicate keys are
invalid. Date/time values are compared exactly as local normalized values; they
are not used alone as identity.

LmsCurriculumEntry.lesson_title is required for a usable current lesson.
homework_title is optional. A missing or blank title returns
CURRICULUM_MISSING; the resolver never substitutes homework text or a guessed
title.

## Resolution behavior

The public function is:

    resolve_lesson_context(
        teaching_session: TeachingSessionExtract,
        teaching_schedule: Sequence[TeachingSessionExtract],
        lms_class: LmsClassExtract,
    ) -> LessonContextResolution

The result contains status, reason_code, current, and next_session. Possible
statuses are matched, curriculum_missing, manual_fallback, and
no_next_session.

The resolver returns these safe reason codes:

- LESSON_CONTEXT_MATCH
- TEACHING_SESSION_NUMBER_MISSING
- LMS_CLASS_MISMATCH
- LMS_SESSION_NOT_FOUND
- LMS_SESSION_AMBIGUOUS
- LMS_SCHEDULE_MISMATCH
- CURRICULUM_MISSING
- CURRICULUM_AMBIGUOUS
- NEXT_SESSION_AMBIGUOUS
- NO_NEXT_SESSION

An exact context mismatch or ambiguity returns manual_fallback and no current
lesson. Missing curriculum returns curriculum_missing and no current lesson.
An exact current lesson with no later Teaching event returns no_next_session
while retaining the current lesson so the UI can show an explicit end-of-course
warning. A later event such as a special event is returned as metadata rather
than discarded.

## Privacy and safety

- All tests use synthetic class codes, curriculum titles, and IDs.
- The resolver carries no student names, credentials, cookies, tokens, raw
  HTML, or live URLs.
- No network client, browser action, Save/Submit control, or write path is
  introduced.
- Evidence records counts, reason codes, and hashes only.

## Verification contract

The Phase 5A tests must prove:

- exact class/session/date/time match succeeds;
- a similar class code fails closed;
- a missing or duplicate LMS session fails closed;
- a date/time mismatch fails closed;
- curriculum lookup uses session number, not list order;
- missing curriculum returns CURRICULUM_MISSING without fabrication;
- the next event is selected by actual later date/time, not by consecutive
  session number;
- a special-event field is preserved in the next-event result;
- duplicate next-event timestamps return NEXT_SESSION_AMBIGUOUS;
- no later event returns NO_NEXT_SESSION with the current lesson retained;
- existing parser, lint, typecheck, web tests, Python tests, and privacy gates
  remain green.

## Acceptance

Phase 5A is complete only when the focused RED → GREEN cycle is recorded,
full required verification passes, redacted evidence and the phase report are
created, and a code review finds no scope or privacy violation. Live data is
used only to validate field shape; live execution remains outside this phase.
