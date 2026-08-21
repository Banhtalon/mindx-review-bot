# Phase 5C Synthetic Autosave and Conflict Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 300 ms revision-checked autosave and explicit conflict resolution to the existing synthetic review-input panel using only an in-memory store.

**Architecture:** A focused synchronous store owns immutable synthetic draft snapshots and performs optimistic revision checks. The existing React review-input surface keeps the editable local draft, schedules debounced commits, pauses after a conflict, and requires the owner to adopt the latest snapshot or explicitly keep the local draft. The entire slice remains synthetic and has no network, Supabase, browser storage, LMS mutation, or generation path.

**Tech Stack:** TypeScript 6 strict mode, React 19 hooks, Vite 8, Vitest 4 fake timers, Testing Library, existing CSS and safety scripts.

## Global Constraints

- Phase 5C operates only on the three existing `Synthetic learner 01/02/03` fixtures and stable `rowKey` values. Never add real learner names, Teaching/LMS payloads, credentials, cookies, tokens, secrets, or PII.
- The draft store is in-memory only. Do not add Supabase, Auth, migrations, RPCs, RLS, Edge Functions, `fetch`, API clients, `localStorage`, IndexedDB, files, or browser-session persistence.
- A full page reload resets the synthetic store. Do not claim durable persistence or cross-tab synchronization.
- Debounce is exactly `300` milliseconds after the latest edit. Initial render must not create a new revision.
- The store starts at revision `1`; a successful `commitDraft(expectedRevision, inputs)` increments once; a stale revision returns a conflict and does not mutate the store.
- Do not implement a generic `save(...)` or `submit(...)` method. `scripts/verify_no_live_write.mjs` reserves those names for prohibited LMS-write detection; use `commitDraft(...)` exactly.
- Do not render buttons named Save, Submit, or Generate. Conflict actions are exactly **Use latest version** and **Keep my local draft**.
- On conflict, preserve the current local draft, pause automatic retries, and require an explicit resolution action. Never silently overwrite either version.
- Autosave is independent of generation readiness. Unknown attendance remains fail-closed for the existing gate but is still valid draft content to commit locally.
- Use immutable copies keyed by `rowKey`; never infer learner identity from array position.
- Add no package dependency and do not refactor unrelated Phase 5 curriculum, session, mapping, security, Supabase, or runner code.
- Keep evidence synthetic and aggregate-only. Do not commit raw terminal dumps, Vite build output, screenshots containing live data, or generated runner artifacts.
- Execute implementation in an isolated worktree created with `superpowers:using-git-worktrees`; use branch `codex/phase5c-synthetic-autosave-conflict` unless Qq explicitly selects another name.
- Every behavior follows RED -> GREEN -> REFACTOR -> VERIFY. Record the failing and passing command outcome before claiming completion.

---

## File Map

| File | Responsibility |
| --- | --- |
| `src/reviewInputs/contracts.ts` | Add immutable draft snapshot, commit result, and store interface types. |
| `src/reviewInputs/syntheticDraftStore.ts` | Synchronous in-memory revision store, deep snapshot copies, optimistic conflict result, and test-only external revision injection. |
| `src/reviewInputs/syntheticDraftStore.test.ts` | Unit tests for revision `1`, immutable snapshots, successful commit, and stale conflict behavior. |
| `src/App.tsx` | Inject/store the synthetic draft, debounce commits, render statuses, preserve local state on conflict, and implement explicit resolution actions. |
| `src/App.test.tsx` | Fake-timer UI tests for 300 ms autosave, readiness independence, conflict preservation, both resolution choices, and absence of network/prohibited actions. |
| `src/styles.css` | Local autosave status, conflict alert/action layout, focus visibility, and narrow-screen behavior. |
| `docs/evidence/phase-5c-synthetic/README.md` | RED/GREEN evidence, synthetic revision scenarios, manual UI observations, command results, and safety boundary. |
| `docs/phase-reports/phase-5c-synthetic.md` | Concise delivered scope, verification totals, limitations, and exit assessment. |

## Task 1: Build the Immutable Revision Store

**Files:**

- Modify: `src/reviewInputs/contracts.ts`
- Create: `src/reviewInputs/syntheticDraftStore.ts`
- Create: `src/reviewInputs/syntheticDraftStore.test.ts`

**Interfaces:**

- Consumes: `SyntheticReviewInput` from `src/reviewInputs/contracts.ts` and `createInitialReviewInputs(PHASE5B_SYNTHETIC_LEARNERS)` from `src/fixtures/phase5bReviewInputs.ts`.
- Produces: `SyntheticReviewDraftSnapshot`, `CommitDraftResult`, `SyntheticReviewDraftStore`, and `InMemorySyntheticReviewDraftStore` with `read()`, `commitDraft(...)`, and `injectExternalRevisionForTest(...)`.

- [ ] **Step 1: Write the failing store tests.**

  Create `src/reviewInputs/syntheticDraftStore.test.ts` with these concrete cases:

  ```ts
  import { describe, expect, it } from "vitest";

  import {
    createInitialReviewInputs,
    PHASE5B_SYNTHETIC_LEARNERS,
  } from "../fixtures/phase5bReviewInputs";
  import { InMemorySyntheticReviewDraftStore } from "./syntheticDraftStore";

  const createStore = () =>
    new InMemorySyntheticReviewDraftStore(
      "synthetic-robotics-session-3",
      createInitialReviewInputs(PHASE5B_SYNTHETIC_LEARNERS),
    );

  describe("InMemorySyntheticReviewDraftStore", () => {
    it("starts at revision one with an immutable synthetic snapshot", () => {
      const snapshot = createStore().read();

      expect(snapshot.sessionKey).toBe("synthetic-robotics-session-3");
      expect(snapshot.revision).toBe(1);
      expect(snapshot.inputs).toHaveLength(3);
      expect(Object.isFrozen(snapshot)).toBe(true);
      expect(Object.isFrozen(snapshot.inputs)).toBe(true);
      expect(snapshot.inputs.every(Object.isFrozen)).toBe(true);
    });

    it("commits against the current revision and increments exactly once", () => {
      const store = createStore();
      const changed = store.read().inputs.map((input) =>
        input.rowKey === "synthetic-review-001"
          ? { ...input, attendance: "present" as const }
          : input,
      );

      const result = store.commitDraft(1, changed);

      expect(result.status).toBe("saved");
      expect(store.read().revision).toBe(2);
      expect(store.read().inputs[0].attendance).toBe("present");
    });

    it("rejects a stale revision without replacing the current snapshot", () => {
      const store = createStore();
      const external = store.read().inputs.map((input) =>
        input.rowKey === "synthetic-review-001"
          ? { ...input, noteDraft: "External synthetic revision" }
          : input,
      );
      store.injectExternalRevisionForTest(external);

      const staleLocal = store.read().inputs.map((input) =>
        input.rowKey === "synthetic-review-001"
          ? { ...input, noteDraft: "Stale local synthetic draft" }
          : input,
      );
      const result = store.commitDraft(1, staleLocal);

      expect(result).toMatchObject({ status: "conflict" });
      expect(store.read().revision).toBe(2);
      expect(store.read().inputs[0].noteDraft).toBe("External synthetic revision");
    });
  });
  ```

- [ ] **Step 2: Prove RED.**

  Run: `npx vitest run src/reviewInputs/syntheticDraftStore.test.ts`

  Expected: FAIL because `./syntheticDraftStore` and its exported class do not exist.

- [ ] **Step 3: Add the draft contracts.**

  Append these exact exports to `src/reviewInputs/contracts.ts`:

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

- [ ] **Step 4: Implement the minimal in-memory store.**

  Create `src/reviewInputs/syntheticDraftStore.ts` with a private immutable-copy boundary and this public class shape:

  ```ts
  import type {
    CommitDraftResult,
    SyntheticReviewDraftSnapshot,
    SyntheticReviewDraftStore,
    SyntheticReviewInput,
  } from "./contracts";

  function freezeInputs(
    inputs: readonly SyntheticReviewInput[],
  ): readonly SyntheticReviewInput[] {
    return Object.freeze(inputs.map((input) => Object.freeze({ ...input })));
  }

  function freezeSnapshot(
    sessionKey: string,
    revision: number,
    inputs: readonly SyntheticReviewInput[],
  ): SyntheticReviewDraftSnapshot {
    return Object.freeze({
      sessionKey,
      revision,
      inputs: freezeInputs(inputs),
    });
  }

  export class InMemorySyntheticReviewDraftStore
    implements SyntheticReviewDraftStore
  {
    private snapshot: SyntheticReviewDraftSnapshot;

    constructor(
      sessionKey: string,
      inputs: readonly SyntheticReviewInput[],
    ) {
      this.snapshot = freezeSnapshot(sessionKey, 1, inputs);
    }

    read(): SyntheticReviewDraftSnapshot {
      return this.snapshot;
    }

    commitDraft(
      expectedRevision: number,
      inputs: readonly SyntheticReviewInput[],
    ): CommitDraftResult {
      if (expectedRevision !== this.snapshot.revision) {
        return { status: "conflict", current: this.snapshot };
      }

      this.snapshot = freezeSnapshot(
        this.snapshot.sessionKey,
        this.snapshot.revision + 1,
        inputs,
      );
      return { status: "saved", snapshot: this.snapshot };
    }

    injectExternalRevisionForTest(
      inputs: readonly SyntheticReviewInput[],
    ): SyntheticReviewDraftSnapshot {
      this.snapshot = freezeSnapshot(
        this.snapshot.sessionKey,
        this.snapshot.revision + 1,
        inputs,
      );
      return this.snapshot;
    }
  }
  ```

  Keep `injectExternalRevisionForTest` off the `SyntheticReviewDraftStore` interface so production UI code cannot depend on conflict simulation.

- [ ] **Step 5: Prove GREEN and run focused static checks.**

  Run:

  ```powershell
  npx vitest run src/reviewInputs/syntheticDraftStore.test.ts
  npm run typecheck
  npm run verify:no-live-write
  git diff --check
  ```

  Expected: all three store tests pass; typecheck, LMS-write safety, and whitespace checks exit `0`.

- [ ] **Step 6: Commit the store deliverable.**

  Run:

  ```powershell
  git add -- src/reviewInputs/contracts.ts src/reviewInputs/syntheticDraftStore.ts src/reviewInputs/syntheticDraftStore.test.ts
  git commit -m "feat: add synthetic revision draft store"
  ```

## Task 2: Add 300 ms Synthetic Autosave

**Files:**

- Modify: `src/App.tsx`
- Modify: `src/App.test.tsx`
- Modify: `src/styles.css`

**Interfaces:**

- Consumes: `SyntheticReviewDraftStore.commitDraft(expectedRevision, inputs): CommitDraftResult` and `InMemorySyntheticReviewDraftStore` from Task 1.
- Produces: an injectable `Phase5BReviewInputSurface` that starts at revision `1`, displays `Draft pending`, commits after 300 ms, and displays `Saved locally · revision N` without changing the existing attendance gate.

- [ ] **Step 1: Add failing fake-timer autosave tests.**

  Update the test imports in `src/App.test.tsx`:

  ```ts
  import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
  import { afterEach, describe, expect, it, vi } from "vitest";
  import App, { Phase5BReviewInputSurface, Phase5ContextSurface } from "./App";
  import {
    createInitialReviewInputs,
    PHASE5B_SYNTHETIC_LEARNERS,
  } from "./fixtures/phase5bReviewInputs";
  import { InMemorySyntheticReviewDraftStore } from "./reviewInputs/syntheticDraftStore";
  ```

  Replace the existing cleanup hook with:

  ```ts
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });
  ```

  Add a local test factory and two tests inside `describe("Synthetic review inputs", ...)`:

  ```ts
  const createDraftStore = () =>
    new InMemorySyntheticReviewDraftStore(
      "synthetic-robotics-session-3",
      createInitialReviewInputs(PHASE5B_SYNTHETIC_LEARNERS),
    );

  it("commits the latest synthetic edit only after 300 milliseconds", () => {
    vi.useFakeTimers();
    const store = createDraftStore();
    render(<Phase5BReviewInputSurface store={store} />);

    fireEvent.change(
      screen.getByRole("textbox", { name: "Synthetic learner 01 draft note" }),
      { target: { value: "Local synthetic autosave note" } },
    );

    expect(screen.getByText("Draft pending")).toBeVisible();
    expect(store.read().revision).toBe(1);

    act(() => vi.advanceTimersByTime(299));
    expect(store.read().revision).toBe(1);

    act(() => vi.advanceTimersByTime(1));
    expect(store.read().revision).toBe(2);
    expect(store.read().inputs[0].noteDraft).toBe("Local synthetic autosave note");
    expect(screen.getByText("Saved locally · revision 2")).toBeVisible();
  });

  it("commits incomplete attendance without opening the generation gate", () => {
    vi.useFakeTimers();
    const store = createDraftStore();
    render(<Phase5BReviewInputSurface store={store} />);

    fireEvent.change(
      screen.getByRole("combobox", { name: "Synthetic learner 01 level" }),
      { target: { value: "developing" } },
    );
    act(() => vi.advanceTimersByTime(300));

    expect(store.read().revision).toBe(2);
    expect(screen.getByText("Generation blocked: attendance unknown")).toBeVisible();
    expect(screen.getByText("Saved locally · revision 2")).toBeVisible();
  });

  it("does not issue a network request while committing a synthetic draft", () => {
    vi.useFakeTimers();
    const requestSpy = vi.fn();
    vi.stubGlobal("fetch", requestSpy);
    const store = createDraftStore();
    render(<Phase5BReviewInputSurface store={store} />);

    fireEvent.change(
      screen.getByRole("textbox", { name: "Synthetic learner 02 draft note" }),
      { target: { value: "Synthetic local-only note" } },
    );
    act(() => vi.advanceTimersByTime(300));

    expect(requestSpy).not.toHaveBeenCalled();
    expect(store.read().revision).toBe(2);
  });
  ```

- [ ] **Step 2: Prove RED.**

  Run: `npx vitest run src/App.test.tsx`

  Expected: FAIL because `Phase5BReviewInputSurface` has no `store` prop, no debounce effect, and no local revision status.

- [ ] **Step 3: Add injected-store initialization and autosave state.**

  In `src/App.tsx`, import `useEffect`, the store contract, and concrete store:

  ```ts
  import { useCallback, useEffect, useMemo, useState } from "react";
  import type {
    CommitDraftResult,
    SyntheticReviewDraftSnapshot,
    SyntheticReviewDraftStore,
  } from "./reviewInputs/contracts";
  import { InMemorySyntheticReviewDraftStore } from "./reviewInputs/syntheticDraftStore";
  ```

  Extend the existing props and initialize one store/snapshot per component mount:

  ```ts
  type Phase5BReviewInputSurfaceProps = {
    readonly learners?: readonly SyntheticLearner[];
    readonly store?: SyntheticReviewDraftStore;
  };

  type DraftCommitStatus = "saved" | "pending" | "conflict";

  export function Phase5BReviewInputSurface({
    learners = PHASE5B_SYNTHETIC_LEARNERS,
    store: suppliedStore,
  }: Phase5BReviewInputSurfaceProps) {
    const [draftStore] = useState<SyntheticReviewDraftStore>(() =>
      suppliedStore ??
      new InMemorySyntheticReviewDraftStore(
        "synthetic-robotics-session-3",
        createInitialReviewInputs(learners),
      ),
    );
    const [initialSnapshot] = useState(() => draftStore.read());
    const [inputs, setInputs] = useState<readonly SyntheticReviewInput[]>(
      initialSnapshot.inputs,
    );
    const [revision, setRevision] = useState(initialSnapshot.revision);
    const [commitStatus, setCommitStatus] =
      useState<DraftCommitStatus>("saved");
    const [conflictSnapshot, setConflictSnapshot] =
      useState<SyntheticReviewDraftSnapshot | null>(null);
  ```

  Add one result handler and the 300 ms effect inside the component:

  ```ts
  const applyCommitResult = useCallback((result: CommitDraftResult) => {
    if (result.status === "saved") {
      setRevision(result.snapshot.revision);
      setConflictSnapshot(null);
      setCommitStatus("saved");
      return;
    }

    setConflictSnapshot(result.current);
    setCommitStatus("conflict");
  }, []);

  useEffect(() => {
    if (commitStatus !== "pending") return;

    const timeoutId = window.setTimeout(() => {
      applyCommitResult(draftStore.commitDraft(revision, inputs));
    }, 300);

    return () => window.clearTimeout(timeoutId);
  }, [applyCommitResult, commitStatus, draftStore, inputs, revision]);
  ```

  In both `updateInput` and `markAllPresent`, mark the draft pending after the immutable `rowKey` update. Preserve conflict pause for Task 3:

  ```ts
  function markPendingUnlessConflicted() {
    setCommitStatus((current) => (current === "conflict" ? current : "pending"));
  }
  ```

  Replace the existing edit helpers with this exact sequencing. Do not call the
  pending helper during initialization, so initial render remains revision `1`:

  ```ts
  function updateInput(rowKey: string, patch: ReviewInputPatch) {
    setInputs((current) =>
      current.map((input) =>
        input.rowKey === rowKey ? { ...input, ...patch } : input,
      ),
    );
    markPendingUnlessConflicted();
  }

  function markAllPresent() {
    setInputs((current) =>
      current.map((input) => ({ ...input, attendance: "present" as const })),
    );
    markPendingUnlessConflicted();
  }
  ```

- [ ] **Step 4: Render the local status without adding a write action.**

  Add this status block after the existing generation gate and before the learner list:

  ```tsx
  <div className={`review-draft-status ${commitStatus}`} role="status" aria-live="polite">
    <strong>
      {commitStatus === "pending"
        ? "Draft pending"
        : commitStatus === "conflict"
          ? "Autosave paused"
          : `Saved locally · revision ${revision}`}
    </strong>
    <span>Synthetic in-memory draft only. A full reload resets it.</span>
  </div>
  ```

  Update the existing panel description so it says the values are committed only to synthetic browser memory and still reset on full reload. Do not add a Save/Submit/Generate button.

- [ ] **Step 5: Add status styles.**

  Add these scoped rules in `src/styles.css` after `.review-input-gate.ready`:

  ```css
  .review-draft-status {
    display: grid;
    gap: 0.2rem;
    margin-bottom: 1rem;
    border-left: 4px solid #18794e;
    padding: 0.7rem 0.8rem;
    color: #17633f;
    background: #eefaf4;
    font-size: 0.82rem;
  }

  .review-draft-status.pending {
    border-left-color: #1769e0;
    color: #174b9b;
    background: #eef5ff;
  }

  .review-draft-status.conflict {
    border-left-color: #b42318;
    color: #8f1d14;
    background: #fff1f0;
  }
  ```

- [ ] **Step 6: Prove GREEN and run related regression checks.**

  Run:

  ```powershell
  npx vitest run src/App.test.tsx src/reviewInputs/syntheticDraftStore.test.ts src/reviewInputs/gate.test.ts
  npm run typecheck
  npm run verify:no-secrets
  npm run verify:no-live-write
  git diff --check
  ```

  Expected: focused tests pass; status changes from pending to revision `2` only after 300 ms; the existing attendance gate remains unchanged; all checks exit `0`.

- [ ] **Step 7: Commit the autosave deliverable.**

  Run:

  ```powershell
  git add -- src/App.tsx src/App.test.tsx src/styles.css
  git commit -m "feat: autosave synthetic review drafts"
  ```

## Task 3: Preserve and Resolve Revision Conflicts

**Files:**

- Modify: `src/App.tsx`
- Modify: `src/App.test.tsx`
- Modify: `src/styles.css`

**Interfaces:**

- Consumes: the `conflictSnapshot` captured from `CommitDraftResult`, `draftStore.read()`, and `draftStore.commitDraft(...)` from Tasks 1-2.
- Produces: accessible conflict warning with **Use latest version** and **Keep my local draft**, both preserving optimistic revision checks.

- [ ] **Step 1: Add a reusable conflict setup and three failing UI tests.**

  In `src/App.test.tsx`, add this helper inside the synthetic-review describe block:

  ```ts
  function createConflictScenario() {
    vi.useFakeTimers();
    const store = createDraftStore();
    render(<Phase5BReviewInputSurface store={store} />);

    const note = screen.getByRole("textbox", {
      name: "Synthetic learner 01 draft note",
    });
    fireEvent.change(note, { target: { value: "Preserve this local draft" } });

    const external = store.read().inputs.map((input) =>
      input.rowKey === "synthetic-review-001"
        ? { ...input, noteDraft: "Latest external synthetic draft" }
        : input,
    );
    store.injectExternalRevisionForTest(external);
    act(() => vi.advanceTimersByTime(300));

    return { note, store };
  }
  ```

  Add these tests:

  ```ts
  it("preserves the local draft and pauses automatic retries on conflict", () => {
    const { note, store } = createConflictScenario();

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Conflict detected · local draft preserved",
    );
    expect(note).toHaveValue("Preserve this local draft");
    expect(store.read().revision).toBe(2);

    fireEvent.change(note, { target: { value: "Edited while conflict remains" } });
    act(() => vi.advanceTimersByTime(600));

    expect(store.read().revision).toBe(2);
    expect(note).toHaveValue("Edited while conflict remains");
  });

  it("adopts the latest snapshot only after the explicit latest-version action", () => {
    const { note, store } = createConflictScenario();

    fireEvent.click(screen.getByRole("button", { name: "Use latest version" }));

    expect(note).toHaveValue("Latest external synthetic draft");
    expect(store.read().revision).toBe(2);
    expect(screen.getByText("Saved locally · revision 2")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("commits the preserved local draft as a new checked revision", () => {
    const { note, store } = createConflictScenario();

    fireEvent.click(screen.getByRole("button", { name: "Keep my local draft" }));

    expect(note).toHaveValue("Preserve this local draft");
    expect(store.read().revision).toBe(3);
    expect(store.read().inputs[0].noteDraft).toBe("Preserve this local draft");
    expect(screen.getByText("Saved locally · revision 3")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
  ```

- [ ] **Step 2: Prove RED.**

  Run: `npx vitest run src/App.test.tsx`

  Expected: FAIL because the alert and explicit conflict-resolution controls do not exist.

- [ ] **Step 3: Implement both explicit resolution handlers.**

  Add these handlers inside `Phase5BReviewInputSurface`:

  ```ts
  function useLatestVersion() {
    const latest = draftStore.read();
    setInputs(latest.inputs);
    setRevision(latest.revision);
    setConflictSnapshot(null);
    setCommitStatus("saved");
  }

  function keepLocalDraft() {
    const latest = draftStore.read();
    applyCommitResult(draftStore.commitDraft(latest.revision, inputs));
  }
  ```

  `useLatestVersion()` must read at click time rather than using a possibly stale captured snapshot. `keepLocalDraft()` must commit against the current revision; do not add a force-overwrite method.

- [ ] **Step 4: Render the accessible conflict alert.**

  Immediately after the draft-status block, render only when `conflictSnapshot !== null`:

  ```tsx
  {conflictSnapshot ? (
    <div className="review-draft-conflict" role="alert">
      <strong>Conflict detected · local draft preserved</strong>
      <p>
        Synthetic revision {conflictSnapshot.revision} is newer. Choose which
        draft to continue with; nothing is written to Teaching or LMS.
      </p>
      <div className="review-draft-conflict-actions">
        <button className="secondary-button" type="button" onClick={useLatestVersion}>
          Use latest version
        </button>
        <button className="secondary-button" type="button" onClick={keepLocalDraft}>
          Keep my local draft
        </button>
      </div>
    </div>
  ) : null}
  ```

  Keep `conflictSnapshot` as the signal that resolution is required. Local attendance, level, and note controls remain editable during conflict; `markPendingUnlessConflicted()` keeps automatic commits paused.

- [ ] **Step 5: Style the warning and responsive actions.**

  Add these rules near the other review-input styles:

  ```css
  .review-draft-conflict {
    display: grid;
    gap: 0.65rem;
    margin-bottom: 1rem;
    border: 1px solid #e29a93;
    border-radius: 0.65rem;
    padding: 0.85rem;
    color: #8f1d14;
    background: #fff7f6;
  }

  .review-draft-conflict p {
    margin: 0;
  }

  .review-draft-conflict-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
  }
  ```

  Add this exact addition inside the existing `@media (max-width: 44rem)` block:

  ```css
  .review-draft-conflict-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .review-draft-conflict-actions .secondary-button {
    width: 100%;
  }
  ```

  Preserve the existing focus-visible styling for `.secondary-button`.

- [ ] **Step 6: Prove GREEN, then verify no prohibited path appeared.**

  Run:

  ```powershell
  npx vitest run src/App.test.tsx src/reviewInputs/syntheticDraftStore.test.ts
  npm run typecheck
  npm run verify:no-secrets
  npm run verify:no-live-write
  git diff --check
  ```

  Expected: conflict tests pass; local drafts survive stale commits; explicit latest/preserved choices produce revisions `2` and `3` respectively; all safety checks exit `0`.

- [ ] **Step 7: Commit the conflict deliverable.**

  Run:

  ```powershell
  git add -- src/App.tsx src/App.test.tsx src/styles.css
  git commit -m "feat: resolve synthetic draft conflicts"
  ```

## Task 4: Record Evidence and Verify the Complete Phase 5C Slice

**Files:**

- Create: `docs/evidence/phase-5c-synthetic/README.md`
- Create: `docs/phase-reports/phase-5c-synthetic.md`
- Review: every source/test/style file listed in the File Map

**Interfaces:**

- Consumes: final Task 1-3 behavior and actual command output from the isolated worktree.
- Produces: reproducible aggregate evidence and an explicit synthetic-only Phase 5C assessment; it does not create a live-integration claim.

- [ ] **Step 1: Run the focused behavior suites before writing outcomes.**

  Run:

  ```powershell
  npx vitest run src/reviewInputs/syntheticDraftStore.test.ts src/reviewInputs/gate.test.ts src/App.test.tsx
  ```

  Expected: PASS. Record the actual file/test totals from this run; do not predict or copy prior Phase 5B totals.

- [ ] **Step 2: Inspect the synthetic UI locally.**

  Run: `npm run dev -- --host 127.0.0.1`

  At the printed local Vite URL, verify only the synthetic page:

  - initial status is `Saved locally · revision 1` and the attendance gate remains blocked;
  - one edit immediately shows `Draft pending`, then `Saved locally · revision 2` after the debounce;
  - `Mark all present` still opens the readiness gate;
  - at a `560 x 900` viewport, inputs and status blocks fit without horizontal overflow;
  - there is no Save, Submit, Generate, LMS-write, or remote action.

  Do not open Teaching/LMS. Conflict resolution is verified by deterministic injected-store tests because the approved design intentionally provides no production conflict-simulation button.

- [ ] **Step 3: Create the evidence record using actual results.**

  In `docs/evidence/phase-5c-synthetic/README.md`, include these sections and fill them only with observed aggregate results:

  ```markdown
  # Phase 5C synthetic autosave/conflict evidence

  ## Scope
  Synthetic in-memory revision store and local review-input UI only.

  ## TDD evidence
  | Behavior | RED command/result | GREEN command/result |
  | --- | --- | --- |
  | Revision store | Record the nonzero exit and missing-module/class failure from Task 1 Step 2. | Record exit `0` and the actual passing test total from Task 1 Step 5. |
  | 300 ms autosave | Record the failing prop/status/debounce assertions from Task 2 Step 2. | Record exit `0` and the actual passing test total from Task 2 Step 6. |
  | Conflict preservation/resolution | Record the missing alert/action failures from Task 3 Step 2. | Record exit `0` and the actual passing test total from Task 3 Step 6. |

  ## Deterministic scenarios
  Record revisions 1 -> 2 for a normal commit, stale revision conflict with no
  mutation, latest-version adoption, and explicit local-draft revision 2 -> 3.

  ## Manual synthetic UI checks
  Record initial, pending, committed, readiness, and 560 x 900 observations.

  ## Final verification
  Record command, exit code, and aggregate result for every required gate.

  ## Safety boundary
  State that no Teaching/LMS/Supabase/Gemini/network/storage/PII/secret/write
  path was used and that reload intentionally resets the in-memory store.
  ```

  Use only the observed command result and aggregate test counts. Do not copy raw
  terminal output or invent a result that was not observed.

- [ ] **Step 4: Create the phase report.**

  In `docs/phase-reports/phase-5c-synthetic.md`, summarize:

  - the 300 ms synthetic autosave and revision contract;
  - conflict preservation and both explicit choices;
  - attendance-gate independence;
  - actual final command/test totals;
  - no backend/network/browser storage and reload reset;
  - PASS only for this synthetic slice, not live Teaching/LMS integration.

- [ ] **Step 5: Run every required project gate from the final implementation commit.**

  Run each command separately so one failure does not hide later evidence:

  ```powershell
  npm run lint
  npm run typecheck
  npm run test
  npm run build
  npm run verify:no-secrets
  npm run verify:no-live-write
  git diff --check
  git status --short
  ```

  Expected: all commands exit `0`; only the two evidence/report files are uncommitted at this point. If any command fails, use `superpowers:systematic-debugging`, record the real failure, and do not claim completion.

- [ ] **Step 6: Self-review the complete Phase 5C diff.**

  Run:

  ```powershell
  git diff --check main...HEAD
  git diff --stat main...HEAD
  git diff main...HEAD -- src/reviewInputs src/App.tsx src/App.test.tsx src/styles.css docs/evidence/phase-5c-synthetic docs/phase-reports/phase-5c-synthetic.md
  ```

  Confirm all of the following from the diff:

  - no imported network, Supabase, storage, browser automation, Gemini, or live-data dependency;
  - no generic `save(...)`/`submit(...)` function and no Save/Submit/Generate button;
  - initial render does not create revision `2`;
  - all edits remain keyed by explicit `rowKey`;
  - conflict leaves store and local draft unchanged until an explicit choice;
  - `Use latest version` reads the latest snapshot at click time;
  - `Keep my local draft` uses a fresh revision-checked `commitDraft`;
  - existing Phase 5 curriculum/session/mapping/readiness behavior is unchanged;
  - evidence contains synthetic labels, aggregate outcomes, and no secrets/PII.

- [ ] **Step 7: Commit evidence and report.**

  Run:

  ```powershell
  git add -- docs/evidence/phase-5c-synthetic/README.md docs/phase-reports/phase-5c-synthetic.md
  git commit -m "docs: record phase 5c autosave evidence"
  ```

## Task 5: Request Code Review and Prepare the Integration Choice

**Files:**

- Review: all Phase 5C files listed in the File Map

**Interfaces:**

- Consumes: clean Phase 5C branch with Tasks 1-4 committed and all gates passing.
- Produces: reviewer findings, fixes for every Critical/Important issue, fresh verification evidence, and an explicit user-controlled integration handoff.

- [ ] **Step 1: Use the required review skill.**

  Invoke `superpowers:requesting-code-review` against `main...HEAD`. Give the reviewer the approved design spec, this implementation plan, the Phase 5C source/test diff, and the synthetic/read-only constraints.

- [ ] **Step 2: Resolve findings through TDD.**

  For each Critical or Important finding, first add or tighten a failing test, run it to prove RED, implement the smallest fix, run the focused suite to prove GREEN, and commit the fix separately. Use `superpowers:receiving-code-review` before applying feedback that is unclear or technically questionable.

- [ ] **Step 3: Run final verification from the reviewed branch head.**

  Use `superpowers:verification-before-completion`, then run:

  ```powershell
  npm run lint
  npm run typecheck
  npm run test
  npm run build
  npm run verify:no-secrets
  npm run verify:no-live-write
  git diff --check main...HEAD
  git status --short --branch
  ```

  Expected: every gate exits `0`, the worktree is clean, and the branch contains only approved Phase 5C changes.

- [ ] **Step 4: Present the integration choice without acting by inference.**

  Use `superpowers:finishing-a-development-branch` and present Qq with the verified options: merge locally, push/create a PR, or keep the branch as-is. Do not merge, push, create a PR, delete a branch, or remove the worktree until Qq explicitly chooses.

## Final Acceptance Checklist

- [ ] Store seed is immutable, synthetic, and revision `1`.
- [ ] Initial render does not autosave or increment the revision.
- [ ] The latest edit commits once after exactly 300 ms and displays the new local revision.
- [ ] Incomplete attendance can be committed locally while the generation gate remains blocked.
- [ ] A stale commit leaves the store unchanged and preserves the local draft.
- [ ] Automatic retries remain paused while conflict is unresolved.
- [ ] **Use latest version** adopts the latest store snapshot only after the click.
- [ ] **Keep my local draft** creates a new revision through `commitDraft` only after the click.
- [ ] No force-overwrite API, network, Supabase, browser storage, LMS/Teaching mutation, Gemini, secret, credential, PII, or real learner data exists.
- [ ] No Save, Submit, or Generate button exists.
- [ ] Existing Phase 5 curriculum/session, mapping, controls, and readiness tests remain green.
- [ ] Focused and full verification gates pass in the isolated worktree.
- [ ] Evidence/report contain actual synthetic aggregate results and state the reload-reset limitation.
- [ ] Reviewer has no unresolved Critical or Important findings before integration handoff.
