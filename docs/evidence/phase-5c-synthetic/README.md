# Phase 5C synthetic autosave/conflict evidence

- Date: 2026-08-14
- Worktree: `E:\mindx-review-bot\.worktrees\phase5c-synthetic-autosave-conflict`
- Branch: `codex/phase5c-synthetic-autosave-conflict`
- Implementation commits: `1c9fc6a`, `fa4d77b`, `1ba31f7`
- Scope: synthetic in-memory revision store and local review-input UI only.

## Synthetic inventory

The existing Phase 5B fixture remains the only learner source:

| Stable row key | Display label |
| --- | --- |
| `synthetic-review-001` | `Synthetic learner 01` |
| `synthetic-review-002` | `Synthetic learner 02` |
| `synthetic-review-003` | `Synthetic learner 03` |

The default synthetic session key is `synthetic-robotics-session-3`. The draft
store starts at revision `1` and keeps immutable snapshots keyed by `rowKey`.

## TDD evidence

| Behavior | RED evidence | GREEN evidence |
| --- | --- | --- |
| Revision store | `npx vitest run src/reviewInputs/syntheticDraftStore.test.ts` failed because `./syntheticDraftStore` was missing; 0 tests ran. | Same suite passed with 3 tests. |
| 300 ms autosave | `npx vitest run src/App.test.tsx` failed on 3 new autosave expectations while 12 existing tests passed. | Focused suite passed with 20 tests after Task 2; final App suite passed with 18 tests. |
| Conflict preservation/resolution | `npx vitest run src/App.test.tsx` failed on 3 conflict expectations while 15 tests passed. | Final focused suite passed with 23 tests; full suite passed with 99 tests. |

## Deterministic scenarios

- Normal commit: seed revision `1` → local edit → one commit at revision `2`.
- Stale commit: an injected external synthetic revision becomes `2`; the
  local commit using expected revision `1` returns `conflict` and leaves the
  external snapshot unchanged.
- Latest-version choice: the UI explicitly adopts the current revision `2`.
- Local-draft choice: the UI explicitly commits the preserved local draft
  against current revision `2`, producing revision `3`.
- While conflict is unresolved, later local edits remain visible and do not
  trigger automatic retries.

## Manual local UI checks

Target: local Vite page at `http://127.0.0.1:5173/`. No Teaching or LMS page
was opened.

| Check | Observed result |
| --- | --- |
| Initial state | `Synthetic review inputs` is visible; attendance gate is blocked; status is `Saved locally · revision 1`. |
| Debounced edit | Editing a synthetic note immediately shows `Draft pending`; after 350 ms the status is `Saved locally · revision 2`. |
| Bulk attendance | `Mark all present` sets all three attendance controls to `present`; the gate says `Generation ready: attendance complete`; after 350 ms status is revision `3`. |
| Narrow viewport | At `560 x 900`, the review grid has one computed column; `innerWidth=560`, `scrollWidth=545`, and horizontal overflow is false. |
| Prohibited actions | The rendered button labels contain no Save, Submit, or Generate action. The only review-input action is `Mark all present`. |
| Conflict simulation | Not exposed in production UI; verified through the injected-store component tests as designed. |

## Final verification

| Command | Exit | Result |
| --- | ---: | --- |
| `npm run lint` | 0 | PASS |
| `npm run typecheck` | 0 | PASS |
| `npm run test` | 0 | PASS - 18 test files, 99 tests |
| `npm run build` | 0 | PASS - Vite production bundle built, 23 modules transformed |
| `npm run verify:no-secrets` | 0 | PASS - secrets check passed |
| `npm run verify:no-live-write` | 0 | PASS - live LMS write check passed |
| `git diff --check` | 0 | PASS - clean result |

## Safety boundary and limitations

- All draft rows and revisions are synthetic.
- Storage is JavaScript memory only; a full page reload resets the store.
- No Teaching, LMS, Supabase, Auth, Gemini, network, browser storage, file
  persistence, credential, cookie, token, secret, PII, or live page content was
  used or logged.
- No LMS attendance write, comment mutation, Save, Submit, Generate, export,
  delivery, or automatic messaging path was added.
- The revision store is not a production persistence or multi-user conflict
  policy. This evidence verifies only the local synthetic Phase 5C slice.
