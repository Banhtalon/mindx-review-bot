# Phase 4B — Manual Mapping and Session/Context Fallback Design

## Status

Approved synthetic UI direction. This phase remains read-only and does not
claim live LMS access or production persistence.

## Goal

Give the owner a deterministic review checkpoint after the Phase 4A LMS reader:
verify the expected and observed session context, resolve ambiguous roster rows
manually, and block downstream work until every identity is safe.

## Scope

Phase 4B includes:

- a synthetic pending-session review screen;
- exact class, session, date, and time comparison in the web client;
- explicit `matched` and `manual_fallback` context states;
- a roster table showing stable signals, attendance, and mapping status;
- local manual mapping for synthetic internal students;
- a fail-closed continue gate when context or identity is unresolved;
- keyboard-accessible controls and responsive layout;
- tests and redacted evidence for the UI contract.

Phase 4B does not include:

- Supabase persistence or migrations;
- real LMS credentials, cookies, selectors, or production URLs;
- Browser Use live execution;
- Gemini generation, LMS Save/Submit, comments, or Zalo delivery;
- fuzzy matching, row-order matching, or automatic guesses.

## Design

### 1. Deterministic review contract

`src/lms/manualMapping.ts` owns pure review functions and types:

- `assertLmsContext(expected, observed)` compares normalized class code and
  exact session/date/time fields and returns a safe reason code;
- `getMappingStatus(row, assignments)` returns `resolved`, `unresolvable`, or
  `ambiguous` without looking at row position;
- `canContinueReview(contextAssertion, rows)` returns true only when context
  matches and every roster row is resolved;
- `assignStudent(assignments, rowKey, internalId)` returns a new immutable
  assignment map after validating the synthetic IDs.

The UI supplies only synthetic fixtures. The contract carries IDs and safe
reason codes, not raw HTML or credentials.

### 2. Owner-facing flow

1. The owner selects an eligible synthetic pending session.
2. The screen compares expected Teaching context with observed LMS context.
3. A mismatch displays `manual_fallback`, the mismatch reason, and disables
   continuation; it never silently accepts the observed page.
4. With a matching context, the roster table shows stable LMS signals and
   attendance. Resolved rows are read-only; unresolved/ambiguous rows expose a
   native select for explicit owner mapping.
5. The continue action stays disabled until all rows are resolved. All state is
   local to the screen and disappears on reload.

### 3. Safety and privacy

- The page is labeled synthetic/read-only.
- No network request is added by this phase.
- No action is named or wired as Save, Submit, update-comment, or delivery.
- Fixtures use synthetic names and identifiers only.
- Context failure and identity ambiguity are visible states, never fallback
  guesses.

### 4. Verification

The phase must prove:

- exact context match succeeds;
- class/session/date/time mismatch produces manual fallback;
- near-equal names are not automatically matched;
- row reordering does not change mapping;
- explicit selections resolve only the selected row;
- continuation remains blocked for unresolved rows and mismatched context;
- keyboard controls expose labels and the old LMS-write guard text remains;
- lint, typecheck, web tests, build, no-secrets, and no-live-write pass.

## Acceptance

The Phase 4B exit evidence is synthetic-only and records the local UI contract
as PASS. Live LMS selectors, credentials, browser-state reuse, timing, and
production persistence remain BLOCKED.
