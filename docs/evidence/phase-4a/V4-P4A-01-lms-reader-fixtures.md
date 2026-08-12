# Evidence V4-P4A-01 — LMS pending reader contract

- Date: 2026-08-13
- Reviewed implementation endpoint: `2e23910` (`3976018..2e23910`)
- Environment: worktree `codex/phase4a-lms-reader`; Node/Vitest/Vite; local Supabase CLI; `uv` app-scoped Python environment under `apps/browser-runner`
- Data class: synthetic
- Requirement: deterministic pending-session selection, exact LMS context and student identity, preserved read-only mutation guard, preserved navigation privacy boundary, and source-hash-only parser output.

## Command/steps

- `uv run pytest` from the worktree root
- `uv run ruff check .` from the worktree root
- `uv run mypy src` from the worktree root
- `cd apps/browser-runner && uv run pytest tests/unit/test_network_guard.py tests/unit/test_privacy_boundary.py tests/unit/test_lms_parser.py -q`
- `cd apps/browser-runner && uv run pytest tests/unit/test_lms_pending.py tests/unit/test_lms_context.py tests/unit/test_lms_identity.py -q`
- `cd apps/browser-runner && uv run pytest tests/unit/test_lms_parser.py tests/unit/test_lms_context.py tests/unit/test_lms_identity.py -q`
- `cd apps/browser-runner && uv run pytest`
- `cd apps/browser-runner && uv run ruff check .`
- `cd apps/browser-runner && uv run mypy src`
- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `npm run verify:no-secrets`
- `npm run verify:no-live-write`
- `npx supabase db reset`
- `npm run test:rls`

## Expected

- Guard/privacy/parser regressions remain green with exact synthetic counts.
- The LMS mutation boundary still blocks save/submit/comment-like requests.
- The navigation privacy boundary still blocks roster-bearing HTML.
- No-homework parser output remains safe: `homework=None`, source digest only.
- Worktree-root Python failures remain explicit and separate from app-scoped Python passes.
- Local Supabase reset completes before RLS tests, or exact failure output is recorded without a false pass claim.

## Actual

- FAIL `uv run pytest` at the worktree root — `Failed to spawn: pytest` / `program not found`.
- FAIL `uv run ruff check .` at the worktree root — `Failed to spawn: ruff` / `program not found`.
- FAIL `uv run mypy src` at the worktree root — `Failed to spawn: mypy` / `program not found`.
- PASS focused guard/privacy/parser suite from `apps/browser-runner` — 54 tests.
- PASS focused pending/context/identity suite from `apps/browser-runner` — 34 tests.
- PASS focused parser/context/identity final-fix suite from `apps/browser-runner` — 49 tests.
- PASS `cd apps/browser-runner && uv run pytest` — 192 tests.
- PASS `cd apps/browser-runner && uv run ruff check .`.
- PASS `cd apps/browser-runner && uv run mypy src` — 20 source files.
- PASS `npm run lint`.
- PASS `npm run typecheck`.
- PASS `npm run test` — 11 files, 46 tests.
- PASS `npm run build`.
- PASS `npm run verify:no-secrets`.
- PASS `npm run verify:no-live-write`.
- PASS `npx supabase db reset`.
- PASS first final-fix `npm run test:rls` after reset — 67 pgTAP assertions.

The verified contract still holds:

- LMS network guard returns `LMS_MUTATION_BLOCKED` for `POST`, `PUT`, `PATCH`, and `DELETE` mutations, case-insensitive save/comment/editor paths, mutation-like request bodies on `GET`/`HEAD`/`OPTIONS`, and non-`POST` requests to an otherwise allowlisted login path.
- Navigation privacy boundary rejects roster HTML when it contains `data-student-id`, `data-discriminator`, `data-roster`, or unmarked roster table/list markup.
- Safe navigation output remains only `<main data-class-code="..." data-session-number="..."></main>`.
- The no-homework parser fixture still returns `homework=None` and only keeps a SHA-256 `source_page_hash`.
- Name fallback resolves only when there is exactly one exact-name candidate and that row has stable identity; mixed-identity duplicates remain ambiguous under row reordering.
- Element identity, rather than tag-depth counters, keeps same-tag nested rows inside the active LMS context while excluding outside rows.
- A semantically valid context with zero student rows fails closed as `LMS_DATA_INVALID`.
- Public parser errors retain only their stable code; source-derived values and raw HTML are absent from the exception cause, context, and parser traceback frames.
- `resolve_lms_student_in_context(...)` performs the context assertion before identity resolution and returns no student resolution on mismatch.
- Optional source-session IDs are compared only when present on both sides.

Safe reason-code coverage:

- Pending selection: `PENDING_ELIGIBLE`, `PENDING_FUTURE`, `PENDING_TOO_OLD`, `PENDING_WORKFLOW_NOT_PENDING`, `PENDING_IDENTITY_INCOMPLETE`.
- LMS context assertion: `LMS_CONTEXT_MATCH`, `LMS_CLASS_MISMATCH`, `LMS_SESSION_MISMATCH`, `LMS_DATE_MISMATCH`, `LMS_TIME_MISMATCH`, `LMS_SOURCE_ID_MISMATCH`.
- LMS student identity: `LMS_STUDENT_ID_MATCH`, `LMS_STUDENT_DISCRIMINATOR_MATCH`, `LMS_STUDENT_NAME_MATCH`, `LMS_STUDENT_IDENTITY_UNRESOLVABLE`, `LMS_STUDENT_IDENTITY_AMBIGUOUS`.

Safe source-hash coverage:

- `normal-session.html` → `6e464ace40744727667520c87d492fc04840816dbaaaaf656af7299cb2cca958`
- `no-homework.html` → `2b594098706077187638d4f605165048e21459e6b8d567b00653c62a7576b937`
- `duplicate-name.html` → `b455679301adc5e94a33574c2c5f8c4d3bd1d62c8f95ce0b34ccfd8437cd6ea1`
- `ambiguous-name.html` → `e3f18ca1d62d3e455f0552204c2d526309d7b0e411b9b91e0787aa70eef14a68`
- `row-reordered.html` → `8cb258f5120744f74fa87388f2d33500b9e75a65a1010464f64a7033609ff33a`
- `outside-context-decoy.html` → `e4f89f0e2791789b9480bf054cd7492cd94d9703e61d5ae29e72f77e5f077745`
- `same-tag-nested.html` → `c0185543de2e239dc3d772b1949aa399733aa8b3a928ff79d297f9e45c4fbdcf`

Live limitation remains explicit: this evidence is synthetic-only and does **not** claim a live LMS read, selector validation, browser-state reuse, production persistence, cold/warm timing, or owner-controlled smoke. Those live checks remain BLOCKED until an explicitly approved live phase.

## Result

- SCOPED PASS for the app-scoped synthetic Phase 4A reader contract and its read-only/privacy regressions.
- FAIL remains recorded for all three worktree-root Python entry points; app-scoped PASS results do not replace those failures.

## Artifacts

- `apps/browser-runner/tests/unit/test_network_guard.py`
- `apps/browser-runner/tests/unit/test_privacy_boundary.py`
- `apps/browser-runner/tests/unit/test_lms_parser.py`
- `apps/browser-runner/tests/unit/test_lms_pending.py`
- `apps/browser-runner/tests/unit/test_lms_context.py`
- `apps/browser-runner/tests/unit/test_lms_identity.py`
- `apps/browser-runner/tests/fixtures/lms/same-tag-nested.html`
- `docs/evidence/phase-4a/index.json`
- `docs/evidence/phase-4a/metrics.csv`
- `docs/phase-reports/phase-4a.md`
- `.superpowers/sdd/2026-08-12-lms-reader-phase4a/final-fix-report.md`

## Privacy review

- [x] No credentials
- [x] No cookies/tokens
- [x] No raw HTML in evidence
- [x] No real student names or notes
- [x] No screenshots, traces, video, or HAR
- [x] No live LMS Save/Submit/update-comment action
- [x] No live result represented as passed
