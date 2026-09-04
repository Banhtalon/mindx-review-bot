---
name: mindx-plan
description: Plans MindX Review Bot work from the V4 specification, current project state, safety rules, acceptance criteria, and risk routing. Use for requirements, architecture, task decomposition, or plan critique before implementation.
---

# MindX Plan

## Read first

1. `AGENTS.md`
2. `docs/CURRENT_STATE.md`
3. the linked product specification/ADR
4. existing evidence/phase report only when needed to resolve current state

## Purpose

Produce a bounded implementation plan. Do not implement product code while using this skill unless the task explicitly changes from planning to implementation.

## Method

Use Superpowers `brainstorming` and `writing-plans` principles.

For every non-trivial task define:

- problem/goal;
- in-scope behavior;
- explicitly out-of-scope behavior;
- business rules already decided;
- unresolved owner decisions;
- architecture impact;
- acceptance criteria;
- test/verification strategy;
- risk level: small, medium, high;
- Terra review requirement;
- rollback/recovery consideration when relevant.

## Safety checks

Before marking `ready-for-implementation`, confirm:

- no live-write behavior is being introduced unless explicitly approved;
- no student identity is inferred from row order;
- no missing business rule is being guessed;
- no PII/secret is requested for chat or repo evidence;
- synthetic evidence is not being treated as live proof;
- task does not silently start an unapproved phase.

## Output

A plan should be written to the repository for medium/high-risk work and include small, independently verifiable steps.

Recommended final status:

- `ready-for-implementation` when complete;
- `blocked-owner` when a business/scope decision is missing;
- `blocked-external` when an external environment/site prerequisite prevents safe planning/verification.

Do not output `VERIFIED`.