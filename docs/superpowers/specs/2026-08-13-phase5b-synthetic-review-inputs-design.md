# Phase 5B Synthetic Review Inputs Design

## Status

Design approved by the owner on 2026-08-13.

## Goal

Add a local synthetic review-input panel for attendance, learning level, and
draft notes. The panel gives the owner a deterministic checkpoint before any
future content-generation phase without saving data or contacting LMS,
Teaching, Supabase, Gemini, or any other remote service.

## Current context

Phase 5 synthetic already provides:

- an immutable synthetic session and curriculum fixture set;
- exact current/next lesson resolution;
- a read-only curriculum/session context surface;
- manual student mapping keyed by explicit synthetic row keys.

Phase 5B adds only the review-input checkpoint. It does not make the existing
mapping screen live and does not turn draft values into persisted records.

## Scope

### Included

1. Synthetic learner-review contracts and a pure readiness helper.
2. A small immutable synthetic roster fixture with explicit stable row keys.
3. Local React state for attendance, level, and note drafts.
4. A **Mark all present** action followed by per-learner exceptions.
5. A visible generation-readiness gate based only on attendance completeness.
6. Accessible component tests and redacted evidence/report updates.

### Excluded

- Supabase tables, migrations, RPCs, Auth, RLS, or persistence.
- Teaching/LMS browser navigation, live selectors, credentials, cookies, or
  live smoke execution.
- Autosave, revision numbers, conflict resolution, or reload recovery.
- Gemini calls, prompt construction, review generation, approval, export, or
  delivery.
- LMS Save, Submit, comment editing, attendance writes, or any other mutation.
- Real student names, PII, production HTML, screenshots, tokens, or secrets.

## Data contracts

The synthetic review-input model uses explicit row keys and no array-position
identity:

~~~ts
export type AttendanceStatus = "present" | "absent" | "unknown";

export type LearningLevel =
  | "strong"
  | "developing"
  | "needs_support"
  | "unknown";

export type SyntheticLearner = {
  readonly rowKey: string;
  readonly displayName: string;
};

export type SyntheticReviewInput = {
  readonly rowKey: string;
  readonly attendance: AttendanceStatus;
  readonly level: LearningLevel;
  readonly noteDraft: string;
};

export type ReviewInputGate =
  | {
      readonly ready: true;
      readonly reasonCode: "ATTENDANCE_COMPLETE";
      readonly unknownAttendanceRowKeys: readonly [];
    }
  | {
      readonly ready: false;
      readonly reasonCode: "ATTENDANCE_UNKNOWN";
      readonly unknownAttendanceRowKeys: readonly string[];
    };
~~~

The pure helper has this behavior:

~~~ts
export function evaluateReviewInputGate(
  inputs: readonly SyntheticReviewInput[],
): ReviewInputGate;
~~~

It returns ready: false when at least one explicit row key has
attendance: "unknown". Level and note values do not affect readiness.
Empty notes and level: "unknown" remain valid draft state.

## State and data flow

~~~text
synthetic roster fixture
        |
        v
initialize local inputs: attendance unknown, level unknown, note ""
        |
        +--> Mark all present --> every row attendance present
        |
        +--> per-row attendance/level/note edits
        |
        v
evaluateReviewInputGate
        |
        +--> ATTENDANCE_UNKNOWN --> block future generation step
        |
        +--> ATTENDANCE_COMPLETE --> show gate open, perform no generation
~~~

React state is local to the panel and keyed by rowKey. The panel does not
write to localStorage, Supabase, a browser session, a file, or an endpoint.
Reloading the page intentionally clears the draft.

## UI behavior

The panel is a new read-only synthetic section below the existing mapping
checkpoint.

### Initial state

- Three synthetic learners are shown with explicit row keys.
- Every attendance value starts as unknown.
- Every level starts as unknown.
- Every note draft is empty.
- The readiness panel says **Generation blocked: attendance unknown**.
- The **Mark all present** button is enabled.

### Bulk and exception flow

- **Mark all present** changes only local attendance values to present.
- Each learner has an attendance control with present, absent, and unknown.
- The owner can set one or more exceptions to absent.
- Changing a learner back to unknown immediately closes the readiness gate.
- A complete attendance set opens the gate even if levels are unknown or notes
  are blank.

### Level and note flow

- Each learner has a level control with strong, developing, needs_support, and
  unknown.
- Each learner has a labeled draft-note textarea.
- Level and note edits remain local and never enable a write action.
- No button is named Save or Submit.
- The gate is informational only; there is no generation button or generation
  request in this slice.

### Accessibility

- Use real labels for every select and textarea.
- Use a visible text status in addition to color.
- **Mark all present** is a type="button" control.
- Keyboard focus uses the existing :focus-visible styling.
- The panel remains usable at the existing narrow responsive breakpoint.

## Error and safety behavior

- Unknown attendance is fail-closed and blocks the future generation gate.
- Unknown level does not block this slice because the approved policy makes
  attendance the only required prerequisite here.
- Empty notes are allowed as drafts and are never silently replaced.
- Explicit row keys are used for all updates; no row ordering is used to
  identify a learner.
- The UI displays synthetic/read-only labels so local draft state cannot be
  mistaken for saved LMS data.

## Testing strategy

Tests follow RED -> GREEN -> REFACTOR -> VERIFY:

1. The pure gate rejects any input with unknown attendance.
2. The pure gate accepts present/absent attendance regardless of level/note.
3. Bulk present changes all synthetic rows to present.
4. A per-row unknown exception blocks the gate again.
5. Level and note edits render and do not change attendance readiness rules.
6. The UI starts blocked and has no Save/Submit control.
7. The UI exposes labels and status text at a narrow responsive layout.

Required final checks:

- npm run lint
- npm run typecheck
- npm run test
- npm run build
- npm run verify:no-secrets
- npm run verify:no-live-write
- git diff --check

## Acceptance criteria

- Owner can mark all synthetic learners present and then set individual
  attendance exceptions.
- The readiness gate is blocked while any attendance is unknown.
- The readiness gate opens when every attendance value is present or absent.
- Level and note drafts are editable but do not persist or call any service.
- No Save, Submit, LMS write, network, Supabase, Gemini, PII, or secret path is
  introduced.
- Existing curriculum/session and manual-mapping tests remain green.
- Evidence records only synthetic counts, status/reason codes, command results,
  and explicit limitations.

## Deferred work

- Real attendance extraction from LMS.
- Autosave and revision/conflict UI.
- Persistent review-input schema and RLS.
- Generation, privacy redaction, approval, export, and delivery.
