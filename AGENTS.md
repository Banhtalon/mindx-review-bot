# MindX Review Bot — QQ Workflow v9

Read `.ai-workflow/V9_CANONICAL_SPEC.md`, `POLICY.md`, `PROJECT_PROFILE.json`,
the current task/frozen manifest, `docs/CURRENT_STATE.md`, and the V4 product
spec. Older workflow plans are audit-only. Routing stays manual.

Owner describes product intent, answers business questions, tests Owner-ready
behavior, and enters account-only values in official UIs. Do not ask Owner to
review code, CI, tests, SQL, security, or logs. Route technical work to the
Controller, Qualified Reviewer, or Technical Operator.

## v9 controls

- Separate risk (`GREEN/YELLOW/RED`) from complexity (`S/M/L/XL`).
- Risk can rise from the actual diff and never falls inside a scope revision.
- Controller freezes and externally anchors verification before implementation.
- Every attempt uses a new worktree at the same base; stop after four attempts.
- Redact subprocess output before display or evidence persistence.
- Deterministic gates outrank model recommendations; required review is fresh
  and bound to the exact candidate head.
- Missing, stale, conflicting, or ambiguous controls fail closed.
- Local/synthetic evidence cannot establish hosted/live/production readiness.

## MindX safety

Teaching/LMS remain read-only. Never add or trigger LMS Save/Submit/comment
writes, automatic Zalo send, CAPTCHA/OTP bypass, guessed identities, or row-order
student mapping. Keep sensitive identity/extraction deterministic. Never expose
student PII, credentials, tokens, cookies, or browser state to models, logs,
frontend, evidence, or commits.

Use the frozen gates and preserve existing lint/typecheck/test/build,
no-secrets, and no-live-write checks. Add Supabase/Python/live gates only when
touched. Work on task branches/worktrees; preserve protected `main`, exact-head
CI/review, thread resolution, and no bypass/force-push. Controller confirms
readiness; Owner performs the final manual merge. Agents cannot declare DONE.
