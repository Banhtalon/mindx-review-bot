# Solo-owner Terra Review Gate Plan

## Context

The repository has one GitHub owner account (`Banhtalon`). Requiring one GitHub approval on a PR authored by that same account makes the branch rule impossible to satisfy because self-approval is not an independent approval.

Owner approved a material workflow revision on 2026-09-03: replace the impossible second-account approval requirement with a deterministic required `review-gate` status check that proves a fresh Terra xHigh review is bound to the exact current PR head.

Authoritative control issue: #7.

Owner approval record: https://github.com/Banhtalon/mindx-review-bot/issues/7#issuecomment-5526241968

This is `scope_revision: 2`. The reset starts with `fix_reentries: 0`.

## Goal

For a solo-owner repository, make merge require both:

1. deterministic repository verification (`verify`), and
2. deterministic validation of a fresh Terra review attestation (`review-gate`).

The gate must fail closed when the review is absent, stale, malformed, not bound to the current PR head, or reports unresolved P0/P1 findings.

## Non-goals

This design does not:

- create a second GitHub identity;
- claim cryptographic proof that Terra itself authored a GitHub comment;
- let Gemini/Antigravity workers author or edit Terra attestations;
- let AI merge directly to `main`;
- weaken existing `verify`, safety, privacy, no-secrets, no-live-write, RLS, or runner gates;
- enable unattended development agents before the manual pilot succeeds;
- change product behavior.

## Trust model

This repository is solo-owner.

Therefore review provenance is **process-enforced, not cryptographically attributable to a second GitHub identity**.

The deterministic gate proves:

- a review attestation exists;
- it names Terra xHigh as the reviewer model;
- it is bound to the exact current PR head SHA;
- it is bound to the linked authoritative control issue and current `scope_revision`;
- the verdict is `RECOMMEND_PASS`;
- P0 and P1 counts are zero;
- material findings are marked resolved;
- a new push makes the old attestation stale automatically because `head_sha` changes.

Fresh-context independence remains an operational rule enforced by the Terra review skill and review packet.

## Required branch rules after implementation

`protect-main` must require:

- pull request before merge;
- `verify` required status check;
- `review-gate` required status check;
- branch up to date before merge;
- conversation/review-thread resolution before merge;
- block force pushes;
- no bypass actors;
- `Required approvals = 0` for this single-account repository.

`Dismiss stale approvals` is not required because GitHub human approvals are not the review authority in this solo-owner design. Freshness is enforced by the attestation `head_sha` plus required `review-gate` on the current head.

## Terra attestation format

The controller/Owner posts the Terra result to the PR conversation after a fresh Terra review.

Use exactly one machine-readable block per attestation:

```text
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
reviewer_model: terra-xhigh
control_issue: 7
scope_revision: 2
pr_number: 6
head_sha: <40-char current PR head SHA>
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: <ISO-8601 UTC timestamp>
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
```

Allowed verdicts in stored attestations:

- `RECOMMEND_PASS`
- `NEEDS_FIX`
- `BLOCKED`

Only `RECOMMEND_PASS` may satisfy the gate.

The attestation must not contain chain-of-thought.

## Gate behavior

Create a dedicated GitHub Actions workflow, recommended path:

`.github/workflows/review-gate.yml`

Required job/context name:

`review-gate`

Trigger initially on:

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]
```

The initial run is expected to fail closed until a current-head Terra attestation exists.

After Terra review is posted, rerun the failed `review-gate` job/run on the same PR head. The rerun must read comments again and may then pass.

A new commit triggers `synchronize`, producing a new head SHA. The previous attestation no longer matches, so `review-gate` fails again until Terra reviews the new head.

This manual rerun is acceptable for the migration and manual pilot. Automatic comment-triggered rerun can be considered only after the pilot succeeds.

## Permissions

Use minimum read-only permissions needed by the gate, for example:

```yaml
permissions:
  contents: read
  pull-requests: read
  issues: read
```

The gate must not need secret access, write access to product data, branch-protection administration, or issue-label administration.

## Implementation shape

Prefer a small testable validator under workflow-owned files, for example:

- `.github/scripts/validate-terra-review.mjs`
- `.github/scripts/validate-terra-review.test.mjs`
- `.github/workflows/review-gate.yml`

The pure validator should parse and validate attestation text without network access.

The workflow wrapper may use GitHub REST to read PR comments and current PR metadata, then pass normalized values into the validator.

Do not add product-runtime dependencies for this gate.

## Validation rules

The validator/gate must fail unless all are true:

1. Event is associated with a pull request.
2. PR number matches the attestation `pr_number`.
3. Attestation `head_sha` exactly equals the current PR `head.sha`.
4. `head_sha` is a 40-character lowercase/uppercase hexadecimal SHA.
5. `reviewer_model` is exactly `terra-xhigh`.
6. `verdict` is exactly `RECOMMEND_PASS`.
7. `p0` parses to integer `0`.
8. `p1` parses to integer `0`.
9. `material_findings_resolved` is exactly `true`.
10. `control_issue` matches the authoritative issue linked from the PR.
11. `scope_revision` matches the authoritative control issue.
12. The authoritative control issue has exactly one primary workflow-state label matching its Agent Control Block.
13. Control state is appropriate for review/verification (`ready-for-review` or `ready-for-verify`); blocked states fail closed.
14. `reviewed_at_utc` parses as a valid timestamp.
15. If multiple attestations exist for the same head, the latest attestation for that head is authoritative; a later `NEEDS_FIX`/`BLOCKED` must override an older pass.
16. Missing/malformed markers or duplicate keys fail closed.

## Attestation source rule

Gemini/Antigravity implementation workers must not create, edit, or replace the Terra attestation.

For the manual pilot, the controller/Owner records Terra's final structured verdict on the PR after receiving it from a fresh Terra context.

The gate validates the attestation contents and freshness, not a second-account identity.

## Unit tests

At minimum cover:

- valid current-head `RECOMMEND_PASS` -> PASS;
- missing attestation -> FAIL;
- stale head SHA -> FAIL;
- malformed SHA -> FAIL;
- P0 > 0 -> FAIL;
- P1 > 0 -> FAIL;
- `NEEDS_FIX` -> FAIL;
- `BLOCKED` -> FAIL;
- unresolved material findings -> FAIL;
- wrong PR number -> FAIL;
- wrong control issue -> FAIL;
- wrong scope revision -> FAIL;
- malformed/duplicate keys -> FAIL;
- later failing attestation overrides earlier pass -> FAIL;
- later valid pass for the same current head may satisfy after findings are resolved -> PASS.

Add the validator unit test to deterministic CI so future edits cannot silently weaken the gate.

## Workflow state transitions

Before Gemini implementation:

```text
Issue #7
state: ready-for-implementation
scope_revision: 2
fix_reentries: 0
```

Controller then performs the normal entry transition to `implementing` without consuming a fix re-entry because this is a newly approved scope, not a `needs-fix` re-entry.

After implementation and current-head `verify`/validator tests pass:

```text
ready-for-review
```

Terra performs fresh review of the exact current head.

If Terra returns `RECOMMEND_PASS`, controller posts the structured attestation, moves task to `ready-for-verify`, and reruns `review-gate` on the same head.

If Terra returns `NEEDS_FIX`, controller routes through `needs-fix`; the next implementation re-entry increments `fix_reentries` to 1.

## Bootstrap for PR #6

Because `review-gate.yml` does not exist on `main` yet, PR #6 itself bootstraps the gate:

1. Gemini adds the workflow + validator/tests on PR #6.
2. The PR `synchronize` event runs `review-gate` from the PR branch and it should fail closed before a Terra attestation exists.
3. Owner confirms the `review-gate` status context appears in GitHub.
4. Owner edits `protect-main` and adds `review-gate` as a required status check, keeps `verify`, keeps approvals at 0, and enables conversation resolution.
5. Terra performs fresh review of the exact PR #6 head.
6. Controller posts the Terra attestation to PR #6.
7. Rerun the failed `review-gate` job/run on that same head.
8. `review-gate` must pass.
9. `verify` must pass on that same current head.
10. No unresolved review conversation may remain.
11. Only then may PR #6 merge.

## Acceptance criteria

- AC1: `review-gate` exists as a distinct required status context.
- AC2: Gate fails with no current-head Terra attestation.
- AC3: Gate passes only for exact current-head `RECOMMEND_PASS`, P0=0, P1=0, material findings resolved.
- AC4: Any new push invalidates the old review without relying on GitHub human-approval dismissal.
- AC5: Gate checks linked control issue and `scope_revision` consistency.
- AC6: Gate has deterministic unit coverage including stale/malformed/conflicting attestations.
- AC7: Existing `verify` remains unchanged as product/code verification authority.
- AC8: Branch rules use approvals=0, require both `verify` and `review-gate`, require branch up-to-date and conversation resolution, and retain no bypass/force-push protections.
- AC9: No application/product/runtime/schema behavior changes.
- AC10: Scheduled development agents remain disabled until the manual pilot succeeds.

## Escalation

Return `BLOCKED` rather than weakening the gate if GitHub event semantics or ruleset behavior prevent reliable current-head binding.
