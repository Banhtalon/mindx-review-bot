---
name: mindx-spec-review
description: Performs a fresh specification-compliance review of MindX Review Bot changes against requirements, acceptance criteria, scope, and tests. Use before adversarial review or final verification.
---

# MindX Spec Review

## Review package

Read only what is needed for independent review:

1. `AGENTS.md`
2. linked specification/acceptance criteria
3. PR diff
4. current deterministic test/CI evidence
5. known limitations

Do not rely on the implementer's reasoning transcript.

## Review questions

Check whether:

- every acceptance criterion is implemented;
- implementation behavior matches the written requirement;
- required behavior is missing;
- extra behavior was added without approval;
- unrelated files/scope changed;
- tests actually exercise the acceptance criteria;
- tests/guards were weakened to fit the implementation;
- existing safety/privacy boundaries remain intact;
- a synthetic/local PASS is being incorrectly represented as live proof.

## Output

Return findings ordered by severity with:

- requirement/AC affected;
- observed implementation evidence;
- expected behavior;
- concrete fix or missing evidence required.

Final verdict must be one of:

- `RECOMMEND_PASS`
- `NEEDS_FIX`
- `BLOCKED`

Do not output `VERIFIED`.

If `RECOMMEND_PASS`, the task still requires deterministic final verification.