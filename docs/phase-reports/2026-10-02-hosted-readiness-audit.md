# Rà soát vận hành trên máy chủ — 02/10/2026

Phạm vi: cập nhật tài liệu và kiểm tra chỉ đọc theo yêu cầu Owner. Bản sản phẩm
được kiểm tra là `main` tại `f02c4ad7135aeff23479e4e66fe60285d1d1b4d4`.
Lead là người ghi duy nhất; subagent Luna 6 max rà soát độc lập phần vận hành.
Không chạy lại pilot, tạo/reset công việc, đổi cấu hình hay dữ liệu máy chủ.

## Bằng chứng đã quan sát

| Hạng mục | Kết quả | Giới hạn kết luận |
| --- | --- | --- |
| [PR #31](https://github.com/Banhtalon/mindx-review-bot/pull/31) | Đã nhập bản `505aad9` vào `main` tại `f02c4ad` | Chỉ phạm vi đã nghiệm thu trước đó |
| [Kiểm tra main](https://github.com/Banhtalon/mindx-review-bot/actions/runs/36980402733) | Thành công, đúng bản main | Không chạy Teaching/LMS thật trong bộ kiểm tra này |
| [Teaching thật](https://github.com/Banhtalon/mindx-review-bot/actions/runs/36968042010) | Thành công; các bước LMS bị bỏ qua | VT-CSI02, buổi 6, ngày 27/09/2026, 08–10 giờ |
| Trạng thái Supabase được đọc lại | Công việc/lượt chạy thành công; 3/3 lượt; đọc 1; không mã lỗi; đúng runner; thời gian đọc 1858 ms | Chưa chứng minh lưu danh mục/buổi học lâu dài |
| Phiên đăng nhập trong không gian pilot | Teaching: 1 phiên active; LMS: 0 | Active không bảo đảm đăng nhập được trong tương lai |
| Nơi lưu phiên đăng nhập | Bucket `browser-state` riêng tư | Không tải nội dung phiên hoặc thử công khai dữ liệu |
| Cấu trúc/quyền máy chủ | Năm bảng hạ tầng bật hạn chế đọc theo hàng; năm hàm nhận việc/báo nhịp/kết thúc/kích hoạt/thu hồi phiên hiện diện | Chỉ đọc cấu trúc/quyền; chưa đối chiếu toàn bộ mã hosted với main |
| Quyền gọi năm hàm | Khách và người dùng thường không được gọi; runner được gọi | Không gọi các hàm hoặc thử toàn bộ hành vi tài khoản |
| [Bootstrap](https://github.com/Banhtalon/mindx-review-bot/actions/runs/36967719095) | Thành công; tên khóa vận chuyển tạm không còn trong kho khóa GitHub của repo | Không đọc giá trị khóa, cookies hoặc dữ liệu đăng nhập |
| Chức năng `dispatch-job` trên Supabase | Hiện diện, 3 lần triển khai | Chưa gọi thử, chưa đối chiếu mã triển khai |
| Lịch tự động | Workflow không có lịch; biến `CRON_DISPATCH_ENABLED=false` không được source dùng | Chưa có bằng chứng chạy khi PC tắt |

Nguồn: GitHub CLI đọc metadata; kết quả SELECT trong SQL Editor chính thức của
đúng dự án Supabase; trang Edge Functions. SELECT chỉ trả số đếm, trạng thái,
tên hàm, quyền và thời gian. Không đọc dữ liệu học viên, HTML, nội dung phiên,
giá trị khóa hay log thô. Các hàm máy chủ không được gọi thực thi.

## Các điểm chặn còn thật

1. **Chưa có phiên LMS hoạt động** trong không gian pilot. Một lần thử LMS cần
   đăng nhập hợp lệ và lớp/buổi cụ thể do Owner đồng ý; không đoán theo Teaching.
2. **Đường điều phối còn thiếu cấu hình.** Kho khóa GitHub của repo không có tên
   `CRON_DISPATCH_SECRET` và `CRON_WORKSPACE_ID` mà workflow dùng; repo không có
   environment. Truy vấn tên khóa kế thừa trả HTTP 422, nên không kết luận về mọi
   kho khóa khác. `PHASE2_WORKSPACE_ID` không tự thay khóa workflow tham chiếu.
3. **Bật lịch hoặc thêm khóa chưa đủ.** `buildCronDispatchRequest` tạo `payload: {}`;
   phép thử dữ liệu giả xác nhận điều đó mà không gửi mạng. Gọi
   `_read_url('sync_teaching', {}, ())` xác nhận lỗi `SITE_ADAPTER_NOT_CONFIGURED`.
   Edge Function chuyển nguyên payload vào công việc, còn bộ chặn từ chối trường
   hoặc giá trị URL. Cần nguồn cấu hình mục tiêu đáng tin cậy phía máy chủ; không
   mở rộng payload tùy ý hoặc bỏ bộ chặn. `MINDX_SITE_ADAPTER` chỉ chọn hàm đọc.
4. **Lần đọc thành công chỉ lưu kết quả lượt chạy.** Adapter trả số lượng đã kiểm
   tra; CLI kết thúc lượt chạy bằng metadata. Hàm đối soát Teaching chưa được luồng
   runner gọi. Chưa chứng minh lưu danh mục/lịch Teaching lâu dài.
5. **Chưa kiểm chứng PC tắt, chạy lâu/tranh chấp/hết hạn hoặc vòng đời tái sử dụng/
   thu hồi phiên trên máy chủ.** Hạ tầng hiện diện và thử cục bộ không thay thế
   kiểm chứng hành vi hosted trong phạm vi được duyệt.

Vị trí: `scripts/cron_dispatch.mjs:134`,
`supabase/functions/_shared/dispatch.ts:80`,
`supabase/functions/_shared/edgeAdapters.ts:164`,
`apps/browser-runner/src/mindx_runner/live_adapter.py:53`,
`apps/browser-runner/src/mindx_runner/cli.py:473`,
`apps/browser-runner/src/mindx_runner/supabase_client.py:346`,
`.github/workflows/cron-dispatch.yml` và `.github/workflows/browser-runner.yml`.

## Bước tiếp theo cụ thể

Chuẩn bị **cấu hình mục tiêu đáng tin cậy cho đường điều phối thủ công** bằng
dữ liệu giả, giữ nguyên kiểm tra địa chỉ/lớp/buổi. Phần triển khai cần hợp đồng
v10 và đánh giá độc lập riêng; báo cáo này chưa chốt thiết kế hoặc cho phép
triển khai/tạo công việc thật. Giữ lịch tự động tắt.

Sau khi có bản sửa cụ thể đã kiểm tra, trình Owner một pilot có giới hạn: đúng
dự án, lớp/buổi/ngày được Owner chọn, tối đa một dispatch thủ công `sync_teaching`
qua đường điều phối khi PC tắt; chỉ đọc Teaching, không thử LMS đồng thời. Lead
kiểm tra cấu hình và xử lý kỹ thuật; Owner quyết định phạm vi, đăng nhập/OTP khi
cần và nghiệm thu hành vi. Cấu hình khóa/triển khai thật cần quyền đúng đích.
Đây là đề xuất, chưa phải quyền chạy mới; không dùng lại job đã đủ 3/3 lượt.

Phase 2 hosted/off-PC vẫn chưa đóng; Phase 3 mới xác nhận một mục tiêu; Phase 4
và các phần lưu trữ/tạo nhận xét thật vẫn chưa đạt. Owner không phải xem mã/SQL.

## Hồ sơ và khả năng khôi phục

Hợp đồng `TASK-STATE-HOSTED-AUDIT`, revision 1; metadata và kiểm tra cuối ở
`.workflow-local/state-hosted-audit/` của bản làm việc `state-hosted-audit`.
Bàn giao và các packet đóng băng của pilot cũ được giữ nguyên. Root Owner status
có bản sao trước cập nhật; sản phẩm main không đổi. Báo cáo/index Phase 2 cũ được
giữ làm lịch sử; bản này không tự đổi các yêu cầu chưa kiểm chứng thành PASS.
