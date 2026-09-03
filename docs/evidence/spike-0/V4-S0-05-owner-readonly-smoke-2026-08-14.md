# Evidence V4-S0-05-OWNER-SMOKE-2026-08-14 — Owner-controlled read-only smoke

## Result

- **Status:** `BLOCKED`
- **Scope:** Existing signed-in Chrome session; read-only GET navigation only.
- **Observed at:** 2026-08-14, Asia/Ho_Chi_Minh.
- **No credential, cookie, token, raw browser state, student name, screenshot,
  or raw page text was copied to this evidence.**

This record supplements the original Spike 0 metric evidence. It does not
replace the required full cold/warm Teaching/LMS runner evidence.

## Teaching

- The existing session opened the weekly view at the observed GET route
  `index.php?view=theo-tuần&week_offset=0` without a login redirect.
- Five warm reloads completed with the following redacted durations in ms:
  `299, 1025, 284, 339, 279`.
- All five observations retained one schedule table, 17 lesson-link targets,
  no login-like state, and zero non-GET forms.
- The separate `schedule.php` page visibly contains a POST form. It was not
  submitted or modified; the smoke used the weekly GET view instead.
- One observed lesson-detail GET route was opened for structure-only inspection;
  no form was submitted and no learner content was copied.

### Fresh live continuation

- Five fresh direct GET navigation attempts to the observed weekly Teaching
  route all ended at the Teaching login page. Redacted navigation durations
  were `541, 373, 383, 387, 391 ms`; no credential was re-entered.
- This fresh result blocks a new cold/warm Teaching PASS even though the
  earlier in-session warm observations remain recorded above.
- Three passive LMS samples on the targeted class/session view remained
  stable: the class drawer was present, session `# 3` was active, and there
  were zero forms, mutation forms, Save/Submit controls, and textareas.

### Teaching after owner re-authentication

- After the owner signed in again, the authenticated Teaching home/weekly
  surface was restored at the observed `index.php` route.
- Five warm reloads completed with redacted durations in ms:
  `618, 480, 515, 554, 492`.
- All five retained one schedule table, six visible rows, 17 lesson-link
  targets, no login-like state, and zero POST forms.
- This is a fresh in-session warm `PASS`; direct/cold navigation, runner
  telemetry/privacy, and billed-minute evidence remain open.

## LMS

- The existing session opened the dashboard and classes route without a login
  redirect.
- The classes route rendered a client-side table during the first inspection,
  but subsequent reloads alternated between a sparse/no-data state and the
  rendered shell.
- After the owner reopened the Classes list, three passive read-only samples
  one second apart were stable: title `Classes`, one table, 20 visible rows,
  no login-like state, no forms, no mutation forms, and no no-data state.
- The owner then supplied an exact class target (redacted here). The observed
  GET-only search filter produced one visible matching row in two passive
  samples; the page had no mutation form and no Save/Submit control. The one
  visible form was the existing GET filter form.
- The current stable observation confirms the class-list surface only; no row
  was selected and no real class/session identity was copied into evidence.
- One read-only `actions` menu was opened for the matching row to inspect
  navigation availability; no menu item was selected. No class mutation
  control, Save, Submit, or mutation form was clicked or submitted.
- Exact class identity is now confirmed at the owner-supplied class-code
  level. Session #3 is covered by the targeted navigation below; student
  identity was not asserted. The earlier reload instability remains a caveat
  for a future cold/warm runner check.

### Targeted class/session read-only navigation

- The owner supplied the target class code and the GET filter matched one row;
  the code is redacted from this evidence.
- The class detail drawer was opened, the `Nhận xét` tab was selected, and
  session `# 3` was selected. The session control showed its active state.
- The targeted view had no form, no mutation form, no textarea, no password
  input, and no Save/Submit control. No comment or learner content was copied.
- This is a targeted UI-navigation `PASS` only. Full live closure remains
  `BLOCKED` pending runner telemetry/privacy, hosted state, cold/warm, and
  billed-minute evidence.

## Closure decision

Teaching has partial warm-navigation observations only. The targeted LMS
class/session navigation passed at read-only UI scope; student identity,
stable cold/warm runs, Browser Use runner telemetry, hosted state reuse, and
billed-minute measurement remain `BLOCKED`. No live-production PASS is
claimed.
