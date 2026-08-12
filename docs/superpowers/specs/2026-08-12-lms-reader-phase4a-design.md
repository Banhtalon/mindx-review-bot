# Phase 4A — LMS Pending Reader and Identity Mapping Design

## Status

Design for user review. This phase is synthetic-only and does not claim live
LMS access or production persistence.

## Goal

Build the deterministic core that selects recently ended LMS sessions, parses
their read-only context, extracts roster/lesson/homework data from semantic
fixture markup, and resolves students only through exact stable identity
signals.

## Scope

Phase 4A includes:

- pending-session selection for the current day and the previous day;
- exact class, session, date, and time assertions;
- semantic LMS context, roster, attendance, lesson, and homework parsing;
- stable `student_id` and `discriminator` extraction;
- an explicit `unresolvable` result for ambiguous or incomplete identity;
- tests proving row order never determines a student mapping;
- reuse and contract tests for the existing LMS read-only network guard and
  navigation privacy boundary.

Phase 4A does not include:

- real LMS credentials, cookies, browser state, or production URLs;
- live selectors, login actions, CAPTCHA/OTP handling, or a live smoke;
- Supabase LMS persistence;
- a manual mapping UI; the parser returns a safe mapping request/result for a
  later UI to consume;
- LMS Save, Submit, update-comment, editor, or any other LMS mutation.

## Design

### 1. Pending-session selection

`pending.py` owns selection of sessions that are eligible for read-only LMS
lookup. The input is an already normalized Teaching session record and an
explicit local `now` value. A session is eligible only when:

1. its scheduled local date is today or yesterday;
2. its scheduled end date/time is not in the future;
3. its workflow state is `context_pending`;
4. its class/session identity is complete.

The filter never infers a timezone from HTML or browser content. Future
sessions, sessions older than yesterday, non-pending states, and incomplete
identity are returned as safe skip reasons. A late session from yesterday is
therefore selected; an older session is not.

### 2. LMS context parser

`lms_parser.py` parses only semantic `data-*` attributes from synthetic HTML.
Generated CSS class names and row positions are not identity inputs. The
parser emits a validated `LmsPageExtract` containing:

- `class_code`;
- `session_number`;
- `scheduled_date`, `start_time`, and `end_time`;
- optional `source_session_id`;
- roster rows with `student_id`, `discriminator`, exact display name, and
  normalized attendance (`present`, `online`, `absent`, or `unknown`);
- normalized lesson text and optional homework text;
- a SHA-256 source-page digest and safe warnings only.

The parser rejects malformed or incomplete context with stable codes such as
`LMS_DATA_INVALID`, `LMS_CLASS_MISMATCH`, `LMS_SESSION_MISMATCH`, and
`LMS_TIME_MISMATCH`. It rejects similar class codes rather than using prefix,
substring, or fuzzy matching.

### 3. Exact context assertion

`assert_lms_context(expected, observed)` compares the pending-session context
with the parsed page:

- class code must be equal after the documented uppercase/whitespace
  normalization;
- session number must be equal;
- scheduled date must be equal;
- start and end times must be equal;
- source session ID, when present in both records, must be equal.

Date/time differences are never treated as a student or session identity
signal. A mismatch returns a safe failure result and no roster mapping is
performed.

### 4. Deterministic student identity

`identity.py` owns mapping after context assertion. Matching priority is:

1. exact stable `student_id` supplied by the expected internal mapping;
2. exact stable `discriminator` supplied by the LMS page and approved mapping;
3. exact Unicode NFC/casefolded full-name equality only when it yields one
   candidate and the candidate has a stable ID or discriminator.

The resolver never uses row index, approximate string similarity, prefix
matching, or date/time. `Nguyễn An` and `Nguyễn Anh` are different names.
Duplicate names with distinct stable IDs/discriminators map independently;
duplicate names without a discriminator return `unresolvable`.

Duplicate page IDs or discriminators are rejected before any mapping result is
returned. A mapping result carries `resolved`, `unresolvable`, or
`ambiguous` status plus a safe reason code and no raw HTML.

### 5. Lesson/homework and fallback contract

Lesson and homework are parsed as deterministic text fields from semantic
fixture attributes. Missing homework is represented as `None`; malformed
lesson markup fails closed rather than inventing context.

When a context or identity assertion fails, the result contains a manual
fallback request with the exact safe reason code. This is a contract for the
later manual mapping/session UI, not an automatic guess and not a live action.

### 6. Read-only and privacy boundaries

The existing `network_guard.py` remains the only mutation decision boundary:
GET/navigation is allowed according to the existing rules, login POST may be
explicitly allowed, and POST/PUT/PATCH/DELETE LMS mutation or comment-like
payloads are blocked. Phase 4A adds no method named `save`, `submit`, or
`update_comment`.

The existing `privacy_boundary.py` continues to prevent roster DOM payloads
from reaching a navigation LLM. Tests use synthetic names only and evidence
stores counts, codes, and hashes rather than raw HTML or production data.

## Data flow

```text
TeachingSessionRecord
        |
        v
PendingSessionFilter --skip reason--> manual fallback/result
        |
        v
LMS semantic fixture parser
        |
        v
Exact context assertion --mismatch--> manual fallback/result
        |
        v
Roster + lesson/homework extraction
        |
        v
Deterministic identity resolver --ambiguous--> unresolvable result
```

## Verification contract

The Phase 4A fixture suite must prove:

- exact class code accepted and similar class code rejected;
- exact session accepted and wrong date/time rejected;
- `Nguyễn An` does not match `Nguyễn Anh`;
- duplicate names with stable IDs map independently;
- duplicate names without a discriminator are unresolvable;
- row reordering produces the same ID-to-name mapping;
- absent and online attendance are parsed;
- yesterday's late session is selected and older sessions are skipped;
- no LMS mutation method/path/body is allowed outside the explicit login rule;
- roster DOM is not passed to a navigation LLM;
- lesson/homework extraction is deterministic and missing homework is safe.

The phase evidence will mark these synthetic contracts PASS while live LMS
selectors, credentials, browser-state reuse, live accuracy, timing, and
production persistence remain BLOCKED.

## Deferred follow-up

Phase 4B may add owner-facing manual mapping/session-context UI and a guarded
site adapter only after this contract is reviewed. Any live work requires
verified selectors and explicit owner authorization for a read-only smoke.
