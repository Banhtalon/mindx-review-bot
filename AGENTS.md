# Làm việc với Owner — MindX Review Bot

Đây là hướng dẫn AI hiện hành duy nhất. Owner không cần biết lập trình.
Đọc yêu cầu, `docs/CURRENT_STATE.md` và nguồn liên quan trước khi làm.
Ý định rõ ràng của Owner có ưu tiên cao nhất; tài liệu lịch sử không đặt quy tắc mới.

## Cách thực hiện

- Trả lời bằng tiếng Việt, ngắn và dễ hiểu; giải thích thuật ngữ khi cần.
- AI tự đọc, sửa, kiểm tra và xử lý lỗi. Chỉ hỏi Owner về sản phẩm, chi phí,
  dữ liệu, quyền tài khoản hoặc quyết định thực sự chưa rõ.
- Bảo vệ thay đổi đang dở; một người/AI ghi mã tại một thời điểm. Sửa ít nhất
  cần thiết. Tạo điểm khôi phục trước thay đổi lớn hoặc gỡ tệp.
- Làm trực tiếp: hiểu hiện trạng → thực hiện → kiểm tra phần ảnh hưởng → báo kết quả.
  Không bắt buộc nhiều model, cầu nối, hồ sơ JSON, khóa hợp đồng hay kích hoạt điều phối.
- Công việc đáng kể dùng một ghi chú trong `.workflow-local/`: mục tiêu, phạm vi,
  bản mã, kết quả kiểm tra và việc còn thiếu. Sửa nhỏ không cần dựng bộ hồ sơ.
- Trong lúc sửa, chạy kiểm tra liên quan. Cuối công việc chạy kiểm tra phần bị
  ảnh hưởng, chống lộ bí mật và chống ghi Teaching/LMS; không lặp bộ đầy đủ nếu
  không có thay đổi hoặc lỗi mới. Chỉ bỏ bài kiểm tra thuộc chức năng đã chủ động gỡ.
- Cùng một lỗi vẫn lặp sau hai lần xử lý thì chẩn đoán trước khi sửa tiếp;
  không đổi chat/nhánh/hồ sơ để che số lượt hoặc tự thử lại khi kết quả chưa rõ.
- Cần đánh giá độc lập khi thay đổi đăng nhập, quyền, phiên, danh tính học viên,
  bảo mật, dữ liệu, triển khai hoặc cơ chế bảo vệ. Reviewer không tham gia thiết kế
  hay sửa phần đó, không tự sửa hoặc giao tiếp việc. Thiếu reviewer thì báo chưa
  hoàn tất phần đánh giá; không tự tuyên bố đạt. Việc ít rủi ro do Lead kiểm tra.
- AI kiểm tra thực tế thay đổi nhìn thấy được bằng dữ liệu giả/an toàn trước,
  rồi đưa Owner bản dùng thử và 1–3 thao tác dễ làm để nghiệm thu.

## Quyền và an toàn

- Teaching/LMS chỉ đọc. Không Save/Submit/ghi nhận xét, tự gửi Zalo, vượt CAPTCHA/OTP
  hoặc đoán danh tính. Ghép học viên bằng mã ổn định, không theo thứ tự hàng.
- Tài khoản, token, cookie, phiên trình duyệt và dữ liệu học viên không vào model,
  nhật ký, hồ sơ hoặc commit. Owner đăng nhập trực tiếp ở giao diện chính thức;
  không yêu cầu gửi mật khẩu/khóa qua chat. Giữ các kiểm tra bảo mật đang có.
- Trước xóa dữ liệu, sửa quyền, migration (đổi cấu trúc dữ liệu), triển khai,
  ghi thật hoặc mở lượt thử máy chủ: xác định đúng đích và quyền Owner đã cấp.
  Nếu thiếu quyền, chuẩn bị phương án cụ thể cùng khôi phục rồi xin duyệt gộp.
- Quyền đã cấp trong chat còn hiệu lực trong đúng phạm vi. Không hỏi lại cho
  bước kỹ thuật đã được duyệt; chỉ hỏi khi vượt phạm vi hoặc hậu quả thay đổi.
- Giữ nguyên hồ sơ cũ, giới hạn và lượt đã dùng. Lượt đã đóng không cấp quyền
  chạy lại; nhiệm vụ cũ được đối chiếu trong bản nguồn/hồ sơ riêng đã giữ.
- Đưa mã lên GitHub, nhập bản chính, phát hành và chạy dữ liệu thật cần quyền
  tương ứng của Owner; nghiệm thu một bản dùng thử không tự cấp các quyền đó.
- Bằng chứng phải đúng bản mã và phạm vi; sửa phần ảnh hưởng làm mất hiệu lực
  kiểm tra tương ứng. Kiểm giả/tại máy không chứng minh máy chủ hoặc PC đã tắt.

## Tiến độ và báo cáo

Chỉ `docs/CURRENT_STATE.md` là bảng tiến độ hiện hành; cập nhật dòng liên quan,
không thêm bảng tổng hợp thứ hai. Hồ sơ gốc là bằng chứng theo thời điểm.
Không bắt Owner xem mã, SQL (lệnh cơ sở dữ liệu), CI (kiểm tra trên GitHub) hoặc log.

Cuối công việc báo bốn ý: **Đã làm / Kết quả / Chưa kiểm tra / Việc tiếp theo**.
Nêu rõ nguyên nhân và bước giải quyết khi bị chặn; không gọi hoàn tất khi chưa kiểm.
