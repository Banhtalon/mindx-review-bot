# Tự đăng nhập Teaching khi chạy trên GitHub

Máy chủ GitHub có thể thực hiện công việc đã được bấm chạy dù máy cá nhân tắt.
Chức năng này không tự bật lịch chạy định kỳ. Phiên đã lưu được dùng trước;
chỉ khi gặp đúng biểu mẫu đăng nhập Teaching, hệ thống mới đăng nhập tối đa
một lần bằng thông tin bên dưới. Các thao tác đọc lịch vẫn giữ nguyên lớp,
buổi, ngày và giờ đã chọn. Không lưu, gửi nhận xét hoặc sửa dữ liệu Teaching/LMS.

## Chỗ nhập tài khoản và mật khẩu

1. Mở [kho bí mật GitHub của dự án](https://github.com/Banhtalon/mindx-review-bot/settings/secrets/actions).
2. Bấm **New repository secret**.
3. Ô **Name** nhập `TEACHING_USERNAME`; ô **Secret** nhập tên đăng nhập Teaching.
   Bấm **Add secret**. Thành công khi tên `TEACHING_USERNAME` xuất hiện trong danh sách.
4. Bấm **New repository secret** lần nữa.
5. Ô **Name** nhập `TEACHING_PASSWORD`; ô **Secret** nhập mật khẩu Teaching.
   Bấm **Add secret**. Thành công khi tên `TEACHING_PASSWORD` xuất hiện trong danh sách.

Không gửi mật khẩu vào chat, ảnh chụp hoặc tệp của dự án. GitHub không hiển thị
lại giá trị đã lưu; để đổi mật khẩu, dùng nút sửa của mục `TEACHING_PASSWORD`.
Nhập hai mục này không tự chạy công việc và không thay đổi dữ liệu Teaching.

Hướng dẫn nền tảng: [GitHub Actions Secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).

## Khi nào cần Owner

- Thiếu thông tin đăng nhập: dừng với `TEACHING_LOGIN_REQUIRED`.
- Sai mật khẩu hoặc không hoàn tất được đăng nhập: dừng với `AUTH_FAILED`.
- Cần OTP (mã xác nhận), CAPTCHA hoặc người xác nhận: dừng với `AUTH_INTERACTION_REQUIRED`.
- Biểu mẫu khác dự kiến: dừng với `TEACHING_SELECTOR_CHANGED`.
- Lỗi lịch `TEACHING_DATA_INVALID` không tự kích hoạt đăng nhập lại.

Đăng nhập mới chỉ dùng trong lượt chạy hiện tại; không ghi đè phiên mã hóa đã
lưu trên Supabase. Lượt sau vẫn dùng phiên cũ trước rồi đăng nhập khi cần.
Giữ nguyên giới hạn số lượt của từng công việc; không bấm chạy lại một công việc
đã dùng hết lượt. Owner chỉ cần báo kết quả; Codex kiểm tra thông tin kỹ thuật.

## Giới hạn kiểm chứng

Kiểm tra trên dữ liệu giả không chứng minh tài khoản thật đăng nhập được từ GitHub.
Sau khi bản sửa được duyệt và đưa vào bản chính, cần chuẩn bị một công việc mới,
đúng mục tiêu và có quyền thử riêng. Không dùng lại các lượt thử cũ đã kết thúc.
