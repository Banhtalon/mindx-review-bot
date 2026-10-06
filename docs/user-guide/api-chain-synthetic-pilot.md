# Phép thử API bằng một việc giả

Tài liệu này mô tả bộ công cụ kiểm tra một việc thử đã được chuẩn bị trước. Nó không đọc lịch học, học viên hay dữ liệu LMS; không dùng trạng thái trình duyệt thật; và không mở lịch chạy tự động. Trình duyệt trên máy GitHub mở trang trống, chờ 650 giây, gửi các lần gia hạn khóa chạy qua API thật rồi kết thúc một việc có sẵn.

## Các chốt bắt buộc

Workflow vẫn nhận hai loại việc cũ và giữ nguyên bước kiểm tra đầu vào 15 phút. Công việc API mới chỉ mở khi đồng thời khớp kho mã, nhánh `main`, đúng lần chạy đầu, đúng mã việc và loại việc giả, cùng dấu cho phép khớp chính xác với mã nguồn đã duyệt. Bước chạy có giới hạn 20 phút. Gọi workflow thủ công với mã việc khác chỉ chạy bước kiểm tra đầu vào; bước API sẽ bị bỏ qua.

Trước khi trình duyệt mở, công cụ đọc lịch sử workflow đúng một lần và yêu cầu có đúng một lượt chạy đầu tiên cho mã việc cố định ở mã nguồn đã duyệt. Worker sau đó kiểm tra việc vẫn ở trạng thái `dispatched`, chưa claim lần nào, có đúng nội dung giả và chưa có trạng thái trình duyệt giả. Trạng thái khác sẽ dừng ngay; công cụ không chờ, gửi lại hay thử việc khác.

Worker dùng client Supabase đang có để claim, gia hạn và kết thúc. Lớp nối của riêng phép thử chỉ đưa qua ba thao tác đó; nó không đưa bộ đọc trạng thái đăng nhập trình duyệt vào worker. Mỗi lệnh có đường dẫn, nội dung và số lần gửi đã khóa; biên nhận ghi ý định trước khi gửi và không lưu khóa xác thực hay nội dung thô. Phản hồi sai định dạng, timeout hoặc kết quả không rõ không được tính là thành công. Tiến trình trình duyệt được nhận diện bằng mã tiến trình và thời điểm tạo; chỉ hồ sơ mới thuộc lần thử mới được dọn.

## Công cụ quyền và trạng thái hiện tại

`scripts/api_chain_operator.py` chuẩn bị ma trận 15 lượt đọc/kiểm tra quyền, ba lượt gọi phủ định cho Edge và tối đa một lần gửi tích cực cho đúng việc đã tạo sẵn. Lỗi `404` hoặc phản hồi không có mã quyền rõ ràng là chưa đủ bằng chứng. Nếu lệnh bị chấp nhận bất ngờ hoặc kết quả mơ hồ, các bước gửi sau bị khóa. Bốn mẫu SQL chỉ nhắm đúng workspace thử; chỗ điền danh tính được để làm tham số riêng, không chứa mã người dùng thật.

Hiện chưa xác nhận được kênh an toàn lấy phiên ứng dụng chính thức và chưa có dấu duyệt cuối cho đúng mã nguồn đã phát hành. Vì vậy giao diện lệnh của công cụ trả `WAITING_AUTH_CAPABILITY` và không thực hiện yêu cầu. Không dán token, mật khẩu hay mã tài khoản vào chat, Terminal, tệp mã nguồn hoặc biên nhận. Kiểm tra tự động cục bộ chỉ chứng minh bộ lọc và cách ghi nhận; nó không thay cho phép thử quyền thật, lần chạy GitHub hay chấp thuận của chủ dự án.

Khi các điều kiện tài khoản và bản phát hành đã được xác minh riêng, Lead mới hướng dẫn đúng bước chạy cần thiết. Không tự bấm **Run workflow** hoặc **Re-run jobs** để dò cấu hình; một lượt thử bị chặn cũng cần được đối soát trước khi lập lượt tiếp theo.

## Giới hạn kết luận

Một lần chạy thành công chỉ chứng minh các quyền API đã thử, việc giả đã có sẵn được giao tới worker, các lần gia hạn lease thật và metadata kết thúc được lưu. Nó không chứng minh Edge tự tạo việc mới, lịch chạy tự động, đường bí mật cron, phục hồi sau timeout, quyền của mọi workspace, lưu trữ Storage, hay việc Teaching/LMS đã lưu và đối soát dữ liệu.
