## Authority

- Owner-visible outcome and linked issue/task:
- frozen manifest and anchored SHA-256:
- scope revision, approved base, current head, clean attempt number:

## Risk and complexity

- declared / observed / effective risk: `GREEN | YELLOW | RED`
- independent complexity: `S | M | L | XL`
- tripwires and required reviewer/operator:

## Scope and evidence

Changed:

Explicitly unchanged:

- [ ] manifest matches lock and Controller anchor
- [ ] actual diff rescanned without lowering risk
- [ ] frozen gates PASS on current head through redaction boundary
- [ ] evidence tier is accurate; local/synthetic is not called hosted/live
- [ ] required independent exact-head review has no unresolved material finding
- [ ] current-state claim is accurate
- [ ] no unapproved model routing/retry, scheduler, migration, deployment, live
      write, or merge

## Owner handoff

- status: `WAITING_FOR_OWNER | READY_FOR_OWNER_TEST | DONE | BLOCKED`
- Owner action or `NONE`:
- agent: `RECOMMEND_PASS | NEEDS_FIX | BLOCKED`
- deterministic gates: `PASS | FAIL | BLOCKED`
- Owner acceptance: `PASS | PENDING | NOT_APPLICABLE`

Controller confirms readiness; Owner manually merges.
