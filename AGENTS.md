# AGENTS.md

## Source of truth

Đọc theo thứ tự trước khi làm việc:

1. `AGENTS.md` — luật kỹ thuật/safety và cách route công việc;
2. `docs/CURRENT_STATE.md` — trạng thái hiện tại, blocker và scope đã duyệt;
3. `docs/DEVELOPMENT_SPEED_POLICY.md` — FAST / STANDARD / STRICT và test ladder;
4. `docs/spec/KE_HOACH_MVP_BOT_NHAN_XET_MINDX_V4_BROWSER_USE_SUPABASE.md` — product requirements;
5. specification/plan được link trong task hiện tại.

Chỉ triển khai phase/task được Owner chỉ định hoặc task đã được controller cho phép. `docs/CURRENT_STATE.md` không được ghi đè business rule trong master spec.

## Project scope

Đây là dự án cá nhân/nhóm nhỏ phục vụ học tập và nghiên cứu. Không mở rộng thành SaaS đa tenant, microservices, Kubernetes, enterprise RBAC hoặc hệ thống production phức tạp nếu không có yêu cầu mới rõ ràng.

## Primary workflow principle

**Dùng workflow nhẹ nhất đủ an toàn cho đúng thay đổi đang làm.**

Không áp dụng toàn bộ Superpowers, full test suite và fresh review cho mọi bug nhỏ. Không biến một lỗi cục bộ thành audit toàn phase nếu lỗi đó không chặn DONE condition hiện tại.

Canonical routing nằm trong `docs/DEVELOPMENT_SPEED_POLICY.md`:

- **FAST** — low-risk/localized;
- **STANDARD** — feature/bug thông thường;
- **STRICT** — migration, auth/session, live systems, privacy/PII, identity/mapping, live-write safeguards, architecture/data-integrity high-risk.

Superpowers là bộ phương pháp **tùy theo nhu cầu**, không phải checklist bắt buộc cho mọi task. Dùng brainstorming/planning/TDD/systematic-debugging/review khi rủi ro hoặc độ phức tạp thực sự cần chúng.

## Agent roles

### Sol High — planner / architect

Dùng khi:

- requirement/spec mơ hồ;
- task medium/high-risk cần plan;
- có architecture/trade-off lớn;
- cần acceptance criteria hoặc Owner decision.

Không cần Sol cho bug nhỏ, CSS/UI nhỏ, validation cục bộ hoặc refactor cơ học.

Sol rời execution loop sau khi task đủ rõ. Chỉ quay lại khi có blocker, scope change hoặc architecture decision mới.

### Implementation worker — Codex/Gemini

Trách nhiệm:

- đọc scope + DONE condition;
- implement đúng phạm vi;
- chạy focused tests trước;
- debug theo nguyên nhân cụ thể;
- chỉ mở rộng test khi cần;
- chuẩn bị diff/evidence ngắn gọn.

Không được:

- tự phát minh business rule;
- đổi kiến trúc âm thầm;
- mở rộng scope vì thấy lỗi không liên quan;
- làm yếu test/safety gate để lấy PASS;
- tự tuyên bố task/phase đã VERIFIED.

### Terra xHigh — fresh adversarial reviewer

Terra **bắt buộc cho STRICT/high-risk diff** trước merge. Terra không bắt buộc cho mọi commit trung gian.

Review nên được gọi **muộn**, sau khi implementation + deterministic checks + runtime/hosted evidence đã ổn định, để tránh invalidate review sau từng commit nhỏ.

Terra trả một trong:

- `RECOMMEND_PASS`;
- `NEEDS_FIX`;
- `BLOCKED`.

P2/P3 optional/style findings không tự động tạo thêm một vòng fix/review nếu không ảnh hưởng acceptance, correctness, safety hoặc maintainability đáng kể.

## Verification authority

Không model nào được tự tạo trạng thái `VERIFIED`.

Machine evidence và runtime evidence phù hợp với scope mới là authority. AI review là risk gate, không thay thế CI/runtime verification.

## Test ladder

### Level 1 — focused

Dùng lặp lại trong khi code/debug. Chạy đúng test file/module tái hiện behavior.

Ví dụ:

- `npx vitest run test/cron-workflow.test.ts`
- `cd apps/browser-runner && uv run pytest tests/unit/test_hosted_probe.py`

### Level 2 — affected subsystem

Chạy khi focused behavior đã green và trước khi coi implementation slice hoàn thành.

Ví dụ:

- `npx vitest run test/cron-workflow.test.ts test/ci-contract.test.ts`
- `cd apps/browser-runner && uv run pytest tests/unit/test_hosted_probe.py tests/unit/test_supabase_client.py tests/unit/test_workflow_contract.py`

Thêm lint/typecheck/Ruff/Mypy khi touched code cần cross-file/static verification.

### Level 3 — final repository gate

Chạy **một lần trên stable final candidate head**, hoặc dùng required GitHub `verify` CI nếu nó đã chạy cùng deterministic checks trên đúng head.

Baseline checks có thể gồm:

- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `npm run verify:no-secrets`
- `npm run verify:no-live-write`
- Supabase reset/RLS khi Supabase behavior thay đổi
- Python Ruff/Mypy/Pytest khi Python behavior thay đổi

**Không rerun full suite sau mỗi edit nhỏ. Không chạy full suite hai lần chỉ để tạo duplicate evidence nếu code không đổi.**

Authenticated/live/hosted changes vẫn cần runtime evidence phù hợp; unit tests không thay thế hosted proof.

## Scope-creep guard

Khi phát hiện lỗi mới, classify trước:

1. lỗi có chặn DONE condition hiện tại không?
2. lỗi có do current diff gây ra không?
3. lỗi có phải safety/security blocker không?

Nếu cả ba đều `no`, ghi riêng và tiếp tục task hiện tại. Không audit toàn repo/phase vì một phát hiện phụ.

## Task states and bounded fix loop

Canonical states:

- `needs-plan`;
- `ready-for-implementation`;
- `implementing`;
- `ready-for-review`;
- `needs-fix`;
- `ready-for-verify`;
- `done`;
- `blocked-owner`;
- `blocked-external`.

Issue Agent Control Block vẫn là authoritative cho agent-driven task:

```text
state: <canonical state>
scope_revision: <positive integer>
fix_reentries: <0..2>
owner_scope_reset: <none | Owner approval link>
```

`MAX_FIX_LOOPS = 2` vẫn giữ nguyên: cho phép hai implementation re-entries cho material fix trong cùng scope revision; lần thứ ba phải route `blocked-owner`.

Không tiêu tốn fix re-entry chỉ vì:

- thay đổi configuration/provider secret;
- rerun cùng hosted check;
- docs/evidence-only update;
- optional P2/P3 suggestion không cần sửa code.

Controller/Owner giữ authority với state/counter. Worker không tự reset counter.

## Risk routing

### FAST / low risk

Ví dụ: text, CSS, localized parser/validation, mechanical refactor.

Flow:

`implement -> focused test -> inspect diff -> required CI -> merge`

Terra optional.

### STANDARD

Ví dụ: feature vừa, API/UI behavior, nhiều file liên quan nhưng không chạm high-risk boundary.

Flow:

`short plan -> implement -> focused tests -> affected subsystem -> CI -> one review if useful -> merge`

### STRICT / high risk

Bắt buộc khi thay đổi liên quan:

- Teaching/LMS live behavior;
- student identity/mapping;
- Supabase migrations/RLS/schema;
- auth/session/browser state;
- privacy/PII/model payload boundary;
- live-write safeguards;
- deployment/infrastructure có thể ảnh hưởng real jobs;
- material architecture/data-integrity change.

Flow:

`plan/spec if needed -> implementation -> focused tests -> risk-specific runtime/hosted evidence -> final CI -> one fresh Terra review on stable head -> Owner merge`

## Safety rules

- MVP 1 chỉ đọc Teaching và LMS.
- Không tạo action lưu nhận xét LMS.
- Không bấm Save hoặc Submit trên LMS.
- Không tự động gửi Zalo.
- Không vượt CAPTCHA, OTP hoặc anti-bot.
- Không suy đoán danh tính lớp, buổi hoặc học viên.
- Không map học viên theo thứ tự row.
- Browser Use Agent chỉ dùng cho navigation có kiểm soát.
- Identity/extraction nhạy cảm phải deterministic.
- Không gửi tên học viên cho Gemini hoặc Browser Use LLM.
- Không ghi credential, cookie, token hoặc PII vào log/evidence.
- Không đưa secret vào frontend.

## Definition of DONE

Một task hoàn thành khi:

- acceptance criteria/DONE condition của task đạt;
- focused + affected tests liên quan pass;
- runtime/hosted evidence bắt buộc pass nếu task cần;
- required final CI pass trên candidate head;
- mandatory risk-routed review hoàn thành;
- không còn P0/P1 hoặc material blocker;
- không có out-of-scope behavior.

DONE **không có nghĩa** phải chứng minh toàn repository không còn lỗi không liên quan.

## Git / PR rules

- Không push feature/fix trực tiếp vào `main`.
- `main` giữ ruleset chống direct push/force-push/delete.
- Solo-owner: `Required approvals = 0` là hợp lệ; Owner thực hiện final Merge thủ công.
- Required status check hiện tại là `verify` với strict up-to-date policy.
- Resolve material review conversations trước merge.
- Fresh Terra exact-head review chỉ bắt buộc khi risk routing yêu cầu. Nếu exact-head review là merge gate, code commit mới làm stale review; vì vậy hãy review trên stable final head.
- PR phải ghi scope, explicit non-scope, tests/evidence cần thiết và known blocker ngắn gọn; không cần reasoning transcript dài.
- Không merge khi required CI đỏ hoặc mandatory risk gate chưa đạt.

## Secrets

Agent chỉ được tạo/cập nhật `.env.example`; không ghi secret thật vào repo.

Owner tự nhập secret trong provider secret stores. Không yêu cầu Owner gửi mật khẩu, OTP, cookie, JWT hoặc token vào chat.

## Current Phase 2 execution

Issue #11 sử dụng kế hoạch rút gọn:

`docs/superpowers/plans/2026-09-06-phase2-fast-closure.md`

Nguyên tắc Phase 2 hiện tại:

- không reopen local work đã PASS nếu hosted failure không chỉ tới nó;
- hosted failure phải classify CONFIG / CODE-IN-SCOPE / UNRELATED / SAFETY trước khi sửa;
- focused tests khi fix;
- full CI + Terra chỉ ở stable final checkpoint;
- product cron giữ default-off;
- Phase 3/4/6 và live-write vẫn ngoài scope.
