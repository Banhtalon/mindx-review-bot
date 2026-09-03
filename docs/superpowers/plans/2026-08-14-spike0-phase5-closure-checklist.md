# Spike 0--Phase 5 Closure Checklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close or explicitly classify every Spike 0--Phase 5 gate with fresh, redacted evidence, without treating synthetic/local PASS as live production readiness.

**Architecture:** The V4 master specification is the requirements source. Phase reports and evidence files are observations, while fresh commands and owner-controlled smoke runs are closure proof. The matrix keeps four states separate: `PASS`, `BLOCKED`, `MISSING EVIDENCE`, and `NOT VERIFIED`.

**Tech Stack:** Markdown, Git, PowerShell, TypeScript/Vitest/Vite, Python/uv/Pytest/Ruff/Mypy, Supabase CLI/pgTAP, Docker Desktop, and GitHub Actions.

## Global Constraints

- Source of truth: `docs/spec/KE_HOACH_MVP_BOT_NHAN_XET_MINDX_V4_BROWSER_USE_SUPABASE.md`.
- MVP 1 remains Teaching/LMS read-only; do not add or exercise LMS `Save`/`Submit`/comment mutation.
- Never request or record passwords, OTPs, cookies, tokens, raw browser state, real student names, or other PII in chat, code, logs, or evidence.
- Owner enters live credentials directly into GitHub/Supabase secret stores; Qq does not paste them into chat.
- Historical PASS is not fresh closure evidence unless the command, date, commit, scope, and artifact are recorded.
- `BLOCKED` is an honest result when an owner-controlled environment, Docker, live site, or approved credential is unavailable; do not convert it to PASS by inference.
- Do not start Phase 6 implementation until the Spike 0--Phase 5 closure decision is recorded as PASS or an explicit owner-approved scope exception.
- Documentation-only changes must not alter application behavior, migrations, secrets, workflows, or live integrations.

## Closure State Definitions

| State | Meaning | May close the gate? |
| --- | --- | --- |
| `PASS` | Fresh evidence satisfies the stated requirement at the declared scope. | Yes |
| `BLOCKED` | The requirement is understood but cannot be verified because an external/owner-controlled prerequisite is missing. | No; record blocker and owner decision |
| `MISSING EVIDENCE` | Implementation may exist, but the required report, evidence ID, artifact, or fresh command result is absent. | No |
| `NOT VERIFIED` | No reliable implementation or verification basis exists yet. | No |
| `WAIVED` | Qq explicitly accepts a documented scope exception with risk and follow-up. | Only with written owner approval |

## Current Audit Baseline

| Scope | Current status | Existing evidence | Closure gap |
| --- | --- | --- | --- |
| Spike 0 | `BLOCKED` overall; 8 evidence items PASS and 4 remain BLOCKED | `docs/evidence/index.json`, `docs/evidence/spike-0/`, `docs/phase-reports/spike-0.md` | Live Teaching/LMS smoke, browser telemetry/privacy probe, hosted state reuse, and billed-minute evidence |
| Phase 1 | `MISSING EVIDENCE` as a formal phase; foundation code exists inside Spike 0 history | `supabase/migrations/`, `supabase/tests/`, Spike 0 RLS evidence | No `phase-1` report or `V4-P1-01`--`V4-P1-08` evidence index; fresh Auth/RLS/role/bundle/CI closure |
| Phase 2 | Partial synthetic implementation; formal gate `MISSING EVIDENCE` and live runner scope `BLOCKED` | Dispatch, crypto, and runner contract commits; `V4-S0-03`, `V4-S0-04`, `V4-S0-09`, runner contract evidence | No `V4-P2-01`--`V4-P2-10` evidence; cloud-off-PC, lease/retry/cleanup, hosted Storage/state reuse not closed |
| Phase 3 | Synthetic parser/reconciliation `PASS`; live/production `BLOCKED` | `V4-P3-01`, `docs/phase-reports/phase-3.md` | Live Teaching selector/login smoke, metrics, and production reconciliation |
| Phase 4A/4B | Synthetic reader, identity, mapping, fallback `PASS`; live/production `BLOCKED` | `V4-P4A-01`, `V4-P4B-01`, phase reports | Full `V4-P4-01`--`V4-P4-12` mapping, live LMS read-only smoke, and root Python gate closure |
| Phase 5 / 5A / 5B / 5C | Synthetic slices `PASS`; overall Phase 5 `MISSING EVIDENCE`/not closed | Phase 5, 5A, 5B, 5C reports and README evidence | Full `V4-P5-01`--`V4-P5-10`, owner/access workflow, 10-learner exit gate, and explicit persistence/live scope decision |

## Inline Execution Log

Observed on `2026-08-14T09:10:07+07:00` at `main` commit
`6e5e3322355f9667aea347173449dbf0e9132d70`.

| Check | Result | Observed evidence |
| --- | --- | --- |
| Baseline | `PASS` | `main` has no code changes; this checklist is the only untracked documentation file. |
| Web typecheck | `PASS` | `npm run typecheck` exited `0`. |
| Web tests | `PASS` | `npm run test`: 18 files, 99 tests. |
| Web build | `PASS` | `npm run build`: Vite production build completed. |
| Security guards | `PASS` | `npm run verify:no-secrets` and `npm run verify:no-live-write` exited `0`. |
| Scoped web lint | `PASS` | `npx eslint src scripts test vite.config.ts vitest.config.ts` exited `0`. |
| Python runner | `PASS` | `uv run pytest`: 210 passed; Ruff and Mypy passed for 22 source files. |
| Local RLS | `PASS` | `npm run test:rls`: 3 SQL files, 67 tests, 0 failures. |
| Full workspace lint | `PASS` | After adding `.worktrees/**` to ESLint global ignores, `npm run lint` exited `0`. |
| Live Teaching/LMS gates | `BLOCKED` | LMS target class/session read-only navigation PASS; five fresh Teaching GET attempts redirected to login, so full cold/warm live closure remains blocked. |

## Owner-Controlled Smoke Update

Observed after Qq's confirmation on 2026-08-14:

- Teaching weekly GET view: five warm reloads completed without a login
  redirect; each retained one schedule table, 17 lesson-link targets, and no
  non-GET forms. The separate schedule-registration page exposed a POST form,
  so it was deliberately not submitted.
- LMS dashboard/classes routes remained signed in. After Qq reopened the
  Classes list, three passive read-only samples one second apart were stable:
  one table, 20 visible rows, no login-like state, no mutation forms, and no
  no-data state. The later owner-supplied class filter used the existing GET
  filter form and kept one matching row in two passive samples. One read-only
  `actions` menu was opened for inspection; no menu item, Save, Submit, or
  mutation form was selected/submitted.
- This closes only the stable class-list observation. Exact class/session/
  student-level identity and the full runner smoke are still not claimed. The
  approved class code was opened in the detail drawer, `Nhận xét` was selected,
  and session `# 3` showed its active state. The targeted view had no form,
  mutation form, textarea, password input, or Save/Submit control. The earlier
  reload instability remains a cold/warm runner caveat.
- Redacted evidence: `docs/evidence/spike-0/V4-S0-05-owner-readonly-smoke-2026-08-14.md`.
- Decision: live closure remains `BLOCKED`; no production PASS is claimed.

Fresh live continuation on 2026-08-14:

- LMS `Nhận xét` session `# 3` remained active in three passive samples with
  zero forms, mutation forms, Save/Submit controls, and textareas.
- Five direct GET attempts to the observed Teaching weekly route redirected to
  the login page before re-authentication. No credential was entered by Codex;
  fresh Teaching navigation was temporarily `BLOCKED` until Qq signed in
  again.
- After Qq signed in again, five warm reloads on the authenticated Teaching
  `index.php` surface passed with durations `618, 480, 515, 554, 492 ms`; all
  retained one table, six visible rows, 17 lesson links, no login-like state,
  and zero POST forms. Cold/direct navigation and runner telemetry remain
  open.

The local Supabase status command succeeded. Its local default keys were not
copied into this document or any evidence; only the non-sensitive test result
was retained.

## Verification Rerun

Fresh local verification on 2026-08-14 after the live smoke:

- Web typecheck, 18-file/99-test suite, production build, secret scan,
  no-live-write scan, and scoped ESLint all exited `0`.
- Python runner: 210 tests passed; Ruff and Mypy passed for 22 source files.
- Local RLS: 3 SQL files and 67 tests passed.
- Root `npm run lint` now passes with exit code `0`; `.worktrees/**` is excluded
  by the ESLint global ignore so sibling worktrees cannot create competing
  `tsconfigRootDir` candidates.

## Inline Execution Pause

Task 1 is complete at the local/synthetic scope. Task 2 has now received an
owner-controlled browser smoke attempt. The LMS class-list surface is stable,
the owner-supplied class-code filter matches one row in two passive samples,
and the targeted read-only path `Nhận xét` → session `# 3` is confirmed. Full
student-level identity, runner/telemetry/storage, cold/direct navigation, and
billed-minute checks remain open. Teaching warm reload is now PASS after owner
re-authentication, but no credential should be pasted into chat. Until the
remaining checks pass, the related rows remain `BLOCKED` and no later phase is
promoted to production-ready.

## Evidence Inventory Checklist

- [ ] Keep the master spec checklist as the requirements list; do not mark a box checked until the matching closure row has fresh evidence.
- [ ] Create or update one phase-level evidence index for each phase, with one row per required evidence ID and a status from the definitions above.
- [ ] Link every evidence row to a report, command output, redacted artifact, commit, and date.
- [ ] Record synthetic/local scope separately from live/production scope in every report.
- [ ] Record the current integration caveat: fresh RLS verification requires Docker Desktop.
- [ ] Reconcile the master evidence references (`V4-P1-*`, `V4-P2-*`, `V4-P3-*`, `V4-P4-*`, `V4-P5-*`) with actual files under `docs/evidence/`.

## Task 1: Freeze the closure baseline

**Files:**
- Read: `docs/spec/KE_HOACH_MVP_BOT_NHAN_XET_MINDX_V4_BROWSER_USE_SUPABASE.md`
- Read: `docs/phase-reports/`, `docs/evidence/`, `git log`, and current worktree status
- Create/update: this checklist

- [x] **Step 1: Record the exact baseline commit and worktree state.**

  Run from `E:\mindx-review-bot`:

  ```powershell
  git status --short --branch
  git log -1 --format="%H %ad %s" --date=iso-strict
  git worktree list
  ```

  Expected: clean `main`; record the observed commit and any remaining worktrees.

- [x] **Step 2: Run the non-destructive current web/Python gates.**

  Record actual output for `npm run typecheck`, `npm run test`, `npm run build`, `npm run verify:no-secrets`, `npm run verify:no-live-write`, scoped ESLint, `uv run pytest`, `uv run ruff check .`, and `uv run mypy src` from `apps/browser-runner`.

- [x] **Step 3: Check infrastructure prerequisites before RLS/live work.**

  Run `npx supabase status`. If Docker is unavailable, mark fresh RLS verification `BLOCKED`; do not run a destructive reset merely to make the checklist look complete.

## Task 2: Close or explicitly retain Spike 0 blockers

**Evidence targets:** `V4-S0-05`, `V4-S0-06`, `V4-S0-09` hosted scope, `V4-S0-11`, and `V4-S0-05-RUNNER`.

- [ ] **Step 1: Owner approves a controlled Teaching read-only smoke.**

  The owner supplies credentials only through the approved secret store/session. Run at least the planned cold/warm sample, capture only redacted duration, step count, safe counts, failure category, and no raw page/PII.

- [ ] **Step 2: Owner approves a controlled LMS read-only smoke.**

  Assert exact class/session/student identity and verify no LMS mutation. Stop before Save/Submit; capture only redacted metrics and reason codes.

- [ ] **Step 3: Verify Browser Use privacy and telemetry boundary.**

  Use synthetic pages first, confirm sensitive roster DOM is not sent to a navigation LLM, verify telemetry settings/hosts, and preserve no raw screenshots/traces.

- [ ] **Step 4: Verify hosted encrypted browser-state reuse/reset.**

  Confirm encrypted Storage/state lifecycle, key-missing and tamper fail-closed behavior, owner-only reset, temporary-file cleanup, and no plaintext state in metadata/evidence.

- [ ] **Step 5: Record pinned dependency and billed-minute evidence.**

  Record exact Browser Use version, runner image, cold/warm duration, p50/p95, and estimated GitHub minutes from the approved environment. Mark `BLOCKED` if the owner-controlled run is not performed.

## Task 3: Close Phase 1 formally

**Evidence targets:** `V4-P1-01`--`V4-P1-08`.

- [ ] **Step 1: Map existing foundation code to P1 requirements.**

  Review migrations, constraints, RLS helpers/policies, synthetic owner seed, React shell, protected/role-aware paths, error handling, `.env.example`, and secret scanner/CI.

- [ ] **Step 2: Freshly verify local Auth/RLS.**

  With Docker available, run the project-approved local reset and RLS suite; record anonymous denial, cross-workspace denial, role matrix, constraints, and fixed search paths. If Docker is unavailable, retain `BLOCKED`.

- [ ] **Step 3: Create a Phase 1 report and evidence index.**

  Do not mark a row PASS when only Spike 0 evidence covers it; link each P1 ID to an observed command/artifact or mark it `MISSING EVIDENCE`.

## Task 4: Close Phase 2 formally

**Evidence targets:** `V4-P2-01`--`V4-P2-10`.

- [ ] **Step 1: Verify dispatch state machine and idempotency.**

  Cover duplicate cron/dispatch, atomic claim, lease expiry, wrong runner completion, bounded retry, safe metrics, wrong cron secret, and invalid GitHub input.

- [ ] **Step 2: Verify encrypted state lifecycle.**

  Cover round-trip, tamper rejection, key rotation, owner-only reset, missing key, and cleanup on exception with synthetic state only.

- [ ] **Step 3: Verify workflow and cloud execution contract.**

  Check permissions, pinned actions, timeout/concurrency, secret scope, kill switch, and an owner-controlled run while the personal computer is off. Keep live success separate from contract-test PASS.

- [ ] **Step 4: Create a Phase 2 report and evidence index.**

  Link existing Spike 0 evidence where it truly satisfies a P2 requirement; add new evidence for requirements not covered by those files.

## Task 5: Close Phase 3 and Phase 4 evidence gaps

**Evidence targets:** `V4-P3-01`--`V4-P3-10` and `V4-P4-01`--`V4-P4-12`.

- [ ] **Step 1: Complete the Phase 3 evidence map.**

  Map normal/empty/reschedule/makeup/duplicate/login/DOM-change/idempotency fixtures, live smoke metadata, privacy, performance, and review. Missing live items remain `BLOCKED`.

- [ ] **Step 2: Complete the Phase 4 evidence map.**

  Map exact class/session/date/time, duplicate-name identity, row-reorder safety, absent/online parsing, late pending selection, no mutation, DOM privacy, fallback, live smoke, and review.

- [ ] **Step 3: Resolve the Phase 4A Python gate discrepancy.**

  Run the required commands from the documented project root with dependencies installed, or explicitly record why the app-scoped PASS is the approved bounded scope. Do not silently replace a root gate with a narrower command.

- [ ] **Step 4: Create refreshed Phase 3 and Phase 4 closure reports.**

  Preserve the existing synthetic PASS and live BLOCKED conclusions unless fresh owner-controlled evidence changes them.

## Task 6: Close the complete Phase 5 checklist

**Evidence targets:** `V4-P5-01`--`V4-P5-10`.

- [ ] **Step 1: Map the existing Phase 5 synthetic slices.**

  Link catalog/validator/resolver to Phase 5 evidence, attendance/quick notes to Phase 5B, autosave/conflict to Phase 5C, and manual fallback/responsive checks to the appropriate rows.

- [ ] **Step 2: Add missing access and workflow evidence.**

  Verify keyboard workflow, reviewer/owner permissions, owner CRUD minimum, responsive viewport, and the no-Save/Submit/no-live-write boundary.

- [ ] **Step 3: Verify the Phase 5 exit gate.**

  Use an explicitly synthetic 10-learner fixture or an owner-approved permitted sample to measure the target workflow. Verify generation remains blocked when context/attendance is incomplete and curriculum is read from stored data rather than invented.

- [ ] **Step 4: Decide persistence/live scope before closing Phase 5.**

  Record whether Phase 5 closes as synthetic-only with an explicit waiver, or whether durable Supabase persistence and live Teaching/LMS context are required before the gate can be PASS.

- [ ] **Step 5: Create the Phase 5 evidence index and closure report.**

  Do not treat the current 5A/5B/5C reports as a substitute for the master `V4-P5-01`--`V4-P5-10` matrix without mapping each row.

## Task 7: Final review and Phase 6 readiness decision

- [x] **Step 1: Run the final required gates on the closure commit.**

  Run the project web/Python/security gates, fresh RLS if Docker is available, and `git diff --check`; record known environment caveats separately.

- [ ] **Step 2: Review every closure row independently.**

  A phase is closed only when all required rows are `PASS`, or Qq has explicitly approved a documented `WAIVED`/`BLOCKED` boundary with a follow-up owner and risk.

- [ ] **Step 3: Update the master checklist and final evidence index.**

  Change `[ ]` to `[x]` only for rows supported by the closure matrix; leave blocked or unverified rows visibly open.

- [ ] **Step 4: Decide whether Phase 6 may start.**

  If Phase 5 is closed at the approved scope, create a separate Phase 6 design/implementation plan for Gemini structured generation. Otherwise continue only the outstanding closure rows.

## Task 7 Review Snapshot

Observed after the final gate rerun on 2026-08-14:

- Spike 0 index: 13 rows, 8 `PASS`, and 5 `BLOCKED`. The owner-smoke row is
  supplemental; the base live metric blockers remain Teaching/LMS cold-warm,
  runner contract, and billed-minute evidence.
- Phase 1: no phase-level evidence index/report; status remains `MISSING
  EVIDENCE`.
- Phase 2: no phase-level evidence index/report; status remains `MISSING
  EVIDENCE`.
- Phase 3: one indexed synthetic evidence row; the full `V4-P3-01`--`V4-P3-10`
  matrix and live rows remain open.
- Phase 4: one indexed row for each 4A/4B slice; the full `V4-P4-01`--`V4-P4-12`
  matrix and live rows remain open.
- Phase 5: one indexed 5A row plus 5B/5C reports; the master
  `V4-P5-01`--`V4-P5-10` matrix and exit-gate decision remain open.
- Decision: Phase 6 is **not started**. Task 7 Step 2--4 remain open until the
  missing evidence is created or Qq approves a documented `WAIVED`/`BLOCKED`
  boundary with owner, risk, and follow-up.

## Definition of Done for this Closure Checklist

- [ ] Every Spike 0--Phase 5 requirement has exactly one status and evidence link.
- [ ] Every `PASS` row has fresh command output or owner-controlled redacted artifact.
- [ ] Every `BLOCKED` row names the external prerequisite and owner action.
- [ ] Missing P1/P2/P3/P4/P5 evidence indexes and reports are created or explicitly marked not yet closed.
- [ ] Fresh web/Python/security checks are recorded; the Docker caveat is not hidden.
- [ ] No credential, cookie, token, PII, raw browser state, LMS Save/Submit, or live write was introduced.
- [ ] Qq approves the final closure decision before Phase 6 implementation begins.
