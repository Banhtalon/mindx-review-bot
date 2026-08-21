# Phase 1–2 Closure Design

**Date:** 2026-08-14
**Status:** Approved by Qq for implementation
**Scope:** Local/synthetic implementation and evidence only

## Goal

Complete the missing local/synthetic contracts for V4 Phase 1 and Phase 2,
then record the remaining owner-controlled live gates explicitly as `BLOCKED`
until Qq performs them through Supabase, GitHub Actions, and signed-in
read-only browser sessions.

## Current gap

The repository already contains the Spike 0 schema/RLS foundation, dispatch
state machine, AES-GCM browser-state envelope, private Storage contract and
read-only runner guard. It does not yet have a phase-level Auth UI contract,
local synthetic owner seed, general CI workflow, or the complete execution
lease/heartbeat/bounded-retry contract required by the V4 Phase 1–2 checklists.

## Design

### Phase 1: Auth and protected application boundary

- Add a small `AuthGateway` interface so React tests use a deterministic fake
  while production uses `@supabase/supabase-js` with only `VITE_SUPABASE_URL`,
  `VITE_SUPABASE_PUBLISHABLE_KEY` and `VITE_SUPABASE_WORKSPACE_ID`.
- Configure Supabase Auth with persisted sessions, automatic token refresh and
  URL-session detection disabled.
- Add an `AuthProvider`, sign-in form, protected route, workspace-role lookup,
  owner/reviewer role surface and logout action. The existing synthetic App
  remains available when the Vite Auth variables are intentionally blank for
  local fixture work.
- Add a safe error boundary that exposes only a stable recovery message and
  never renders raw exception text.
- Add a local-only synthetic owner/workspace/member seed and a CI workflow that
  runs the web, runner and privacy gates. No real account or secret is seeded.

### Phase 2: Execution lease and dispatch schedule

- Extend the job/run schema with bounded attempts, runner ownership,
  heartbeat/lease timestamps and safe run metrics.
- Replace the runner claim/finish path with service-only RPCs that require a
  validated runner ID. A second runner cannot finish another runner's run.
- Add `heartbeat_automation_job(job_id, runner_id)` and a 10-minute lease.
  Expired runs become safe failures and can be reclaimed only while the job is
  below `max_attempts`.
- Keep AES-256-GCM state encryption, key-version checks, private Storage and
  reset behavior unchanged; add only the missing runner integration and tests.
- Add a scheduled GitHub workflow contract for the two read-only job types.
  It sends only a workspace ID, allowlisted type, deterministic idempotency key
  and empty payload. Secrets are referenced by name only.

## Explicit non-scope

- No password, OTP, cookie, token, real learner name, raw browser state or PII
  is added to the repository or evidence.
- No LMS `Save`, `Submit`, comment mutation, Zalo delivery, CAPTCHA bypass or
  live browser navigation is added.
- No hosted Supabase migration/function deployment, Auth account creation,
  GitHub secret entry, cloud-off-PC run or live Teaching/LMS smoke is claimed
  by this implementation. Those are owner-controlled gates.

## Acceptance criteria

- New Auth, role, protected-route, safe-error, seed and CI contracts have
  failing tests observed before implementation and passing tests afterward.
- Local Postgres tests cover runner ownership, heartbeat, lease expiry and
  bounded retry without weakening existing RLS or private Storage policies.
- Python runner uses a stable runner ID, emits only safe metrics, heartbeats
  during a long read-only job and always closes the browser in `finally`.
- Scheduled workflow validation covers all scheduled UTC expressions,
  read-only permissions, secret names, deterministic idempotency and no
  artifact upload.
- Phase-level evidence indexes and reports link every `V4-P1-*` and `V4-P2-*`
  row to a command, artifact, commit and honest status.
