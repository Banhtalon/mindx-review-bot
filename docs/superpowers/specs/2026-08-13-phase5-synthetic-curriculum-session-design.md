# Phase 5 Synthetic Curriculum and Session Read-Only Design

## Status

Design approved by the owner after choosing the synthetic-first approach.

## Goal

Add a deterministic, read-only curriculum and lesson-context surface to the
existing Vite/React synthetic shell. The screen must show the selected session,
its current lesson, the next actual scheduled session, or an explicit safe
warning when the data is incomplete or the course has ended.

The high-level word "store" in this slice means keeping a validated read model
in application state and fixtures. It does not mean writing to Supabase or to
Teaching/LMS.

## Context and constraints

- The repository currently has one root Vite/React app under `src/`.
- Phase 5A already provides a Python-only deterministic lesson-context
  resolver, but the web shell has no shared TypeScript curriculum contract.
- Supabase currently has foundation, dispatch, and browser-state migrations;
  this slice does not add course, session, or curriculum persistence.
- All examples and fixtures are synthetic.
- MVP 1 remains read-only: no LMS Save, Submit, comment update, delivery, or
  Zalo action exists in this slice.
- No credential, cookie, token, real student identity, raw HTML, or production
  URL is added to code, logs, or evidence.
- No new dependency is required. The implementation uses TypeScript and the
  existing React/Vitest setup.

## Scope

### Included

1. A TypeScript curriculum contract and pure validator.
2. A TypeScript lesson-context resolver for the synthetic web read model.
3. Synthetic course, curriculum, and session fixtures.
4. A read-only session list and context panel in the existing app.
5. Unit, component, and privacy-oriented tests.
6. Redacted evidence and a Phase 5 slice report.

### Excluded

- Supabase migrations, RPCs, Auth, RLS, or remote persistence.
- Teaching/LMS browser navigation, selectors, credentials, cookies, or live
  smoke execution.
- Attendance, performance levels, quick notes, autosave, or revision conflict
  handling.
- Gemini, review generation, approval, export, or delivery.
- Any LMS mutation, including Save, Submit, or comment editing.

## Data contracts

The web layer will use small immutable TypeScript types:

```ts
type CurriculumEntry = {
  sessionNumber: number;
  lessonTitle: string;
  lessonContent: readonly string[];
  homeworkTitle?: string;
};

type CourseCatalog = {
  courseCode: string;
  courseName: string;
  totalSessions: number;
  entries: readonly CurriculumEntry[];
};

type SyntheticSession = {
  id: string;
  classCode: string;
  courseCode: string;
  sessionNumber: number;
  scheduledDate: string;
  startTime: string;
  endTime: string;
  workflowStatus: "context_pending" | "context_ready";
};
```

The resolver returns a discriminated result with one of these safe states:

- `matched`: current lesson is present and a next actual session is available;
- `no_next_session`: current lesson is present and there is no later scheduled
  session;
- `curriculum_missing`: the current session has no usable curriculum entry;
- `manual_fallback`: the selected session has an invalid or ambiguous context.

The result contains the selected session, the current curriculum entry when
available, the next actual session when available, and a stable reason code.
The UI never substitutes `sessionNumber + 1` for a missing schedule entry.

## Validation rules

`validateCourseCatalog` is pure and returns either a normalized catalog or a
list of stable issues. It must:

- reject a blank course code or course name;
- require a positive integer `totalSessions`;
- require every session number to be an integer from `1` through
  `totalSessions`;
- reject duplicate session numbers;
- reject a blank lesson title;
- reject a lesson with no content items after trimming;
- preserve optional homework only after trimming it;
- never infer a missing title, session number, or homework value.

The resolver must:

- match the catalog by normalized exact `courseCode`;
- find the current lesson by explicit `sessionNumber`, not array position;
- select the next session by the earliest later `scheduledDate + startTime` in
  the same class and course;
- preserve non-consecutive real session numbers;
- return `manual_fallback` for an invalid or ambiguous next timestamp;
- return `no_next_session` without fabricating a next lesson at course end;
- return `curriculum_missing` when the current lesson title/content is absent.

If a later scheduled session exists but its curriculum entry is absent, the
resolver still returns that actual next session and marks its lesson as
unavailable with a `NEXT_CURRICULUM_MISSING` warning. It never copies the
current lesson into the next-session card.

## UI behavior

The current synthetic review shell remains available. A new read-only section
will add:

1. A session list with class code, session number, date/time, and workflow
   status.
2. A selected-session header showing class, course, date, time, and an
   explicit `Synthetic read-only` label.
3. A current-lesson card showing title, content points, and homework when
   present.
4. A next-session card showing the actual next session and its lesson title.
5. A warning card for missing curriculum, ambiguous context, or the final
   session.

Selecting a session changes only React state. There is no Save, Submit, or
persistence button. The UI must remain usable on a narrow viewport and use
  text plus status labels rather than color alone.

## File boundaries

- `src/curriculum/contracts.ts`: immutable web curriculum/session types and
  result unions.
- `src/curriculum/validator.ts`: pure catalog validation and normalization.
- `src/curriculum/validator.test.ts`: validator RED/GREEN coverage.
- `src/session/lessonContext.ts`: pure current/next lesson resolution.
- `src/session/lessonContext.test.ts`: resolver RED/GREEN coverage.
- `src/fixtures/phase5Curriculum.ts`: synthetic catalog and session fixtures.
- `src/App.tsx`: render and select the read-only session/context section.
- `src/styles.css`: focused responsive styles for the new section.
- `src/App.test.tsx`: component behavior for selection and safe warnings.
- `docs/evidence/phase-5-synthetic/`: redacted evidence with counts and reason
  codes only.
- `docs/phase-reports/phase-5-synthetic.md`: scope, tests, limitations, and
  exit gate.

## Testing strategy

The implementation follows RED -> GREEN -> REFACTOR for each behavior:

1. Validator rejects malformed catalogs and accepts a normalized valid catalog.
2. Resolver finds the current entry by explicit session number.
3. Resolver chooses a later non-consecutive actual session.
4. Resolver returns an explicit final-session warning.
5. Resolver fails closed for missing current curriculum and ambiguous context.
6. The UI changes the selected session and displays its safe result.

Required verification after implementation:

- `npm run lint`;
- `npm run typecheck`;
- `npm run test`;
- `npm run build`;
- `npm run verify:no-secrets`;
- `npm run verify:no-live-write`.

The existing root lint caveat must be reported if linked sibling worktrees are
included by ESLint; no unrelated worktree will be changed to hide that issue.

## Acceptance criteria

- A valid synthetic catalog renders without guessing or array-order identity.
- Invalid catalog entries produce stable validation issues.
- A selected session shows the exact current lesson from its session number.
- A non-consecutive later session is shown as the next actual session.
- The final session shows a clear end-of-course warning and no fabricated next
  lesson.
- Missing curriculum and ambiguous context block progression in the read model.
- No network, Supabase write, LMS mutation, credential, cookie, token, or PII
  path is introduced.
- All required tests, type checks, build, and security/privacy scripts pass.
- Evidence and the phase report contain synthetic counts/reason codes only.
