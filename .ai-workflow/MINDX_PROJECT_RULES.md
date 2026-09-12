# MindX Review Bot — project constraints

These are product and data-safety constraints for this repository. Workflow authority remains `.ai-workflow/V10_CANONICAL_SPEC.md`.

- Teaching/LMS automation remains read-only unless the Owner explicitly approves a later product scope revision.
- Do not add or trigger LMS Save/Submit/comment writes, automatic Zalo send, CAPTCHA/OTP bypass, or guessed identities.
- Student mapping must use stable identifiers; row-order or fuzzy identity guesses are not acceptable.
- Student PII, credentials, tokens, cookies and browser session state must not be sent to models, logs, evidence, frontend output or commits.
- Existing no-secret and no-live-write deterministic guards stay mandatory for implementation work.
- Database migrations, destructive operations, deployment changes and any live write are elevated-risk work and require the v10 elevated path plus explicit Owner intent.
- Local/synthetic evidence must never be described as hosted, live or production acceptance.
