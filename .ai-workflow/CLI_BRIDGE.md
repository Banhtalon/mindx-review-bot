# Sequential Windows CLI bridge

[Quy tắc workflow v10](V10_CANONICAL_SPEC.md) định nghĩa vai trò, ngân sách sửa, trạng thái và điều kiện `LOCAL_AUTO`. Trang này mô tả lệnh cầu nối CLI và các packet nó lưu.

## Chuẩn bị

Cầu nối dùng Node 20+, Git, Codex CLI và Antigravity CLI đã có trên máy Windows. Cấu hình chạy nằm trong `.workflow-local/`; tài khoản tiếp tục do CLI chính thức quản lý. `doctor --probe` tạo capability packet có kết quả dạng cấu trúc.

## Lệnh

```text
node scripts/bridge.mjs doctor <bridge-config.json> <repo> <doctor-packets> --probe
node scripts/bridge.mjs pilot <bridge-config.json> <frozen-task.json> <repo> <run-packets>
node scripts/bridge.mjs status <run-packets>
node scripts/bridge.mjs resume <bridge-config.json> <frozen-task.json> <repo> <run-packets> --pilot
node scripts/bridge.mjs quota-drill <bridge-config.json> <accepted-pilot-packets> <activation-packets>
node scripts/bridge.mjs activate <bridge-config.json> <accepted-pilot-packets> <target-run-packets>
```

`workflow.mjs route` trả đề xuất trong chế độ ASSISTED. Bridge ghi argv, thời gian, session, model báo cáo, head, kết quả đã redaction và checkpoint vào run packets. `quota-drill` không gọi AI: nó kiểm tra cầu nối xử lý `WAITING_QUOTA` (hết hạn mức) và resume (tiếp tục) an toàn trên bản sao trạng thái. Dùng thư mục activation tách khỏi packet pilot đã chấp nhận. `activate` chỉ nhận pilot và biên nhận quota drill cùng khớp với canonical spec.

## Ngữ cảnh review và dữ liệu test

`review_context_paths` trong config liệt kê file hoặc thư mục bổ sung cho reviewer,
ví dụ model, form và template nền mà thay đổi đang sử dụng. Packet riêng của mỗi
lượt review có `review-source.json`: diff, nội dung đã kiểm tra và hash base/head.
`source_sha256` trong lịch sử liên kết với packet này.

`synthetic_source_approvals` cho file test có dạng
`[{"path":"notes/tests.py","sha256":"<SHA-256 nội dung UTF-8 chính xác>","kind":"synthetic-test-data","reason":"Lead đã đọc và xác nhận dữ liệu thử"}]`.
Đây là ghi nhận kiểm tra nguồn của Lead trước khi bắt đầu checkpoint, tách khỏi
cấu hình tự phát hiện dữ liệu giả. File test mới hoặc thay đổi nội dung cần được
kiểm tra lại; config thay đổi không thể tiếp tục checkpoint cũ.

Với file phụ thuộc phục vụ review, dùng cùng cấu trúc nhưng
`"kind":"static-review-dependency"`. File này phải không phải file test và phải
được ghi đúng đường dẫn file trong `gate_paths` hoặc `review_context_paths`.
Khai báo một thư mục không duyệt cả thư mục hay các file con. SHA-256 phải khớp
nguyên văn nội dung của từng phiên bản base/head cần đọc.

Quyền test chỉ nhận thêm nguyên chuỗi `cookie=synthetic-cookie` có dấu nháy;
quyền file phụ thuộc chỉ nhận thêm nguyên chuỗi thay thế `Bearer [REDACTED]`
có dấu nháy. Chỉ nhận dòng Python `.py` gọi `raise RuntimeError` với một nguyên
chuỗi, hoặc khai báo hằng `const` JavaScript `.js`/`.mjs`/`.cjs` đứng riêng và
bảng `const replacements` chỉ gồm cặp biểu thức kiểm tra/chuỗi thay thế.
Phải xác định đúng chuỗi nguồn, không nhận mẫu nằm trong comment hay chuỗi lớn
hơn. Cú pháp chưa hỗ trợ, ghép thêm sau ngoặc hoặc biến đổi cả mảng vẫn bị chặn.
Thêm ký tự, ghép chuỗi hoặc header khác vẫn bị chặn. Khóa thật, URL chứa thông
tin đăng nhập và giá trị bí mật của môi trường vẫn bị chặn. Packet giữ nguyên
toàn bộ nguồn; không thay thế hoặc xóa các chuỗi này khi gửi review.
Các chi tiết giới hạn nằm trong canonical spec.
Task Gemini-first ghi `execution.source_approvals_sha256` bằng SHA-256 của
`JSON.stringify(config.synthetic_source_approvals)` trước khi freeze.

`V10_TEMPLATE_PIN.json` lưu hash của các byte core đang dùng. Khi có bản vá cục
bộ, `provenance.local_patch` ghi task và điểm bắt đầu, còn `commit` vẫn chỉ là
commit upstream gốc, không phải bằng chứng upstream đã chứa bản vá. Pin và
checker của bản ứng viên không thay thế review độc lập trên đúng commit.

## Khôi phục

Lệnh trạng thái cho packet Gemini-first: `node scripts/workflow.mjs status <task> <evidence> <review> <repo> <bridge-config>`. Tham số cuối cung cấp cấu hình reviewer kỳ vọng cho cùng phép kiểm tra readiness được bridge sử dụng.

Khi tiến trình kết thúc bất thường, run packet giữ in-flight marker, session và diff để Lead đối chiếu trước lần thao tác tiếp theo. `status` đọc checkpoint hiện có. Danh sách tham số và cấu hình mẫu ở [BRIDGE_CONFIG.example.json](BRIDGE_CONFIG.example.json).
