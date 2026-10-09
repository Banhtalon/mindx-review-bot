# Tiến độ hiện hành — MindX Review Bot

Đối chiếu hồ sơ ngày **09/10/2026** (Asia/Saigon). **Phase 2 chưa hoàn tất.**
Bản sản phẩm làm gốc: `7cfaab350812cd1f01d9924a7c3364088f77d433` (#43).

**Điểm chặn cũ đã xử lý:** hủy đúng một tác vụ thử; hậu kiểm máy chủ đạt
0 tác vụ còn gây chặn và 0 lượt chưa kết thúc. Dữ liệu ngoài phạm vi giữ nguyên;
đánh giá độc lập đạt. Chưa mở R13 mới hoặc xác nhận toàn chuỗi.

Đây là bảng tiến độ hiện hành duy nhất trong bản tinh gọn. Hướng dẫn AI ở
[AGENTS.md](../AGENTS.md). Bản tinh gọn đang trên nhánh riêng, chưa nhập main.
Các bản cũ trong bản làm việc khác là bằng chứng theo thời điểm.

## Việc đang làm và việc tiếp theo

1. Hoàn tất tinh gọn: gỡ bộ điều phối AI cũ, kiểm sản phẩm và đánh giá độc lập;
   trình Owner duyệt nhập bản chính. Chưa chạy R13 hoặc gọi máy chủ.
2. Sau tinh gọn, chuẩn bị một lượt R13 mới: tận dụng bằng chứng còn hiệu lực,
   gom điều kiện/kiểm quyền/chạy/dọn và phương án khôi phục để Owner duyệt đúng phạm vi.
3. Kiểm toàn chuỗi, lưu kết quả, gia hạn, lỗi và PC-off (máy Owner tắt); nghiệm thu
   đủ điều kiện Phase 2 trước khi nối lưu lịch Teaching, LMS và các phần sau.

Giữ bộ đếm cũ: sửa **13/13**, yêu cầu máy chủ **96 xác nhận / 100 bảo thủ**,
SQL **41** trong trần **173/55**; bốn lượt Auth lịch sử chưa xác minh.
Không đặt lại giới hạn hoặc dùng quyền của lượt đã đóng cho lượt mới.
Owner chỉ quyết định phạm vi, thao tác tài khoản khi cần và dùng thử kết quả.

## Checklist sản phẩm

24 mục: **13 đạt theo phạm vi, 11 còn mở**. Đây không phải phần trăm hoàn thành.
Tại máy/dữ liệu giả không thay bằng chứng máy chủ; mỗi dòng giữ đúng phạm vi đã đạt.

| Mục | Đã xác nhận và bằng chứng | Còn thiếu / điều kiện hoàn tất |
| --- | --- | --- |
| [x] P1-LOCAL — nền tảng tại máy | Nền tảng và kiểm tra dữ liệu giả đã đạt. [Chỉ mục Phase 1](evidence/phase-1/index.json) | Còn kiểm chứng tài khoản/quyền trên máy chủ ở dòng kế tiếp. |
| [ ] Nền tảng — Spike 0 / Phase 1 | Có nhiều bằng chứng tại máy; nền tảng thực tế chưa nghiệm thu đủ. [Chỉ mục Spike 0](evidence/index.json) | Đo thời gian/chi phí Teaching và LMS, kiểm quyền và tài khoản trên máy chủ. |
| [x] P2-LOCAL — chương trình nhận/chạy việc và công cụ thử giả | Chương trình nhận/chạy việc và kiểm thử giả đã có. [Chỉ mục Phase 2](evidence/phase-2/index.json) | Toàn chuỗi còn mở ở E3/F/G. |
| [ ] P2-A — cấu trúc, quyền và mã đã triển khai | Đã đối chiếu nguồn máy chủ và quyền trong phạm vi cũ. [Đối chiếu chính xác 07/10](<C:/Users/QQ/.codex/worktrees/progress-checklist/MINDX-REVIEW-BOT/.workflow-local/progress-checklist-consolidation/hosted-exact-20261007/REPORT.md>) | Làm mới cấu hình đích, phạm vi và quyền cần thiết trước lượt mới; không triển khai lại khi mã đã khớp. |
| [x] P2-B — nhận việc, tranh việc và hết hạn, phạm vi SQL trên máy chủ | Máy chủ đã chặn nhận trùng/sai người/vượt lượt; dữ liệu thử đã dọn. [Lượt 04/10](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/phase2-hosted-rpc-pilot/OWNER_RESULT.md>) | Đã hoàn tất phạm vi SQL; không suy ra quyền ứng dụng. |
| [x] P2-C1 — gia hạn, nhận lại và giới hạn thử lại, phạm vi SQL | Gia hạn, hết hạn, nhận lại và giới hạn thử lại đã kiểm trên máy chủ. [Lượt 06/10](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/phase2-heartbeat-recovery-execution/OWNER_RESULT.md>) | Đã hoàn tất phạm vi SQL; không chạy lại. |
| [x] P2-C2 — chạy dài, quá thời gian và dọn tiến trình, phạm vi chương trình thử | Chương trình thử chạy 650 giây, 21 lần báo hoạt động, dừng quá hạn và dọn tiến trình. [Kết quả 06/10](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/phase2-runtime-cloud-execution/OWNER_RESULT.md>) | Đã đạt phạm vi chương trình giả; còn chứng minh cả chuỗi lưu kết quả. |
| [x] P2-D1 — lưu, tải lại, đổi và vô hiệu hóa hai phiên giả | Hai phiên giả đã lưu/tải lại, đổi khóa, vô hiệu hóa và dọn. [Kết quả Storage 06/10](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/phase2-storage-direct-execution/OWNER_RESULT.md>) | Đã đạt đúng lượt thành công; phạm vi lỗi riêng ở D2. |
| [x] P2-D-LOCAL — mã hóa và vòng đời phiên bằng dữ liệu giả | Mã hóa, nạp phiên và vòng đời được kiểm bằng dữ liệu giả. [Bài kiểm tra hiện hành](../apps/browser-runner/tests/unit/test_browser_state.py) | Đã đạt tại máy; không thay bằng chứng máy chủ. |
| [x] P2-D2 — vòng đời phiên trong phạm vi phiên/dữ liệu giả | Năm nhóm vòng đời phiên/dữ liệu giả đã đối chiếu và Owner nghiệm thu 08/10. [Nghiệm thu 08/10](<C:/Users/QQ/.codex/worktrees/api-chain-session/MINDX-REVIEW-BOT/.workflow-local/post-tamper-owner-acceptance-20261008/OWNER_ACCEPTANCE.md>) | Đã đóng đúng phạm vi; không lặp phép tamper đã đạt. |
| [x] P2-E1 — một lượt Teaching trực tiếp khi máy Owner tắt | Một lượt Teaching đúng mục tiêu thành công trong phạm vi PC-off đã ghi. [Hồ sơ GI34](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/teaching-post37-gi34-preparation/result-37190777967>) | Chỉ một mục tiêu; chưa chứng minh toàn chuỗi ứng dụng. |
| [x] P2-E2-LOCAL — công cụ phiên ứng dụng đã chuẩn bị tại máy | #41 đã nhập 09/10; bản R12 kiểm tại máy, CI và nghiệm thu mẫu đạt. [Nguồn đã nhập #41](https://github.com/Banhtalon/mindx-review-bot/pull/41) | Đã đạt công cụ tại máy; quyền thật của lượt mới ở E2. |
| [ ] P2-E2 — hoàn tất kênh đăng nhập ứng dụng, liên quan #41 | #41/#43 đã nhập; tác vụ thử cũ đã hủy và hậu kiểm không còn chặn. [Hậu kiểm 09/10](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/legacy-resolution-20261009/execution/OWNER_RESULT.md>) | Lượt R13 cũ đã đóng. Cần quyền riêng, xác thực và kiểm quyền ứng dụng của lượt mới. |
| [ ] P2-E3 — một chuỗi ứng dụng → máy chủ → GitHub → chương trình chạy | Đã có công cụ chuỗi và sửa R13; hậu kiểm tác vụ cũ đạt 0/0, không còn writer cũ. [Hậu kiểm 09/10](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/legacy-resolution-20261009/execution/OWNER_RESULT.md>) | Chưa chạy toàn chuỗi mới: ứng dụng → máy chủ → GitHub → chương trình chạy → lưu kết quả → dọn. |
| [ ] P2-F — nhánh lỗi của cả chuỗi | Đã kiểm lỗi từng phần; giữ lịch sử lỗi giao việc và dừng trước nhận việc. [Lượt đầu 07/10](<C:/Users/QQ/.codex/worktrees/api-chain-session/MINDX-REVIEW-BOT/.workflow-local/api-chain-session/execution.json>) | Chứng minh lỗi trước/giữa/cuối trên cả chuỗi, không chạy trùng và không thử lại khi chưa rõ. |
| [ ] P2-G — quyền và dữ liệu riêng tư của chuỗi hoàn chỉnh | Một số kiểm quyền thật đã đạt; xử lý tác vụ cũ giữ nguyên dữ liệu ngoài phạm vi. [Hậu kiểm 09/10](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/legacy-resolution-20261009/execution/OWNER_RESULT.md>) | Kiểm quyền/đầu ra an toàn và đối soát dữ liệu của toàn chuỗi mới. |
| [ ] P2-CLOSE — nghiệm thu toàn Phase 2 | Các phần B/C/D và thử tại máy đạt đúng phạm vi. [Chỉ mục Phase 2](evidence/phase-2/index.json) | Đối chiếu các mục A/E2/E3/F/G còn mở, đánh giá độc lập và Owner nghiệm thu tổng thể. |
| [x] P3-LOCAL — đọc và đối soát Teaching bằng dữ liệu giả | Đọc/đối soát Teaching bằng dữ liệu giả đã đạt. [Bằng chứng gốc](evidence/phase-3/V4-P3-01-teaching-fixtures.md) | Đã đạt tại máy; không thay lưu lịch thật. |
| [ ] P3-HOSTED — lưu và đối soát Teaching thực tế | Một lượt đọc Teaching thật đã có; hiện chủ yếu lưu trạng thái/số lượng. [Chương trình đọc](../apps/browser-runner/src/mindx_runner/live_adapter.py) | Nối lưu lịch, đọc lại và đối soát bền vững; tránh trùng và đo các tình huống thực tế. |
| [x] P4-LOCAL — đọc LMS và ghép học viên bằng dữ liệu giả | Đọc LMS và ghép bằng mã ổn định có kiểm giả. [Bộ đọc giả](evidence/phase-4a/index.json) | Đã đạt tại máy; không thay đọc học viên thật. |
| [ ] P4-HOSTED — LMS thực tế | Nguồn chỉ đọc và chặn danh tính không chắc chắn đã có. [Hồ sơ gốc](history/progress-before-streamline-20261009.md) | Đăng nhập/đọc thật, ghép đúng mã, lưu kết quả và Owner nghiệm thu. |
| [x] P5-LOCAL — chương trình học, nhập nhanh, nháp và xuất tệp giả | Mẫu chương trình học, nhập nhanh, tự lưu/khôi phục nháp và xuất tệp đã có. [Ngữ cảnh bài học](evidence/phase-5a/index.json) | Đã đạt dữ liệu giả; xuất đầu vào chưa phải sinh nhận xét AI. |
| [ ] P5-HOSTED — màn hình và nháp dùng dữ liệu thật | Có cấu trúc đăng nhập và màn hình chờ khi chưa đủ khả năng máy chủ. [App](../src/App.tsx) | Nối Teaching/LMS thật, nháp máy chủ, quyền vai trò và nghiệm thu giáo viên. |
| [ ] Phase 6–8 — nhận xét, duyệt/xuất và vận hành thường xuyên | Yêu cầu sản phẩm đã có; chưa có bằng chứng hoàn tất. [Kế hoạch V4](spec/KE_HOACH_MVP_BOT_NHAN_XET_MINDX_V4_BROWSER_USE_SUPABASE.md) | Chỉ mở phạm vi mới theo phụ thuộc sau nghiệm thu các phần trước; lịch tự chạy cần quyết định riêng. |

## Lịch sử và giới hạn bằng chứng

[Bản tiến độ đầy đủ trước tinh gọn](history/progress-before-streamline-20261009.md)
được giữ nguyên nội dung, gồm chi tiết tiêu chí và bằng chứng từng lượt. Các hồ sơ
đóng băng, ngày/môi trường và quyền đã duyệt giữ nguyên. Không gọi lại máy chủ để
cập nhật bảng này. Liên kết tệp cục bộ chỉ dùng được trên máy có thư mục đó.

Khi có kết quả mới, cập nhật đúng dòng và việc kế tiếp; không nối thêm khối trạng
thái trùng. [Hồ sơ gỡ bộ điều phối và khôi phục](history/ai-workflow-retirement.md).
