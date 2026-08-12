# Task 4 Report - Deterministic student identity mapping

## Scope

- Implemented only:
  - `apps/browser-runner/src/mindx_runner/lms_identity.py`
  - `apps/browser-runner/tests/unit/test_lms_identity.py`
- No parser, context, guard, live-runner, cookie, credential, or PII/log behavior changes.

## RED evidence

Command:

```powershell
uv run pytest tests/unit/test_lms_identity.py -q
```

Result:

```text
ModuleNotFoundError: No module named 'mindx_runner.lms_identity'
```

This proved the new behavior did not exist before implementation.

## GREEN evidence

Command:

```powershell
uv run pytest tests/unit/test_lms_identity.py -q
```

Result:

```text
........                                                                 [100%]
```

Covered behaviors:

- exact stable `student_id` match;
- exact `discriminator` match;
- exact NFC + whitespace + casefolded full-name match;
- no fuzzy match for `Nguyễn An` vs `Nguyễn Anh`;
- duplicate names with distinct IDs still resolve by stable identity;
- duplicate names without stable identity are `unresolvable`;
- duplicate non-null page IDs fail closed as `ambiguous`;
- row reorder invariance.

## VERIFY evidence

Commands and fresh results:

```powershell
uv run ruff check src/mindx_runner/lms_identity.py tests/unit/test_lms_identity.py
# All checks passed!

uv run mypy src
# Success: no issues found in 20 source files

uv run pytest
# 168 passed in 0.82s

git diff --check
# no output
```

## Implementation notes

- Resolver rejects duplicate non-null `student_id` or `discriminator` values before any match attempt.
- Match priority is fail-closed:
  1. exact `student_id`;
  2. exact `discriminator`;
  3. exact normalized name only when the candidate set yields exactly one row with stable identity.
- No row index, fuzzy, prefix, or guessed matching is used.
- Failure returns only:
  - `status="unresolvable"` + `LMS_STUDENT_IDENTITY_UNRESOLVABLE`
  - `status="ambiguous"` + `LMS_STUDENT_IDENTITY_AMBIGUOUS`

## Self-review

- Checked both new files directly for scope leakage and accidental dependency changes.
- `ExpectedStudent` normalization mirrors Task 2 roster semantics for NFC + whitespace cleanup.
- Name fallback intentionally does not resolve duplicate nameless rows, matching the brief's fail-closed rule.
- No additional exports or package wiring were needed.

## Concerns

- Reviewer subagent tool was not available in this harness, so review was a read-only self-review rather than a separate reviewer process.
- Report file is intentionally outside the implementation commit so the code commit contains only the two Task 4 files plus the exact required commit message.

---

## Fix append - 2026-08-12 review follow-up

### Review issues addressed

- Important: when `ExpectedStudent` has both non-null `student_id` and `discriminator`, resolution now requires a single roster row to satisfy both stable signals. If the signals split across different rows, or either signal has no matching row, the result fails closed as `unresolvable`.
- Minor: added a direct regression test for duplicate non-null discriminator values, asserting `ambiguous` before matching.

### Changes made

- Updated `apps/browser-runner/src/mindx_runner/lms_identity.py`
  - added a combined stable-identity branch before single-signal fallback;
  - preserved existing allowed statuses/reason codes only.
- Updated `apps/browser-runner/tests/unit/test_lms_identity.py`
  - added regression test where `student_id` and `discriminator` agree on one row;
  - added regression test where `student_id` matches one row and `discriminator` matches another, expecting fail-closed `unresolvable`;
  - added direct regression test for duplicate non-null discriminator values, expecting `ambiguous`.

### RED evidence for the review fix

Command:

```powershell
uv run pytest tests/unit/test_lms_identity.py -q
```

Result before the code fix:

```text
...F.......
FAILED tests/unit/test_lms_identity.py::test_conflicting_student_id_and_discriminator_fail_closed
AssertionError: assert StudentResolution(... LMS_STUDENT_ID_MATCH) == StudentResolution(... LMS_STUDENT_IDENTITY_UNRESOLVABLE)
```

This proved the implementation incorrectly resolved from `student_id` even when the `discriminator` pointed to a different row.

### GREEN / VERIFY evidence for the review fix

Commands and fresh results:

```powershell
uv run pytest tests/unit/test_lms_identity.py -q
# ...........                                                              [100%]

uv run ruff check src/mindx_runner/lms_identity.py tests/unit/test_lms_identity.py
# All checks passed!

uv run mypy src
# Success: no issues found in 20 source files

uv run pytest
# 171 passed in 0.79s
```

### Scope check

- No later-task files were changed.
- No parser, context, guard, or live-runner code was changed.
- Only Task 4 code/tests plus this report file were updated.
