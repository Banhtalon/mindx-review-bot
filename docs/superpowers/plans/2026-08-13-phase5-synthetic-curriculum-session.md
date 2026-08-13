# Phase 5 Synthetic Curriculum and Session Read-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`-`) syntax for tracking.

**Goal:** Add a deterministic synthetic curriculum/session read-only surface to the existing Vite/React shell, including validation, current/next lesson resolution, safe warnings, and evidence.

**Architecture:** Keep pure TypeScript contracts and resolution logic separate from React rendering. Store only immutable synthetic fixtures in the repository; the UI selects a fixture in React state and never calls Supabase, Teaching, LMS, Gemini, or a write endpoint. Use stable reason codes and discriminated result states so missing or ambiguous data is visible and cannot be guessed.

**Tech Stack:** TypeScript 6, React 19, Vite 8, Vitest 4, Testing Library, existing ESLint configuration.

## Global Constraints

- All examples and fixtures are synthetic.
- MVP 1 remains read-only: no LMS Save, Submit, comment update, delivery, or Zalo action.
- No Supabase migration, RPC, Auth, RLS, or remote persistence in this slice.
- No Teaching/LMS browser navigation, selector, credential, cookie, or live-smoke code.
- No Gemini, review generation, approval, export, or delivery.
- No credential, cookie, token, real student identity, raw HTML, or production URL in code, logs, or evidence.
- Never use array position or sessionNumber + 1 as lesson identity.
- Do not add a dependency.
- Every behavior follows RED -> GREEN -> REFACTOR -> VERIFY.
- Required final commands are npm run lint, npm run typecheck, npm run test, npm run build, npm run verify:no-secrets, and npm run verify:no-live-write.

## File Map

- Create src/curriculum/contracts.ts: immutable curriculum, catalog, synthetic session, validation, and resolution result types.
- Create src/curriculum/validator.ts: pure catalog normalization and validation.
- Create src/curriculum/validator.test.ts: validator behavior tests.
- Create src/session/lessonContext.ts: pure current/next lesson resolver.
- Create src/session/lessonContext.test.ts: resolver behavior tests.
- Create src/fixtures/phase5Curriculum.ts: synthetic catalogs and sessions used by the UI.
- Create src/fixtures/phase5Curriculum.test.ts: fixture contract test.
- Modify src/App.tsx: render and select the synthetic read-only session/context surface while preserving the existing mapping demo.
- Modify src/App.test.tsx: component tests for selection and safe warnings.
- Modify src/styles.css: responsive styles for the new surface.
- Create docs/evidence/phase-5-synthetic/README.md: redacted verification evidence.
- Create docs/phase-reports/phase-5-synthetic.md: scope, outcome, limitations, and exit gate.

---

### Task 1: Add curriculum contracts and validator

**Files:**

- Create: src/curriculum/contracts.ts
- Create: src/curriculum/validator.ts
- Test: src/curriculum/validator.test.ts

**Interfaces:**

- contracts.ts produces these types:

```
export type CurriculumEntryInput = {
  readonly sessionNumber: number;
  readonly lessonTitle: string;
  readonly lessonContent: readonly string[];
  readonly homeworkTitle?: string | null;
};

export type CourseCatalogInput = {
  readonly courseCode: string;
  readonly courseName: string;
  readonly totalSessions: number;
  readonly entries: readonly CurriculumEntryInput[];
};

export type CurriculumEntry = {
  readonly sessionNumber: number;
  readonly lessonTitle: string;
  readonly lessonContent: readonly string[];
  readonly homeworkTitle?: string;
};

export type CourseCatalog = {
  readonly courseCode: string;
  readonly courseName: string;
  readonly totalSessions: number;
  readonly entries: readonly CurriculumEntry[];
};

export type CurriculumIssueCode =
  | "COURSE_CODE_REQUIRED"
  | "COURSE_NAME_REQUIRED"
  | "TOTAL_SESSIONS_INVALID"
  | "SESSION_NUMBER_INVALID"
  | "SESSION_NUMBER_OUT_OF_RANGE"
  | "SESSION_NUMBER_DUPLICATE"
  | "LESSON_TITLE_REQUIRED"
  | "LESSON_CONTENT_REQUIRED";

export type CurriculumIssue = {
  readonly code: CurriculumIssueCode;
  readonly path: string;
};

export type CurriculumValidationResult =
  | { readonly ok: true; readonly catalog: CourseCatalog }
  | { readonly ok: false; readonly issues: readonly CurriculumIssue[] };

export function normalizeCourseCode(value: string): string;
```

- validator.ts produces:

```
export function validateCourseCatalog(
  input: CourseCatalogInput,
): CurriculumValidationResult;
```

- Later tasks consume CourseCatalog, CurriculumEntry, and normalizeCourseCode; they must not consume unvalidated CourseCatalogInput.

- [ ] Step 1: Write the failing normalization test.

  Add a test named normalizes course text, lesson text, content, and homework. Pass a catalog with surrounding whitespace, lower-case course code, a blank content item, and padded homework. Assert that the result is ok true, the course code is upper-case and trimmed, blank content is removed, non-blank content is trimmed, and homework is trimmed.

- [ ] Step 2: Run the normalization test and verify RED.

  Run:

```powershell
npx vitest run src/curriculum/validator.test.ts -t "normalizes course text"
```

  Expected: the test cannot load ./validator because the production validator does not exist yet.

- [ ] Step 3: Write the minimal contracts and validator.

  Create the types above. Implement normalizeCourseCode with NFC normalization, whitespace collapsing, trimming, and toLocaleUpperCase(). Implement validateCourseCatalog to return a new normalized catalog and remove blank content items; do not fill missing fields.

- [ ] Step 4: Run the normalization test and verify GREEN.

  Run the same command. Expected: one test passes with no test failure.

- [ ] Step 5: Add failing validation tests.

  Add separate tests for these behaviors and assert the exact issue codes and paths:

```ts
it("rejects blank course code and name", () => { /* COURSE_CODE_REQUIRED, COURSE_NAME_REQUIRED */ });
it("rejects a non-positive or fractional total", () => { /* TOTAL_SESSIONS_INVALID */ });
it("rejects out-of-range and duplicate session numbers", () => { /* two stable issues */ });
it("rejects blank lesson title and empty lesson content", () => { /* two stable issues */ });
it("allows an intentionally incomplete catalog without inventing entries", () => { /* ok: true, entries unchanged */ });
```

- [ ] Step 6: Run the validation tests and verify RED.

  Run:

```powershell
npx vitest run src/curriculum/validator.test.ts
```

  Expected: the new malformed-input tests fail because the validator currently only handles the first normalization behavior.

- [ ] Step 7: Implement the minimum validation rules.

  Validate course code/name, positive integer totalSessions, integer and range for each entry session number, duplicate session numbers, non-blank lesson title, and at least one non-blank content item. Accumulate issues in input order. Allow missing session numbers in an otherwise valid catalog so the resolver can return CURRICULUM_MISSING safely.

- [ ] Step 8: Run the validator suite and verify GREEN.

  Run:

```powershell
npx vitest run src/curriculum/validator.test.ts
```

  Expected: every validator test passes.

- [ ] Step 9: Refactor only after GREEN.

  Extract a small private string-normalization helper if it removes duplication; keep issue codes, paths, and output shape unchanged. Re-run the validator suite.

- [ ] Step 10: Commit the task.

```powershell
git add src/curriculum/contracts.ts src/curriculum/validator.ts src/curriculum/validator.test.ts
git commit -m "feat: validate synthetic curriculum catalogs"
```

---

### Task 2: Add deterministic current/next lesson resolution

**Files:**

- Modify: src/curriculum/contracts.ts
- Create: src/session/lessonContext.ts
- Test: src/session/lessonContext.test.ts

**Interfaces:**

- Add this immutable session contract to contracts.ts:

```ts
export type SyntheticSession = {
  readonly id: string;
  readonly classCode: string;
  readonly courseCode: string;
  readonly sessionNumber: number;
  readonly scheduledDate: string;
  readonly startTime: string;
  readonly endTime: string;
  readonly workflowStatus: "context_pending" | "context_ready";
};
```

- Add these result contracts:

```ts
export type LessonContextStatus =
  | "matched"
  | "no_next_session"
  | "curriculum_missing"
  | "manual_fallback";

export type LessonContextReasonCode =
  | "LESSON_CONTEXT_MATCH"
  | "NO_NEXT_SESSION"
  | "CURRICULUM_MISSING"
  | "COURSE_NOT_FOUND"
  | "COURSE_AMBIGUOUS"
  | "SESSION_CONTEXT_INVALID"
  | "NEXT_SESSION_AMBIGUOUS";

export type LessonContextWarningCode = "NEXT_CURRICULUM_MISSING";

export type LessonContextResolution = {
  readonly status: LessonContextStatus;
  readonly reasonCode: LessonContextReasonCode;
  readonly session: SyntheticSession;
  readonly currentLesson?: CurriculumEntry;
  readonly nextSession?: SyntheticSession;
  readonly nextLesson?: CurriculumEntry;
  readonly warnings: readonly LessonContextWarningCode[];
};
```

- lessonContext.ts produces:

```ts
export function resolveLessonContext(
  selectedSession: SyntheticSession,
  sessions: readonly SyntheticSession[],
  catalogs: readonly CourseCatalog[],
): LessonContextResolution;
```

- [ ] Step 1: Write the failing exact-current test.

  Create an out-of-order catalog with entries for sessions 5, 1, and 3. Pass a session numbered 3 and assert that currentLesson.sessionNumber is 3 and its title is the session-3 title, proving that array order is not identity.

- [ ] Step 2: Run the exact-current test and verify RED.

  Run:

```powershell
npx vitest run src/session/lessonContext.test.ts -t "finds current lesson by explicit session number"
```

  Expected: the test cannot load ./lessonContext because the resolver does not exist yet.

- [ ] Step 3: Implement minimal current-lesson resolution.

  Normalize course codes, require exactly one matching catalog, find the current entry by sessionNumber, and return CURRICULUM_MISSING when it is absent. Return COURSE_NOT_FOUND or COURSE_AMBIGUOUS as manual_fallback. Initialize warnings to an empty array.

- [ ] Step 4: Run the exact-current test and verify GREEN.

  Run the same command. Expected: one test passes.

- [ ] Step 5: Add failing next-session tests.

  Add tests for these exact behaviors:

```ts
it("chooses the earliest later actual session even when the number is non-consecutive", () => {
  // selected session 3; later sessions 5 and 7; expect session 5 by date/start time
});

it("returns no_next_session for the final actual session", () => {
  // expect status no_next_session, reason NO_NEXT_SESSION, currentLesson retained
});

it("returns the actual next session with a warning when its curriculum is missing", () => {
  // expect nextSession present, nextLesson undefined, warnings ['NEXT_CURRICULUM_MISSING']
});

it("fails closed when two later sessions share the earliest timestamp", () => {
  // expect status manual_fallback and reason NEXT_SESSION_AMBIGUOUS
});

it("rejects malformed date or time context", () => {
  // expect status manual_fallback and reason SESSION_CONTEXT_INVALID
});
```

- [ ] Step 6: Run the resolver tests and verify RED.

  Run:

```powershell
npx vitest run src/session/lessonContext.test.ts
```

  Expected: the new next-session tests fail because only current lookup exists.

- [ ] Step 7: Implement actual next-session selection.

  Validate ISO local date and HH:mm values before comparing them. Filter later sessions by exact normalized class code and course code, sort by scheduledDate + startTime + endTime + id, and detect two different IDs at the same earliest date/start timestamp as NEXT_SESSION_AMBIGUOUS. If no later session exists, return no_next_session with the current lesson retained. If a later session has no curriculum entry, return that session and the NEXT_CURRICULUM_MISSING warning without copying any lesson content.

- [ ] Step 8: Run the resolver suite and verify GREEN.

  Run:

```powershell
npx vitest run src/session/lessonContext.test.ts
```

  Expected: all resolver tests pass.

- [ ] Step 9: Refactor after GREEN.

  Extract private helpers for session timestamp validation, normalized class/course matching, and result construction only if they keep the public function pure and make the reason-code paths clearer. Re-run the resolver suite.

- [ ] Step 10: Commit the task.

```powershell
git add src/curriculum/contracts.ts src/session/lessonContext.ts src/session/lessonContext.test.ts
git commit -m "feat: resolve synthetic current and next lessons"
```

---

### Task 3: Add synthetic catalog/session fixtures

**Files:**

- Create: src/fixtures/phase5Curriculum.ts
- Test: src/fixtures/phase5Curriculum.test.ts

**Interfaces:**

- Export:

```ts
export const PHASE5_COURSE_CATALOGS: readonly CourseCatalog[];
export const PHASE5_SESSIONS: readonly SyntheticSession[];
```

- Fixtures must remain immutable and contain synthetic codes only.

- [ ] Step 1: Write the failing fixture contract test.

  Import the two constants and assert:

```ts
it("contains valid synthetic catalogs and sessions", () => {
  expect(PHASE5_COURSE_CATALOGS).toHaveLength(2);
  expect(PHASE5_SESSIONS).toHaveLength(3);
  for (const catalog of PHASE5_COURSE_CATALOGS) {
    expect(validateCourseCatalog(catalog).ok).toBe(true);
  }
});
```

  Also assert that the fixture includes a robotics session 3, a robotics session 5 later in the schedule, and a Python session whose current curriculum entry is intentionally absent.

- [ ] Step 2: Run the fixture test and verify RED.

  Run:

```powershell
npx vitest run src/fixtures/phase5Curriculum.test.ts
```

  Expected: the test cannot load the fixture module because it does not exist.

- [ ] Step 3: Add the minimal synthetic fixtures.

  Create two catalogs:

  - SYN-ROBOTICS-FOUNDATION, total 5, with entries in non-array order for sessions 5, 1, and 3; sessions 2 and 4 may remain absent.
  - SYN-PYTHON-FOUNDATION, total 3, with entries for sessions 1 and 3 but no entry for session 2.

  Create three sessions:

  - synthetic-robotics-session-3, class SYN-ROBOTICS-01, session 3, 2026-08-11 19:00-20:30, workflow context_pending.
  - synthetic-robotics-session-5, same class/course, session 5, 2026-08-25 19:00-20:30, workflow context_pending.
  - synthetic-python-session-2, class SYN-PYTHON-02, session 2, 2026-08-12 18:00-19:30, workflow context_pending.

  Use synthetic lesson titles and content only.

- [ ] Step 4: Run the fixture test and verify GREEN.

  Run the same command. Expected: all fixture contract assertions pass.

- [ ] Step 5: Commit the task.

```powershell
git add src/fixtures/phase5Curriculum.ts src/fixtures/phase5Curriculum.test.ts
git commit -m "test: add synthetic phase 5 curriculum fixtures"
```

---

### Task 4: Integrate the read-only context surface into the app

**Files:**

- Modify: src/App.tsx
- Modify: src/App.test.tsx
- Modify: src/styles.css

**Interfaces:**

- App.tsx consumes PHASE5_COURSE_CATALOGS, PHASE5_SESSIONS, and resolveLessonContext.
- React state stores only the selected synthetic session ID:

```ts
const [selectedPhase5SessionId, setSelectedPhase5SessionId] = useState(
  PHASE5_SESSIONS[0].id,
);
```

- The new UI must expose these accessible labels:
  - heading Curriculum and session context;
  - text Synthetic read-only;
  - current card Current lesson;
  - next card Next actual session;
  - final-session warning No next lesson is scheduled;
  - missing-current warning Curriculum unavailable.

- [ ] Step 1: Write failing component tests.

  Add tests to src/App.test.tsx:

```tsx
it("shows the selected synthetic lesson and actual next session", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "Curriculum and session context" })).toBeVisible();
  expect(screen.getByText("Synthetic read-only")).toBeVisible();
  expect(screen.getByRole("heading", { name: "Current lesson" })).toBeVisible();
  expect(screen.getByText("Robotics session three synthetic lesson")).toBeVisible();
  expect(screen.getByRole("heading", { name: "Next actual session" })).toBeVisible();
  expect(screen.getByText(/Session 5/)).toBeVisible();
});

it("shows a final-session warning without inventing a next lesson", () => {
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: /select SYN-ROBOTICS-01 session 5/i }));
  expect(screen.getByText("No next lesson is scheduled")).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Next actual session" })).not.toBeInTheDocument();
});

it("shows a missing-curriculum warning for an incomplete synthetic session", () => {
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: /select SYN-PYTHON-02 session 2/i }));
  expect(screen.getByText("Curriculum unavailable")).toBeVisible();
});
```

- [ ] Step 2: Run the new component tests and verify RED.

  Run:

```powershell
npx vitest run src/App.test.tsx -t "selected synthetic lesson|final-session warning|missing-curriculum warning"
```

  Expected: the tests fail because the new heading, buttons, and cards do not exist yet.

- [ ] Step 3: Implement the minimum React surface.

  Import the fixtures and resolver. Derive the selected session and resolution with useMemo. Render a section containing a session list, exact session metadata, current lesson content, next actual session metadata/title, and the safe warning branches. Give each session button an aria-label of the form Select {classCode} session {sessionNumber} so it is unambiguous even though the existing app has another synthetic session demo.

  Do not add a form submit handler, persistence call, network request, or button named Save/Submit. Keep the existing Spike 0 mapping demo and its tests intact.

- [ ] Step 4: Run the component tests and verify GREEN.

  Run:

```powershell
npx vitest run src/App.test.tsx
```

  Expected: all existing and new App tests pass.

- [ ] Step 5: Add focused responsive styles.

  Add styles for the session list, selected state, context cards, lesson content list, warning card, metadata grid, and a narrow viewport. Preserve visible text status labels and use :focus-visible for keyboard focus. Do not remove the existing responsive rules.

- [ ] Step 6: Verify UI after styling.

  Run:

```powershell
npx vitest run src/App.test.tsx
npm run typecheck
```

  Expected: App tests and TypeScript checking pass.

- [ ] Step 7: Commit the task.

```powershell
git add src/App.tsx src/App.test.tsx src/styles.css
git commit -m "feat: show synthetic lesson context in read-only UI"
```

---

### Task 5: Record evidence and phase report

**Files:**

- Create: docs/evidence/phase-5-synthetic/README.md
- Create: docs/phase-reports/phase-5-synthetic.md

**Interfaces:**

- Evidence records only command names, test counts, stable reason codes, synthetic fixture counts, and scope limitations.
- The report must not include names, credentials, cookies, tokens, raw HTML, screenshots, production URLs, or guessed live behavior.

- [ ] Step 1: Run the focused evidence commands.

  Run from the isolated worktree:

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
npm run verify:no-secrets
npm run verify:no-live-write
git diff --check
```

  Record the real exit status and counts from each command; do not write an anticipated result.

- [ ] Step 2: Write the redacted evidence file.

  Include sections for:

  - synthetic fixture inventory: 2 catalogs and 3 sessions;
  - validator behavior and stable issue codes;
  - resolver behavior: exact current, non-consecutive next, final-session NO_NEXT_SESSION, missing-current CURRICULUM_MISSING, and ambiguity NEXT_SESSION_AMBIGUOUS;
  - web test, lint, typecheck, build, no-secrets, and no-live-write observations;
  - explicit statement that no network, Supabase, LMS, Gemini, or mutation path was exercised.

- [ ] Step 3: Write the phase report.

  State scope completed, verification evidence, security/privacy review, known limitations, and exit gate. Mark live LMS integration, Supabase persistence, attendance/quick notes, Gemini generation, and approval as outside this slice.

- [ ] Step 4: Commit the evidence.

```powershell
git add docs/evidence/phase-5-synthetic/README.md docs/phase-reports/phase-5-synthetic.md
git commit -m "docs: record synthetic phase 5 evidence"
```

---

### Task 6: Review, full verification, and handoff

**Files:**

- Review all changed files and the final diff; no new source file is required.

**Interfaces:**

- The reviewer evaluates the branch against docs/superpowers/specs/2026-08-13-phase5-synthetic-curriculum-session-design.md and this plan.
- Final branch must contain only the synthetic curriculum/session slice and its tests/evidence.

- [ ] Step 1: Inspect the final diff and status.

  Run:

```powershell
git status --short --branch
git diff --stat main...HEAD
git diff --check main...HEAD
```

  Confirm there are no Supabase migrations, live URLs, secrets, LMS mutation verbs, or unrelated worktree changes.

- [ ] Step 2: Request code review.

  Use superpowers:requesting-code-review with base main, the final branch HEAD, the approved design, and the acceptance criteria. Fix every Critical or Important finding with a new RED test before changing implementation; record a Minor finding only if it is genuinely outside this slice.

- [ ] Step 3: Re-run all required verification after review fixes.

  Run the six required npm commands from Task 5 plus git diff --check again. Only report a pass when each command has a fresh exit code of zero and the test output has zero failures.

- [ ] Step 4: Merge only after review and verification.

  Fast-forward the root main branch to the reviewed branch only after the user confirms integration. Do not push to GitHub or create a PR unless separately requested.

---

## Self-review checklist

- [x] Every design requirement has a task: validator, current resolver, next resolver, final warning, missing curriculum, UI selection, evidence, and privacy boundary.
- [x] The plan does not require Supabase/LMS implementation that the approved synthetic-first scope excluded.
- [x] Later task interfaces use the exact types and function names produced by earlier tasks.
- [x] No step uses unfinished-work markers or an unspecified edge case.
- [x] Test steps explicitly state the command and expected RED/GREEN result.
- [x] The known root lint/worktree caveat is handled by verification evidence, not by changing unrelated worktrees.
