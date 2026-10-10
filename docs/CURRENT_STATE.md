# Tiến độ hiện hành — MindX Review Bot

Đối chiếu hồ sơ ngày **10/10/2026** (Asia/Saigon). **Phase 2 chưa hoàn tất.**
Bản chính hiện hành: `4f7781d358fdf7dbd2aea6590797f1fe29d24f8c` (#51).
Bản sản phẩm làm gốc: `7cfaab350812cd1f01d9924a7c3364088f77d433` (#43).

**Điểm chặn cũ đã xử lý:** hủy đúng một tác vụ thử; hậu kiểm máy chủ đạt
0 tác vụ còn gây chặn và 0 lượt chưa kết thúc. Dữ liệu ngoài phạm vi giữ nguyên;
đánh giá độc lập đạt. R13 mới đã gửi đúng một lượt; đăng nhập và kiểm quyền
ứng dụng đạt trong phạm vi thử. GitHub dừng ở kiểm lịch sử trước khi chương trình
nhận việc, nên chưa xác nhận toàn chuỗi. Quyền chạy tạm đã thu hồi; tác vụ thử
đã hủy và dọn đúng mục tiêu, hậu kiểm đạt 0 dữ liệu thử còn lại; dữ liệu ngoài
phạm vi và cấu trúc/quyền trên máy chủ giữ nguyên. R14 đã mở đúng một lượt nhưng
dừng trước đăng nhập/gửi tác vụ; không có chương trình chạy 650 giây. Không gian
thử trống đã dọn và hậu kiểm đạt; lượt R14 đã đóng, không tự chạy lại.
R15 mở được công cụ đăng nhập nhưng phiên đã đóng trước biên nhận sẵn sàng;
chưa gửi tác vụ 650 giây. Đã dọn phần thử trống, hậu kiểm đạt và thu hồi quyền tạm.
R16 qua đăng nhập/kiểm quyền/gửi/nhận việc một lần nhưng dừng ở phản hồi gia hạn;
chưa đạt 650 giây. Bản sửa đã nhập #50; tác vụ treo đã kết thúc thất bại rồi dọn
đúng phạm vi riêng. Hậu kiểm đạt 0 dữ liệu thử; không mở lượt thử mới.
R17 đã xác nhận toàn chuỗi dữ liệu giả chạy đủ 650 giây và dọn an toàn;
đánh giá độc lập đạt. Chưa chứng minh PC-off hoặc toàn Phase 2.

Đây là bảng tiến độ hiện hành duy nhất trong bản tinh gọn. Hướng dẫn AI ở
[AGENTS.md](../AGENTS.md). Owner đã duyệt nhập bản tinh gọn ngày 09/10/2026.
Các bản cũ trong bản làm việc khác là bằng chứng theo thời điểm.

## Việc đang làm và việc tiếp theo

1. Tinh gọn đã thực hiện: gỡ 59 tệp điều phối cũ, kiểm sản phẩm tại máy và
   đánh giá độc lập đạt; Owner đã duyệt áp dụng ngày 09/10. R13 đã gửi một lượt.
   Kiểm tra tại máy: 141 bài web, 16 bài phiên và 735 bài Python đạt.
   Bản sửa tiếp nối đã thêm kiểm tra 16 bài phiên vào GitHub sau bước chuẩn bị
   Python; dùng đường dẫn phù hợp Windows/Linux. Quét toàn thư mục chính bằng
   bộ kiểm đã sửa đạt: chỉ nhận diện đúng giá trị giả trong một tệp lịch sử
   có dấu kiểm nội dung cố định, không bỏ quét thư mục hay sửa hồ sơ cũ.
   Nguồn R13 đã đối chiếu đúng bản `b5a709c99a01473363666732a71fccf9a7ebe2a4`.
2. R13: đăng nhập, kiểm quyền và chuyển đúng tác vụ từ ứng dụng sang GitHub đã đạt.
   Lượt [37907247747](https://github.com/Banhtalon/mindx-review-bot/actions/runs/37907247747)
   dừng trước nhận việc. Nguyên nhân có khả năng cao là giới hạn đọc lịch sử:
   phản hồi hiện dài 38.304 byte, vượt mức 32.768; dữ liệu giả tái hiện đúng lỗi
   của bản đã chạy. Ngoại lệ chi tiết của lượt GitHub không được lưu. Bản sửa đã
   nhập [#46](https://github.com/Banhtalon/mindx-review-bot/pull/46), nguồn `13f0bec`;
   [kiểm GitHub 37914378511](https://github.com/Banhtalon/mindx-review-bot/actions/runs/37914378511) đạt.
   Lượt mới đọc tối đa 65.536 byte và báo
   đúng mã lỗi; giữ giới hạn chương trình chạy và không thêm thử lại. 114 bài
   kiểm liên quan, kiểm mã, chống lộ bí mật và chống ghi Teaching/LMS đạt;
   Luna Max đánh giá độc lập đạt phạm vi sửa; nguồn đã áp dụng giữ đúng nội dung kiểm.
   Dọn và hậu kiểm đã đạt; bản sao khôi phục kiểm đủ năm tệp, thử phục hồi bằng
   dữ liệu giả đạt. Luna Max chốt dọn đúng một lần; hồ sơ cũ giữ nguyên.
   R14: Owner duyệt một lượt 650 giây, tối đa 79 yêu cầu máy chủ (20 SQL)
   và 16 yêu cầu GitHub. Nguồn `2aa12ad` (#47), hồ sơ chuẩn bị được đánh giá
   độc lập; 59 tệp giữ đúng dấu kiểm. Lượt đã dừng ở công cụ mở đăng nhập,
   trước gửi tác vụ. Công cụ thiếu chỉ định thư mục làm việc từng có ở lượt
   R13 thành công; dữ liệu giả tái hiện lỗi và bản sửa một dòng đạt 17 bài kiểm.
   Đây là nguyên nhân có khả năng cao; lỗi chi tiết của lượt thật không được lưu.
   Bản sửa công cụ mới được chuẩn bị tại máy, chưa chạy lại với tài khoản thật.
   Không gian thử trống đã sao lưu và thử phục hồi tại máy trước khi dọn;
   hậu kiểm máy chủ xác nhận mục tiêu bằng 0, dữ liệu khác và cấu trúc/quyền
   giữ nguyên. Quyền tạm đã thu hồi, giữ nguyên hồ sơ và số lượt đã dùng.
   [Kết quả R14](<C:/Users/QQ/.codex/worktrees/r14-confirmation/MINDX-REVIEW-BOT/.workflow-local/r14-confirmation-20261009/execution/OUTCOME.json>).
   R15 đã nhập [#48](https://github.com/Banhtalon/mindx-review-bot/pull/48),
   nguồn chính `176aa34`: đã áp dụng sửa chọn thư mục
   trong công cụ mới, danh tính thử mới và chỉ cho tác vụ R15 chạy; chặn R14 cũ.
   Kiểm mã giả 177 bài, công cụ riêng 17 bài, dữ liệu/dọn 49 bài và khôi phục
   16 bài đạt tại máy. Owner đã duyệt một lượt 650 giây, tối đa 79 yêu cầu máy chủ
   (20 SQL) và 16 yêu cầu GitHub, không thử lại; tổng bảo thủ 296/SQL 91.
   [Hồ sơ R15](<C:/Users/QQ/.codex/worktrees/r15-confirmation/MINDX-REVIEW-BOT/.workflow-local/r15-confirmation-20261009/NOTE.md>).
   Kiểm GitHub lần đầu dừng vì một dòng bài kiểm tra quá dài; sửa xuống dòng,
   kiểm lại nguồn `9b005ca` đạt, nội dung bản chính giống hệt bản đã kiểm.
   [Kiểm GitHub bản chính 37928448956](https://github.com/Banhtalon/mindx-review-bot/actions/runs/37928448956)
   đạt. Luna Max chốt 74 tệp khớp bản chính và công cụ chống gọi lặp đạt;
   quyền R15 đã ghi đúng phạm vi Owner duyệt. Công cụ mở thành công lúc 19:21;
   Owner báo trang đóng. Kiểm lúc 20:03 xác nhận công cụ đã thoát bình thường,
   không còn cổng mở hoặc biên nhận phiên sẵn sàng. Công cụ tự hết hạn sau 15 phút;
   đây là nguyên nhân có khả năng cao, chưa có ghi nhận chính xác lý do đóng.
   Chưa xác nhận đăng nhập, chưa gửi tác vụ và chưa chạy 650 giây.
   Không gian thử trống đã sao lưu, thử phục hồi tại máy và được đánh giá độc lập
   trước khi dọn. Hậu kiểm máy chủ: mục tiêu bằng 0; dữ liệu ngoài phạm vi và
   cấu trúc/quyền giữ nguyên. Đã thu hồi quyền tạm, giữ nguyên lượt đã dùng;
   không tự mở lại. Luna Max đánh giá độc lập hậu kiểm đạt, 74 tệp nguồn giữ nguyên;
   công cụ bị chặn mở lại trước khi truy cập tài khoản hoặc mạng. Chống lộ bí mật,
   chống ghi Teaching/LMS và kiểm thay đổi tệp đạt. Toàn chuỗi 650 giây vẫn chưa đạt.
   [Kết quả R15](<C:/Users/QQ/.codex/worktrees/r15-confirmation/MINDX-REVIEW-BOT/.workflow-local/r15-confirmation-20261009/execution/OUTCOME.json>).
   R16: Owner duyệt lượt mới cùng giới hạn 650 giây, 79 yêu cầu máy chủ (20 SQL),
   16 GitHub, một lần mở và một lần gửi, không tự thử lại. Đã nhập
   [#49](https://github.com/Banhtalon/mindx-review-bot/pull/49), nguồn chính `6c7ff91`;
   kiểm GitHub của bản đề xuất và
   [bản chính 37937484461](https://github.com/Banhtalon/mindx-review-bot/actions/runs/37937484461) đạt.
   222 bài Python, 16 bài phiên, 18 bài công cụ, 49 kiểm dữ liệu, 16 kiểm khôi phục,
   5 kiểm chống gọi lặp và 10 kiểm biên nhận duyệt đạt tại máy. Luna Max chốt bản
   đề xuất và bản chính đạt sau khi bổ sung ràng buộc đúng lời duyệt/phạm vi.
   78 tệp nguồn/hồ sơ được đối chiếu; bản sao trước nhập kiểm đủ 80 mục;
   hồ sơ R15 giữ nguyên 74 tệp. Owner đã sẵn sàng và đăng nhập; kiểm quyền,
   một lần gửi từ ứng dụng và một lần nhận việc đúng tác vụ R16 đạt.
   [Lượt R16 37939315863](https://github.com/Banhtalon/mindx-review-bot/actions/runs/37939315863)
   **thất bại**, chương trình dừng sau khoảng 45 giây, không đủ 650 giây: phản hồi
   gia hạn được máy chủ nhận nhưng bộ kiểm tra từ chối. Danh mục máy chủ xác nhận
   hàm chỉ trả 3 cột; bộ kiểm R16 đòi thêm workspace_id. Tái hiện tại máy và 12 kiểm
   cho bản sửa đề xuất đạt; phản hồi thô của lượt thật không được lưu.
   Chương trình GitHub và công cụ tại máy đã dừng, không còn tiến trình dư,
   hồ sơ trình duyệt thử đã gỡ, marker đã vắng mặt, quyền R16 đã thu hồi.
   Sau lượt thất bại, job/run thử từng còn trạng thái đang chạy dù lease hết hạn.
   Owner đã duyệt phạm vi phục hồi riêng: kết thúc thất bại đúng lỗi R16, giữ
   số lượt/thời lượng đã ghi; không ép thành công hoặc khôi phục tác vụ đang chạy.
   Sau bản sao terminal mới và đánh giá độc lập đạt, đã dọn đúng dữ liệu thử R16.
   Hậu kiểm đạt 0 mục tiêu; dữ liệu khác và cấu trúc/quyền giữ nguyên.
   Bản sao 11 mục cũ giữ nguyên, chỉ làm bằng chứng lịch sử.
   [Kết quả R16](<C:/Users/QQ/.codex/worktrees/r16-confirmation/MINDX-REVIEW-BOT/.workflow-local/r16-confirmation-20261009/execution/OUTCOME.json>).
   Giữ sai lệch kiểm soát: 11 yêu cầu nội bộ Edge được ghi dự trù sau 3 pha âm tính;
   ít nhất 4 yêu cầu nội bộ xảy ra trước khoản ghi này, không thấy vượt tổng trần.
   Bản sửa bộ đọc gia hạn, nguồn `b20da7d`, đã nhập
   [#50](https://github.com/Banhtalon/mindx-review-bot/pull/50);
   bản chính `44527d8` giữ đúng toàn bộ nội dung đã kiểm. Kiểm GitHub trước nhập và
   [bản chính 37953191021](https://github.com/Banhtalon/mindx-review-bot/actions/runs/37953191021) đạt.
   275 bài kiểm Python và 19 kiểm phục hồi bằng dữ liệu giả đạt; chống lộ bí mật
   và chống ghi Teaching/LMS đạt. Không sửa thêm mã sau các kiểm tra này.
   Đợt phục hồi riêng đã hoàn tất đúng 8/8 yêu cầu máy chủ: 2 ghi, 6 đọc,
   dự trù toàn bộ trước gửi; không thử lại, không Auth/gửi việc hay mở lượt mới.
   Ảnh gốc trước ghi được sao lưu; ảnh terminal mới sau kết thúc đã có bản sao
   4 mục, kiểm từng byte và thử khôi phục terminal bằng dữ liệu giả đạt;
   cơ sở dữ liệu giả đã dừng. Bản sao chuẩn bị v3 giữ đúng 25 mục.
   Luna Max đánh giá độc lập trước xóa và hậu kiểm đạt đúng phạm vi hồ sơ.
   Hậu kiểm máy chủ: mục tiêu/name/key/probe bằng 0; dấu kiểm dữ liệu ngoài phạm vi,
   cấu trúc và quyền giữ nguyên. 15 mục biên nhận hậu kiểm đã sao lưu và đối chiếu.
   Claude CLI đánh giá trước xóa không đọc được tệp do giới hạn công cụ;
   giữ kết quả INCOMPLETE, không tính là đạt. Lịch sử lỗi/giới hạn cũ giữ nguyên.
   [Kết quả phục hồi](<C:/Users/QQ/.codex/worktrees/heartbeat-repair/MINDX-REVIEW-BOT/.workflow-local/r16-heartbeat-repair-20261009/execution/OUTCOME.json>).
   Toàn chuỗi 650 giây và PC-off vẫn chưa đạt; đợt này chỉ sửa và phục hồi.
   [Hồ sơ bản sửa và phục hồi](<C:/Users/QQ/.codex/worktrees/heartbeat-repair/MINDX-REVIEW-BOT/.workflow-local/r16-heartbeat-repair-20261009/NOTE.md>).
3. R17 ngày 10/10 đã hoàn tất đúng một lượt trên bản chính #51, nguồn 4f7781d.
   [Lượt GitHub 37965370858](https://github.com/Banhtalon/mindx-review-bot/actions/runs/37965370858)
   đạt: ứng dụng → máy chủ → GitHub → chương trình chạy → lưu kết quả → dọn.
   Dữ liệu giả: 650,076 giây thực đo; máy chủ lưu 650.078 ms, attempt 1,
   21 lần gia hạn, 25 yêu cầu chương trình; 19 yêu cầu ứng dụng đạt.
   Bản sao terminal mới kiểm đủ 4 mục, thử khôi phục tại máy đạt; đánh giá
   độc lập trước xóa và hậu kiểm đạt. Mục tiêu sau dọn bằng 0; dữ liệu khác,
   cấu trúc/quyền máy chủ giữ nguyên; không có tiến trình/phiên thử còn lại.
   Quyền chạy tạm đã thu hồi; lượt R17 đóng, không thử lại hoặc dùng phần dư.
   Lượt này: ít nhất 64 yêu cầu máy chủ xác nhận / 76 bảo thủ (trần 79),
   17 SQL (trần 20), 14 GitHub gồm worker (trần 16), 1 trang kết quả,
   1 công cụ đăng nhập và 1 gửi dương tính. Toàn bộ hạn mức dự trù trước gửi.
   Cộng dồn: ít nhất 275 xác nhận / 407 bảo thủ, SQL 121; trần duyệt 410/124.
   Giữ nguyên 11 yêu cầu Edge nội bộ và 26 chương trình đã dự trù; số dự trù
   không được gọi là số gửi đã xác nhận. Đưa/nhập/kiểm mã dùng 11/12 thao tác
   riêng (9 yêu cầu, 2 đồng bộ mã); phần dư đóng, không chuyển sang lượt khác.
   [Kết quả R17](<C:/Users/QQ/.codex/worktrees/r17-confirmation/MINDX-REVIEW-BOT/.workflow-local/r17-confirmation-20261009/execution/OUTCOME.json>).
   Chỉ đạt toàn chuỗi dữ liệu giả; chưa chứng minh PC-off hoặc toàn Phase 2.
   Hai nhánh lỗi tại máy ngày10/10 đã chuẩn bị và chạy sáu biến thể; phát hiện
   rồi sửa lỗi báo thành công khi phản hồi lưu thiếu/sai trạng thái. 167 bài
   liên quan, kiểm an toàn và đánh giá độc lập Luna Max đạt. Owner đã duyệt
   đưa lên GitHub và nhập khi kiểm tra/đánh giá lại đạt. Chưa mở R18 hoặc lặp lượt650giây.
   PC-off đã có minh chứng GI34 riêng; không tự yêu cầu mọi lượt R chạy khi tắt máy.

Giữ bộ đếm gốc trước R13: sửa **13/13**, yêu cầu máy chủ **96 xác nhận / 100 bảo thủ**,
SQL **41**; bốn lượt Auth lịch sử chưa xác minh. Quyền mở rộng của Owner được
ghi nối tiếp, không đặt lại lịch sử. Sau R13: máy chủ **ít nhất 141 xác nhận /
185 bảo thủ**, SQL **61**, GitHub **23 lượt dự trù**, gửi tác vụ dương tính **1**.
Giữ cả 26 yêu cầu chương trình chạy và 11 yêu cầu bên trong đã dự trù dù chương
trình bị bỏ qua; không coi số dự trù là số đã xác nhận gửi. Một bản sửa nguồn
R13 tại máy được ghi riêng; giới hạn của lượt mới không thay lịch sử 13/13.
R14: **10 yêu cầu máy chủ xác nhận / 32 bảo thủ**, gồm **10 SQL**;
**3 yêu cầu GitHub**, không gửi tác vụ, không có chương trình nhận việc.
Số 32 giữ cả phần mở đăng nhập/ứng dụng đã dự trù; không coi là 32 yêu cầu
đã gửi. Kết quả yêu cầu lấy khóa không được ghi nhận; giữ dự trù đã tiêu thụ.
Cộng đến sau R14: **ít nhất 151 xác nhận / 217 bảo thủ**, **SQL 71**;
GitHub R13 **23 dự trù** và R14 **3 xác nhận** ghi riêng, lịch sử sửa **13/13**.
R15: **ít nhất 11 yêu cầu máy chủ xác nhận / 32 bảo thủ**, gồm **10 SQL**
và một yêu cầu lấy khóa đã hoàn tất; **3 GitHub**, **1 lần mở công cụ**, **0 lần gửi**.
Phần 22 yêu cầu mở đăng nhập/ứng dụng giữ nguyên dự trù; số yêu cầu đăng nhập
thực tế chưa xác nhận, không coi tất cả dự trù là đã gửi.
Cộng đến sau R15: **ít nhất 162 xác nhận / 249 bảo thủ**, **SQL 81**;
GitHub R13 **23 dự trù**, R14 **3 xác nhận**, R15 **3 xác nhận** ghi riêng.
R16: **ít nhất 41 yêu cầu máy chủ xác nhận / 74 bảo thủ**, gồm **15 SQL**;
**15 GitHub**, **1 trang summary**, **1 host / 1 gửi dương tính**. Worker gửi 4 yêu cầu,
gồm 1 nhận/1 gia hạn/0 kết thúc; giữ nguyên 26 worker + 11 nội bộ đã dự trù, không hoàn lại.
Tổng sau R16: **ít nhất 203 xác nhận / 323 bảo thủ / SQL 96**; trần được duyệt 328/SQL 101.
R16 đã đóng; đợt phục hồi riêng đã dùng **8 xác nhận / 8 bảo thủ / SQL 8**,
gồm **2 ghi, 6 đọc**, dọn đúng dữ liệu thử. Cộng sau phục hồi:
**ít nhất 211 xác nhận / 331 bảo thủ / SQL 104**. Không tái dùng quyền đã đóng;
lượt xác nhận mới cần phạm vi riêng.
Không đặt lại giới hạn hoặc dùng quyền của lượt đã đóng cho lượt mới.
Owner chỉ quyết định phạm vi, thao tác tài khoản khi cần và dùng thử kết quả.

## Checklist sản phẩm

24 mục: **15 đạt theo phạm vi, 9 còn mở**. Đây không phải phần trăm hoàn thành.
Tại máy/dữ liệu giả không thay bằng chứng máy chủ; mỗi dòng giữ đúng phạm vi đã đạt.

| Mục | Đã xác nhận và bằng chứng | Còn thiếu / điều kiện hoàn tất |
| --- | --- | --- |
| [x] P1-LOCAL — nền tảng tại máy | Nền tảng và kiểm tra dữ liệu giả đã đạt. [Chỉ mục Phase 1](evidence/phase-1/index.json) | Còn kiểm chứng tài khoản/quyền trên máy chủ ở dòng kế tiếp. |
| [ ] Nền tảng — Spike 0 / Phase 1 | Có nhiều bằng chứng tại máy; nền tảng thực tế chưa nghiệm thu đủ. [Chỉ mục Spike 0](evidence/index.json) | Đo thời gian/chi phí Teaching và LMS, kiểm quyền và tài khoản trên máy chủ. |
| [x] P2-LOCAL — chương trình nhận/chạy việc và công cụ thử giả | Chương trình nhận/chạy việc và kiểm thử giả đã có. [Chỉ mục Phase 2](evidence/phase-2/index.json) | Toàn chuỗi thành công bằng dữ liệu giả đã đạt ở E3; còn F/G và nghiệm thu tổng thể. |
| [ ] P2-A — cấu trúc, quyền và mã đã triển khai | Q01/Q16 R17 ghi cấu trúc/quyền không đổi và đường giao việc đúng main. Năm tệp Edge hiện hành khớp nguồn đã đối chiếu 07/10; đây là bằng chứng triển khai cũ, không phải đọc mới. [Đối chiếu sau R17](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/phase2-close-audit-20261010/NOTE.md>) | Còn chốt phạm vi quyền tối thiểu của tích hợp và cấu hình vận hành cần nghiệm thu; không bật lịch tự động hoặc triển khai lại chỉ để đóng mục. |
| [x] P2-B — nhận việc, tranh việc và hết hạn, phạm vi SQL trên máy chủ | Máy chủ đã chặn nhận trùng/sai người/vượt lượt; dữ liệu thử đã dọn. [Lượt 04/10](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/phase2-hosted-rpc-pilot/OWNER_RESULT.md>) | Đã hoàn tất phạm vi SQL; không suy ra quyền ứng dụng. |
| [x] P2-C1 — gia hạn, nhận lại và giới hạn thử lại, phạm vi SQL | Gia hạn, hết hạn, nhận lại và giới hạn thử lại đã kiểm trên máy chủ. [Lượt 06/10](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/phase2-heartbeat-recovery-execution/OWNER_RESULT.md>) | Đã hoàn tất phạm vi SQL; không chạy lại. |
| [x] P2-C2 — chạy dài, quá thời gian và dọn tiến trình, phạm vi chương trình thử | Chương trình thử chạy 650 giây, 21 lần báo hoạt động, dừng quá hạn và dọn tiến trình. [Kết quả 06/10](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/phase2-runtime-cloud-execution/OWNER_RESULT.md>) | Đã đạt phạm vi chương trình giả; còn chứng minh cả chuỗi lưu kết quả. |
| [x] P2-D1 — lưu, tải lại, đổi và vô hiệu hóa hai phiên giả | Hai phiên giả đã lưu/tải lại, đổi khóa, vô hiệu hóa và dọn. [Kết quả Storage 06/10](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/phase2-storage-direct-execution/OWNER_RESULT.md>) | Đã đạt đúng lượt thành công; phạm vi lỗi riêng ở D2. |
| [x] P2-D-LOCAL — mã hóa và vòng đời phiên bằng dữ liệu giả | Mã hóa, nạp phiên và vòng đời được kiểm bằng dữ liệu giả. [Bài kiểm tra hiện hành](../apps/browser-runner/tests/unit/test_browser_state.py) | Đã đạt tại máy; không thay bằng chứng máy chủ. |
| [x] P2-D2 — vòng đời phiên trong phạm vi phiên/dữ liệu giả | Năm nhóm vòng đời phiên/dữ liệu giả đã đối chiếu và Owner nghiệm thu 08/10. [Nghiệm thu 08/10](<C:/Users/QQ/.codex/worktrees/api-chain-session/MINDX-REVIEW-BOT/.workflow-local/post-tamper-owner-acceptance-20261008/OWNER_ACCEPTANCE.md>) | Đã đóng đúng phạm vi; không lặp phép tamper đã đạt. |
| [x] P2-E1 — một lượt Teaching trực tiếp khi máy Owner tắt | Một lượt Teaching đúng mục tiêu thành công trong phạm vi PC-off đã ghi. [Hồ sơ GI34](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/teaching-post37-gi34-preparation/result-37190777967>) | Chỉ một mục tiêu; chưa chứng minh toàn chuỗi ứng dụng. |
| [x] P2-E2-LOCAL — công cụ phiên ứng dụng đã chuẩn bị tại máy | #41 đã nhập 09/10; bản R12 kiểm tại máy, CI và nghiệm thu mẫu đạt. [Nguồn đã nhập #41](https://github.com/Banhtalon/mindx-review-bot/pull/41) | Đã đạt công cụ tại máy; quyền thật của lượt mới ở E2. |
| [x] P2-E2 — phiên ứng dụng và quyền vai trò trong không gian thử R13 | Phiên đúng tài khoản thử; người ngoài bị chặn, người xem không tạo việc, Owner tạo đúng một việc; 19 yêu cầu ứng dụng gồm một lượt gửi. Luna Max chốt đúng phạm vi phiên và vai trò trên máy chủ. [Biên nhận an toàn](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/r13-private-handoff-20261009/execution/SAFE_APP_DISPATCH_RESULT.json>) | Chỉ không gian dữ liệu thử; chưa thay bằng chứng toàn bộ hành trình đăng nhập giao diện hay toàn chuỗi E3/G. |
| [x] P2-E3 — một chuỗi ứng dụng → máy chủ → GitHub → chương trình chạy, dữ liệu giả | R17 trên #51 chạy một lần 650,076 giây, 21 lần gia hạn, lưu succeeded; bản sao/khôi phục tại máy/đánh giá độc lập đạt trước dọn. Hậu kiểm mục tiêu0, dữ liệu khác/cấu trúc/quyền nguyên vẹn; chương trình/quyền tạm đã đóng. [Kết quả R17](<C:/Users/QQ/.codex/worktrees/r17-confirmation/MINDX-REVIEW-BOT/.workflow-local/r17-confirmation-20261009/execution/OUTCOME.json>) | Đạt đúng toàn chuỗi dữ liệu giả; chưa chứng minh PC-off, Teaching/LMS thật hoặc nghiệm thu toàn Phase 2. Không mở lượt mới. |
| [ ] P2-F — nhánh lỗi của cả chuỗi | Hai tình huống lỗi sau nhận việc và lỗi khi lưu đã kiểm tại máy bằng sáu biến thể, dùng CLI/client/bảo vệ thật với nơi nhận và phiên giả. Đã sửa lỗi phản hồi lưu thiếu/sai trạng thái vẫn báo thành công; 167 bài liên quan và đánh giá độc lập Luna Max đạt. [Hồ sơ kiểm tại máy](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/failure-cases-local-20261010/NOTE.md>) | Owner đã duyệt đưa bản sửa lên GitHub và nhập khi kiểm tra/đánh giá lại đạt. Còn xác nhận nhánh lỗi trên máy chủ, lưu biên nhận/đối soát trước phục hồi hoặc dọn; chưa mở lượt mới, không dùng lại quyền R17. |
| [ ] P2-G — quyền và dữ liệu riêng tư của chuỗi hoàn chỉnh | R17 kiểm vai trò19 yêu cầu và dọn an toàn đạt. Sáu biến thể lỗi mới tại máy kiểm không lộ chuỗi riêng tư giả, không gửi finish lại, không báo thành công chưa xác nhận; quét bí mật/chống ghi LMS đạt. [Hồ sơ lỗi tại máy](<F:/MINDX_project test/MINDX-REVIEW-BOT/.workflow-local/failure-cases-local-20261010/NOTE.md>) | Chốt an toàn đầu ra và dữ liệu cùng bằng chứng máy chủ của hai nhánh lỗi F; kiểm giả không chứng minh dọn tiến trình thật hoặc dữ liệu máy chủ. |
| [ ] P2-CLOSE — nghiệm thu toàn Phase 2 | Các phần B/C/D và thử tại máy đạt đúng phạm vi. [Chỉ mục Phase 2](evidence/phase-2/index.json) | Đối chiếu các mục A/F/G còn mở, đánh giá độc lập và Owner nghiệm thu tổng thể. |
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
