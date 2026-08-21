# Phase 5C Synthetic Autosave and Conflict Design

## Status

Design approved by the owner on 2026-08-14. Written-spec review is pending;
implementation has not started.

## Goal

Extend the Phase 5B synthetic review-input panel with deterministic,
revision-checked autosave behavior. The slice demonstrates how a draft is
debounced, saved to an in-memory synthetic store, and protected from stale
revision overwrites without contacting Teaching, LMS, Supabase, Gemini, or any
other remote service.

## Current context

Phase 5B already provides:

- an immutable synthetic learner fixture with explicit stable row keys;
- local attendance, learning-level, and draft-note controls;
- a fail-closed attendance readiness gate;
- no persistence, generation action, LMS mutation, or remote call.

Phase 5C changes only the local draft lifecycle. It does not make the
Phase 5B surface live or turn the synthetic draft into a production review
record.

## Scope

### Included

1. A typed synthetic draft snapshot and save-result contract.
2. An in-memory store seeded with revision `1` and immutable snapshots.
3. A 300 ms debounced autosave for local attendance, level, and note edits.
4. Optimistic revision checking that rejects stale saves without overwriting
   the newer snapshot.
5. A deterministic test-only way to inject an external revision; there is no
   production conflict-simulation control.
6. Conflict UI that preserves the local draft and requires an explicit choice.
7. Component/store tests, redacted evidence, and a Phase 5C report.

### Excluded

- Supabase tables, migrations, RPCs, Auth, RLS, Edge Functions, or network
  requests.
- Teaching/LMS browser navigation, selectors, credentials, cookies, or live
  smoke execution.
- `localStorage`, IndexedDB, browser session persistence, or file persistence.
- Gemini calls, prompt construction, review generation, approval, export, or
  delivery.
- LMS Save, Submit, comment editing, attendance writes, or any other LMS
  mutation.
- Real learner names, PII, production HTML, screenshots, tokens, or secrets.
- Automatic conflict resolution or silent overwrite.

## Data contracts

The store wraps the existing `SyntheticReviewInput` contract from Phase 5B and
continues to use `rowKey` rather than array position for identity:

```ts
export type SyntheticReviewDraftSnapshot = {
  readonly sessionKey: string;
  readonly revision: number;
  readonly inputs: readonly SyntheticReviewInput[];
};

export type CommitDraftResult =
  | {
      readonly status: "saved";
      readonly snapshot: SyntheticReviewDraftSnapshot;
    }
  | {
      readonly status: "conflict";
      readonly current: SyntheticReviewDraftSnapshot;
    };

export interface SyntheticReviewDraftStore {
  read(): SyntheticReviewDraftSnapshot;
  commitDraft(
    expectedRevision: number,
    inputs: readonly SyntheticReviewInput[],
  ): CommitDraftResult;
}
```

The default synthetic session key is stable and non-identifying, for example
`synthetic-robotics-session-3`. The seed is the Phase 5B fixture state with
revision `1`. The store clones/freezes input snapshots at its boundary so
later React mutations cannot alter a saved revision by reference.

The store has these semantics:

- `read()` returns the current immutable snapshot.
- `commitDraft(expectedRevision, inputs)` succeeds only when the expected
  revision is the current revision. The name deliberately avoids a generic
  `save(...)` method because the repository safety checker reserves that name
  for detecting prohibited LMS write paths.
- A successful save stores the new inputs and increments the revision by one.
- A stale expected revision returns `status: "conflict"` and leaves the store
  unchanged.
- A test harness may inject a newer synthetic snapshot to reproduce a conflict;
  this helper is not exposed as a production button or user workflow.

## State and data flow

```text
Phase 5B synthetic fixture
          |
          v
read immutable snapshot (revision 1)
          |
          v
local React draft edits
          |
          +--> wait 300 ms after the last edit
          |
          v
commitDraft(expectedRevision, draft)
          |
          +--> saved: revision + 1, show "Saved locally"
          |
          +--> stale: keep local draft, show conflict warning, pause retries
                         |
                         +--> Use latest version
                         |       replace local draft with current snapshot
                         |
                         +--> Keep my local draft
                                 retry against the current revision explicitly
```

Autosave is independent of the Phase 5B readiness gate: incomplete attendance,
unknown level, and empty notes may still be saved as a local draft. The gate
continues to decide only whether a future generation step would be allowed;
Phase 5C adds no generation step.

The default store lives only in JavaScript memory for the current app session.
A full page reload resets the synthetic store and is an intentional limitation.
Tests inject a fresh store so revision state cannot leak between cases.

After a conflict, automatic retries are paused until the owner chooses a
resolution. This prevents a repeated stale-save loop and makes the overwrite
choice explicit. If the owner edits while the warning is visible, the local
draft remains the source of truth until one of the two resolution actions is
chosen.

## UI behavior

The existing Phase 5B controls remain unchanged. A text status is added below
the inputs:

- `Draft pending` while the debounce timer is active;
- `Saved locally · revision N` after a successful in-memory save;
- `Conflict detected · local draft preserved` after a stale save.

The conflict message uses an accessible alert/status region and explains that a
newer synthetic revision exists. It does not display or log any real learner
data.

Only during conflict are these explicit controls shown:

- **Use latest version**: replace the local React draft with the store's current
  snapshot and clear the warning. This does not issue a remote request.
- **Keep my local draft**: save the still-local draft against the store's
  current revision. If successful, it becomes a new revision and the warning
  clears. If another revision appears first, the warning remains and the local
  draft is preserved again.

There is no button named **Save**, **Submit**, or **Generate**. The status text
must make clear that `Saved locally` means the synthetic in-memory store only,
not LMS persistence.

Accessibility requirements:

- keep real labels for every existing select and textarea;
- expose status changes through visible text and `aria-live`;
- expose the conflict warning through a semantic alert/status region;
- make both conflict actions keyboard reachable and type `button`;
- preserve the existing narrow responsive layout and focus-visible styling.

## Error and safety behavior

- A stale revision is a recoverable conflict, not a generic save failure.
- The local draft is never replaced automatically by the newer snapshot.
- A conflict response never increments the store revision.
- The explicit local-draft resolution uses a fresh current revision check; it is
  not a force-overwrite API.
- No request, credential, cookie, token, PII, or live page content is created,
  logged, or committed.
- Stable row keys remain the only learner identity mechanism.
- The Phase 5B attendance gate remains fail-closed and unchanged.

## Testing strategy

Tests follow RED -> GREEN -> REFACTOR -> VERIFY:

1. The store starts at revision `1` with the synthetic seed.
2. A save with the current revision succeeds and increments the revision.
3. A stale save returns `conflict` and does not mutate the current snapshot.
4. The UI does not autosave before 300 ms and saves after the debounce period.
5. A successful autosave renders the local revision status.
6. An injected external revision produces a conflict while preserving the
   local attendance, level, and note draft.
7. **Use latest version** adopts the current store snapshot.
8. **Keep my local draft** creates a new revision only after the explicit
   resolution action.
9. The readiness gate still blocks unknown attendance and is independent of
   autosave.
10. No Save/Submit/Generate LMS action or network/Supabase call is introduced.

Required final checks:

- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `npm run verify:no-secrets`
- `npm run verify:no-live-write`
- `git diff --check`

## Acceptance criteria

- Editing a synthetic review input schedules one debounced local autosave.
- A successful save increments the displayed revision.
- A stale save leaves the local draft untouched and shows a visible conflict
  warning.
- The owner must explicitly choose the latest snapshot or keep the local draft.
- Keeping the local draft succeeds only through a fresh revision-checked save.
- A full reload reset is documented; no browser or remote persistence exists.
- Existing Phase 5A/5B curriculum, session, mapping, and readiness behavior
  remains green.
- Evidence contains only synthetic counts, revisions, status/reason codes,
  command results, and explicit limitations.

## Deferred work

- Persistent review-input schema and RLS.
- Live Teaching/LMS extraction and any real identity mapping.
- Cross-tab synchronization and durable reload recovery.
- Generation, redaction, approval, export, and delivery.
- Production multi-user conflict resolution policy.

## References

- `docs/spec/KE_HOACH_MVP_BOT_NHAN_XET_MINDX_V4_BROWSER_USE_SUPABASE.md`
- `docs/superpowers/specs/2026-08-13-phase5-synthetic-curriculum-session-design.md`
- `docs/superpowers/specs/2026-08-13-phase5b-synthetic-review-inputs-design.md`
