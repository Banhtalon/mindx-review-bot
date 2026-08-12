# Phase 4A Final Review Fix Report

- Date: 2026-08-13
- Branch: `codex/phase4a-lms-reader`
- Review base: `3976018`
- Reviewed implementation endpoint: `2e23910`
- Review range: `3976018..2e23910`
- Scope: synthetic-only Phase 4A; pure/read-only LMS contracts

## Status

- All seven supplied findings were reproduced and addressed in the reviewed
  implementation endpoint.
- App-scoped Python, web, build, security, and local RLS verification passed.
- The three Python commands required at the worktree root still fail because
  `pytest`, `ruff`, and `mypy` cannot be spawned there. These remain explicit
  FAIL results and are not overridden by app-scoped PASS results.
- Live LMS credentials, selectors, browser state, mutations, and smoke remain
  BLOCKED and outside Phase 4A.

## Fixes

1. Exact-name identity fallback now resolves only when the complete exact-name
   candidate set contains one row and that row has stable identity. A mixed
   stable/unstable duplicate is ambiguous in either row order.
2. The parser now tracks unique open elements for context and row ownership.
   Same-tag nesting retains all in-context rows and still ignores outside rows.
3. Added `resolve_lms_student_in_context(...)`, a pure composition API that
   runs exact context assertion before the unchanged exact identity resolver.
   Context mismatch returns no student resolution.
4. Parser failures are translated outside the internal exception scope and
   raised from `None`; tests inspect the public string, cause, context, formatted
   traceback, and parser-frame locals for source-value retention.
5. A valid LMS context with zero semantic student rows now fails closed with
   existing code `LMS_DATA_INVALID`.
6. Evidence restores all worktree-root Python FAIL rows and labels all Python
   PASS rows as app-scoped. Reports point to concrete implementation `2e23910`.
7. Optional source-session IDs are compared only when both expected and
   observed records contain an ID, matching the approved design.

No public identity status/reason set was expanded, the exact
`resolve_lms_student(expected, rows)` API remains intact, and no guardrail was
weakened.

## TDD evidence

- Identity RED: 2 failures showed mixed-identity duplicate names incorrectly
  returning `LMS_STUDENT_NAME_MATCH`; GREEN: 13 identity tests.
- Parser RED: 3 failures showed the third same-tag row missing, an empty roster
  accepted, and a retained source-derived `ValueError`; GREEN: 21 parser tests.
- Source-ID RED: 2 failures showed a missing ID on either side incorrectly
  returning `LMS_SOURCE_ID_MISMATCH`; GREEN: 13 context tests at that step.
- Composition RED: collection failed because the composition API did not yet
  exist; GREEN: 15 final context tests, including matched and mismatched flows.
- Final focused parser/context/identity suite: 49 tests passed.

## Fresh verification

| Command | Scope | Result |
|---|---|---|
| `uv run pytest` | worktree root | FAIL — `Failed to spawn: pytest`; program not found |
| `uv run ruff check .` | worktree root | FAIL — `Failed to spawn: ruff`; program not found |
| `uv run mypy src` | worktree root | FAIL — `Failed to spawn: mypy`; program not found |
| `uv run pytest` | `apps/browser-runner` | PASS — 192 tests |
| `uv run ruff check .` | `apps/browser-runner` | PASS |
| `uv run mypy src` | `apps/browser-runner` | PASS — 20 source files |
| focused guard/privacy/parser | `apps/browser-runner` | PASS — 54 tests |
| focused pending/context/identity | `apps/browser-runner` | PASS — 34 tests |
| `npm run lint` | worktree root | PASS |
| `npm run typecheck` | worktree root | PASS |
| `npm run test` | worktree root | PASS — 11 files, 46 tests |
| `npm run build` | worktree root | PASS |
| `npm run verify:no-secrets` | worktree root | PASS |
| `npm run verify:no-live-write` | worktree root | PASS |
| `npx supabase db reset` | worktree root | PASS |
| `npm run test:rls` | worktree root | PASS — 3 files, 67 assertions |

## Evidence and privacy

- Updated `V4-P4A-01`, `index.json`, `metrics.csv`, and the Phase 4A report
  only after the implementation verification above.
- Added the safe SHA-256 digest for the new same-tag synthetic fixture:
  `c0185543de2e239dc3d772b1949aa399733aa8b3a928ff79d297f9e45c4fbdcf`.
- Evidence contains no credentials, cookies, tokens, raw HTML, real student
  data, screenshots, traces, video, or HAR.
- No LMS Save/Submit/update-comment action or live browser behavior was added.

## Review and unresolved gates

- A read-only manual diff review found no remaining Critical or Important issue
  in `3976018..2e23910`.
- No independent reviewer/subagent tool was callable in this harness. The
  controller's scoped re-review is therefore still the independent review gate.
- The worktree-root Python entry points remain an environment/layout concern;
  their exact failures are preserved in both metrics and phase report.
- Live LMS verification remains BLOCKED by Phase 4A scope, not treated as PASS.

## Commit

- `2e23910` — `fix: harden phase 4a lms reader contracts`
