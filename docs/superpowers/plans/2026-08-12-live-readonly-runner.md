# Live Read-only Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed GitHub runner boundary for owner-authorized Teaching/LMS read-only jobs without claiming live site success.

**Architecture:** Validate configuration and request policy before browser startup, claim and finish jobs through service-only Supabase RPCs, and isolate a guarded Browser Use session behind deterministic site-adapter interfaces. Store browser state only as encrypted envelopes in a private bucket.

**Tech Stack:** Python 3.12, `browser-use==0.13.6`, `cryptography`, Supabase Postgres/Storage REST, pgTAP, GitHub Actions.

## Global Constraints

- MVP 1 only reads Teaching and LMS.
- No LMS Save/Submit action exists in the browser runner MVP.
- No CAPTCHA, OTP or anti-bot bypass.
- Identity and sensitive extraction remain deterministic.
- No credential, cookie, token, student name or raw page body in logs/evidence.
- `AUTOMATION_ENABLED` must be true and `MVP_LMS_WRITE_ENABLED` must be false.
- Production host allowlist is `teachingmindx.top,lms.mindx.edu.vn`.
- Python checks: `uv run ruff check .`, `uv run mypy src`, `uv run pytest`.
- Web/RLS/security checks remain required before merge.

---

### Task 1: Runner policy and configuration contract

**Files:**
- Create: `apps/browser-runner/src/mindx_runner/live_runner.py`
- Create: `apps/browser-runner/src/mindx_runner/network_guard.py`
- Test: `apps/browser-runner/tests/unit/test_live_runner.py`
- Test: `apps/browser-runner/tests/unit/test_network_guard.py`

**Interfaces:**
- `load_live_config(environment: Mapping[str, str]) -> LiveRunConfig`
- `validate_job_id(value: str) -> str`
- `classify_request(method: str, url: str, body: bytes | None, content_type: str | None) -> RequestDecision`
- `safe_error_code(error: BaseException) -> str`

- [ ] **Step 1: Write failing tests** for invalid UUID/job type, unsafe flags, malformed base64 key, allowed GET navigation, explicit login POST, mutation methods, Save/Submit paths and comment-like bodies.
- [ ] **Step 2: Run focused tests** with `uv run pytest tests/unit/test_live_runner.py tests/unit/test_network_guard.py -q`; confirm failure because the modules/interfaces do not exist.
- [ ] **Step 3: Implement minimal validators and policy classifier** with no secret values in exceptions or repr output.
- [ ] **Step 4: Run focused tests** and confirm all new cases pass.
- [ ] **Step 5: Refactor only after green** to share host/path constants with existing `guardrails.py` without changing existing behavior.
- [ ] **Step 6: Commit** with `feat: add live runner safety contract`.

### Task 2: Supabase runner claim and encrypted-state persistence

**Files:**
- Create: `supabase/migrations/20260812000000_live_runner.sql`
- Modify: `supabase/tests/0002_spike0_dispatch.sql`
- Create: `supabase/tests/0003_live_runner.sql`
- Create: `apps/browser-runner/src/mindx_runner/supabase_client.py`
- Test: `apps/browser-runner/tests/unit/test_supabase_client.py`

**Interfaces:**
- `SupabaseRunnerClient.claim_job_run(job_id: str) -> ClaimedRun`
- `SupabaseRunnerClient.finish_job_run(run_id: str, status: RunStatus, records_read: int, error_code: str | None) -> None`
- `SupabaseStorageObjectStore.put/get/delete(...)` implements the existing `ObjectStore` protocol.

- [ ] **Step 1: Write pgTAP and unit tests** for service-only claim/finish, single active run, valid terminal statuses, private browser-state metadata, and no raw state in metadata.
- [ ] **Step 2: Run `npm run test:rls`** and confirm RED from missing RPC/table/client behavior.
- [ ] **Step 3: Add the migration** with locked-down RPCs, RLS, a private-state metadata table and Storage object policies keyed by workspace UUID.
- [ ] **Step 4: Implement the REST client** using standard-library HTTP and redacted error mapping; never log headers/body.
- [ ] **Step 5: Run focused Python and pgTAP tests** and confirm GREEN.
- [ ] **Step 6: Commit** with `feat: add live runner Supabase lifecycle`.

### Task 3: Guarded browser boundary and CLI

**Files:**
- Create: `apps/browser-runner/src/mindx_runner/browser_driver.py`
- Create: `apps/browser-runner/src/mindx_runner/cli.py`
- Modify: `apps/browser-runner/pyproject.toml`
- Test: `apps/browser-runner/tests/unit/test_browser_driver.py`
- Test: `apps/browser-runner/tests/unit/test_cli.py`

**Interfaces:**
- `ReadonlyBrowserSession.start() -> None`
- `ReadonlyBrowserSession.open(url: str) -> None`
- `ReadonlyBrowserSession.close() -> None`
- `run_job(job_id: str, environment: Mapping[str, str]) -> SafeRunSummary`

- [ ] **Step 1: Write failing tests** for allowlisted startup options, no trace/video/screenshot settings, cleanup on adapter error, preflight-only behavior and safe summary fields.
- [ ] **Step 2: Run focused tests** and confirm RED because the driver/CLI are absent.
- [ ] **Step 3: Implement the guarded BrowserSession wrapper** with request callbacks, allowlisted domains and `finally` cleanup.
- [ ] **Step 4: Implement CLI entry points**; reject missing site adapter configuration before browser startup.
- [ ] **Step 5: Add the `mindx-runner` console script** and run the focused tests GREEN.
- [ ] **Step 6: Commit** with `feat: add guarded live runner cli`.

### Task 4: GitHub workflow and evidence

**Files:**
- Create: `.github/workflows/browser-runner.yml`
- Create: `apps/browser-runner/tests/unit/test_workflow_contract.py`
- Create: `docs/evidence/spike-0/V4-S0-05-live-runner-contract.md`
- Modify: `docs/evidence/index.json`
- Modify: `docs/phase-reports/spike-0.md`

**Interfaces:**
- Workflow inputs: `job_id`, `job_type` (`sync_teaching` or `read_lms_pending`).
- Runner command: `uv run --project apps/browser-runner mindx-runner run "$JOB_ID"`.

- [ ] **Step 1: Write failing static contract tests** for `workflow_dispatch`, `contents: read`, 15-minute timeout, non-cancelling concurrency, pinned action SHAs, required secret names and `MVP_LMS_WRITE_ENABLED=false`.
- [ ] **Step 2: Run the focused contract test** and confirm RED because the live workflow is absent.
- [ ] **Step 3: Add the workflow** with no screenshots/artifacts and secrets scoped to the runner step.
- [ ] **Step 4: Add redacted evidence** recording contract PASS while live Teaching/LMS cold/warm metrics remain BLOCKED.
- [ ] **Step 5: Run all required checks**: web lint/typecheck/test/build, Python lint/typecheck/test, no-secrets, no-live-write and RLS.
- [ ] **Step 6: Request code review**, fix Important findings, verify again, then commit with `feat: add live read-only runner workflow`.

## Verification checklist

- [ ] New tests were observed failing before implementation.
- [ ] All Python/web/RLS/security checks pass with fresh output.
- [ ] No secret or PII value appears in the diff, logs or evidence.
- [ ] Live site adapter is not represented as verified without owner-controlled runs.
- [ ] Branch remains separate from `main` until review and PR merge.
