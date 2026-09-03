---
name: mindx-spec-review
description: Fresh specification-compliance review against requirements, acceptance criteria, current project state, scope, and deterministic evidence.
---

# MindX Spec Review

## Review package

Read independently:

1. `AGENTS.md`
2. `docs/CURRENT_STATE.md`
3. linked GitHub issue Agent Control Block and current workflow-state label
4. linked specification and acceptance criteria
5. PR diff
6. deterministic test/CI evidence from the current PR head
7. known limitations/blockers
8. relevant `docs/evidence/index.json` entries when a live/hosted readiness claim is made

Do not rely on implementer reasoning transcripts.

If task control state is missing, malformed, conflicting, or ambiguous, return `BLOCKED`.

## Review questions

Check whether:

- every acceptance criterion is implemented;
- behavior matches the written requirement;
- required behavior is missing;
- extra behavior was added without approval;
- unrelated scope changed;
- tests exercise the acceptance criteria;
- tests/guards were weakened;
- safety/privacy boundaries remain intact;
- `docs/CURRENT_STATE.md` contradicts a readiness or scope claim;
- synthetic/local evidence is mislabeled as live;
- any live/hosted claim is supported by the relevant evidence index;
- issue `state`, workflow label, `scope_revision`, and `fix_reentries` are consistent.

## Output

Return findings ordered by severity with requirement, evidence, expected behavior, and required fix/evidence.

Final verdict must be exactly one of:

- `RECOMMEND_PASS`
- `NEEDS_FIX`
- `BLOCKED`

Do not output `VERIFIED`.
