# ADR 001 — Spike 0 Browser Use privacy boundary

- Date: 2026-08-10
- Status: Accepted for Spike 0
- Scope: Synthetic fixtures only

## Decision

Use a hybrid boundary for sensitive pages:

1. Browser Use is allowed to navigate an allowlisted page that contains class
   and session context but no roster markers.
2. The navigation agent must stop before a roster page.
3. Deterministic HTML parsing resolves student rows using stable identifiers or
   discriminators; row order and similar names are never identity.
4. Model payload construction uses a per-generation alias and redacts known
   personal values from free-text performance input.
5. Logs use a small allowlist of safe metadata fields.

The implementation is in `apps/browser-runner/src/mindx_runner/` and the
synthetic fixtures under `apps/browser-runner/tests/fixtures/` contain no real
data.

## Consequences

- The LMS live feasibility gate remains blocked until outbound telemetry and
  live cold/warm runs are audited by the owner.
- A pure Browser Use roster extraction flow is explicitly out of scope.
- If the live privacy probe cannot prove the boundary, the fallback is
  Playwright-only deterministic extraction or manual import.
