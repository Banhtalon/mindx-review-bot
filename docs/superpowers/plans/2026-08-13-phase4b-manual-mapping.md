# Phase 4B Manual Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a synthetic, read-only React review checkpoint for exact LMS context and explicit manual student mapping.

**Architecture:** Keep deterministic context and mapping rules in a pure TypeScript module. Keep the React screen responsible only for local state, rendering, and native controls. No network, Supabase write, Browser Use session, or real identity is introduced.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Vite, existing privacy and no-live-write scripts.

## Global Constraints

- MVP 1 only reads Teaching and LMS.
- No LMS Save/Submit action exists.
- No CAPTCHA, OTP, anti-bot bypass, credential, cookie, token, raw HTML, or PII.
- Mapping never uses row order, fuzzy matching, prefix matching, or guessed identity.
- Context mismatch and identity ambiguity fail closed to manual fallback.
- All fixtures and evidence values are synthetic.

---

### Task 1: Add deterministic Phase 4B review contract

**Files:**
- Create: `src/lms/manualMapping.ts`
- Test: `src/lms/manualMapping.test.ts`

**Interfaces:**
- `assertLmsContext(expected: LmsContext, observed: LmsContext): ContextAssertion`
- `getMappingStatus(row: LmsRosterRow, assignments: Readonly<Record<string, string>>): MappingStatus`
- `assignStudent(assignments: Readonly<Record<string, string>>, rowKey: string, internalId: string, allowedIds: ReadonlySet<string>): Record<string, string>`
- `canContinueReview(assertion: ContextAssertion, rows: ReadonlyArray<MappingStatus>): boolean`

- [ ] **Step 1: Write the failing tests**

```typescript
it("fails closed when the observed class differs", () => {
  expect(assertLmsContext(expected, { ...expected, classCode: "SYN-ROBOTICS-01B" })).toEqual({
    matched: false,
    reasonCode: "LMS_CLASS_MISMATCH",
    manualFallback: true,
  });
});

it("does not resolve an ambiguous row without an explicit assignment", () => {
  expect(getMappingStatus({ rowKey: "gamma", identity: "ambiguous" }, {})).toBe("ambiguous");
});

it("allows continuation only after exact context and every row resolve", () => {
  const assertion = assertLmsContext(expected, expected);
  expect(canContinueReview(assertion, ["resolved", "resolved"])).toBe(true);
  expect(canContinueReview(assertion, ["resolved", "unresolvable"])).toBe(false);
});
```

- [ ] **Step 2: Run the focused test to verify RED**

Run: `npm run test -- src/lms/manualMapping.test.ts`

Expected: collection fails because `src/lms/manualMapping.ts` does not exist.

- [ ] **Step 3: Implement the minimal pure contract**

Normalize class code with trim/uppercase, compare date/time strings exactly,
accept only allowed synthetic internal IDs, and return new assignment maps.
Never inspect an array index to determine identity.

- [ ] **Step 4: Run the focused test to verify GREEN**

Run: `npm run test -- src/lms/manualMapping.test.ts`

Expected: all contract tests pass.

- [ ] **Step 5: Refactor only after green**

Keep the reason-code and status unions explicit; do not add fuzzy or inferred
matching behavior.

- [ ] **Step 6: Commit**

```powershell
git add src/lms/manualMapping.ts src/lms/manualMapping.test.ts
git commit -m "feat: add phase 4b manual mapping contract"
```

### Task 2: Build the synthetic review screen

**Files:**
- Modify: `src/App.tsx`
- Modify: `src/App.test.tsx`
- Modify: `src/styles.css`

**Interfaces:**
- App-local state stores only `contextMismatch` and a `Record<rowKey, internalId>` assignment map.
- Synthetic rows are keyed by explicit `rowKey` values, never array position.
- The main continue control is disabled when `canContinueReview(...)` is false.

- [ ] **Step 1: Add failing UI tests**

```tsx
it("shows the manual fallback and blocks continuation for a mismatched context", async () => {
  render(<App />);
  await userEvent.click(screen.getByRole("button", { name: /xem trạng thái context sai/i }));
  expect(screen.getByText(/manual fallback bắt buộc/i)).toBeVisible();
  expect(screen.getByRole("button", { name: /tiếp tục khi đã giải quyết/i })).toBeDisabled();
});

it("requires explicit mapping before the review can continue", async () => {
  render(<App />);
  expect(screen.getByRole("button", { name: /tiếp tục khi đã giải quyết/i })).toBeDisabled();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: /student beta/i }), "internal-002");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: /student gamma/i }), "internal-003");
  expect(screen.getByRole("button", { name: /tiếp tục khi đã giải quyết/i })).toBeEnabled();
});
```

- [ ] **Step 2: Run the focused UI tests to verify RED**

Run: `npm run test -- src/App.test.tsx`

Expected: the new queries fail because the review screen and controls are absent.

- [ ] **Step 3: Implement the minimal screen**

Render the selected session, expected/observed context, mismatch alert, roster
table, stable signals, attendance, two labeled native selects, and a disabled
continue button. Keep the existing synthetic-only and LMS-write-disabled copy.

- [ ] **Step 4: Run the focused UI tests to verify GREEN**

Run: `npm run test -- src/App.test.tsx`

Expected: the existing bootstrap test and new review-flow tests pass.

- [ ] **Step 5: Refactor styling after green**

Use semantic headings, labeled controls, responsive stacking, visible focus
states, and status text that does not rely on color alone.

- [ ] **Step 6: Commit**

```powershell
git add src/App.tsx src/App.test.tsx src/styles.css
git commit -m "feat: add phase 4b manual mapping review screen"
```

### Task 3: Add redacted Phase 4B evidence

**Files:**
- Create: `docs/evidence/phase-4b/V4-P4B-01-manual-mapping-ui.md`
- Create: `docs/evidence/phase-4b/index.json`
- Create: `docs/evidence/phase-4b/metrics.csv`

**Interfaces:**
- Evidence contains synthetic class codes, counts, reason codes, and test totals only.
- Evidence explicitly marks live LMS selectors, credentials, browser state, and persistence as BLOCKED.

- [ ] **Step 1: Write the redacted evidence**

Record exact-context PASS, mismatch fallback PASS, explicit mapping PASS,
continue-gate PASS, and privacy/no-write boundaries. Do not include raw DOM,
real names, tokens, URLs, screenshots, or secret values.

- [ ] **Step 2: Run the required verification commands**

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
npm run verify:no-secrets
npm run verify:no-live-write
```

Expected: every command exits 0; the web test suite includes the new contract
and screen tests.

- [ ] **Step 3: Review the diff and commit**

```powershell
git diff --check
git status --short
git add src docs/evidence/phase-4b
git commit -m "docs: record phase 4b manual mapping evidence"
```

## Verification checklist

- [ ] The new contract tests were observed failing before implementation.
- [ ] The UI tests were observed failing before implementation.
- [ ] All web tests, lint, typecheck, build, no-secrets, and no-live-write checks pass.
- [ ] Evidence has no credential, cookie, token, raw HTML, or real PII.
- [ ] The screen has no LMS mutation control or network call.
- [ ] The branch stays separate from `main` until review and merge.
