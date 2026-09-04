# Scope Revision 4 — GitHub-native manual trusted merge gate

## Decision

Owner approved simplifying PR #6 so that no external review-gate infrastructure is required.

Approval record:
https://github.com/Banhtalon/mindx-review-bot/issues/7#issuecomment-5535792176

This revision intentionally replaces the revision-3 external GitHub App / Cloudflare trusted check architecture with a simpler GitHub-native manual merge authority.

## Goals

- No Cloudflare account setup for this workflow.
- No Durable Object.
- No dedicated GitHub App.
- No new private key, webhook secret, API token, or other secret.
- Keep current deterministic CI protection.
- Keep fresh Terra xHigh adversarial review on the exact PR head SHA.
- Keep Controller review of evidence and workflow state.
- Keep final merge under explicit Owner control.

## Authoritative merge process

1. Implementation is pushed only to `chore/agent-workflow-migration`.
2. Current-head GitHub Actions `verify` must pass.
3. Issue #7 must be in a reviewable workflow state with exactly one matching primary state label.
4. Terra xHigh receives fresh context and reviews the exact current PR head SHA.
5. Terra reports P0/P1/P2/P3 plus verdict `RECOMMEND_PASS`, `NEEDS_FIX`, or `BLOCKED`.
6. A pass candidate requires P0=0, P1=0, no unresolved material findings, and exact-head evidence.
7. Controller re-fetches the PR head, current-head CI, Issue #7, branch freshness, and material review conversations.
8. Any new push after Terra review invalidates that Terra evidence and requires a fresh exact-head review.
9. Controller may report `merge-eligible` only when all required evidence is current and consistent.
10. Owner performs or explicitly authorizes the final Merge action only after Controller prompts.

The assistant/model must not silently merge PR #6.

## Required GitHub protections

Keep the existing simple repository protections:

- pull request required for `main`;
- `Required approvals = 0` for this solo-owner repository;
- required deterministic `verify` status check;
- strict up-to-date branch requirement;
- review conversation/thread resolution;
- no force-push or bypass path that defeats the protected branch policy.

Revision 4 does not require `terra-review-gate` as a hard status check.

## Terra authority

Terra is an independent review layer, not a GitHub identity or status-check producer.

For merge eligibility:

- review must bind the exact current head SHA;
- verdict must be `RECOMMEND_PASS`;
- P0 must be 0;
- P1 must be 0;
- material findings must be resolved;
- new commits invalidate prior review evidence.

The Controller records/reasons from Terra evidence but does not claim that Terra or any model is GitHub's deterministic `VERIFIED` authority.

## Revision-3 external worker

`apps/review-gate-worker/` and related revision-3 GitHub App/serverless artifacts are no longer part of merge authority.

Revision-4 implementation should remove them if they are used only for the abandoned external gate, or clearly isolate/retire them so that:

- they are not deployed;
- they are not required by CI or rulesets;
- Owner setup docs do not ask for Cloudflare/GitHub App/secrets;
- they cannot be mistaken for a required production merge gate.

Prefer deletion of dead experimental infrastructure when safe and when no unrelated functionality depends on it.

## Documentation changes

Update current workflow documentation to describe only the selected revision-4 path as authoritative:

- `docs/CURRENT_STATE.md`
- `docs/AGENT_WORKFLOW.md`
- `docs/AGENT_WORKFLOW_OWNER_SETUP.md`
- `.agents/skills/mindx-verify/SKILL.md`
- relevant migration/review-gate plans where they would otherwise misstate current authority.

Historical revision-2/revision-3 plans may remain as historical records but must be labeled superseded where necessary.

## CI / code changes

- Preserve the full deterministic `verify` suite.
- Remove revision-3 external-worker tests/scripts from required CI if the worker is removed.
- Keep the bootstrap Actions `review-gate` only if it still has a useful non-authoritative self-test role; otherwise remove it and its branch-rule requirement as part of the approved simplification.
- Do not weaken product/security tests just to make migration CI faster.

## Safety boundaries

No revision-4 change may alter:

- Teaching/LMS product behavior;
- browser automation behavior;
- database schema/RLS behavior;
- live-write safeguards;
- product phase scope;
- pre-existing `cron-dispatch` behavior.

## Bounded fix loop

For scope revision 4:

- `fix_reentries = 0` initially;
- `needs-fix / 0 -> implementing / 1` allowed;
- `needs-fix / 1 -> implementing / 2` allowed;
- a third implementation re-entry under unchanged scope is blocked-owner.

## Owner interaction policy

Do not ask Owner to create infrastructure or secrets for this workflow.

The expected Owner interaction is only the final Merge action when all evidence is complete. The Controller should explicitly prompt Owner at that point and not before.
