# Phase 1–2 Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the missing local/synthetic Phase 1–2 contracts and create honest phase evidence while leaving owner-controlled live work explicitly blocked.

**Architecture:** A dependency-injected AuthGateway keeps React Auth behavior testable without credentials. Postgres owns runner identity, lease and attempt transitions through service-only RPCs; the Python runner supplies a stable runner ID and refreshes the lease during a read-only job. A scheduled GitHub workflow calls the existing Edge dispatch contract with deterministic, non-sensitive inputs.

**Tech Stack:** React 19, TypeScript/Vitest, Supabase JS/Auth, Postgres/pgTAP, Python 3.12/pytest/Ruff/mypy, GitHub Actions, Markdown/JSON/CSV evidence.

## Global Constraints

- MVP 1 remains Teaching/LMS read-only; do not add or exercise LMS `Save`/`Submit`/comment mutation.
- Never request or record passwords, OTPs, cookies, tokens, raw browser state, real student names, or PII in chat, code, logs or evidence.
- Codex may create `.env.example`; Qq enters live values only in GitHub/Supabase secret stores or the signed-in browser session.
- Production browser hosts remain `teachingmindx.top` and `lms.mindx.edu.vn`.
- `AUTOMATION_ENABLED` must be true and `MVP_LMS_WRITE_ENABLED` must be false for the runner.
- Every behavior follows RED → GREEN → REFACTOR → VERIFY.
- Live success is never inferred from synthetic/local tests; owner-controlled rows remain `BLOCKED` until redacted evidence exists.

---

### Task 1: Supabase Auth boundary and protected React shell

**Files:**
- Create: `src/auth/contracts.ts`
- Create: `src/auth/supabaseAuthGateway.ts`
- Create: `src/auth/AuthBoundary.tsx`
- Create: `src/auth/AuthBoundary.test.tsx`
- Create: `src/ui/SafeErrorBoundary.tsx`
- Create: `src/ui/SafeErrorBoundary.test.tsx`
- Modify: `src/main.tsx`
- Modify: `.env.example`
- Modify: `package.json` and `package-lock.json`

**Interfaces:**
- `AuthGateway.getSession(): Promise<AuthSession | null>`
- `AuthGateway.signIn(email: string, password: string): Promise<AuthSession>`
- `AuthGateway.signOut(): Promise<void>`
- `AuthGateway.subscribe(listener: (session: AuthSession | null) => void): () => void`
- `AuthGateway.getWorkspaceRole(workspaceId: string, userId: string): Promise<WorkspaceRole | null>`
- `AuthBoundary` renders loading, sign-in, access-denied or protected children states.

- [ ] **Step 1: Write failing Auth and protected-route tests.**

  Add tests proving an unauthenticated user sees the sign-in form, a successful
  sign-in exposes the protected child and role, logout removes the child,
  reviewer and owner receive distinct role labels, and a missing workspace
  membership is denied. Use a fake `AuthGateway`; do not mock React elements.

- [ ] **Step 2: Run the focused tests and verify RED.**

  Run:

  ```powershell
  npm exec vitest run src/auth/AuthBoundary.test.tsx --reporter=verbose
  ```

  Expected: collection or assertion failure because the Auth boundary files
  and behavior do not exist.

- [ ] **Step 3: Add the Supabase gateway and minimal Auth boundary.**

  Add `@supabase/supabase-js`. Configure the real gateway with persisted
  sessions, `autoRefreshToken: true` and `detectSessionInUrl: false`. Map only
  safe session fields and query `workspace_members.role`; never expose the
  secret key to Vite. Keep blank Vite variables as an explicit synthetic-mode
  fallback so existing fixture tests remain deterministic.

- [ ] **Step 4: Run the focused tests and verify GREEN.**

  Run the same Vitest command and then `npm run typecheck`.

- [ ] **Step 5: Add the safe error boundary test first, then implementation.**

  The test must render a child that throws and assert only the stable message
  `The application could not continue safely. Reload the page to try again.`;
  it must not render the thrown error text. Implement the class boundary with
  `getDerivedStateFromError` and no raw error logging.

- [ ] **Step 6: Wire the boundary and Auth shell into `main.tsx`.**

  Use Auth only when the three `VITE_SUPABASE_*` values are present; otherwise
  render the existing synthetic App inside the safe boundary. Add the three
  blank variable names to `.env.example`.

- [ ] **Step 7: Run the complete web tests and commit.**

  ```powershell
  npm run test
  npm run lint
  git add src/auth src/ui src/main.tsx .env.example package.json package-lock.json
  git commit -m "feat: add protected supabase auth shell"
  ```

### Task 2: Phase 1 seed, CI contract and database evidence hooks

**Files:**
- Modify: `supabase/seed.sql`
- Create: `supabase/tests/0004_phase1_auth.sql`
- Create: `.github/workflows/ci.yml`
- Create: `test/ci-contract.test.ts`
- Modify: `test/supabase-config.test.ts`

**Interfaces:**
- Local seed creates only synthetic owner/workspace/member values with
  `example.invalid` email; it never runs against hosted data automatically.
- CI workflow runs the existing web/privacy gates and locked browser-runner
  checks with `contents: read`.

- [ ] **Step 1: Write failing seed/RLS/CI contract tests.**

  Add pgTAP assertions for the synthetic seed owner role, `workspaces` and
  `workspace_members` RLS, role check constraints and fixed `search_path`.
  Add a Vitest workflow contract test for pull-request/push triggers,
  read-only permissions, secret scan, no-live-write scan and locked Python
  checks.

- [ ] **Step 2: Run the focused tests and verify RED.**

  ```powershell
  npm exec vitest run test/ci-contract.test.ts test/supabase-config.test.ts --reporter=verbose
  npm run test:rls
  ```

  Expected: the CI contract and new pgTAP assertions fail because the seed,
  workflow and complete Phase 1 assertions are absent.

- [ ] **Step 3: Add the local-only synthetic seed and pgTAP assertions.**

  Use deterministic UUIDs and `owner@example.invalid`; use `on conflict` so a
  reset remains repeatable. Keep the fixture isolated from existing test IDs.
  Add only assertions that observe database behavior, not source-text checks.

- [ ] **Step 4: Add the pinned CI workflow and contract.**

  Use the already pinned checkout and uv action SHAs from the repository. Run
  `npm ci`, web gates, `npm run verify:no-secrets`,
  `npm run verify:no-live-write`, `uv sync --locked --project apps/browser-runner`,
  Ruff, mypy and pytest. Do not upload artifacts or expose environment values.

- [ ] **Step 5: Run GREEN verification and commit.**

  ```powershell
  npm exec vitest run test/ci-contract.test.ts test/supabase-config.test.ts
  npx supabase db reset
  npm run test:rls
  git add supabase/seed.sql supabase/tests/0004_phase1_auth.sql .github/workflows/ci.yml test/ci-contract.test.ts test/supabase-config.test.ts
  git commit -m "test: close phase one seed and ci contracts"
  ```

### Task 3: Bounded execution lease, heartbeat and runner ownership

**Files:**
- Create: `supabase/migrations/20260814000000_phase12_lease_retry.sql`
- Create: `supabase/tests/0005_phase12_lease_retry.sql`
- Modify: `apps/browser-runner/src/mindx_runner/live_runner.py`
- Modify: `apps/browser-runner/src/mindx_runner/supabase_client.py`
- Modify: `apps/browser-runner/src/mindx_runner/cli.py`
- Modify: `apps/browser-runner/tests/unit/test_live_runner.py`
- Modify: `apps/browser-runner/tests/unit/test_supabase_client.py`
- Modify: `apps/browser-runner/tests/unit/test_cli.py`

**Interfaces:**
- `LiveRunConfig.runner_id: str` from a safe `RUNNER_ID` environment value.
- `SupabaseRunnerClient.claim_job_run(job_id: str, runner_id: str) -> ClaimedRun`.
- `SupabaseRunnerClient.heartbeat_job(job_id: str, runner_id: str) -> None`.
- `SupabaseRunnerClient.finish_job_run(run_id: str, runner_id: str, status: str, *, records_read: int, error_code: str | None, duration_ms: int = 0) -> None`.
- SQL RPCs require `service_role`, a matching runner ID, a 10-minute lease and
  `attempt_count < max_attempts`; expired leases produce `JOB_LEASE_EXPIRED`.

- [ ] **Step 1: Write failing Python tests for runner ID and heartbeat calls.**

  Add tests for missing/unsafe `RUNNER_ID`, exact claim/heartbeat/finish JSON
  bodies, wrong runner rejection from the fake transport, and a long-running
  adapter receiving at least one heartbeat while `run_job` still closes the
  browser and records a safe terminal result.

- [ ] **Step 2: Run the focused Python tests and verify RED.**

  ```powershell
  uv run --project apps/browser-runner pytest apps/browser-runner/tests/unit/test_live_runner.py apps/browser-runner/tests/unit/test_supabase_client.py apps/browser-runner/tests/unit/test_cli.py -q
  ```

- [ ] **Step 3: Write failing pgTAP lease/retry tests.**

  Cover active lease contention, matching heartbeat extension, wrong-runner
  finish denial, expired lease recovery, and terminal rejection after three
  attempts. The tests must use synthetic UUIDs and no secret values.

- [ ] **Step 4: Run pgTAP and verify RED.**

  ```powershell
  npm run test:rls
  ```

- [ ] **Step 5: Add the migration and minimal client/CLI implementation.**

  Add bounded job columns, runner-owned run metadata, service-only RPCs and
  safe constraints. The migration must replace the existing live-runner RPC
  signatures (and update existing pgTAP callers) rather than leaving an old
  one-argument claim path available. Update the client to send runner IDs,
  update the CLI to heartbeat every 30 seconds during a long adapter call, and
  keep browser cleanup in `finally`. The existing browser-state reset remains
  a service-only operation; hosted owner authorization is an owner-controlled
  live gate and must not be claimed as locally verified.

- [ ] **Step 6: Run GREEN focused and database verification.**

  ```powershell
  uv run --project apps/browser-runner pytest apps/browser-runner/tests/unit -q
  npx supabase db reset
  npm run test:rls
  ```

- [ ] **Step 7: Run Ruff/mypy and commit.**

  ```powershell
  uv run --project apps/browser-runner ruff check .
  uv run --project apps/browser-runner mypy src
  git add supabase/migrations/20260814000000_phase12_lease_retry.sql supabase/tests/0005_phase12_lease_retry.sql apps/browser-runner
  git commit -m "feat: add bounded runner lease and heartbeat"
  ```

### Task 4: Scheduled read-only dispatch contract

**Files:**
- Create: `.github/workflows/cron-dispatch.yml`
- Create: `scripts/cron_dispatch.mjs`
- Create: `test/cron-workflow.test.ts`
- Modify: `package.json`

**Interfaces:**
- `node scripts/cron_dispatch.mjs` reads `SUPABASE_URL`,
  `CRON_DISPATCH_SECRET`, `CRON_WORKSPACE_ID` and `JOB_TYPE` from the
  environment and sends a POST with an empty payload and deterministic key.
- Scheduled UTC jobs are `22:33 sync_teaching`, `15:07 read_lms_pending` and
  `16:37 read_lms_pending` retry; manual dispatch accepts only the two existing
  allowlisted job types.

- [ ] **Step 1: Write failing script/workflow contract tests.**

  Run the script against a local fake fetch and assert the safe request shape,
  deterministic idempotency key and failure on missing configuration. Assert
  the workflow has the three schedules, `contents: read`, non-cancelling
  concurrency and secret names only.

- [ ] **Step 2: Run the focused tests and verify RED.**

  ```powershell
  npm exec vitest run test/cron-workflow.test.ts --reporter=verbose
  ```

- [ ] **Step 3: Implement the script and scheduled workflow.**

  Never print request headers, environment values or response bodies. Print
  only a safe status and UUID when the endpoint accepts the request. Do not
  add cleanup/generation types that the current Edge allowlist rejects.

- [ ] **Step 4: Run GREEN and security checks.**

  ```powershell
  npm exec vitest run test/cron-workflow.test.ts
  npm run verify:no-secrets
  npm run verify:no-live-write
  ```

- [ ] **Step 5: Commit the scheduled contract.**

  ```powershell
  git add .github/workflows/cron-dispatch.yml scripts/cron_dispatch.mjs test/cron-workflow.test.ts package.json
  git commit -m "feat: add scheduled read-only dispatch contract"
  ```

### Task 5: Phase 1–2 evidence indexes and reports

**Files:**
- Create: `docs/evidence/phase-1/index.json`
- Create: `docs/evidence/phase-1/metrics.csv`
- Create: `docs/evidence/phase-1/V4-P1-01.md` through `V4-P1-08.md`
- Create: `docs/phase-reports/phase-1.md`
- Create: `docs/evidence/phase-2/index.json`
- Create: `docs/evidence/phase-2/metrics.csv`
- Create: `docs/evidence/phase-2/V4-P2-01.md` through `V4-P2-10.md`
- Create: `docs/phase-reports/phase-2.md`

**Interfaces:**
- Each index row has `id`, `requirement`, `path`, `status`, `commit`,
  `environment` and `scope`.
- Each evidence document has command/steps, expected, actual, result,
  artifacts and an explicit privacy review.

- [ ] **Step 1: Build the phase matrices from fresh outputs.**

  Link local/synthetic PASS rows only to commands actually run in this branch.
  Link historical Spike 0 evidence only when its requirement is identical.
  Mark hosted Auth, cloud-off-PC, hosted Storage reuse, live browser smoke and
  code review as `BLOCKED` or `MISSING EVIDENCE`, never PASS by inference.

- [ ] **Step 2: Write reports with exit gates and owner actions.**

  State clearly that Phase 1 and Phase 2 are locally implemented but live
  closure remains blocked until Qq configures accounts/secrets and performs
  redacted owner-controlled checks.

- [ ] **Step 3: Validate evidence shape and commit docs.**

  ```powershell
  npm run verify:no-secrets
  git diff --check
  git add docs/evidence/phase-1 docs/evidence/phase-2 docs/phase-reports/phase-1.md docs/phase-reports/phase-2.md
  git commit -m "docs: record phase one and two closure evidence"
  ```

### Task 6: Full verification and review handoff

- [ ] **Step 1: Run all project gates from the worktree root.**

  ```powershell
  npm run lint
  npm run typecheck
  npm run test
  npm run build
  npm run verify:no-secrets
  npm run verify:no-live-write
  uv run --project apps/browser-runner ruff check .
  uv run --project apps/browser-runner mypy src
  uv run --project apps/browser-runner pytest
  npx supabase db reset
  npm run test:rls
  git diff --check
  ```

- [ ] **Step 2: Request task and whole-branch code review.**

  Reviewers must check Auth does not expose backend secrets, SQL RPCs remain
  service-only and runner-owned, schedules cannot dispatch unsupported types,
  the browser remains read-only and evidence does not contain credentials/PII.

- [ ] **Step 3: Prepare the owner-controlled live handoff.**

  Provide a copy-ready checklist for Qq to create Auth users/workspace
  membership, link/deploy Supabase migrations and Edge Function, set GitHub and
  Supabase secrets, run one cloud dispatch with the PC off, verify encrypted
  Storage/reset and record only redacted metadata. Do not perform these actions
  or request secret values in chat.

## Completion boundary

This plan may report local/synthetic PASS for implemented behavior, but the
Phase 1/2 exit gate remains `BLOCKED` until the owner-controlled live rows are
verified. Phase 6 must not start without a documented PASS or an explicit
owner-approved waiver.
