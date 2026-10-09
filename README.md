# MindX Review Bot

Ứng dụng hỗ trợ chuẩn bị nhận xét học tập. Phần mẫu tại máy có chọn buổi học,
kiểm tra ngữ cảnh, ghép học viên, tự lưu/khôi phục nháp và xuất CSV/Markdown.
Teaching/LMS chỉ đọc; không tự ghi nhận xét hoặc gửi Zalo. Dữ liệu mẫu không
được trình bày như dữ liệu thật khi đăng nhập máy chủ.

## Owner cần biết

- [Tiến độ hiện hành](docs/CURRENT_STATE.md): phần nào đạt, còn thiếu và việc kế tiếp.
- [Hướng dẫn AI](AGENTS.md): AI tự xử lý mã, kiểm tra và nhật ký; Owner nêu mục tiêu,
  quyết định sản phẩm/dữ liệu/chi phí, thao tác tài khoản khi cần và dùng thử.
- Điểm chặn tác vụ thử cũ đã xử lý theo hồ sơ 09/10. Toàn chuỗi và Phase 2 còn mở.
  Bản tinh gọn này đang chờ duyệt nhập bản chính; chưa chạy R13 mới.

## Chạy và kiểm tra — dành cho AI

Dùng Node và các phiên bản đã khóa. `npm ci` cài thư viện; `npm run dev` mở bản
dùng thử tại máy. Đọc điều kiện môi trường trước khi chạy công cụ vận hành.

```text
npm run lint
npm run typecheck
npm test
npm run build
npm run verify:no-secrets
npm run verify:no-live-write
```

Trên Windows, `npm run test:session` chạy các kiểm tra phiên ứng dụng/chuỗi bằng
dữ liệu giả tại máy. Bộ Python ở `apps/browser-runner` có Ruff, Mypy và Pytest;
dùng đường dẫn Python của môi trường dự án đã có hoặc `uv run` với khóa hiện hành.
`npm run test:rls` kiểm quyền trong cơ sở dữ liệu cục bộ và cần Docker/Supabase
cục bộ. Không chạy reset hoặc các công cụ máy chủ để thay cho kiểm tra tại máy.

Các kiểm tra sản phẩm trên GitHub được giữ. `npm test` chạy kiểm thử sản phẩm
và bảo vệ đầu ra, không cần bộ điều phối AI hoặc kích hoạt v10.

## Vận hành sản phẩm

`MINDX_SITE_ADAPTER` là biến cấu hình đường đọc Teaching/LMS đã duyệt, theo dạng
`mindx_runner.<module>:<callable>`. Khi thiếu/sai, chương trình dừng trước nhận
việc hoặc mở trình duyệt. Có mã adapter không đồng nghĩa đủ quyền chạy thật.
Giữ chốt đúng mục tiêu và quyền Owner cho từng lượt; không bật lịch tự chạy ở đây.

Ghép học viên bằng mã ổn định; không đoán theo thứ tự hàng. Giữ dữ liệu học viên,
cookie, token và khóa ngoài model/nhật ký/commit. AI tự kiểm tra các chốt an toàn.

[Hồ sơ gỡ quy trình AI cũ và khôi phục](docs/history/ai-workflow-retirement.md).
