# Teaching Reader and Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (recommended). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build a synthetic-only deterministic Teaching schedule parser and reconciliation core for Phase 3 without live credentials or website access.

**Architecture:** Parse semantic fixture HTML into Pydantic models, normalize class/date/time/source identity, hash the source page, and reconcile observations through an in-memory store with quarantine outcomes. Keep browser navigation and persistence adapters out of this phase until selectors and database contracts are verified.

**Tech Stack:** Python 3.12, Pydantic 2, `html.parser`, SHA-256, pytest, Ruff, mypy.

## Global Constraints

- MVP 1 only reads Teaching and LMS.
- No LMS Save/Submit/update-comment action exists.
- No CAPTCHA, OTP or anti-bot bypass.
- Identity and sensitive extraction remain deterministic.
- No credential, cookie, token, student name or raw page body in logs/evidence.
- Empty/login pages cannot mass-cancel existing sessions.
- Ambiguous identity is quarantined, never guessed.

---

### Task 1: Validated Teaching schedule parser

**Files:**
- Create: `apps/browser-runner/src/mindx_runner/teaching_models.py`
- Create: `apps/browser-runner/src/mindx_runner/teaching_parser.py`
- Create: `apps/browser-runner/tests/fixtures/teaching/normal-week.html`
- Create: `apps/browser-runner/tests/fixtures/teaching/empty-week.html`
- Create: `apps/browser-runner/tests/fixtures/teaching/login-page.html`
- Create: `apps/browser-runner/tests/fixtures/teaching/css-class-change.html`
- Create: `apps/browser-runner/tests/unit/test_teaching_parser.py`

**Interfaces:**
- `TeachingSessionExtract` contains `class_code`, optional source/session/type fields, local date/time fields, and optional teacher name.
- `TeachingBatchExtract` contains `sessions`, `source_page_hash`, and safe `warnings`.
- `parse_teaching_schedule(html: str) -> TeachingBatchExtract`.
- `normalize_class_code(value: str) -> str` and `normalize_session_type(value: str | None) -> str | None`.

- [ ] **Step 1: Write failing tests** for the normal week, empty week, login page, CSS class change, invalid dates/times, duplicate source IDs, and page hash stability.
- [ ] **Step 2: Run focused tests** with `uv run pytest tests/unit/test_teaching_parser.py -q`; confirm failure because the models/parser are absent.
- [ ] **Step 3: Implement semantic extraction** using `data-teaching-session`, `data-class-code`, `data-source-session-id`, and text fields such as `data-scheduled-date`, `data-start-time`, `data-end-time`, `data-session-number`, `data-session-type`, and `data-teacher-name`; reject login markers and malformed records.
- [ ] **Step 4: Add Pydantic validation and SHA-256 hashing**; return only structured values and safe warning codes.
- [ ] **Step 5: Run focused tests** and confirm all parser fixtures pass.
- [ ] **Step 6: Commit** with `feat: add deterministic teaching parser`.

### Task 2: Deterministic reconciliation and quarantine

**Files:**
- Create: `apps/browser-runner/src/mindx_runner/teaching_reconcile.py`
- Create: `apps/browser-runner/tests/unit/test_teaching_reconcile.py`

**Interfaces:**
- `TeachingSessionRecord` stores an internal ID, normalized identity fields, source ID, source hash, and status.
- `ReconcileResult` contains `action` (`created`, `updated`, `unchanged`, or `quarantined`), optional record ID, and a safe reason code.
- `TeachingReconciliationStore.reconcile(batch: TeachingBatchExtract) -> list[ReconcileResult]`.

- [ ] **Step 1: Write failing tests** for create, idempotent second run, reschedule update, makeup/repeat separate record, missing session type quarantine, duplicate candidates quarantine, and empty/login no mass cancellation.
- [ ] **Step 2: Run focused tests** with `uv run pytest tests/unit/test_teaching_reconcile.py -q`; confirm failure because the store is absent.
- [ ] **Step 3: Implement exact matching** in priority order: source session ID, verified internal source ID, then `(class_code, session_number, session_type)` only when the type is present; never use date/time alone.
- [ ] **Step 4: Implement quarantine and idempotent updates**; retain existing records when a batch has zero sessions or parser warnings indicate login/empty content.
- [ ] **Step 5: Run focused tests** and confirm all reconciliation cases pass.
- [ ] **Step 6: Commit** with `feat: add teaching reconciliation contract`.

### Task 3: Evidence and phase verification

**Files:**
- Modify: `docs/evidence/index.json`
- Create: `docs/evidence/phase-3/V4-P3-01-teaching-fixtures.md`
- Modify: `docs/phase-reports/phase-3.md`

**Interfaces:**
- Evidence records fixture-only parser/reconciliation results and explicitly marks live accuracy/timing as BLOCKED.

- [ ] **Step 1: Add redacted evidence** with fixture counts, parser hash behavior, quarantine behavior, and no-live-data limitation.
- [ ] **Step 2: Run required checks**: `uv run pytest`, `uv run ruff check .`, `uv run mypy src`, web lint/typecheck/test/build, `npm run verify:no-secrets`, and `npm run verify:no-live-write`.
- [ ] **Step 3: Request code review** focused on deterministic identity, empty-page behavior, raw HTML leakage, and no mutation paths.
- [ ] **Step 4: Fix review findings and rerun affected checks**.
- [ ] **Step 5: Commit** with `docs: record teaching reader fixture evidence`.

## Explicitly deferred

- Live Teaching selectors, login actions, browser-state reuse, and production
  Supabase reconciliation RPCs.
- Live cold/warm metrics and owner-controlled smoke evidence.
- LMS reader and student mapping, which belong to Phase 4.
