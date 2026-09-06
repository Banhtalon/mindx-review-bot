# Development Speed Policy

Status: active workflow policy for agent-driven development.

Purpose: keep the repository safe without making every small change follow the same high-cost process as migrations, authentication, browser-session, or live-system changes.

This policy changes development process only. It does not relax product safety boundaries, branch protection, `verify`, or the read-only MVP contract.

## Core rule

Use the lightest workflow that is sufficient for the risk of the exact change.

Do not turn a small bug into a phase-wide investigation. Do not reopen already-passing areas unless there is concrete evidence that they are related to the current failure.

Every task must have:

1. a narrow scope;
2. a concrete DONE condition;
3. the smallest relevant test set during implementation;
4. one final required verification checkpoint appropriate to its risk.

## Mode A — FAST

Use for low-risk, localized work such as:

- CSS/copy/UI polish;
- small pure-function bug fixes;
- isolated validation/parsing fixes;
- mechanical refactors with unchanged behavior;
- focused test repairs that do not weaken coverage or safety.

Flow:

`implement -> focused test -> inspect diff -> commit/PR -> required CI`

Rules:

- no Sol plan required;
- no mandatory RED transcript;
- no full repository test suite after every edit;
- no Terra review unless a safety boundary is touched;
- one implementation pass plus focused fixes is preferred.

DONE means the target behavior works, focused tests pass, no unrelated files changed, and required CI passes before merge.

## Mode B — STANDARD

Use for ordinary features or non-trivial bugs that are not high-risk.

Examples:

- new UI/API behavior;
- normal CRUD slice;
- medium refactor;
- workflow logic that does not touch secrets/auth/live systems;
- several related files with clear acceptance criteria.

Flow:

`short plan -> implement -> focused tests -> one integration/checkpoint test -> PR/CI -> review if useful -> merge`

Rules:

- plan should normally fit in the issue or a short task document;
- test affected modules first;
- run broader integration tests once near completion, not after each small fix;
- one review round is the default;
- additional review is required only when a material finding changes the implementation.

## Mode C — STRICT

Use only when the exact change is high-risk.

High-risk boundaries include:

- Supabase migrations/RLS/schema;
- authentication, credentials, session/browser state;
- Teaching/LMS live navigation or selectors;
- student identity/mapping;
- privacy/PII/model payload boundaries;
- live-write safeguards;
- deployment/infrastructure that can affect real jobs;
- material architecture/data-integrity changes.

Flow:

`Sol plan/spec when needed -> implementation -> focused tests -> risk-specific integration/runtime evidence -> full required CI -> fresh Terra review on final head -> Owner merge`

Rules:

- Terra is mandatory for the high-risk diff, not for every intermediate edit;
- do not request fresh Terra review until implementation and deterministic checks are stable;
- if review finds a material problem, fix all related findings in one bounded pass when possible, then run the relevant focused tests and final gates again;
- do not perform full-suite verification twice merely to create duplicate evidence unless the first run is stale because code changed.

## Test ladder

During implementation, climb only as high as needed.

### Level 1 — focused

Run the smallest test file/module that reproduces the behavior.

Examples:

```bash
npx vitest run test/cron-workflow.test.ts
```

```bash
cd apps/browser-runner
uv run pytest tests/unit/test_hosted_probe.py
```

Use Level 1 repeatedly while editing.

### Level 2 — affected subsystem

Run when the focused behavior is green and before declaring the implementation slice complete.

Examples:

```bash
npx vitest run test/cron-workflow.test.ts test/ci-contract.test.ts
```

```bash
cd apps/browser-runner
uv run pytest tests/unit/test_hosted_probe.py tests/unit/test_supabase_client.py tests/unit/test_workflow_contract.py
```

Add lint/typecheck for touched languages when they can catch cross-file errors.

### Level 3 — final repository gate

Run once on the final candidate head, or rely on the required `verify` CI when it covers the same checks.

Repository baseline may include:

- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `npm run verify:no-secrets`
- `npm run verify:no-live-write`
- Supabase reset/RLS tests when Supabase behavior changed
- Python Ruff/Mypy/Pytest when Python behavior changed

Do not rerun unrelated expensive suites after every local fix.

## Stop scope creep

When a new defect is discovered, ask only:

1. Does it prevent the current DONE condition?
2. Was it caused by the current diff?
3. Is it a safety/security issue that must block merge?

If all three are no, record it separately and continue the current task.

Do not silently expand a task from one failing behavior into a general repository audit.

## Review economy

- FAST: Terra normally skipped.
- STANDARD: one review round if useful/risk-routed.
- STRICT: one fresh Terra review on the final stable head is mandatory.
- A new commit invalidates exact-head review evidence only when that review is a required merge gate. Therefore request final review late, not early.
- P2/P3 style or optional-improvement findings do not automatically trigger another implementation/review cycle unless they affect acceptance, safety, correctness, or maintainability materially.

## Evidence economy

Evidence must prove the acceptance criterion, not document every keystroke.

Keep:

- command/test name;
- pass/fail and useful count;
- exact commit/head SHA for final evidence;
- hosted/runtime run link when required;
- concise blocker or cleanup result.

Normally omit:

- duplicate full logs;
- repeated identical PASS runs;
- long reasoning transcripts;
- exhaustive inventories unrelated to the current DONE condition.

Never store secrets, credentials, cookies, tokens, raw authenticated page content, or student PII in evidence.

## Definition of DONE

A task is DONE when:

- its explicit acceptance criteria are met;
- relevant focused/subsystem tests pass;
- required risk-specific runtime evidence passes when applicable;
- required repository CI passes on the final candidate head;
- mandatory risk-routed review is complete;
- no unresolved P0/P1 or material blocking finding remains;
- no out-of-scope behavior was introduced.

DONE does not require proving that the entire repository has no unrelated defects.

## Phase rule

A phase must be decomposed into small closure packets with independent DONE conditions. Finish one packet before opening another.

For Phase 2 hosted/off-PC closure, the active packet plan is `docs/superpowers/plans/2026-09-06-phase2-fast-closure.md`.
