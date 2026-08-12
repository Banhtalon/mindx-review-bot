# Phase 4A — LMS Pending Reader and Identity Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the synthetic-only, deterministic LMS pending reader and student identity contract without live credentials, production URLs, or LMS mutation.

**Architecture:** Add focused Python modules for pending-session selection, semantic LMS parsing/context assertion, and stable student identity resolution. Reuse the existing network mutation guard and navigation privacy boundary. Return structured safe reason codes and manual-fallback results instead of guesses; retain only source-page hashes in evidence.

**Tech Stack:** Python 3.12, Pydantic 2, `html.parser`, SHA-256, pytest, Ruff, mypy, and the existing Browser Use guard contracts.

## Global Constraints

- MVP 1 only reads Teaching and LMS; no LMS Save/Submit/update-comment action.
- No real credentials, cookies, browser state, production URLs, student PII, raw HTML, screenshots, traces, or HAR in code/evidence.
- No CAPTCHA, OTP, anti-bot bypass, Zalo automation, or live smoke in Phase 4A.
- Identity/extraction is deterministic; no row-order, fuzzy, prefix, date/time-only, or guessed mapping.
- Exact class/session/date/time assertions fail closed before roster mapping.
- Unknown, duplicate, or ambiguous identity returns `unresolvable`/`ambiguous` with a safe reason code.
- Existing `network_guard.py` remains the mutation boundary; no new LMS write function/tool is added.
- Existing `privacy_boundary.py` continues to block roster DOM from navigation LLM input.
- Every behavior follows RED → GREEN → REFACTOR → VERIFY.

---

### Task 1: Pending session eligibility filter

**Files:**
- Create: `apps/browser-runner/src/mindx_runner/lms_pending.py`
- Create: `apps/browser-runner/tests/unit/test_lms_pending.py`

**Interfaces:**
- `PendingSessionInput`: frozen Pydantic model with `class_code: str`, `session_number: int`, `scheduled_date: date`, `start_time: time`, `end_time: time`, and `workflow_status: Literal["context_pending", "completed", "failed", "skipped"]`.
- `PendingSelection`: frozen Pydantic model with `eligible: bool` and `reason_code: str`.
- `select_pending_session(session: PendingSessionInput, *, now: datetime) -> PendingSelection`.

- [ ] **Step 1: Write failing tests** for an eligible session ending today, an eligible late session ending yesterday, a future session, a session older than yesterday, a non-pending state, and incomplete identity.

```python
def test_selects_late_session_from_yesterday() -> None:
    result = select_pending_session(
        session(class_code="SYN-CLASS-01", scheduled_date=date(2026, 8, 11), end_time=time(23, 0)),
        now=datetime(2026, 8, 12, 9, 0),
    )
    assert result == PendingSelection(eligible=True, reason_code="PENDING_ELIGIBLE")
```

- [ ] **Step 2: Run RED:** `uv run pytest tests/unit/test_lms_pending.py -q`. Expected: import/function-not-found failure because the module does not exist.
- [ ] **Step 3: Implement the minimal filter.** Compute `end_at = datetime.combine(session.scheduled_date, session.end_time)` and accept only `session.scheduled_date in {now.date() - timedelta(days=1), now.date()}`, `end_at <= now`, and `workflow_status == "context_pending"`. Return exactly `PENDING_IDENTITY_INCOMPLETE`, `PENDING_WORKFLOW_NOT_PENDING`, `PENDING_TOO_OLD`, `PENDING_FUTURE`, or `PENDING_ELIGIBLE`.
- [ ] **Step 4: Run GREEN:** `uv run pytest tests/unit/test_lms_pending.py -q`; expected all focused tests pass.
- [ ] **Step 5: Verify style/types:** `uv run ruff check src/mindx_runner/lms_pending.py tests/unit/test_lms_pending.py` and `uv run mypy src`.
- [ ] **Step 6: Commit:** `git add apps/browser-runner/src/mindx_runner/lms_pending.py apps/browser-runner/tests/unit/test_lms_pending.py; git commit -m "feat: add lms pending session filter"`.

### Task 2: Semantic LMS page parser

**Files:**
- Create: `apps/browser-runner/src/mindx_runner/lms_models.py`
- Create: `apps/browser-runner/src/mindx_runner/lms_parser.py`
- Create: `apps/browser-runner/tests/fixtures/lms/normal-session.html`
- Create: `apps/browser-runner/tests/fixtures/lms/duplicate-name.html`
- Create: `apps/browser-runner/tests/fixtures/lms/ambiguous-name.html`
- Create: `apps/browser-runner/tests/fixtures/lms/similar-class.html`
- Create: `apps/browser-runner/tests/fixtures/lms/row-reordered.html`
- Create: `apps/browser-runner/tests/fixtures/lms/no-homework.html`
- Create: `apps/browser-runner/tests/unit/test_lms_parser.py`

**Interfaces:**
- `LmsRosterRow`: frozen Pydantic model with `student_id: str | None`, `discriminator: str | None`, `full_name: str`, and `attendance: Literal["present", "online", "absent", "unknown"]`.
- `LmsPageExtract`: frozen Pydantic model with `class_code`, `session_number`, `scheduled_date`, `start_time`, `end_time`, `source_session_id`, `rows: tuple[LmsRosterRow, ...]`, `lesson: str`, `homework: str | None`, `source_page_hash`, and `warnings: tuple[str, ...]`.
- `LmsParserError` carries only a stable `code`.
- `parse_lms_page(html: str, *, allowed_class_codes: Collection[str] = DEFAULT_SYNTHETIC_CLASS_CODES) -> LmsPageExtract`.

- [ ] **Step 1: Write failing fixture tests** for normal context, exact attendance (`present`, `online`, `absent`, missing → `unknown`), lesson/homework, missing homework as `None`, duplicate page IDs/discriminators, blank fields, stable hash, similar class rejection, and row-reorder invariance.
- [ ] **Step 2: Run RED:** `uv run pytest tests/unit/test_lms_parser.py -q`. Expected: module/function-not-found failure.
- [ ] **Step 3: Implement strict models and semantic parsing.** Read only `data-lms-context="true"`, `data-class-code`, `data-session-number`, `data-scheduled-date`, `data-start-time`, `data-end-time`, optional `data-source-session-id`, `data-lesson`, `data-homework`, and `data-lms-student="true"` attributes. Normalize Unicode NFC/whitespace; preserve display names; reject duplicate non-null IDs/discriminators and malformed values with `LMS_DATA_INVALID`.
- [ ] **Step 4: Enforce exact class allowlisting.** Accept `SYN-CLASS-01`; reject `SYN-CLASS-010`, `SYN-CLASS-01-EXTRA`, or other values when an explicit catalog is provided. Do not use prefix, substring, or fuzzy matching.
- [ ] **Step 5: Run GREEN:** `uv run pytest tests/unit/test_lms_parser.py -q`; expected all parser tests pass and output contains no raw HTML.
- [ ] **Step 6: Verify and commit:** run `uv run ruff check src/mindx_runner/lms_models.py src/mindx_runner/lms_parser.py tests/unit/test_lms_parser.py`, `uv run mypy src`, then `git add` the listed Task 2 files and commit `feat: add deterministic lms page parser`.

### Task 3: Exact LMS context assertion and safe fallback

**Files:**
- Create: `apps/browser-runner/src/mindx_runner/lms_context.py`
- Create: `apps/browser-runner/tests/unit/test_lms_context.py`

**Interfaces:**
- `ExpectedLmsContext`: frozen Pydantic model with exact class/session/date/time fields and optional `source_session_id`.
- `LmsContextAssertion`: frozen Pydantic model with `matched: bool`, `reason_code: str`, and `manual_fallback: bool`.
- `assert_lms_context(expected: ExpectedLmsContext, observed: LmsPageExtract) -> LmsContextAssertion`.

- [ ] **Step 1: Write failing tests** for exact match, similar class, wrong session, wrong date, wrong time, source-ID mismatch, and the rule that mismatch prevents roster processing.
- [ ] **Step 2: Run RED:** `uv run pytest tests/unit/test_lms_context.py -q`; expected module/function-not-found failure.
- [ ] **Step 3: Implement exact comparisons.** Normalize class code with uppercase/trim only; compare integer session and ISO date/time values exactly; return `LMS_CLASS_MISMATCH`, `LMS_SESSION_MISMATCH`, `LMS_DATE_MISMATCH`, `LMS_TIME_MISMATCH`, `LMS_SOURCE_ID_MISMATCH`, or `LMS_CONTEXT_MATCH`. Set `manual_fallback=True` for every mismatch.
- [ ] **Step 4: Run GREEN and commit:** `uv run pytest tests/unit/test_lms_context.py -q`, then `git add apps/browser-runner/src/mindx_runner/lms_context.py apps/browser-runner/tests/unit/test_lms_context.py; git commit -m "feat: add exact lms context assertion"`.

### Task 4: Deterministic student identity mapping

**Files:**
- Create: `apps/browser-runner/src/mindx_runner/lms_identity.py`
- Create: `apps/browser-runner/tests/unit/test_lms_identity.py`

**Interfaces:**
- `ExpectedStudent`: frozen Pydantic model with `internal_id: str`, optional `student_id`, optional `discriminator`, and exact `full_name`.
- `StudentResolution`: frozen Pydantic model with `internal_id: str | None`, `status: Literal["resolved", "unresolvable", "ambiguous"]`, and `reason_code: str`.
- `resolve_lms_student(expected: ExpectedStudent, rows: tuple[LmsRosterRow, ...]) -> StudentResolution`.

- [ ] **Step 1: Write failing tests** for exact stable ID, exact discriminator, exact unique name, `Nguyễn An` vs `Nguyễn Anh`, duplicate names with IDs, duplicate names without discriminator, duplicate page IDs, and row reorder invariance.
- [ ] **Step 2: Run RED:** `uv run pytest tests/unit/test_lms_identity.py -q`; expected module/function-not-found failure.
- [ ] **Step 3: Implement exact matching.** Reject duplicate non-null page IDs/discriminators first. Match expected `student_id`, then discriminator, then NFC + whitespace + casefolded full name only when exactly one candidate has stable identity. Return only `LMS_STUDENT_ID_MATCH`, `LMS_STUDENT_DISCRIMINATOR_MATCH`, `LMS_STUDENT_NAME_MATCH`, `LMS_STUDENT_IDENTITY_UNRESOLVABLE`, or `LMS_STUDENT_IDENTITY_AMBIGUOUS`.
- [ ] **Step 4: Run GREEN:** `uv run pytest tests/unit/test_lms_identity.py -q`; expected all identity tests pass. Confirm no matching branch reads row index.
- [ ] **Step 5: Verify and commit:** run `uv run ruff check src/mindx_runner/lms_identity.py tests/unit/test_lms_identity.py`, `uv run mypy src`, then commit `feat: add deterministic lms student identity mapping` with the Task 4 files.

### Task 5: Read-only/privacy regression, evidence, and final verification

**Files:**
- Modify: `apps/browser-runner/tests/unit/test_network_guard.py`
- Modify: `apps/browser-runner/tests/unit/test_privacy_boundary.py`
- Create: `docs/evidence/phase-4a/V4-P4A-01-lms-reader-fixtures.md`
- Create: `docs/evidence/phase-4a/index.json`
- Create: `docs/evidence/phase-4a/metrics.csv`
- Create: `docs/phase-reports/phase-4a.md`

**Interfaces:**
- Existing `evaluate_request(...)` continues to return `LMS_MUTATION_BLOCKED` for LMS Save/Submit/comment paths and comment-like bodies.
- Existing `assert_agent_page_safe(...)` continues to reject roster HTML from navigation-agent input.
- Evidence contains only synthetic counts, safe reason codes, and source hashes.

- [ ] **Step 1: Add regression assertions** for mutation methods/paths/bodies, roster DOM privacy, and no-homework parser output. Do not add a mutation exception or weaken existing guards.
- [ ] **Step 2: Run focused regression tests:** `uv run pytest tests/unit/test_network_guard.py tests/unit/test_privacy_boundary.py tests/unit/test_lms_parser.py -q`.
- [ ] **Step 3: Run the complete verification matrix from the worktree root:** `uv run pytest`, `uv run ruff check .`, `uv run mypy src`, `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`, `npm run verify:no-secrets`, `npm run verify:no-live-write`, and `npm run test:rls`.
- [ ] **Step 4: Write evidence/report** with exact fresh counts, identity/context reason-code coverage, read-only/privacy results, source hashes, and the explicit synthetic-only/live-BLOCKED limitation. Do not copy raw HTML, student names, credentials, cookies, tokens, or screenshots.
- [ ] **Step 5: Request code review** focused on exact context assertions, duplicate identity handling, no row-order mapping, fallback safety, raw HTML leakage, and read-only guard preservation. Fix all Critical/Important findings and rerun affected checks.
- [ ] **Step 6: Run `git diff --check`, stage only Phase 4A files, and commit:** `git commit -m "feat: add synthetic lms pending reader contract"`.

## Explicitly deferred

- Manual mapping/session-context UI (Phase 4B).
- Live LMS selectors, login, browser-state reuse, owner-controlled smoke, cold/warm timing, and production persistence.
- LMS Save/Submit/update-comment/editor actions.
- Gemini, curriculum, dashboard, and Zalo work from later phases.
