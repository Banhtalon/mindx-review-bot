# Trusted Review Architecture — Scope Revision 3

> [!NOTE]
> **SUPERSEDED BY SCOPE REVISION 4**: This architecture was superseded by [Scope Revision 4 — GitHub-native manual trusted merge gate](file:///e:/mindx-review-bot/docs/superpowers/plans/2026-09-04-github-native-manual-trusted-merge-gate.md) approved in [Issue #7 comment 5535792176](https://github.com/Banhtalon/mindx-review-bot/issues/7#issuecomment-5535792176). External review-gate worker infrastructure is retired in favor of GitHub-native manual merge authority. This document remains as a historical design record.

## Goal

Replace the PR-controlled GitHub Actions `review-gate` as merge authority with a trusted review result that a pull request cannot forge by editing its own workflow or validator.

This is a workflow/security-control change only. It must not change Teaching/LMS behavior, browser runtime behavior, product schemas, RLS, live-write safeguards, or start Phase 6.

## Why revision 3 exists

Scope revision 2 correctly bound Terra review to current PR head, Issue #7, scope revision, reviewable state, and deterministic fields, but final Terra review found two material trust-boundary gaps:

1. any PR comment/review author could supply a syntactically valid Terra attestation;
2. a PR-controlled GitHub Actions workflow could retain the required status context name while weakening the validator that produced it.

GitHub required status checks identify the check context and optionally the source GitHub App, but they do not pin a specific workflow file or event. Therefore a GitHub Actions context produced by PR-controlled workflow code is not a sufficient trust anchor for this solo-owner design.

## Selected architecture

Use a dedicated GitHub App as the trusted merge-check producer.

The App runs a minimal external/serverless validator whose deployed implementation is outside the pull request execution context. The repository may contain the App source and tests, but changing source in a PR does not change the deployed validator until Owner performs an explicit deployment from an approved commit.

The trusted check name is:

`terra-review-gate`

The active `protect-main` ruleset will eventually require:

- `verify` from GitHub Actions;
- `terra-review-gate` from the dedicated GitHub App as the expected source;
- strict branch-up-to-date policy;
- pull request required;
- `Required approvals = 0`;
- conversation resolution required;
- no normal bypass path;
- force-push protection.

The existing GitHub Actions `review-gate` is retained only as a bootstrap/self-test artifact until the trusted App check is live, then it must no longer be merge authority.

## Trust model

### Trusted identities

For scope revision 3:

- repository Owner GitHub login: `Banhtalon`;
- repository Owner GitHub user id: `105797112`;
- trusted check producer: dedicated `mindx-review-gate` GitHub App installation;
- Terra model identity remains process-enforced, not cryptographically provable by GitHub.

The gate proves that the accepted attestation was posted by the authorized Owner/controller GitHub identity, not that GitHub itself executed Terra.

### Attestation provenance

Only top-level PR conversation comments are accepted as Terra attestation carriers for this pilot.

A candidate attestation comment must satisfy all of:

- comment author login exactly `Banhtalon`;
- comment author user id exactly `105797112`;
- `author_association` is `OWNER`;
- exactly one `TERRA_REVIEW_ATTESTATION_V1` block exists in that comment;
- block is strictly parsed with no duplicate or unknown required keys;
- `reviewer_model: terra-xhigh`;
- exact current PR head SHA;
- exact PR number;
- exact control issue;
- exact scope revision;
- valid verdict;
- canonical integer `p0` and `p1`;
- pass requires `RECOMMEND_PASS`, `p0 === 0`, `p1 === 0`, and `material_findings_resolved: true`;
- `reviewed_at_utc` is a real calendar-valid UTC timestamp.

Comments from all other identities are ignored as authority even if they contain a syntactically valid marker.

Later authorized Owner attestations take precedence over older authorized attestations. A later `NEEDS_FIX` or `BLOCKED` therefore invalidates an older pass.

## Trusted check producer

### GitHub App permissions

Minimum repository permissions:

- Metadata: read;
- Pull requests: read;
- Issues: read;
- Checks: write.

No Contents write, Actions write, Administration, Secrets, Deployments, or repository mutation permissions are required.

### Webhook/event inputs

The App should recalculate the check on events that can change authority:

- pull request opened/reopened/synchronize/ready-for-review;
- issue comment created/edited/deleted on a pull request.

The App may also expose an authenticated/manual recompute path for bootstrap/diagnostics, but normal pass/fail authority must come from GitHub API state, not caller-supplied fields.

### Check behavior

For every evaluation:

1. fetch PR metadata from GitHub;
2. obtain exact current `head.sha` from the PR API;
3. fetch authoritative Issue #7;
4. strictly parse and validate the unique Agent Control Block;
5. validate the scope-reset approval record when required;
6. fetch all pages of PR top-level comments;
7. retain only authorized Owner attestation comments;
8. select the latest authorized attestation deterministically;
9. validate it against current head / PR / issue / scope / control state;
10. create or update a `terra-review-gate` check run on the exact PR head SHA.

Network/API/parsing ambiguity fails closed.

The App must never:

- execute PR code;
- checkout the PR branch;
- accept PR-body values as trusted control state;
- accept caller-provided head SHA without re-fetching the PR;
- create or modify Terra attestation comments;
- merge the pull request.

## Agent Control Block V1

Revision 3 replaces generic first-`text`-fence discovery with explicit unique markers in Issue #7:

```text
<!-- AGENT_CONTROL_BLOCK_V1 -->
state: <canonical-state>
scope_revision: <canonical-positive-integer>
fix_reentries: <0..2>
owner_scope_reset: <none-or-valid-approval-comment-url>
<!-- /AGENT_CONTROL_BLOCK_V1 -->
```

Validation rules:

- exactly one start marker and exactly one end marker;
- exactly one block;
- exactly the four required keys;
- no duplicate keys;
- no missing keys;
- state is canonical;
- exactly one canonical workflow label exists and matches state;
- only `ready-for-review` or `ready-for-verify` may pass review authority;
- `scope_revision` is canonical and equals expected revision;
- `fix_reentries` is canonical and in `0..2`;
- for revision > 1, `owner_scope_reset` must be a GitHub issue-comment URL in this repository and issue;
- the linked approval comment is fetched and validated, not trusted by URL syntax alone.

## Owner scope-reset approval V1

A revision > 1 approval link must resolve to a comment with exactly one block:

```text
<!-- OWNER_SCOPE_RESET_V1 -->
old_scope_revision: <n>
new_scope_revision: <n+1>
reason: <non-empty>
material_scope_change: <non-empty>
owner_decision: APPROVED
approved_by: Banhtalon
<!-- /OWNER_SCOPE_RESET_V1 -->
```

The fetched approval comment must be authored by GitHub user id `105797112` with `author_association: OWNER` when that field is available, and its revision numbers must match the control issue transition being validated.

## Strict UTC timestamp

Accepted shape:

`YYYY-MM-DDTHH:MM:SSZ`

Fractional seconds may be supported only if tests define one canonical rule.

Validation must parse numeric components and round-trip them through UTC construction so impossible dates such as `2026-02-29T00:00:00Z`, invalid month/day combinations, hour 24, leap-second-like seconds, or offsets such as `+07:00` fail closed.

## Required deterministic tests

### Provenance

- valid Owner comment passes provenance filtering;
- same block from non-Owner user is ignored/rejected;
- wrong user id with same-looking login fails;
- missing/wrong author association fails where association is required;
- authorized later `NEEDS_FIX` overrides older authorized pass;
- untrusted later comment cannot override or create authority.

### Control block

- exactly one marker block accepted;
- missing marker fails;
- duplicate blocks fail;
- duplicate key fails;
- unknown/missing required key fails;
- zero/multiple primary state labels fail;
- label/state mismatch fails;
- invalid `fix_reentries` fails;
- fake/nonexistent approval URL fails;
- approval comment by wrong author fails;
- approval revision mismatch fails;
- valid revision-3 approval record passes.

### Attestation

Preserve and extend existing tests for:

- exact current head;
- stale head;
- strict canonical numeric fields;
- exact-zero P0/P1;
- conflicting blocks;
- pagination;
- later-attestation precedence;
- wrong PR/issue/scope/model/verdict;
- unresolved material findings;
- malformed/duplicate keys.

### Time

Reject at minimum:

- `2026-02-29T00:00:00Z`;
- `2026-13-01T00:00:00Z`;
- `2026-04-31T00:00:00Z`;
- date-only values;
- local time without `Z`;
- offsets such as `+07:00`;
- malformed seconds/minutes/hours.

Accept valid leap/non-leap and normal UTC examples.

### Trusted check adapter

Use mocked GitHub API responses to verify:

- current PR head is fetched rather than accepted from webhook payload alone;
- pagination is exhaustive;
- API error fails closed;
- check run is created on the exact current head;
- successful check is impossible without authorized current-head Terra pass;
- no code checkout/execution path exists.

## Source layout

Gemini may choose the smallest implementation consistent with repository conventions, but the preferred shape is:

- `apps/review-gate-worker/` — minimal GitHub App/serverless adapter;
- a pure validator module with no network side effects;
- adapter tests with mocked GitHub API;
- existing `.github/scripts/validate_terra_attestation.mjs` may be refactored/reused only as non-authoritative library/test code;
- `.github/workflows/review-gate.yml` remains clearly labeled bootstrap/self-test and must not claim final merge authority after cutover.

Do not introduce product runtime dependencies.

## Bootstrap and cutover sequence for PR #6

1. Owner approval record for scope revision 3 exists.
2. Sol commits this plan and controller moves Issue #7 to `ready-for-implementation`.
3. Controller performs normal `ready-for-implementation / 0 -> implementing / 0` entry.
4. Gemini implements the GitHub App validator/adapter and revision-3 tests/docs.
5. Current-head `verify` passes.
6. Controller moves to `ready-for-review`.
7. Terra performs fresh adversarial review of the exact current head, including the App implementation and bootstrap plan.
8. If Terra returns `NEEDS_FIX`, use at most two revision-3 fix re-entries under the normal bounded-loop rule.
9. When Terra returns `RECOMMEND_PASS`, Owner creates/installs the dedicated GitHub App and deploys the exact reviewed implementation as the trust anchor. Deployment must not execute or deploy code from a newer unreviewed head.
10. The App evaluates PR #6 and emits `terra-review-gate` on the exact current head; before an authorized attestation it should fail closed.
11. Owner edits `protect-main`: keep `verify`; replace the required GitHub Actions `review-gate` with `terra-review-gate` and select the dedicated GitHub App as expected source; keep strict up-to-date and conversation resolution.
12. Controller posts the authorized Owner-carried Terra attestation for the exact unchanged head.
13. App recomputes and `terra-review-gate` passes on that head.
14. Reconfirm `verify` is green on the same head and no material conversations remain unresolved.
15. Only then merge PR #6.

## Fail-closed bootstrap rule

Until step 11 completes, the existing required GitHub Actions `review-gate` may remain red and PR #6 remains unmergeable. Do not weaken or remove merge protection early merely to obtain green status.

If the dedicated App cannot be created/installed/deployed, route `blocked-owner` or `blocked-external`; do not substitute the PR-controlled Actions gate as equivalent authority.

## Owner/manual actions expected later

Owner will be required once, after Terra approves the implementation, to:

- create/install the dedicated GitHub App;
- configure its private key/app credentials in the external/serverless host;
- deploy the exact approved revision;
- change the ruleset required review check from Actions `review-gate` to App `terra-review-gate` with the expected App source.

No Owner action is required during Gemini implementation before that checkpoint.

## Acceptance criteria for revision 3

- AC1: arbitrary commenters cannot satisfy Terra provenance.
- AC2: PR-controlled workflow code cannot forge the required trusted review result.
- AC3: ruleset ultimately requires `terra-review-gate` from the dedicated GitHub App source.
- AC4: exact-head, Issue #7, scope revision 3, state/label, Terra verdict, P0/P1, and material-resolution bindings remain fail closed.
- AC5: control block and scope-reset approval records are unique, strict, and fetched/validated.
- AC6: strict UTC validation rejects impossible calendar timestamps.
- AC7: pagination/later-attestation precedence remains correct.
- AC8: live workflow/current-state/owner docs match the deployed architecture and active ruleset.
- AC9: no product/browser/schema/live-write behavior changes.
- AC10: current-head `verify` and trusted `terra-review-gate` are both green before merge.
