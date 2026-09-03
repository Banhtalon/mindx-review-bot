# AGENTS.md

## Source of truth

Đọc theo thứ tự trước khi làm việc:

1. `AGENTS.md` — luật kỹ thuật và safety lâu dài;
2. `docs/CURRENT_STATE.md` — trạng thái hiện tại, blocker và scope đã được duyệt;
3. `docs/spec/KE_HOACH_MVP_BOT_NHAN_XET_MINDX_V4_BROWSER_USE_SUPABASE.md` — source of truth cho product requirements;
4. specification/plan được link trong task hiện tại.

Chỉ triển khai phase/task được Owner chỉ định hoặc task đã ở trạng thái được controller cho phép.

`docs/CURRENT_STATE.md` không được tự ý ghi đè business rule trong master spec.

## Project scope

Đây là dự án cá nhân/nhóm nhỏ phục vụ học tập và nghiên cứu.

Không mở rộng thành:

- SaaS đa tenant;
- microservices;
- Kubernetes;
- enterprise RBAC;
- hệ thống production phức tạp.

## Agent roles

### Sol High — planner / architect

Trách nhiệm:

- làm rõ requirement;
- kiến trúc và trade-off quan trọng;
- acceptance criteria;
- implementation plan cho task medium/high-risk;
- phát hiện business decision cần Owner quyết định.

Thông thường không làm:

- code feature thường lệ;
- fix bug thường lệ;
- làm message broker giữa Gemini và Terra;
- tự tuyên bố task đã VERIFIED.

Sol rời execution loop sau khi task đạt `ready-for-implementation`. Chỉ quay lại khi có `blocked-owner`, `blocked-external`, spec mơ hồ hoặc thay đổi kiến trúc đáng kể.

### Gemini 3.8 Flash — implementer / fixer

Trách nhiệm:

- đọc plan/spec đã duyệt;
- implementation;
- test;
- debugging;
- refactor trong đúng scope;
- CI fixes;
- xử lý review findings;
- chuẩn bị PR/evidence.

Không được:

- tự phát minh business rule;
- đổi kiến trúc âm thầm;
- mở rộng scope không xin escalation;
- làm yếu test/safety gate để lấy PASS;
- waive acceptance criteria;
- tự reset fix-loop counter hoặc workflow state;
- tự tuyên bố task đã VERIFIED.

Gemini chỉ bắt đầu sửa code khi linked issue đã ở `implementing` và label `implementing` khớp. Nếu requirement hoặc task control state mơ hồ/xung đột: dừng và trả `BLOCKED`, không đoán.

### Terra xHigh — fresh adversarial reviewer

Terra bắt đầu từ fresh context và phải đọc tối thiểu:

- `AGENTS.md`;
- `docs/CURRENT_STATE.md`;
- linked GitHub issue Agent Control Block + workflow-state label;
- task specification;
- acceptance criteria;
- PR diff;
- current-head test/CI evidence;
- relevant `docs/evidence/index.json` entries nếu có claim live/hosted readiness.

Không dựa vào chain-of-thought hoặc reasoning transcript của implementer.

Review hai pass:

1. **Spec compliance** — thiếu requirement, thừa behavior, sai acceptance criteria, vượt scope;
2. **Adversarial review** — edge case, regression, auth/session, retry/idempotency, partial failure, data integrity, privacy/PII, student identity/mapping và live-write safety khi liên quan.

Terra chỉ trả một trong:

- `RECOMMEND_PASS`;
- `NEEDS_FIX`;
- `BLOCKED`.

Terra không được đổi scope hoặc rewrite code chỉ vì preference.

## Verification authority

**Không model nào được tự tạo trạng thái `VERIFIED`.**

Sol, Gemini và Terra chỉ đưa recommendation. `VERIFIED` chỉ được xác lập bằng deterministic evidence tương ứng với scope: test, lint, typecheck, build, RLS, security guards, browser/E2E hoặc các gate máy khác.

Nếu AI nói PASS nhưng required machine gate fail thì task vẫn FAIL.

## Required development workflow

Sử dụng Superpowers làm methodology:

1. brainstorming;
2. writing-plans;
3. using-git-worktrees;
4. test-driven-development;
5. systematic-debugging;
6. requesting-code-review;
7. verification-before-completion.

Mỗi behavior phải đi qua:

RED → GREEN → REFACTOR → VERIFY.

Role-specific project skills nằm ở `.agents/skills/` và không được làm yếu các Superpowers/safety rules này.

## Task states and authoritative loop counter

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

Mỗi agent-driven task phải link đúng một GitHub issue có **Agent Control Block**:

```text
state: <canonical state>
scope_revision: <positive integer>
fix_reentries: <0..2>
owner_scope_reset: <none | Owner approval link>
```

GitHub issue là authoritative source. PR chỉ tham chiếu, không sở hữu counter.

Rules:

- exactly one primary workflow-state label phải khớp với `state`;
- worker chỉ đọc control state, không được unattended-edit issue/label/counter;
- controller thực hiện transition trước khi worker code;
- initial implementation: `ready-for-implementation / 0 -> implementing / 0`;
- fix re-entry chỉ hợp lệ khi current state là `needs-fix` và current `fix_reentries < MAX_FIX_LOOPS`;
- transition fix phải atomic: controller đồng thời đổi `state/label` sang `implementing` và tăng `fix_reentries` đúng 1;
- `needs-fix / 0 -> implementing / 1` là fix re-entry thứ nhất, được phép;
- `needs-fix / 1 -> implementing / 2` là fix re-entry thứ hai, được phép;
- nếu một re-entry mới được yêu cầu khi task đang `needs-fix` và current `fix_reentries >= 2`, đó là lần thứ ba: không increment, chuyển `blocked-owner`, không code;
- deterministic verification fail cần code change cũng phải đi qua `needs-fix` và tiêu tốn re-entry kế tiếp theo cùng rule;
- missing/malformed/conflicting control state => fail closed, trả `BLOCKED`, không sửa code;
- reset counter chỉ hợp lệ khi `scope_revision` tăng và có `owner_scope_reset` link tới Owner approval record.

`MAX_FIX_LOOPS = 2` nghĩa là **cho phép đúng 2 fix implementation re-entries; chặn lần thứ 3**.

## Risk routing

Terra review là bắt buộc với thay đổi liên quan:

- Teaching/LMS;
- student identity hoặc mapping;
- Supabase/RLS/migrations;
- auth/session/browser state;
- privacy/PII;
- model payload boundary;
- live-write safeguards;
- thay đổi kiến trúc hoặc dữ liệu high-risk.

Thay đổi text/CSS/mechanical nhỏ có thể không cần Terra nếu không chạm safety boundary và deterministic gates đầy đủ.

## Safety rules

- MVP 1 chỉ đọc Teaching và LMS.
- Không tạo action lưu nhận xét LMS.
- Không bấm Save hoặc Submit trên LMS.
- Không tự động gửi Zalo.
- Không vượt CAPTCHA, OTP hoặc anti-bot.
- Không suy đoán danh tính lớp, buổi hoặc học viên.
- Không map học viên theo thứ tự row.
- Browser Use Agent chỉ dùng cho navigation có kiểm soát.
- Identity và extraction nhạy cảm phải deterministic.
- Không gửi tên học viên cho Gemini hoặc Browser Use LLM.
- Không ghi credential, cookie, token hoặc PII vào log/evidence.
- Không đưa secret vào frontend.

## Definition of done

Một task chỉ hoàn thành khi:

- acceptance criteria rõ và không còn blocker chưa xử lý;
- Agent Control Block hợp lệ và state/counter không mâu thuẫn;
- test RED được chứng minh cho behavior mới/bug fix khi phù hợp;
- implementation GREEN;
- required lint/typecheck/test/build pass;
- security/privacy checks pass;
- evidence được tạo;
- diff được review theo risk routing;
- không có unresolved material review thread;
- không có thay đổi ngoài scope;
- final deterministic verification pass trên current PR head.

## Required commands

Web:

- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `npm run verify:no-secrets`
- `npm run verify:no-live-write`

Supabase khi task liên quan:

- `npx supabase db reset`
- `npm run test:rls`

Python runner khi task liên quan:

- `uv run ruff check .`
- `uv run mypy src`
- `uv run pytest`

Authenticated live-web changes cần thêm browser/E2E evidence phù hợp; unit review không thay thế runtime verification.

## Git / PR rules

- Không push feature/fix trực tiếp vào `main`.
- `main` phải được active ruleset chặn direct push/force-push/delete.
- Repo thuộc sở hữu solo-owner (1 tài khoản): giữ `Required approvals = 0` trên GitHub; việc đòi hỏi tài khoản người thứ 2 approve là không khả thi.
- Thay vào đó, PR vào `main` bắt buộc phải vượt qua 2 status check độc lập trên đúng current PR head:
  1. `verify` (toàn bộ deterministic gates: lint, typecheck, test, build, no-secrets, no-live-write, Supabase RLS, Python runner);
  2. `review-gate` (kiểm tra Terra xHigh attestation hợp lệ cho đúng `head_sha` hiện tại, `RECOMMEND_PASS`, `p0: 0`, `p1: 0`, `material_findings_resolved: true`).
- Bắt buộc resolve toàn bộ conversation/review threads trước khi merge.
- Bất kỳ push commit mới nào làm thay đổi `head_sha` đều tự động vô hiệu hóa attestation trước đó (head SHA mismatch).
- Worker phát triển (Gemini, Sol) tuyệt đối không được tự ý tạo hoặc chỉnh sửa Terra attestation.
- Dùng branch/worktree riêng cho task.
- PR phải ghi requirement, acceptance criteria, changed/not-changed scope, tests, current-head verification evidence, known limitations và linked task control state.
- Không merge khi required CI (`verify` hoặc `review-gate`) còn đỏ hoặc required review control chưa đạt.
- Không dùng review transcript của implementer làm bằng chứng thay cho fresh review hoặc machine verification.

## Secrets

Agent chỉ được tạo/cập nhật `.env.example`; không ghi secret thật vào repo.

Owner tự nhập secret trong:

- GitHub Actions Secrets;
- Supabase Edge Function Secrets;
- frontend hosting environment.

Không yêu cầu Owner gửi mật khẩu, OTP, cookie hoặc token vào chat.

## Background automation gate

Phân biệt hai loại automation:

1. `.github/workflows/cron-dispatch.yml` là pre-existing read-only **product-job scheduler**; nó có trước migration này, recent scheduled run đang failure và Phase 2 hosted/off-PC vẫn BLOCKED. Migration này không coi nó là bằng chứng pilot cho development agents.
2. **New unattended development-agent automation** (Antigravity Scheduled Tasks / equivalent) chưa được bật cho tới khi hoàn thành ít nhất một manual pilot:

Owner → Sol plan → controller transition → Gemini implement → CI → Terra fresh review → controller transition nếu needs-fix → Gemini fix → final CI → merge.

Scheduled development controller phải fail closed nếu Agent Control Block thiếu/sai, label/state mâu thuẫn, third fix re-entry would be attempted at current `fix_reentries >= 2`, scope reset thiếu Owner approval, task blocked hoặc spec/plan bị thiếu. Worker chỉ code sau khi controller đã đưa task sang `implementing` hợp lệ.

Sau pilot mới được đề xuất automation/background handoff cho development workers.
