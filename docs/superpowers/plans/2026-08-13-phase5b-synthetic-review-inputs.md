# Phase 5B Synthetic Review Inputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only synthetic review-input panel where attendance, learning level, and note drafts can be edited in browser memory, while a visible gate blocks review generation until every synthetic learner has an explicit attendance value.

**Architecture:** Keep the readiness rule deterministic and pure in a small review-input module. A frozen, explicitly keyed synthetic roster supplies initial values. The existing React page owns all edits in component state and renders the new panel below its current manual-mapping checkpoint; it performs no persistence, browser automation, remote API call, or generation action.

**Tech Stack:** TypeScript strict mode, React 19, Vite, Vitest, Testing Library, existing CSS.

## Global Constraints

- Phase 5B uses only three clearly synthetic learners with stable explicit row keys. It must not use real learner data, LMS/Teaching data, cookies, tokens, or secrets.
- The UI remains browser-memory only. Reloading loses the draft by design. Do not add Supabase, Auth, migrations, localStorage, APIs, Gemini, browser automation, background work, or any write path.
- Do not render or invoke Save, Submit, Generate, Export, Delivery, LMS mutation, attendance write, or Zalo actions.
- Attendance is the only readiness requirement. Any `unknown` attendance blocks the gate; `unknown` learning level and an empty note remain valid drafts.
- Preserve existing Phase 5 curriculum/session and manual-mapping behavior. Do not change the current review policy gate or synthetic mapping rules.
- Use immutable state replacement keyed by `rowKey`; never infer identity from list position.
- Keep all evidence synthetic and aggregate-only. Do not commit terminal dumps, generated runner artefacts, secrets, or PII.
- Execute implementation in an isolated worktree. In that worktree `npm run lint` must pass. The root checkout currently has sibling worktrees that make `eslint .` scan their source trees and can produce a known `tsconfigRootDir` parser conflict; record that integration limitation if observed, but do not broaden this phase to reconfigure lint.

---

## File Map

| File | Responsibility |
| --- | --- |
| `src/reviewInputs/contracts.ts` | Strict review-input types and the `ReviewInputGate` discriminated union. |
| `src/reviewInputs/gate.ts` | Pure deterministic attendance-readiness evaluator. |
| `src/reviewInputs/gate.test.ts` | Unit tests for blocking and ready gate outcomes. |
| `src/fixtures/phase5bReviewInputs.ts` | Frozen three-learner synthetic fixture and initial-input factory. |
| `src/fixtures/phase5bReviewInputs.test.ts` | Fixture shape, stable key, and default-draft tests. |
| `src/App.tsx` | Local review-input panel and immutable UI state transitions, placed below mapping. |
| `src/App.test.tsx` | User-visible Phase 5B interaction, accessibility, and no-action tests. |
| `src/styles.css` | Panel, controls, gate status, focus, and narrow-screen layout styles. |
| `docs/evidence/phase-5b-synthetic/README.md` | Reproducible synthetic verification evidence and safety limitations. |
| `docs/phase-reports/phase-5b-synthetic.md` | Concise phase outcome, scope boundary, and command-result report. |

## Task 1: Define and Test the Deterministic Attendance Gate

**Files:**

- Create: `src/reviewInputs/contracts.ts`
- Create: `src/reviewInputs/gate.ts`
- Create: `src/reviewInputs/gate.test.ts`

- [ ] **Step 1: Write failing gate tests before implementation.**

  In `src/reviewInputs/gate.test.ts`, import the not-yet-created contracts and evaluator. Add focused cases that assert:

  - one `attendance: "unknown"` returns `ready: false`, `reasonCode: "ATTENDANCE_UNKNOWN"`, and only that explicit `rowKey` in `unknownAttendanceRowKeys`;
  - all attendance values set to `present` or `absent` returns `ready: true`, `reasonCode: "ATTENDANCE_COMPLETE"`, and an empty unknown-key array;
  - unknown learning levels and blank notes do not prevent readiness when attendance is complete.

- [ ] **Step 2: Prove RED.**

  Run: `npx vitest run src/reviewInputs/gate.test.ts`

  Expected: failure because the review-input modules do not exist yet.

- [ ] **Step 3: Add the strict contracts.**

  In `src/reviewInputs/contracts.ts`, export exactly these public concepts:

  ~~~ts
  export type AttendanceStatus = "present" | "absent" | "unknown";
  export type LearningLevel = "strong" | "developing" | "needs_support" | "unknown";
  export type SyntheticLearner = {
    readonly rowKey: string;
    readonly displayName: string;
  };
  export type SyntheticReviewInput = {
    readonly rowKey: string;
    readonly attendance: AttendanceStatus;
    readonly level: LearningLevel;
    readonly noteDraft: string;
  };
  export type ReviewInputGate =
    | {
        readonly ready: true;
        readonly reasonCode: "ATTENDANCE_COMPLETE";
        readonly unknownAttendanceRowKeys: readonly [];
      }
    | {
        readonly ready: false;
        readonly reasonCode: "ATTENDANCE_UNKNOWN";
        readonly unknownAttendanceRowKeys: readonly string[];
      };
  ~~~

- [ ] **Step 4: Implement the smallest pure evaluator.**

  In `src/reviewInputs/gate.ts`, export `evaluateReviewInputGate(inputs: readonly SyntheticReviewInput[]): ReviewInputGate`. Filter only `attendance === "unknown"`, preserve the supplied `rowKey` order, and return the matching discriminated-union result. The function must have no React, storage, network, logging, or fixture dependencies.

- [ ] **Step 5: Prove GREEN and refactor only if clarity improves.**

  Run: `npx vitest run src/reviewInputs/gate.test.ts`

  Expected: all gate cases pass. Keep the evaluator direct; do not introduce a generic workflow framework.

- [ ] **Step 6: Commit the focused behavior.**

  Run: `git add src/reviewInputs/contracts.ts src/reviewInputs/gate.ts src/reviewInputs/gate.test.ts && git commit -m "feat: add synthetic review input gate"`

## Task 2: Add an Immutable Synthetic Roster and Default Drafts

**Files:**

- Create: `src/fixtures/phase5bReviewInputs.ts`
- Create: `src/fixtures/phase5bReviewInputs.test.ts`

- [ ] **Step 1: Write failing fixture tests.**

  In `src/fixtures/phase5bReviewInputs.test.ts`, assert that the Phase 5B roster has exactly three learners, row keys are non-empty and unique, names are visibly synthetic, and the initial-input factory returns a record for every supplied learner with `attendance: "unknown"`, `level: "unknown"`, and `noteDraft: ""`. Also assert that attempts to mutate the exported fixture do not change its data.

- [ ] **Step 2: Prove RED.**

  Run: `npx vitest run src/fixtures/phase5bReviewInputs.test.ts`

  Expected: failure because the fixture module is absent.

- [ ] **Step 3: Implement the minimal fixture module.**

  Export `PHASE5B_SYNTHETIC_LEARNERS` as a deeply frozen readonly roster with exactly these stable values:

  | rowKey | displayName |
  | --- | --- |
  | `synthetic-review-001` | `Synthetic learner 01` |
  | `synthetic-review-002` | `Synthetic learner 02` |
  | `synthetic-review-003` | `Synthetic learner 03` |

  Export `createInitialReviewInputs(learners: readonly SyntheticLearner[]): readonly SyntheticReviewInput[]`. It must construct new immutable-value records from the passed learners, rather than relying on list index or sharing editable UI-state objects with the fixture.

- [ ] **Step 4: Prove GREEN.**

  Run: `npx vitest run src/fixtures/phase5bReviewInputs.test.ts`

  Expected: all fixture/default tests pass.

- [ ] **Step 5: Commit the fixture boundary.**

  Run: `git add src/fixtures/phase5bReviewInputs.ts src/fixtures/phase5bReviewInputs.test.ts && git commit -m "feat: add phase 5b synthetic review fixtures"`

## Task 3: Build the Local-Only Review-Input Surface

**Files:**

- Modify: `src/App.tsx`
- Modify: `src/App.test.tsx`
- Modify: `src/styles.css`

- [ ] **Step 1: Extend the existing app tests first.**

  Add focused Phase 5B tests in `src/App.test.tsx` that interact through accessible labels and cover all of the following:

  - the default page shows `Synthetic review inputs`, the three synthetic learners, a `Mark all present` button, and `Generation blocked: attendance unknown`;
  - the default page has no button whose accessible name matches Save or Submit, and no Generate action;
  - clicking `Mark all present` changes every attendance selection to `present` and shows `Generation ready: attendance complete` even while all levels remain unknown and notes are blank;
  - selecting one learner as `absent` remains ready; changing that learner back to `unknown` returns to the blocked gate and exposes the unknown-attendance reason in visible text;
  - changing a learning-level select and its labelled note textarea updates only local rendered state and does not change a ready attendance gate;
  - each attendance control, level control, and note textarea has a learner-specific accessible label.

- [ ] **Step 2: Prove RED.**

  Run: `npx vitest run src/App.test.tsx`

  Expected: the new review-input expectations fail because the panel does not exist.

- [ ] **Step 3: Implement the panel with local state only.**

  In `src/App.tsx`:

  - import the Phase 5B fixture, contracts, and `evaluateReviewInputGate`;
  - add an exported `Phase5BReviewInputSurface` component beneath the existing manual-mapping checkpoint in `App`;
  - initialize its `useState` with `createInitialReviewInputs(PHASE5B_SYNTHETIC_LEARNERS)` and derive its gate with `useMemo`;
  - implement `Mark all present` as an immutable map that changes only `attendance` to `present` for every current input;
  - implement individual attendance, level, and note changes as immutable replacements found by `rowKey`, never by array position;
  - render a concise visible gate section: `Generation blocked: attendance unknown` plus the count/reason when blocked, or `Generation ready: attendance complete` when ready;
  - render a labelled select for attendance, a labelled select for level, and a labelled textarea for note for each learner; use plain options matching the contract unions;
  - label the panel as synthetic/local/browser-memory-only and explicitly state that reload discards the draft;
  - add no action beyond editing input state. In particular, do not add a generation button, persistence, browser call, API client, or side effect.

- [ ] **Step 4: Add scoped visual and responsive styles.**

  In `src/styles.css`, add narrowly named styles for the review-input panel, per-learner control group, status/gate, status variants, and focus-visible controls. Add a narrow-screen media rule that stacks the control grid without horizontal overflow. Preserve the existing page, context, and mapping styles.

- [ ] **Step 5: Prove GREEN, then run related safety checks.**

  Run:

  ~~~powershell
  npx vitest run src/App.test.tsx
  npm run typecheck
  npm run verify:no-secrets
  npm run verify:no-live-write
  ~~~

  Expected: tests and checks pass. If a static safety check flags a prohibited word in explanatory text, adjust the wording without adding a write path.

- [ ] **Step 6: Inspect the running page before committing.**

  Run: `npm run dev`

  Inspect at the Vite URL using a browser with the synthetic fixture only. Confirm that the panel sits below mapping, the initial gate is blocked, bulk present opens it, an individual unknown closes it, controls remain keyboard reachable, and the narrow viewport stacks controls. Do not log in to or navigate Teaching/LMS for this task.

- [ ] **Step 7: Commit the UI behavior.**

  Run: `git add src/App.tsx src/App.test.tsx src/styles.css && git commit -m "feat: add local synthetic review inputs"`

## Task 4: Record Synthetic Evidence and Run the Full Verification Set

**Files:**

- Create: `docs/evidence/phase-5b-synthetic/README.md`
- Create: `docs/phase-reports/phase-5b-synthetic.md`

- [ ] **Step 1: Create a concise synthetic evidence record.**

  In `docs/evidence/phase-5b-synthetic/README.md`, record the three synthetic row keys, the two gate reason codes, test scenarios, exact verification commands, command outcomes, and manual UI checks. State explicitly that no Teaching/LMS/Supabase/Gemini data, credential, cookie, real learner name, Save, Submit, or persistent write was involved.

- [ ] **Step 2: Create the phase report.**

  In `docs/phase-reports/phase-5b-synthetic.md`, summarize goal, delivered local behavior, intentionally excluded behaviors, privacy/safety boundary, test totals from the final run, and the reload-loses-draft limitation. If the root checkout lint issue is observed after merging, document it as an integration-environment caveat, not as a Phase 5B code failure.

- [ ] **Step 3: Run full isolated-worktree verification.**

  Run:

  ~~~powershell
  npm run lint
  npm run typecheck
  npm run test
  npm run build
  npm run verify:no-secrets
  npm run verify:no-live-write
  git diff --check
  ~~~

  Expected: every command passes in the isolated worktree. Copy only aggregate outcomes and the final test count into the evidence/report; do not copy terminal logs wholesale.

- [ ] **Step 4: Review the diff before committing evidence.**

  Run: `git diff --check HEAD~1..HEAD` and `git status --short`. Confirm only Phase 5B source, test, style, evidence, and report files are staged; do not stage generated Vite output or unrelated workspace changes.

- [ ] **Step 5: Commit the evidence.**

  Run: `git add docs/evidence/phase-5b-synthetic/README.md docs/phase-reports/phase-5b-synthetic.md && git commit -m "docs: record phase 5b review input evidence"`

## Task 5: Request Review and Prepare Integration Handoff

**Files:**

- Review: all Phase 5B files listed in the File Map

- [ ] **Step 1: Re-run final verification from the final commit.**

  Run:

  ~~~powershell
  npm run lint
  npm run typecheck
  npm run test
  npm run build
  npm run verify:no-secrets
  npm run verify:no-live-write
  git diff --check HEAD~3..HEAD
  git status --short
  ~~~

  Expected: clean working tree and passing verification in the implementation worktree.

- [ ] **Step 2: Perform a scoped code review.**

  Check that every UI update is row-keyed and immutable; only the pure gate decides readiness; all user-facing labels remain synthetic; no persistence/network/automation dependency was imported; no prohibited action was added; existing Phase 5 context/mapping tests still pass; and the new UI is readable at narrow viewport width.

- [ ] **Step 3: Hand off without merging automatically.**

  Push the feature branch and open a PR to `main` only after Qq approves the reviewed diff. The PR description must link the Phase 5B evidence/report and restate that this is a synthetic, local-only input surface with no LMS/Teaching write path. Do not merge or delete a branch without explicit user approval.

## Final Acceptance Checklist

- [ ] Default has exactly three synthetic learner drafts, all unknown attendance/level and blank notes.
- [ ] Initial visible state says `Generation blocked: attendance unknown`.
- [ ] Bulk `Mark all present` sets only attendance and opens the readiness gate.
- [ ] A learner marked absent remains allowed; any returned unknown attendance blocks again.
- [ ] Level and note editing are local only and do not decide readiness.
- [ ] No Save, Submit, Generate, persistence, remote call, LMS/Teaching interaction, secret, PII, or write action exists.
- [ ] Existing Phase 5 curriculum/session and mapping UI remain intact.
- [ ] Isolated-worktree lint, typecheck, tests, build, safety checks, and whitespace check pass.
- [ ] Evidence and report contain only synthetic, reproducible, aggregate information.
