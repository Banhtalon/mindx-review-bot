# Bộ điều phối AI đã ngừng sử dụng — 09/10/2026

Đây là hồ sơ lịch sử, không phải hướng dẫn công việc mới. Hướng dẫn hiện hành
ở [AGENTS.md](../../AGENTS.md); tiến độ ở [CURRENT_STATE.md](../CURRENT_STATE.md).

Owner đã duyệt gỡ bộ điều phối AI v9/v10 có khôi phục. Gỡ hướng dẫn/phân vai,
profile/template/pin, bridge/routing/activation/Fast Lane và bài kiểm tra dành riêng
cho chúng; giữ thư viện che bí mật, phiên ứng dụng và toàn bộ công cụ sản phẩm.

## Khôi phục khi cần

- Bản mã trước dọn: `7cfaab350812cd1f01d9924a7c3364088f77d433`. Khôi phục vào một
  bản làm việc riêng từ commit này, không reset hoặc ghi đè công việc đang có.
- Bản sao tại máy: `F:/MINDX_project test/_backups/MINDX-REVIEW-BOT/streamline-20261009`.
  `tracked-working-bytes.zip` giữ đúng nội dung 353 tệp tại máy; `tracked-before.zip`
  giữ bản Git; `manifest.json` giữ dấu kiểm tra và `removal-list.json` giữ danh sách gỡ.
  Đã kiểm lại toàn bộ ZIP và thử khôi phục ba tệp vào thư mục riêng trước dọn.
- Hồ sơ R13 và xử lý tác vụ cũ ở các thư mục gốc được giữ nguyên, không di chuyển
  hoặc sửa giới hạn. Các bản làm việc/nhánh lịch sử vẫn giữ, không xóa trong đợt này.
- Bản sao ở cùng máy chỉ phục vụ khôi phục cục bộ, không phải sao lưu ngoài máy.

## Bản gốc của hướng dẫn cũ

Các liên kết sau trỏ đúng bản lịch sử, không phải quy tắc hiện hành:

- [.ai-workflow/V10_CANONICAL_SPEC.md](https://github.com/Banhtalon/mindx-review-bot/blob/7cfaab350812cd1f01d9924a7c3364088f77d433/.ai-workflow/V10_CANONICAL_SPEC.md)
- [.ai-workflow/MINDX_PROJECT_RULES.md](https://github.com/Banhtalon/mindx-review-bot/blob/7cfaab350812cd1f01d9924a7c3364088f77d433/.ai-workflow/MINDX_PROJECT_RULES.md)
- [docs/AGENT_WORKFLOW.md](https://github.com/Banhtalon/mindx-review-bot/blob/7cfaab350812cd1f01d9924a7c3364088f77d433/docs/AGENT_WORKFLOW.md)
- [docs/AGENT_WORKFLOW_OWNER_SETUP.md](https://github.com/Banhtalon/mindx-review-bot/blob/7cfaab350812cd1f01d9924a7c3364088f77d433/docs/AGENT_WORKFLOW_OWNER_SETUP.md)
- [docs/WORKFLOW_V10_LOCAL_AUTO.md](https://github.com/Banhtalon/mindx-review-bot/blob/7cfaab350812cd1f01d9924a7c3364088f77d433/docs/WORKFLOW_V10_LOCAL_AUTO.md)

## Tệp đã gỡ

- `.agents/skills/mindx-adversarial-review/SKILL.md`
- `.agents/skills/mindx-implement/SKILL.md`
- `.agents/skills/mindx-plan/SKILL.md`
- `.agents/skills/mindx-spec-review/SKILL.md`
- `.agents/skills/mindx-verify/SKILL.md`
- `.ai-workflow/ACTOR_REGISTRY.md`
- `.ai-workflow/BOOTSTRAP.md`
- `.ai-workflow/BRIDGE_CONFIG.example.json`
- `.ai-workflow/CLI_BRIDGE.md`
- `.ai-workflow/DATA_MODEL.md`
- `.ai-workflow/FAST_LANE.md`
- `.ai-workflow/HANDOFF_FILES.md`
- `.ai-workflow/MIGRATION.md`
- `.ai-workflow/MINDX_PROJECT_RULES.md`
- `.ai-workflow/OWNER_GUIDE.md`
- `.ai-workflow/OWNER_STATUS.md`
- `.ai-workflow/POLICY.md`
- `.ai-workflow/PROJECT_PROFILE.example.json`
- `.ai-workflow/PROJECT_PROFILE.json`
- `.ai-workflow/ROUTING.md`
- `.ai-workflow/STATE_MACHINE.md`
- `.ai-workflow/V10_CANONICAL_SPEC.md`
- `.ai-workflow/V10_TEMPLATE_PIN.json`
- `.ai-workflow/fast-lane.allowlist.json`
- `.ai-workflow/prompts/IMPLEMENTER_BOOTSTRAP.md`
- `.ai-workflow/prompts/LEAD_BOOTSTRAP.md`
- `.ai-workflow/prompts/OWNER_QUICK_PROMPTS.md`
- `.ai-workflow/prompts/REVIEWER_BOOTSTRAP.md`
- `.ai-workflow/roles/CONTROLLER.md`
- `.ai-workflow/roles/IMPLEMENTER.md`
- `.ai-workflow/roles/REVIEWER.md`
- `.ai-workflow/roles/TECHNICAL_OPERATOR.md`
- `.ai-workflow/state/OWNER_STATUS.md`
- `.ai-workflow/tasks/TASK-12/revision-2/verification-manifest.json`
- `.ai-workflow/tasks/TASK-12/revision-2/verification-manifest.lock.json`
- `.ai-workflow/tasks/TASK-12/task.json`
- `.ai-workflow/tasks/TASK-12/verification-manifest.json`
- `.ai-workflow/tasks/TASK-12/verification-manifest.lock.json`
- `.ai-workflow/templates/implementer-result.md`
- `.ai-workflow/templates/review.json`
- `.ai-workflow/templates/task.json`
- `scripts/bridge.mjs`
- `scripts/workflow.mjs`
- `scripts/fast-lane.mjs`
- `scripts/qq-auto.mjs`
- `scripts/qq-setup.mjs`
- `scripts/check-workflow-v10.mjs`
- `scripts/lib/bridge.mjs`
- `scripts/lib/bridge-adapters.mjs`
- `scripts/lib/bridge-process.mjs`
- `scripts/lib/workflow.mjs`
- `scripts/lib/documentation.mjs`
- `scripts/lib/fast-lane.mjs`
- `test/workflow-v10-host.test.mjs`
- `docs/AGENT_WORKFLOW.md`
- `docs/AGENT_WORKFLOW_OWNER_SETUP.md`
- `docs/WORKFLOW_V10_LOCAL_AUTO.md`
- `test/source-review-policy.test.ts`
