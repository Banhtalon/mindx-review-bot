# Live Read-only Runner Design

- Date: 2026-08-12
- Status: Accepted for implementation in `codex/live-readonly-runner`
- Scope: live-runner infrastructure and fail-closed workflow boundary

## Goal

Turn the synthetic browser runner into a guarded execution boundary that can
later run owner-authorized Teaching/LMS read-only adapters without introducing
LMS Save/Submit behavior, credential logging, arbitrary URL navigation or
unreviewed site selectors.

This work does not claim a live Teaching/LMS smoke pass. The live gate remains
blocked until site-specific navigation/extraction contracts are verified by the
owner on the real sites.

## Decisions

1. Use deterministic runner code for identity and extraction. Browser Use may
   provide a browser session, but no navigation agent receives roster HTML or
   student names.
2. Allow only `https` requests to `teachingmindx.top` and
   `lms.mindx.edu.vn` in production mode. Read requests are allowed; only
   explicitly configured login POST requests may be allowed. LMS mutation
   routes and comment-like payloads fail closed.
3. Require `AUTOMATION_ENABLED=true` and
   `MVP_LMS_WRITE_ENABLED=false`. Missing or unsafe configuration stops before
   browser startup.
4. Claim the automation job and create one run row before browser startup.
   The job is finished with a safe status and numeric record count; secrets,
   cookies, page bodies and PII never enter logs or evidence.
5. Store browser state as AES-256-GCM envelopes in a private Supabase Storage
   bucket. Database metadata contains only workspace/site/version/status,
   object path, key version and a state hash.
6. Use a manual `workflow_dispatch` workflow with `contents: read`, pinned
   action references, a 15-minute timeout and non-cancelling per-job
   concurrency.

## Components

### Runner configuration and safety

`mindx_runner.live_runner` validates UUIDs, job types, required environment
values and the 32-byte base64 encryption key. It exposes safe result/error
types and does not expose secret values.

`mindx_runner.network_guard` classifies requests by host, method, path and
content-type. It permits navigation/read methods and a small explicit login
POST allowlist. It rejects mutation methods, Save/Submit/comment paths and
comment-like request bodies.

### Supabase adapters

`mindx_runner.supabase_client` calls only the documented RPC and Storage REST
endpoints using the server-side secret key. It supports atomic job claim,
run completion, encrypted object put/get/delete and browser-state metadata
activation/reset. It never prints authorization headers or response bodies.

### Browser boundary

`mindx_runner.browser_driver` wraps `browser_use.browser.BrowserSession` with
allowlisted domains, no screenshots/traces/video and a request guard. The
driver is a narrow interface so synthetic tests can use a fake page without
opening a real site.

Site-specific Teaching and LMS adapters are separate from this boundary. They
must provide deterministic selectors and identity assertions before a live
smoke run is enabled.

### Workflow and CLI

`mindx_runner.cli` provides `preflight` and `run` entry points. `preflight`
validates configuration without starting a browser. `run` validates, claims,
executes the registered site adapter and always closes the browser and removes
temporary state in `finally`.

The workflow installs the locked Python project, installs Chromium, passes
secrets only to the runner process and invokes `mindx-runner run`.

## Data flow

```text
workflow_dispatch
  -> validate JOB_ID/job_type
  -> runner preflight
  -> Supabase claim_job_run RPC
  -> private encrypted state download
  -> guarded BrowserSession
  -> deterministic site adapter
  -> encrypted state upload + metadata activation
  -> finish_job_run RPC
  -> safe summary in GitHub log
```

Any error before or during browser execution maps to a safe allowlisted error
code. CAPTCHA, OTP, anti-bot detection, ambiguous identity, selector changes
and mutation attempts stop the run; they are never bypassed or retried by a
loop.

## Testing

- Unit tests prove configuration validation, URL/method/body policy, safe
  redaction, job request parsing and lifecycle cleanup.
- pgTAP tests prove runner claim/finish and browser-state metadata RLS/RPC
  boundaries.
- The workflow has a static contract test for permissions, pinned actions,
  secret names, timeout and the read-only flag.
- Existing web/Python/RLS/security suites remain required.
- Live Teaching/LMS metrics remain BLOCKED until owner-controlled cold/warm
  runs produce redacted evidence.

## Explicit non-goals

- No LMS Save, Submit, update-comment or editor action.
- No Zalo dispatch.
- No CAPTCHA/OTP/anti-bot bypass.
- No real credentials, cookies, screenshots, traces or student data in the
  repository or evidence.
- No guessed selectors or arbitrary URLs.
