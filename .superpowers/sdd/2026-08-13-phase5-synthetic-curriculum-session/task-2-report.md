# Task 2 Report - Deterministic Current/Next Lesson Resolution

Date: 2026-08-13
Worktree: `E:\mindx-review-bot\.worktrees\phase5-synthetic-ui`
Task brief: `E:\mindx-review-bot\.worktrees\phase5-synthetic-ui\.superpowers\sdd\2026-08-13-phase5-synthetic-curriculum-session\task-2-brief.md`

## Scope delivered

- Extended `src/curriculum/contracts.ts` with the immutable synthetic session and lesson-context result contracts required by Task 2.
- Added pure resolver logic in `src/session/lessonContext.ts`.
- Added focused Vitest coverage in `src/session/lessonContext.test.ts`.

No dependency was added. No Supabase migration/RPC/Auth/RLS, no Teaching/LMS navigation, no persistence, no network, no live URL, no credential/cookie/token/PII, and no LMS save/submit/comment delivery behavior was introduced.

## RED -> GREEN -> REFACTOR -> VERIFY evidence

### RED 1: current lesson lookup

Command:

```powershell
npx vitest run src/session/lessonContext.test.ts -t "finds current lesson by explicit session number"
```

Result:

- FAIL because `./lessonContext` did not exist yet.

### GREEN 1: minimal current lesson lookup

Command:

```powershell
npx vitest run src/session/lessonContext.test.ts -t "finds current lesson by explicit session number"
```

Result:

- PASS after adding the minimal resolver and new contracts.

### RED 2: actual next-session resolution

Command:

```powershell
npx vitest run src/session/lessonContext.test.ts
```

Result:

- FAIL with 5 failing tests covering:
  - earliest later actual session selection
  - `NO_NEXT_SESSION`
  - `NEXT_CURRICULUM_MISSING`
  - `NEXT_SESSION_AMBIGUOUS`
  - `SESSION_CONTEXT_INVALID`

### GREEN 2: deterministic next-session logic

Command:

```powershell
npx vitest run src/session/lessonContext.test.ts
```

Result:

- PASS (`6` tests) after implementing pure matching, validation, sorting, ambiguity detection, and warning behavior.

### REFACTOR

- Extracted private helpers for:
  - class-code normalization
  - ISO date validation
  - HH:mm validation
  - session-context validation
  - consistent result construction
- Kept the public resolver pure and side-effect free.

### Self-review

#### Scope check

- Stayed inside the Task 2 surface only:
  - `src/curriculum/contracts.ts`
  - `src/session/lessonContext.ts`
  - `src/session/lessonContext.test.ts`

#### Reason-code check

- `COURSE_NOT_FOUND`: returned when no normalized course catalog matches.
- `COURSE_AMBIGUOUS`: returned when more than one normalized course catalog matches.
- `CURRICULUM_MISSING`: returned when the selected synthetic session has no curriculum entry.
- `SESSION_CONTEXT_INVALID`: returned when the selected session or any exact class/course candidate session has malformed date/time or non-integer session number.
- `NEXT_SESSION_AMBIGUOUS`: returned when two later sessions with different IDs share the earliest date + start time.
- `NO_NEXT_SESSION`: returned when the selected session is the final actual session for the exact class/course stream.
- `LESSON_CONTEXT_MATCH`: retained for successful resolution, including the warning-only case where the next real session exists but its curriculum entry is omitted.

#### Design-rule check

- Incomplete catalogs are handled only by omitted entries.
- No `NaN`, fractional, or other invalid `sessionNumber` sentinel is permitted in present session context.

### VERIFY

Commands run fresh after the final code change:

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
npm run verify:no-secrets
npm run verify:no-live-write
```

Results:

- `npm run lint` PASS
- `npm run typecheck` PASS
- `npm run test` PASS (`14` files, `70` tests)
- `npm run build` PASS
- `npm run verify:no-secrets` PASS
- `npm run verify:no-live-write` PASS

## Files changed

- `src/curriculum/contracts.ts`
- `src/session/lessonContext.ts`
- `src/session/lessonContext.test.ts`

## Behavior covered

- finds the current lesson by exact `sessionNumber`, not array order
- normalizes course matching before catalog selection
- fails closed on missing or ambiguous course catalogs
- chooses the earliest later actual session even when session numbers are non-consecutive
- returns `NO_NEXT_SESSION` for the final actual session while preserving the current lesson
- returns the actual next session with `NEXT_CURRICULUM_MISSING` when its curriculum entry is omitted
- fails closed on malformed date/time context
- fails closed when the earliest later slot is ambiguous

## Concerns

- None.

---

## Fix report - Round 1

Date: 2026-08-13

### Review finding addressed

- Same-slot duplicates were being classified as "later" because the resolver used `scheduledDate|startTime|endTime|id` to decide whether a session came after the selected session.
- That allowed a session with the same `scheduledDate + startTime` but different `endTime` or `id` to become `nextSession`, which violates the fail-closed design.

### Root cause

- The resolver mixed two separate concepts:
  - slot identity: `scheduledDate + startTime`
  - deterministic ordering among truly later sessions
- Using `endTime` and `id` inside the "later than selected" comparison turned same-slot duplicates into apparently later sessions instead of ambiguous context.

### Test additions

- Added direct coverage for:
  - `COURSE_NOT_FOUND`
  - `COURSE_AMBIGUOUS`
  - `CURRICULUM_MISSING`
- Added a regression test proving a same-slot duplicate with a different `id`/`endTime` cannot resolve as the next actual session.

### RED evidence

#### RED 1: same-slot duplicate bug reproduction

Command:

```powershell
npx vitest run src/session/lessonContext.test.ts -t "returns course_not_found when no normalized catalog matches|returns course_ambiguous when more than one normalized catalog matches|returns curriculum_missing when the selected session has no curriculum entry|fails closed when a same-slot duplicate differs only by end time or id"
```

Output summary:

- FAIL (`1 failed, 3 passed`) because:
  - `fails closed when a same-slot duplicate differs only by end time or id`
  - expected `NEXT_SESSION_AMBIGUOUS`
  - received `LESSON_CONTEXT_MATCH` with `NEXT_CURRICULUM_MISSING`

#### RED 2: direct fail-first proof for COURSE_NOT_FOUND

Temporary mutation:

- changed the zero-match branch to return `COURSE_AMBIGUOUS`

Command:

```powershell
npx vitest run src/session/lessonContext.test.ts -t "returns course_not_found when no normalized catalog matches"
```

Output summary:

- FAIL because expected `COURSE_NOT_FOUND` but received `COURSE_AMBIGUOUS`

#### RED 3: direct fail-first proof for COURSE_AMBIGUOUS

Temporary mutation:

- changed the multi-match branch to return `COURSE_NOT_FOUND`

Command:

```powershell
npx vitest run src/session/lessonContext.test.ts -t "returns course_ambiguous when more than one normalized catalog matches"
```

Output summary:

- FAIL because expected `COURSE_AMBIGUOUS` but received `COURSE_NOT_FOUND`

#### RED 4: direct fail-first proof for CURRICULUM_MISSING

Temporary mutation:

- changed the missing-current-entry branch to return `status: "manual_fallback"`

Command:

```powershell
npx vitest run src/session/lessonContext.test.ts -t "returns curriculum_missing when the selected session has no curriculum entry"
```

Output summary:

- FAIL because expected `status: "curriculum_missing"` but received `status: "manual_fallback"`

### GREEN changes

- Added `sessionSlotKey()` for slot identity using only `scheduledDate + startTime`.
- Kept `sessionOrderKey()` for deterministic ordering among truly later sessions.
- Added an early fail-closed check: if another exact class/course session has the same slot but a different `id`, return `NEXT_SESSION_AMBIGUOUS`.
- Changed later-session filtering to require a strictly later slot key instead of comparing `endTime` and `id` against the selected slot.
- Preserved previous behavior for:
  - non-consecutive next-session selection
  - final-session `NO_NEXT_SESSION`
  - `NEXT_CURRICULUM_MISSING`
  - malformed session context
  - earliest-later-slot ambiguity

### GREEN evidence

Command:

```powershell
npx vitest run src/session/lessonContext.test.ts
```

Output summary:

- PASS (`10` tests) after restoring the temporary mutations and applying the resolver fix.

### Self-review

- The fix stays inside Task 2 files only.
- Reason-code behavior remains explicit and fail-closed.
- Same-slot duplicates now never become `nextSession`.
- Existing direct behaviors now have explicit tests in the suite, not just implicit branch coverage.

### Verification commands

Commands run fresh after the final code change:

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
npm run verify:no-secrets
npm run verify:no-live-write
```

Results:

- `npm run lint` PASS
- `npm run typecheck` PASS
- `npm run test` PASS
- `npm run build` PASS
- `npm run verify:no-secrets` PASS
- `npm run verify:no-live-write` PASS

### Result

- Same-slot duplicate session rows now fail closed as ambiguous instead of being misclassified as the next actual session.
- `COURSE_NOT_FOUND`, `COURSE_AMBIGUOUS`, and `CURRICULUM_MISSING` now each have direct test coverage in `src/session/lessonContext.test.ts`.
