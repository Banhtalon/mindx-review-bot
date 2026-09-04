# V4-P2-10 Hosted Inventory

- Observed: 2026-09-04
- Main baseline: `255ccf9635aecc50474a0a88049355ef4c3638fc`
- Issue: #11, Scope Revision 1
- Result: BLOCKED pending hosted configuration, hosted execution, and Owner
  off-PC attestation

## Hosted observations

- GitHub recorded 42 `cron-dispatch` runs; 42 concluded `failure`.
- The first inspected run (`32499129628`) and latest inspected run
  (`33821214878`) both emitted only the safe code `CRON_CONFIG_INVALID`.
- GitHub Actions settings showed no repository secrets and no environment
  secrets at inspection time.
- `browser-runner.yml` had zero hosted runs.
- The product CLI invoked `run_job(..., adapter=None)` and therefore stopped at
  `SITE_ADAPTER_NOT_CONFIGURED` before claiming a job.

These observations describe the inspection snapshot only. They are not a hosted
PASS and do not establish live Teaching/LMS readiness.

## Local RED evidence for this implementation

- Cron gate contract: five focused assertions failed before implementation
  because an absent/false gate still reached the network path, malformed gate
  input was not rejected, and the workflow had no explicit gate.
- Hosted workflow contract: both TypeScript and Python contract tests failed
  before implementation because `phase2-hosted-verify.yml` did not exist.
- Hosted Python primitives: test collection failed before implementation because
  `BrowserStateRecord` and `mindx_runner.hosted_probe` did not exist.

Only safe assertion names and counts are retained here. Raw environment values,
HTTP bodies, tokens, cookies, browser state, and provider responses are excluded.

## Local GREEN evidence

Run on Windows with Node/Vitest, the locked Python 3.12 environment, and a
temporary local Supabase stack:

- ESLint: PASS.
- TypeScript typecheck: PASS.
- Vitest: 23 files, 130 tests, PASS.
- Production build: PASS.
- no-secret guard: PASS.
- no-live-write guard: PASS.
- Ruff: PASS.
- Mypy: PASS across 23 source files.
- Pytest: 255 tests, PASS.
- Local Supabase database reset: PASS with all committed migrations.
- pgTAP/RLS: 5 files, 101 assertions, PASS.

These results establish local implementation health only. The manual hosted
workflow has not run and the Owner PC-off condition has not been attested.

## Scope boundary

The implementation may add a manual synthetic hosted probe and a default-off
cron gate. It must not add a Teaching/LMS site adapter, browser navigation, a
product job type, a migration, an LMS write, a Zalo send, or a Phase 3/4/6
feature. Hosted PASS remains blocked until the owner-linked run and exact cleanup
evidence exist.
