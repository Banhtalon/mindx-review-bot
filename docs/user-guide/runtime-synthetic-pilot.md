# Phép thử chương trình thật trên GitHub

Bản này chuẩn bị một lượt thủ công trên máy của GitHub, dùng Python và Chromium thật nhưng dữ liệu giả. Không cần tài khoản Teaching/LMS, khóa Supabase hay công việc mới trong cơ sở dữ liệu. Không đọc lịch hoặc học viên, không đăng nhập, không lưu nhận xét. Chương trình sản phẩm giữ nguyên.

| Tình huống | Điều cần xác nhận khi chạy GitHub |
| --- | --- |
| Chạy lâu | Giữ việc 650 giây, khoảng 10 phút 50 giây; gia hạn theo chu kỳ 30 giây, có gia hạn sau mốc 10 phút; kết thúc thành công đúng một lần |
| Quá thời gian | Giữ giới hạn mặc định 720 giây. Chương trình dành 3 giây cho hủy/kết thúc/dọn nên dự kiến hủy phần việc gần giây 717, ghi RUNNER_TIMEOUT đúng một lần và dừng trình duyệt |
| Tắt cưỡng bức | Tắt riêng tiến trình thử 3 giây sau khi trình duyệt sẵn sàng; ghi rõ những tiến trình còn lại rồi bộ giám sát dọn đúng tiến trình đã nhận diện |

Ba tình huống chạy lần lượt; gặp lỗi bất ngờ thì dừng, không tự chạy lại hoặc chuyển tiếp. Dự kiến 25–35 phút gồm chuẩn bị, giới hạn công việc 40 phút. Chỉ có một lần đọc lịch sử GitHub trước khi mở trình duyệt. Không ghi dữ liệu Supabase/Teaching/LMS.

## Các bước của Owner

1. **Duyệt đưa bản đã kiểm tra lên GitHub để mở đề nghị cập nhật.** AI tự đưa đúng nhánh, đối chiếu thay đổi và kiểm tra GitHub. Bước này chưa cho phép nhập vào bản chính hay chạy thử.
2. **Duyệt nhập đề nghị cập nhật sau khi AI xác nhận kiểm tra đạt.** AI tự nhập và kiểm tra lại bản chính. Lúc này lượt thử vẫn bị khóa.
3. **Duyệt đúng một lượt chạy trong hồ sơ thực thi mới.** AI kiểm tra lịch sử và bản chính, rồi mới đặt dấu cho phép đúng bản đã duyệt và chạy theo lựa chọn đã được Owner xác nhận. Không cần nhập thêm mật khẩu hoặc tắt máy để kiểm tra kỹ thuật này.

Không bấm **Run workflow** trước bước 3. Bản này chỉ nhận lần bấm đầu tiên của workflow mới; bấm trước khi được mở khóa có thể tiêu hao lần bấm đó dù chương trình chưa chạy. Không dùng **Re-run jobs**, không xóa lịch sử để chạy lại. Nếu bị chặn hoặc có lỗi, AI đối soát trước khi lập phương án tiếp theo; không tự mở lại giới hạn.

Khi được duyệt chạy, workflow là **runtime-synthetic-pilot**, chọn **main**. Dấu cho phép có tên `MINDX_RUNTIME_PILOT_APPROVAL_SHA`; AI đặt giá trị đúng mã bản chính đã duyệt, Owner không cần tự tìm mã hoặc mở Terminal. Không cần thêm Secrets nào cho lượt này. Mã GitHub tạm chỉ có quyền đọc và chỉ được dùng ở bước kiểm tra lịch sử; không chuyển cho tiến trình trình duyệt.

Sau chạy, mở lượt chạy và xem **Summary**. AI sẽ đọc biên nhận an toàn, kiểm tra cả ba tình huống và báo đạt/không đạt cùng phần chưa chứng minh. Màu xanh của lượt chạy không tự thay thế việc đối soát này.

## Giới hạn của kết quả

Nơi nhận kết quả công việc là bộ ghi nhận giả trong bộ nhớ. Lượt này kiểm tra điều phối chương trình, đồng hồ và trình duyệt; không chứng minh quyền API, hạn giữ thực tế hoặc lưu dữ liệu Supabase. Nó gọi hàm điều phối `run_job`, chưa thử đầu vào lệnh `mindx-runner run` với kết nối thật.

Tắt cưỡng bức khiến chương trình không tự thực hiện phần kết thúc. Việc dọn sau đó thuộc bộ giám sát; nếu chính bộ giám sát hoặc toàn máy thử bị tắt thì chưa có bằng chứng dọn. Tiến trình được theo dõi bằng mã tiến trình và thời điểm tạo, chỉ dọn các tiến trình đã xác định thuộc lượt thử. Đây là theo dõi có giới hạn, chưa phải hệ điều hành giữ kín toàn bộ cây tiến trình. Tiến trình Linux đã ngừng chạy nhưng còn chờ hệ điều hành thu hồi được ghi riêng, không coi là trình duyệt vẫn hoạt động.

Trình duyệt dùng hồ sơ mới và các cờ hạn chế kết nối ngoài. Chưa đo lưu lượng hoặc thiết lập tường lửa để chứng minh mọi kết nối của Chrome và tiến trình con đều bị chặn. Không thử phiên đăng nhập mã hóa hoặc dọn dữ liệu phiên thật.

Kiểm tra tại Windows dùng 35 giây làm việc/35 giây giới hạn rút ngắn, nên không thay cho bằng chứng Ubuntu hay đủ mốc 12 phút. Phase 2 chỉ được đóng sau khi các phần còn thiếu có bằng chứng riêng.

Tham chiếu kỹ thuật: [lịch sử lượt chạy GitHub](https://docs.github.com/en/rest/actions/workflow-runs), [phần mềm trên máy Ubuntu 24.04 của GitHub](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md). Workflow phát hiện Chrome sẵn có; thiếu thì dừng, không tự tải trình duyệt bổ sung.
