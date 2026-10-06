# Kênh đăng nhập ứng dụng — trạng thái chuẩn bị

## Bản xem trước hiện tại

Hiện chỉ có bản mô phỏng bằng dữ liệu giả. Lead mở bản xem trước tại máy bằng lệnh `node scripts/app_session_host.mjs --preview` trong thư mục dự án rồi gửi Owner đường dẫn `localhost` để xem. Owner không cần mở Terminal.

Trang phải ghi rõ “dữ liệu giả”. Có thể nhập email và mật khẩu giả để xem thông báo “Mô phỏng hoàn tất”; công cụ không gửi dữ liệu ra ngoài, không cần tài khoản, và chỉ nhận một lần thử trong mỗi phiên mở. Nút “Đóng công cụ” kết thúc phiên; máy cũng tự đóng sau tối đa 15 phút.

## Đăng nhập thật và hồ sơ thử sau này

Chưa được chạy đăng nhập thật hay pilot. Owner đã báo chưa có hoặc chưa chắc có tài khoản ứng dụng; công cụ không tạo, đặt lại hoặc mời tài khoản. Kế hoạch tài khoản và hồ sơ pilot riêng vẫn ở trạng thái **NOT_RUNNABLE**, gắn với mốc `main` `1855c37`.

Chỉ xem xét bước sau khi công cụ đăng nhập được rà soát và chấp nhận độc lập, tài khoản ứng dụng hiện có được xác nhận trong Supabase chính thức, khóa công khai của đúng dự án được cung cấp từ cấu hình chính thức, và việc kiểm tra đúng mục tiêu/quyền/mã định danh được làm mới. Mọi lần đăng nhập thật hoặc đọc dữ liệu cần Owner duyệt riêng trước khi chạy. Kênh này không đọc bảng, gọi RPC/Edge/Storage, kiểm tra vai trò, hay khởi chạy bộ điều phối.
