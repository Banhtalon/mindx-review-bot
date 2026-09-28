# v10 cho Owner

Owner chỉ cần nói kết quả mong muốn, trả lời câu hỏi business, dùng thử khi có
`READY_FOR_OWNER`, và tự thao tác account/secret trong trang chính thức.

Owner không đọc code/PR/CI/test/SQL/security/log, không chọn model và không gửi
secret cho AI. AI/LEAD tự đọc project, viết code, cấu hình, chạy kiểm tra và
điều phối review; Owner chỉ làm thao tác tài khoản trên trang chính thức, xác
nhận hành vi sản phẩm và duyệt merge. Không cần Technical Operator riêng.
Status theo `.ai-workflow/OWNER_STATUS.md`. LOCAL_AUTO chỉ được bật sau khi
doctor, pilot, quota-drill và activation đều có bằng chứng thật.
