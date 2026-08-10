# Spike 0 Dispatch and Idempotency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a server-only Supabase Edge Function that idempotently enqueues Spike 0 jobs and dispatches a synthetic GitHub Actions workflow exactly once per claimed job.

**Architecture:** Postgres owns the unique idempotency key and atomic dispatch claim. The Edge Function authenticates manual JWT or Cron secret requests, authorizes owners, calls server-only RPCs, and invokes GitHub only after a successful claim. Pure TypeScript adapters are dependency-injected for tests, while the Deno entrypoint uses fetch and environment secrets.

**Tech Stack:** Supabase Postgres/pgTAP, Supabase Edge Functions on Deno 2, TypeScript/Vitest, GitHub Actions `workflow_dispatch`, fetch-based adapters.

## Global Constraints

- Spike 0 remains synthetic/read-only; no LMS Save/Submit, Zalo automation, CAPTCHA/OTP bypass, or live roster data.
- Allowed job types are exactly `sync_teaching` and `read_lms_pending`.
- No credential, cookie, token, raw payload, or PII is written to logs, evidence, frontend code, or responses.
- `automation_jobs.requested_by` remains non-null; manual JWT requests use the authenticated user and Cron uses `CRON_ACTOR_USER_ID`.
- GitHub tests use a mock fetch; real GitHub dispatch is never performed by unit tests.
- Every behavior follows RED → GREEN → REFACTOR → VERIFY.

---

### Task 1: Add internal idempotency and dispatch RPCs

**Files:**
- Create: `supabase/migrations/20260810000001_spike0_dispatch.sql`
- Create: `supabase/tests/0002_spike0_dispatch.sql`

**Interfaces:**
- `public.enqueue_automation_job(uuid, text, text, jsonb, uuid)` returns one row containing `job_id`, `status`, `idempotency_key`, `payload_json`, and `created`.
- `public.claim_automation_job_dispatch(uuid)` returns `claimed` and `status`.
- `public.finish_automation_job_dispatch(uuid, text)` returns the resulting status.

- [ ] **Step 1: Write failing pgTAP assertions** for the internal functions, same-key reuse, payload conflict, first claim, duplicate claim, success transition, and failed transition.

- [ ] **Step 2: Run the SQL test**

Run: `npm run test:rls`

Expected: FAIL because the three RPCs do not exist.

- [ ] **Step 3: Implement the migration**

Use `security definer`, `set search_path = ''`, reject callers whose role is
not `service_role`, validate the two job types and key shape, use
`ON CONFLICT (workspace_id, idempotency_key) DO NOTHING`, compare type/payload
on reuse, and allow only `queued|dispatch_failed -> dispatching` and
`dispatching -> dispatched|dispatch_failed` transitions.

- [ ] **Step 4: Run the SQL test again**

Run: `npm run test:rls`

Expected: PASS with all assertions.

- [ ] **Step 5: Commit**

```powershell
git add supabase/migrations/20260810000001_spike0_dispatch.sql supabase/tests/0002_spike0_dispatch.sql
git commit -m "feat: add idempotent dispatch RPCs"
```

### Task 2: Implement pure dispatch orchestration

**Files:**
- Create: `supabase/functions/_shared/dispatch.ts`
- Create: `test/dispatch.test.ts`

**Interfaces:**
- `handleDispatch(command, dependencies, config): Promise<DispatchResult>`.
- Dependencies provide `authenticateUser`, `authorizeOwner`, `enqueue`, `claim`, `finish`, and `dispatchGitHub`.
- Results contain only `jobId`, `status`, `created`, and safe `errorCode` values.

- [ ] **Step 1: Write failing Vitest tests** for missing auth, invalid Cron secret, non-owner, invalid type/key/payload, first dispatch, same-key reuse, payload conflict, dispatch claim contention, GitHub failure, and GitHub success.

- [ ] **Step 2: Run the focused tests**

Run: `npx vitest run test/dispatch.test.ts --reporter=verbose`

Expected: FAIL because the orchestration module does not exist.

- [ ] **Step 3: Implement the smallest pure state machine**

Authorize first, enqueue second, claim third, call GitHub fourth, and finish
the database status last. Never include secrets or payloads in thrown errors or
results. Return an existing terminal/in-progress job without another GitHub
call.

- [ ] **Step 4: Run focused tests and refactor**

Run: `npx vitest run test/dispatch.test.ts --reporter=verbose`

Expected: PASS for all dispatch behaviors.

- [ ] **Step 5: Commit**

```powershell
git add supabase/functions/_shared/dispatch.ts test/dispatch.test.ts
git commit -m "feat: add dispatch idempotency state machine"
```

### Task 3: Add Deno Edge Function adapters

**Files:**
- Create: `supabase/functions/dispatch-job/index.ts`
- Modify: `.env.example`
- Modify: `scripts/verify_no_secrets.mjs` only if a scanner test proves a safe false positive.
- Test: `test/dispatch.test.ts`

**Interfaces:**
- HTTP method: `POST /functions/v1/dispatch-job`.
- Manual headers: `Authorization: Bearer <JWT>`.
- Cron header: `X-Cron-Dispatch-Secret`.
- Body: `{ workspace_id, type, idempotency_key, payload? }`.

- [ ] **Step 1: Add adapter tests** that inject fake `fetch` responses for Auth, workspace role, RPCs, and GitHub `204`/error responses.

- [ ] **Step 2: Run the focused tests**

Run: `npx vitest run test/dispatch.test.ts --reporter=verbose`

Expected: FAIL for missing HTTP adapter behavior.

- [ ] **Step 3: Implement `index.ts`** with `Deno.serve`, strict JSON parsing, environment validation, safe HTTP status mapping, and fetch adapters. Use `SUPABASE_SECRET_KEY`, `GITHUB_DISPATCH_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_WORKFLOW_ID`, `GITHUB_REF`, `CRON_DISPATCH_SECRET`, `CRON_ACTOR_USER_ID`, and `CRON_WORKSPACE_ID` only from Edge secrets/environment.

- [ ] **Step 4: Add blank names to `.env.example` and run security checks**

Run: `npm run verify:no-secrets; npm run verify:no-live-write`

Expected: PASS and no secret values printed.

- [ ] **Step 5: Commit**

```powershell
git add supabase/functions/dispatch-job/index.ts supabase/functions/_shared/dispatch.ts .env.example test/dispatch.test.ts
git commit -m "feat: add dispatch job edge function"
```

### Task 4: Add synthetic GitHub workflow

**Files:**
- Create: `.github/workflows/spike0-dispatch-probe.yml`
- Create: `test/workflow-contract.test.ts`

- [ ] **Step 1: Write a failing workflow contract test** that checks manual dispatch inputs, UUID/job-type validation, read-only permissions, concurrency group, and no Save/Submit action.

- [ ] **Step 2: Run the contract test**

Run: `npx vitest run test/workflow-contract.test.ts --reporter=verbose`

Expected: FAIL because the workflow does not exist.

- [ ] **Step 3: Add the workflow** with `workflow_dispatch` inputs `job_id` and `job_type`, `contents: read`, `cancel-in-progress: false`, a 15-minute timeout, and a shell-only synthetic validation step. Do not use floating third-party action tags.

- [ ] **Step 4: Run the contract and live-write checks**

Run: `npx vitest run test/workflow-contract.test.ts --reporter=verbose; npm run verify:no-live-write`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add .github/workflows/spike0-dispatch-probe.yml test/workflow-contract.test.ts
git commit -m "test: add synthetic dispatch workflow contract"
```

### Task 5: Evidence and final verification

**Files:**
- Modify: `docs/evidence/index.json`
- Modify: `docs/evidence/spike-0/V4-S0-03.md`
- Modify: `docs/evidence/spike-0/V4-S0-04.md`
- Modify: `docs/evidence/spike-0/metrics.csv`
- Modify: `docs/phase-reports/spike-0.md`

- [ ] **Step 1: Record synthetic dispatch/idempotency evidence** with mock GitHub results and clearly mark real GitHub/cloud dispatch BLOCKED until owner secrets are configured.

- [ ] **Step 2: Run the complete verification suite**

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
npm run verify:no-secrets
npm run verify:no-live-write
uv run ruff check .
uv run mypy src
uv run pytest
npm run test:rls
```

- [ ] **Step 3: Request code review** for the implementation range.

- [ ] **Step 4: Commit evidence and final report**

```powershell
git add docs/evidence docs/phase-reports/spike-0.md
git commit -m "docs: record spike 0 dispatch evidence"
```
