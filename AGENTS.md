# AGENTS.md

## Source of truth

Đọc trước khi làm việc:

- docs/spec/KE_HOACH_MVP_BOT_NHAN_XET_MINDX_V4_BROWSER_USE_SUPABASE.md

Chỉ triển khai phase được người dùng chỉ định.

## Project scope

Đây là dự án cá nhân/nhóm nhỏ phục vụ học tập và nghiên cứu.

Không mở rộng thành:

- SaaS đa tenant;
- microservices;
- Kubernetes;
- enterprise RBAC;
- hệ thống production phức tạp.

## Required development workflow

Sử dụng Superpowers:

1. brainstorming;
2. writing-plans;
3. using-git-worktrees;
4. test-driven-development;
5. systematic-debugging;
6. requesting-code-review;
7. verification-before-completion.

Mỗi behavior phải đi qua:

RED → GREEN → REFACTOR → VERIFY.

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

- test RED được chứng minh;
- implementation GREEN;
- lint và typecheck pass;
- security/privacy checks pass;
- evidence được tạo;
- diff được review;
- không có thay đổi ngoài scope.

## Required commands

Web:

- npm run lint
- npm run typecheck
- npm run test
- npm run build

Supabase:

- npx supabase db reset
- npm run test:rls

Python runner:

- uv run ruff check .
- uv run mypy src
- uv run pytest

## Secrets

Codex chỉ được tạo `.env.example`.

Người dùng tự nhập secret trong:

- GitHub Actions Secrets;
- Supabase Edge Function Secrets;
- frontend hosting environment.

Không yêu cầu người dùng gửi mật khẩu vào chat.