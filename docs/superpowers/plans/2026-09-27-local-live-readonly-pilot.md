# Local Live Read-only Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the local runner ready for a bounded, read-only Teaching/LMS pilot, connect encrypted browser state and one-time login safely, add revision-checked hosted persistence, and prove the v10 bridge can reach a reviewed pilot without enabling production automation.

**Architecture:** Keep site navigation behind one allowlisted async adapter that only opens configured read pages and passes their HTML to the existing deterministic parsers. Load the active encrypted browser state through the service-only Supabase client and pass it to the guarded browser session; a first login remains an owner-controlled bootstrap because credentials and OTP/CAPTCHA cannot be automated safely. Hosted review-input writes use a single RPC with `expected_revision`; local synthetic storage remains the fallback while Supabase is unavailable. The v10 pilot is a clean, synthetic task with real Antigravity and Codex probes, bounded repair, and no automatic merge.

**Tech Stack:** Python 3.12, browser-use session wrapper, Pydantic parsers, Supabase Postgres RPC/Storage, Node.js/Vitest, Antigravity CLI (`agy`), Codex CLI, GitHub CLI.

**Spec:** `.ai-workflow/V10_CANONICAL_SPEC.md`, `.ai-workflow/MINDX_PROJECT_RULES.md`, and the Owner-provided AI self-operation plan.

## Global Constraints

- Teaching/LMS automation remains read-only; `MVP_LMS_WRITE_ENABLED=false` is mandatory.
- Stable identifiers and exact class/session context are required; no row-order or fuzzy identity guesses.
- Credentials, cookies, browser state, student PII, and tokens stay out of logs, packets, models, frontend output, and commits.
- No CAPTCHA/OTP bypass, LMS Save/Submit/comment, automatic Zalo send, database reset, force push, or automatic merge.
- A hosted/live claim requires hosted/live evidence; local tests cannot close a live gate.
- Existing no-secret, no-live-write, lint, typecheck, test, build, RLS, and workflow-v10 gates remain mandatory.

## Review Focus

- A job with no active browser state must fail with a safe capability/auth status before browser startup. The workspace ID is returned by the claim RPC, so the current runner finalizes that claim as failed rather than opening a browser; a pre-claim state check requires a separate job-metadata RPC.
- A login flow must allow only explicitly configured login paths and must never allow mutation paths.
- A page from the wrong class/session or a duplicate stable ID must be quarantined without persistence.
- A stale `expected_revision` must return a conflict and leave the newer row unchanged.
- A quota, inactive Supabase project, missing adapter, or unavailable Python toolchain must preserve progress and report a waiting/blocking state.

---

### Task 1: Read-only Teaching/LMS adapter and browser-state wiring

**Files:**
- Create: `apps/browser-runner/src/mindx_runner/live_adapter.py`
- Modify: `apps/browser-runner/src/mindx_runner/browser_driver.py`
- Modify: `apps/browser-runner/src/mindx_runner/cli.py`
- Modify: `apps/browser-runner/src/mindx_runner/supabase_client.py`
- Test: `apps/browser-runner/tests/unit/test_live_adapter.py`
- Test: `apps/browser-runner/tests/unit/test_browser_driver.py`
- Test: `apps/browser-runner/tests/unit/test_cli.py`

**Interfaces:**
- `readonly_site_adapter(config, claimed, browser) -> int` reads only the job type and allowlisted URLs from the claimed payload, obtains page HTML, and calls the existing parser; it returns the number of validated records.
- `ReadonlyBrowserSession(storage_state=..., login_paths=...)` remains the only browser entry point.
- `SupabaseRunnerClient.load_active_browser_state(workspace_id, site)` returns encrypted state bytes or `None`; no secret is exposed to the adapter.

- [x] Write failing tests for page-content extraction, job-type URL allowlisting, login-path handling, active-state loading, and safe failure on missing state.
- [x] Implement the minimal adapter and browser-state handoff; keep Teaching/LMS writes disabled.
- [x] Run targeted Python tests, then the full available Python suite.
- [ ] Run an owner-controlled Teaching/LMS login and verify encrypted state activation against the restored hosted project.

### Task 2: Revision-checked review-input persistence

**Files:**
- Modify: `supabase/migrations/20260926000000_review_inputs.sql`
- Modify: `supabase/tests/0006_review_inputs.sql`
- Modify: `apps/browser-runner/src/mindx_runner/supabase_client.py`
- Test: `apps/browser-runner/tests/unit/test_supabase_client.py`

**Interfaces:**
- `update_review_input(..., expected_revision: int) -> ReviewInputSnapshot` calls `update_review_input_if_revision_matches` and maps a conflict to `REVIEW_INPUT_REVISION_CONFLICT`.
- The SQL function updates only when `revision = expected_revision`, preserves `workspace_id`, and returns the new revision.

- [x] Write failing client and SQL contract tests for matching and stale revisions.
- [x] Implement the RPC, immutable workspace enforcement, and client mapping.
- [x] Run client tests and static SQL inspection; do not deploy without hosted verification.
- [ ] Run the pgTAP suite after the owner restores this project and local/hosted database access is available.

### Task 3: Python 3.12 runner verification

**Files:**
- Modify: `apps/browser-runner/pyproject.toml` only if the existing tool configuration cannot run on Python 3.12.
- Create: `scripts/run-python-runner-tests.ps1` only if a checked-in wrapper is needed.
- Test: existing Python unit suite.

- [x] Detect an installed Python 3.12 or the project-supported `uv` runtime without copying credentials.
- [x] Run Ruff and Pytest under Python 3.12; preserve the exact command/output in the pilot evidence.
- [ ] Run Mypy with the locked `browser-use` dependency set; the current machine lacks the complete dependency environment, so this remains unverified.

### Task 4: v10 clean pilot and independent review

**Files:**
- Create: `.workflow-local/task.json` (ignored local packet only)
- Create: `.workflow-local/pilot/*` (ignored evidence only)
- Modify: `.ai-workflow/OWNER_STATUS.md` only with redacted status if needed.

- [x] Freeze a synthetic/local task with base SHA, exact file allowlist, acceptance criteria, risk, complexity, and deterministic gates.
- [ ] Run `npm run qq:doctor` on a clean candidate, then `npm run qq:pilot` using the verified Antigravity worker and Codex reviewer.
- [ ] Run the quota drill; require a fresh safe resume and retain the checkpoint.
- [ ] Run an independent review on the exact head; repair only within the two-round budget.
- [ ] Activate `LOCAL_AUTO` only if all actual probes and evidence pass; otherwise keep `ASSISTED` and report the exact waiting/blocking state.

### Task 5: Branch/PR readiness without merge

**Files:**
- Modify: documentation/status packets only after the pilot is accepted.

- [ ] Create the feature branch from the frozen clean base, run final gates, and verify the exact diff.
- [ ] Push the branch and create a Pull Request only after the pilot reaches `READY_FOR_OWNER`.
- [ ] Never merge automatically; present Owner-facing behavior steps and preserve a rollback checkpoint.
