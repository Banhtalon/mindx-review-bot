# Review Gate Worker (`apps/review-gate-worker`)

## Purpose

`apps/review-gate-worker` is a minimal, serverless-ready GitHub App webhook handler and review-gate validator. It serves as the trusted merge check producer (`terra-review-gate`) for the solo-owner engineering pipeline in `mindx-review-bot`.

## Trust Boundary & Architecture

Under Scope Revision 3:

1. **Independent Merge Authority**:
   - The merge gate (`terra-review-gate`) is emitted via the GitHub Checks API by this dedicated GitHub App.
   - The production code of this worker is deployed by the repository Owner to an external serverless runtime (e.g. Cloudflare Worker, Vercel, AWS Lambda, or Node container) outside PR-controlled GitHub Actions code.
   - Pull requests cannot forge or bypass this check by modifying `.github/workflows/review-gate.yml` or script files.

2. **Attestation Provenance**:
   - Only top-level PR conversation comments authored by the authorized Owner identity (`Banhtalon`, user ID `105797112`, `author_association: OWNER`) are accepted as Terra review attestation carriers.
   - Comments from any other user are strictly ignored and cannot create or invalidate review authority.

3. **Exact Head Verification**:
   - The worker always re-fetches the current PR metadata directly from the GitHub REST API to obtain `head.sha`.
   - It never trusts caller- or webhook-provided head SHAs.
   - It never checks out or executes PR code.

4. **Strict Calendar & UTC Time Validation**:
   - Attestation timestamps (`reviewed_at_utc`) must be valid UTC ISO-8601 timestamps ending in `Z`.
   - Real calendar rules are strictly enforced (e.g. leap years, 30/31-day months, rejecting dates like `2026-02-29T00:00:00Z` or `2026-04-31T00:00:00Z`).

5. **Agent Control Block & Scope Reset**:
   - Authoritative control issue (#7) must contain a unique `<!-- AGENT_CONTROL_BLOCK_V1 -->` block.
   - For `scope_revision > 1`, `owner_scope_reset` must link to an authenticated Owner approval record containing `<!-- OWNER_SCOPE_RESET_V1 -->` authored by `Banhtalon` (ID `105797112`).

## Environment Variables

- `GITHUB_APP_ID`: The GitHub App ID.
- `GITHUB_PRIVATE_KEY`: The GitHub App RS256 private key (PEM format).
- `GITHUB_WEBHOOK_SECRET`: The HMAC secret configured on the GitHub App webhook.
- `DEFAULT_CONTROL_ISSUE`: (Optional) Fallback control issue number if not specified in PR body.
- `DEFAULT_SCOPE_REVISION`: (Optional) Expected scope revision.

## Local Testing

```bash
npm run test:review-gate-worker
```
