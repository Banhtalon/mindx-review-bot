# Task 1 Report - Synthetic Curriculum Contracts and Validator

Date: 2026-08-13
Worktree: `E:\mindx-review-bot\.worktrees\phase5-synthetic-ui`
Task brief: `E:\mindx-review-bot\.worktrees\phase5-synthetic-ui\.superpowers\sdd\2026-08-13-phase5-synthetic-curriculum-session\task-1-brief.md`

## Scope delivered

- Added a pure TypeScript synthetic-only curriculum contract layer in `src/curriculum/contracts.ts`.
- Added `validateCourseCatalog()` in `src/curriculum/validator.ts`.
- Added focused Vitest coverage in `src/curriculum/validator.test.ts`.

No dependencies added. No network, persistence, Supabase, LMS, Teaching, auth, live URLs, secrets, cookies, tokens, or PII introduced.

## RED -> GREEN -> REFACTOR -> VERIFY evidence

### RED 1: normalization behavior

Command:

```powershell
npx vitest run src/curriculum/validator.test.ts -t "normalizes course text"
```

Result:

- FAIL because `./validator` did not exist yet.

### GREEN 1: minimum normalization implementation

Commands:

```powershell
npx vitest run src/curriculum/validator.test.ts -t "normalizes course text"
npx vitest run src/curriculum/validator.test.ts
```

Results:

- normalization test passed after adding contracts and minimal validator
- suite later expanded and passed

### RED 2: validation rules

Command:

```powershell
npx vitest run src/curriculum/validator.test.ts
```

Result:

- FAIL with 4 failing tests for missing validation behavior:
  - blank course code/name
  - invalid total sessions
  - out-of-range/duplicate session numbers
  - blank lesson title/empty lesson content

### GREEN 2: minimum validation rules

Command:

```powershell
npx vitest run src/curriculum/validator.test.ts
```

Result:

- PASS with validator rules implemented

### Extra regression check: non-integer session number

Added a direct test for `SESSION_NUMBER_INVALID`.

Red/green proof:

```powershell
npx vitest run src/curriculum/validator.test.ts -t "rejects a non-integer session number"
```

- FAIL when the integer-validation branch was temporarily removed
- PASS again after restoring the branch

### REFACTOR

- Kept the implementation small.
- Reused one private `normalizeText()` helper in validator.
- No behavior changes after green.

### VERIFY

Commands run fresh before completion:

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```

Results:

- `npm run lint` PASS
- `npm run typecheck` PASS
- `npm run test` PASS (`13` files, `64` tests)
- `npm run build` PASS

## Files changed

- `src/curriculum/contracts.ts`
- `src/curriculum/validator.ts`
- `src/curriculum/validator.test.ts`

## Behavior covered

- normalizes course code, course name, lesson title, lesson content, and homework
- trims/removes blank lesson content items
- rejects blank course code and course name
- rejects non-positive and fractional `totalSessions`
- rejects non-integer session numbers
- rejects out-of-range session numbers
- rejects duplicate session numbers
- rejects blank lesson titles
- rejects empty lesson content
- allows intentionally incomplete synthetic catalogs without inventing entries by preserving `sessionNumber: NaN`

## Self-review

- Scope check: stayed inside the first pure TypeScript layer only.
- Safety check: synthetic-only behavior preserved; no persistence or external access added.
- Test quality check: assertions use exact issue codes and exact paths for stable contracts.
- Interface check: later tasks can depend on validated output types instead of raw input.

## Concerns

- None. The implementation matched the Task 1 brief and passed the required web verification commands.

---

## Fix report - Round 1

Date: 2026-08-13

### Root cause

- The previous validator had a special-case branch that treated `sessionNumber: NaN` as valid synthetic incompleteness.
- The prior test suite reinforced that behavior by asserting a catalog with `Number.NaN` could still validate successfully.
- That contradicted the approved design rule that every present curriculum entry must use an integer `sessionNumber` in `1..totalSessions`.
- Incomplete curriculum support belongs to omitted entries, not sentinel values inside an entry.

### Test changes

- Replaced the old acceptance test for `sessionNumber: Number.NaN` with a success test that validates a catalog containing only sessions `1` and `3` out of `totalSessions: 5`.
- Strengthened the invalid-session test so it now asserts both:
  - fractional `sessionNumber` is rejected with `SESSION_NUMBER_INVALID`
  - `sessionNumber: Number.NaN` is rejected with `SESSION_NUMBER_INVALID`

### RED evidence

Command:

```powershell
npx vitest run src/curriculum/validator.test.ts -t "rejects a non-integer or NaN session number"
```

Output summary:

- FAIL because the validator still accepted `sessionNumber: NaN` as valid and returned `ok: true`.

### GREEN evidence

Command:

```powershell
npx vitest run src/curriculum/validator.test.ts
```

Output summary:

- PASS (`7` tests) after removing the `NaN` special case and requiring every present entry to have an integer session number.

### Verification commands

Commands:

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```

Output summary:

- `npm run lint` PASS
- `npm run typecheck` PASS
- `npm run test` PASS (`13` files, `64` tests)
- `npm run build` PASS

### Result

- Valid catalogs may omit entire session entries.
- Present entries must now always use integer `sessionNumber` values in range.
- Missing current/next curriculum entries remain a later resolver concern (`CURRICULUM_MISSING` / `NEXT_CURRICULUM_MISSING`), not a validator escape hatch.
