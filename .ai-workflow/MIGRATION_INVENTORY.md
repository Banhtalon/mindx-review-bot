# v9 Migration Inventory

Issue [#12](https://github.com/Banhtalon/mindx-review-bot/issues/12), base
`255ccf9635aecc50474a0a88049355ef4c3638fc`.

## Replaced

The root agent policy, agent workflow/Owner docs, PR/issue task templates, five
MindX role skills, and current workflow status are replaced by v9 entry points.
MindX safety rules remain active.

## Retained only as history

The four 2026-09-03/04 workflow plans carry explicit v9 superseded notices and
have no active actor/state/retry authority.

## Preserved unchanged

All `.github/workflows/*` files, product code, database/RLS, product specs/ADRs,
phase evidence, credentials, deployments, and live-write guards are unchanged.
The existing cron runs product jobs, not development models.

No model router, scheduled development agent, automatic retry, migration,
deployment, product write, credential, or merge is introduced.
