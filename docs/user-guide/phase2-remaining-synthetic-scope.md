# Phạm vi chuẩn bị thử giả còn thiếu của Phase 2

Bản chuẩn bị tại máy ngày 07/10/2026. **Chưa cho phép chạy trên máy chủ.**
Chốt mã của #41 và các bài kiểm tra tại máy là phần có thể chạy ngay; kế hoạch
bên dưới dành cho lượt hosted (chạy trên máy chủ) sau khi có công cụ và phạm vi
thực thi đúng bản nguồn được duyệt. Không dùng lại quyền của lượt Storage cũ.

## Chốt mã của #41

Công cụ phiên chính kiểm đúng mã commit, cây mã đã lưu và bảy tệp liên quan,
bao gồm tệp chứa chốt dùng lại từ công cụ tiếp tục. Trước mỗi yêu cầu gửi,
nó kiểm lại những điều kiện này và dấu của bản duyệt đã đọc lúc khởi chạy.
Thay một bản duyệt mới dù tự nó hợp lệ cũng không mở các bước còn lại.

Nếu kiểm tra thất bại, công cụ dừng gửi. Một lượt đã được giữ chỗ trong biên nhận
vẫn tính vào giới hạn, kể cả khi bị chặn trước mạng; không đặt lại sổ hoặc tự thử
lại. Các bản duyệt cũ có sáu tệp cần được giữ làm lịch sử, không sửa để chạy lại.
Mã workflow cũ1855c37 vẫn giữ nguyên; sửa chốt này không kích hoạt công việc cũ.

## Kiểm tra giả có sẵn tại máy

AI chạy các lệnh dưới trong bản làm việc đã chọn; Owner không cần chạy lệnh.

- Ở thư mục dự án: node --test test/api-chain-session.test.mjs test/api-chain-continuation.test.mjs scripts/lib/app_session.test.mjs
- Ở apps/browser-runner: C:\Users\QQ\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/unit/test_browser_state.py tests/unit/test_supabase_client.py tests/unit/test_storage_synthetic_pilot.py

Các bài có sẵn dùng kết nối giả hoặc localhost: sai/thiếu/khác phiên bản khóa,
tệp bị sửa, đổi phiên, reset, phản hồi không rõ, giữ tệp khi chưa rõ kích hoạt
và chặn xóa khi xuất hiện tệp ngoài danh sách. Không gọi Supabase/Teaching/LMS.

P2-D1 đã có bằng chứng hosted riêng tại a6bd0ed / GitHub37437960659 ngày06/10:
hai tệp tải lại và giải mã bằng hai khóa giả khác nhau, đổi key_version1/2,
reset thành công và dọn đúng hai tệp. Không lặp toàn bộ lượt thành công này.
Bằng chứng trên chưa phải thử các nhánh lỗi dưới đây.

## Một phạm vi hosted đề xuất, chỉ phần còn thiếu

Đích duy nhất: project gnvzjvgfsxfjgldatbwt.
Workspace đề xuất: 8dfeeaf2-99f0-5475-b8fc-023960050de2,
tên phase2-state-failure-synthetic-20261007.
Không thành viên, việc automation hoặc lượt worker sản phẩm mới.

Tối đa hai phiên/tệp thuộc workspace mới, site teaching là nhãn dữ liệu giả:

- V1: 2ff71e45-d7aa-5577-9d9a-c77c66375a21.
- V2: e7afa6d9-96ed-5cb5-884e-e4bd0f398746.
- Đường dẫn metadata: browser-state/<workspace>/teaching/<version>.json.
  Bucket là browser-state; đường dẫn trong bucket bỏ phần browser-state/ đầu.
- Mỗi tệp tối đa1024byte. Tái dùng nội dung/khóa công khai của fixture giả hiện có;
  không dùng cookie, khóa mã hóa, mật khẩu hoặc phiên thật của Teaching/LMS.

| Phần thiếu | Phép thử tối thiểu | Bằng chứng phải có |
| --- | --- | --- |
| Thiếu/sai/khác phiên bản khóa | Thiếu khóa dừng trước mạng; tải phiên giả rồi dùng khóa sai/khác phiên bản | Thiếu khóa0 yêu cầu; còn lại báo lỗi an toàn, không mở trình duyệt, không gửi lại |
| Khóa cũ sau đổi phiên | Chọn phiên đang active từ máy chủ rồi dùng khóa V1 để mở V2 | Bị từ chối; không biến bài giải mã tệp cố định thành chứng minh loader active |
| Tệp lưu bị sửa | Sửa ciphertext của đúng V2 trên Storage, tải lại rồi kiểm tra | Bị từ chối; danh tính và đường dẫn vẫn đúng allowlist |
| Thiếu quyền reset | Một yêu cầu anon và một authenticated không thuộc workspace giả | Bị chặn bằng mã quyền rõ; trạng thái/tệp trước và sau không đổi |
| Kích hoạt trả kết quả không rõ | Sau thao tác kích hoạt V2, giả lập mất phản hồi tại lớp nhận | Dừng, giữ tệp và sổ; đối soát riêng trước khi tiếp tục, không gửi RPC lần hai |
| Dọn sau lỗi | Sau khi đối soát, thu hồi phiên giả rồi xóa đúng V1/V2 và dọn workspace | Dữ liệu giả còn0; dấu dữ liệu bảo vệ không đổi; không có xóa theo thư mục rộng |

Mỗi trường hợp ghi rõ môi trường. Việc giả lập mất phản hồi xảy ra ở lớp nhận,
không chứng minh lỗi mạng Supabase tự nhiên. Dừng công cụ lúc kết quả không rõ
không được coi là dọn thành công; dọn chỉ mở sau đối soát trạng thái chính xác.

## Ngân sách đề xuất và chốt thực thi

Đây là trần đề xuất để khóa cùng entrypoint sau; chưa phải hạn mức được cấp.
Công cụ cần ghi giữ chỗ trước mỗi gửi, lưu biên nhận riêng một lần, không retry.

- Supabase của bộ thử: tối đa40 lượt đọc metadata, 8 tải xuống, 3 tải lên/ghi đè
  (V1, V2, sửa đúng V2), 5 RPC (kích hoạt2, phủ định reset2, reset service1),
  1 xóa Storage với danh sách đúng hai đường dẫn: tổng tối đa57.
- Auth cho tài khoản ứng dụng nếu cần: tối đa1 đăng nhập và1 xác nhận getUser;
  Owner nhập trên trang riêng. Đây là quyền mới đề xuất, không dùng phiên đã đóng.
- Quản lý SQL: thêm tối đa6 lần chỉ đọc và2 lần ghi có điều kiện (tạo đúng
  workspace; dọn đúng hai phiên/workspace đã đối soát). Tổng đọc tích lũy cũ19
  lên tối đa25 nếu Owner duyệt rõ phần thêm6; không gọi đó là đặt lại19/19.
- Chưa chọn nơi chạy. Nếu dùng GitHub phải khóa thêm một lượt chạy và ngân sách
  đọc quản lý cụ thể; không tự thêm workflow/marker hay dùng lại phép thử cũ.
- App23 / Edge dương tính2 / GitHub việc cũ1 / worker0 / max_attempts1 và mọi
  bộ đếm sửa cũ giữ nguyên. Lượt giả mới không tự cấp thêm lần nhận việc cũ.

Giới hạn40 lượt đọc đã được đối chiếu với công cụ ba bước tại máy bên dưới. Các
ngân sách không cộng để tăng quyền của thao tác khác. Bị lỗi/không rõ cũng
tính đã dùng; không dò tài nguyên khác hoặc lặp để tìm kết quả xanh.

**Điều kiện trước khi xin duyệt chạy:** entrypoint nhỏ dùng cipher/client/sổ
có sẵn, chốt chính xác từng method/path/body/role, kiểm tra giả về giới hạn và
dọn dữ liệu, điểm khôi phục, đọc trước cấu hình không bí mật và trạng thái đích
trong ngân sách được cấp, review độc lập đúng bản nguồn, rồi Owner duyệt đúng
hậu quả ghi máy chủ. Chưa có quyền chạy, cấu hình kết nối hoặc bản duyệt máy chủ.

## Công cụ ba bước đã có tại máy

Tệp `scripts/storage_failure_pilot.py` tái dùng cipher/client, fixture công khai,
kiểm bản mã và cách lưu biên nhận hiện có; không thêm thư viện hoặc workflow.
Gọi trực tiếp bằng Python chỉ in trạng thái chuẩn bị, không kết nối mạng.
Hàm `execute` cần kết nối được cung cấp riêng và bản duyệt đúng nguồn;
không tự lấy khóa từ môi trường hoặc tự dùng quyền của công cụ cũ.

- `exercise`: kiểm workspace trống, bucket riêng tư; tạo đúng hai tệp/phiên giả,
  giả lập mất phản hồi kích hoạt V2 tại lớp nhận rồi dừng ở `WAITING_RECONCILE`.
- `reconcile`: đối soát đúng V1/V2, dùng loader chọn active V2 rồi thử khóa cũ,
  sai khóa/phiên bản; thiếu khóa dừng trước mạng. Kiểm hai quyền reset qua HTTP,
  so trạng thái và byte tệp trước/sau; ghi đè đúng V2 bằng ciphertext bị sửa,
  tải bằng loader rồi xác nhận không giải mã được. Dừng ở `READY_CLEANUP`.
- `cleanup`: bước gọi riêng, kiểm lại workspace/phiên/tệp và byte chính xác;
  reset service, xác nhận cả hai phiên revoked, xóa đúng hai đường dẫn và
  xác nhận Storage còn0. Trạng thái `STORAGE_CLEAN_SQL_PENDING` vẫn giữ phần
  dọn bản ghi/workspace và đối chiếu dữ liệu bảo vệ bằng SQL ở ngoài công cụ.

Đường đi đủ ba bước dùng40 lượt đọc metadata,7 tải xuống,3 tải lên/ghi đè,
5 RPC,1 xóa:56 yêu cầu giả; trần vẫn57 vì tải xuống cho phép tối đa8.
Mỗi yêu cầu chốt method/path/body/role, lưu giữ chỗ trước gửi, kiểm lại HEAD,
nguồn và dấu bản duyệt. Lỗi bất kỳ giữ sổ/tệp và dừng; không tự chạy lại.
Một bước đã bắt đầu không chạy lần hai. Thay bản duyệt giữa hai yêu cầu hoặc
hai bước không mở lượt còn lại. Không có dọn tự động khi phản hồi không rõ.

Kiểm tại máy: từ `apps/browser-runner`, AI chạy
`C:\Users\QQ\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/unit/test_storage_failure_pilot.py`.
Các kết nối trong bài kiểm tra hoàn toàn giả. Chưa có quan sát lỗi trên máy chủ.
Chưa tạo workspace, chưa cấp bản duyệt hay kích hoạt lượt mới; chưa chọn nơi
chạy/khóa cơ chế lấy tài khoản chính thức và kết nối không retry/redirect.
Phần quản lý SQL/so dữ liệu bảo vệ và nghiệm thu thật vẫn cần chuẩn bị riêng.

Không cần sửa cấu trúc dữ liệu, triển khai lại Edge, đổi khóa thật, bật lịch,
đọc học viên, mở trình duyệt thật hoặc nhập #41 để thực hiện các bài tại máy.
Phase2/Spike0 và các mục hosted còn thiếu giữ mở.

## Khôi phục

Bản sửa chốt được lưu bằng commit riêng. Hoàn tác riêng commit này nếu cần;
không đặt lại dự án, không ghi đè nhánh/hồ sơ cũ hoặc xóa dữ liệu máy chủ.
Lượt hosted tương lai phải có allowlist/dấu trước-sau và quy tắc dọn riêng,
không có quyền khôi phục dữ liệu thật từ tài liệu này.

