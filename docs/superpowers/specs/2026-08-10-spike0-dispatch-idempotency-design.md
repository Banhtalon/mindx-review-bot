# Spike 0 Dispatch and Idempotency Design

## Goal

Prove the read-only Spike 0 path from a Supabase Edge Function to a manually
dispatched GitHub Actions workflow without duplicate job execution, leaked
secrets, or untrusted job types/payloads.

## Scope

- Add one `dispatch-job` Edge Function for manual owner and trusted Cron
  requests.
- Add internal Postgres RPCs for idempotent enqueue, dispatch claiming, and
  terminal dispatch status transitions.
- Add a synthetic GitHub `workflow_dispatch` workflow with input validation and
  per-job concurrency.
- Add unit, SQL, and mocked GitHub tests plus `V4-S0-03` and `V4-S0-04` evidence.

Out of scope: real LMS/Teaching navigation, Gemini, browser-state encryption,
automatic runner execution, dashboard UI, and real secrets in the repository.

## Recommended architecture

The Edge Function is the only component allowed to call GitHub. It accepts a
manual Supabase JWT or a Cron secret, validates the request, and authorizes a
manual caller as a workspace owner. It then calls server-only Postgres RPCs
using `SUPABASE_SECRET_KEY`; the secret key is never exposed to the client.

The database owns idempotency and the dispatch claim:

```text
request
  -> authenticate/authorize
  -> enqueue(workspace_id, type, idempotency_key, payload)
  -> queued/dispatch_failed --atomic claim--> dispatching
  -> GitHub workflow_dispatch(job_id)
  -> dispatched or dispatch_failed
```

The unique `(workspace_id, idempotency_key)` constraint prevents duplicate job
rows. An atomic `queued|dispatch_failed -> dispatching` update ensures only one
Edge request calls GitHub for a job at a time. GitHub workflow concurrency and
the later runner claim remain the second line of defense for an ambiguous
network response.

## Authentication and attribution

- Manual requests require `Authorization: Bearer <Supabase JWT>`, and the
  caller must be an owner of the requested workspace.
- Cron requests require `X-Cron-Dispatch-Secret` and are restricted to the
  configured `CRON_WORKSPACE_ID`.
- Because `automation_jobs.requested_by` is non-null, Cron uses a dedicated
  synthetic Auth actor configured by `CRON_ACTOR_USER_ID`. The actor UUID is
  configuration, not a secret; its credentials are never stored in code.
- The internal RPCs are revoked from `anon` and `authenticated` and granted
  only to `service_role`. The Edge Function performs the user-facing
  authorization before invoking them.

## Validation and failure behavior

- Allowed job types: `sync_teaching`, `read_lms_pending`.
- Workspace IDs and actor IDs must be canonical UUIDs.
- Idempotency keys are lowercase ASCII, 1–128 characters, and contain no
  whitespace or PII-like free text.
- Payload must be a small JSON object; it cannot contain credential, cookie,
  token, secret, password, or arbitrary URL fields.
- Reusing a key with the same type/payload returns the existing job and does
  not call GitHub again.
- Reusing a key with a different type/payload returns `409`.
- Missing/invalid JWT returns `401`; invalid Cron secret or owner access returns
  `403`; invalid input returns `400`; GitHub failure returns `502` and marks the
  job `dispatch_failed`.
- Responses contain only job ID, status, and safe error code. Tokens and raw
  payloads are never logged or returned.

## Testing strategy

- Pure Edge Function tests inject fake auth, database, and GitHub adapters.
- RED tests cover auth/cron rejection, owner-only access, input validation,
  duplicate idempotency, payload conflict, concurrent dispatch claim, GitHub
  success, and GitHub failure.
- pgTAP tests exercise the internal RPCs, same-key reuse, payload conflict,
  atomic claim, and terminal transitions under a synthetic service role.
- The GitHub workflow is synthetically dispatchable and validates only UUID/job
  type inputs; no real LMS action is performed.
