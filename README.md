# Hướng dẫn sử dụng Athena Assistant (Rocket.Chat -> WorkAI Automation)

Athena Assistant là trợ lý ảo tự động hóa quy trình làm việc hàng ngày: Quét tin nhắn, email và lịch sử git commit của bạn, sử dụng trí tuệ nhân tạo (AI) để tổng hợp thành các đầu việc (Tasks) và tự động nhập chúng lên hệ thống quản lý công việc WorkAI.

---

## 📌 Các Tính Năng Chính
1. **Đồng bộ hóa đa nền tảng**: Hỗ trợ quét tin nhắn từ **Rocket.Chat**, **Telegram**, **Slack**, đọc hộp thư **Email (IMAP)**, và lịch sử commit của các thư mục **Git (Local)**.
2. **Tự động hóa bằng AI**: Sử dụng Gemini, DeepSeek, hoặc OpenAI để tóm tắt nội dung thô thành các task rõ ràng theo định dạng `[Hành động] - [Mục tiêu]`.
3. **Quản lý & Tương tác thông minh**: Hỗ trợ chỉnh sửa nhanh, đổi dự án trực tiếp, hoặc chat trực tiếp với AI ở thanh bên để sửa đổi/tách nhỏ task hàng loạt.
4. **Tự động nhập việc (Auto Submission)**: Sử dụng trình duyệt tự động (Playwright) đăng nhập vào WorkAI, tạo thẻ công việc và chuyển trạng thái sang **Done** chỉ với một cú click chuột.

---

## 🚀 Hướng Dẫn Khởi Chạy

Bạn có thể chạy ứng dụng theo 2 cách:

### Cách 1: Sử dụng file chạy nhanh `main.exe` (Khuyến nghị cho người dùng cuối)
1. Truy cập thư mục chứa file chạy: [dist/main.exe](file:///f:/prototype/Agent/dist/main.exe).
2. Sao chép file `main.exe` vào một thư mục làm việc trống bất kỳ trên máy tính của bạn (Ví dụ: `D:\AthenaTool\`).
3. Nhấp đúp chuột để chạy file `main.exe`. Giao diện WebUI sẽ tự động mở ra trên trình duyệt mặc định của bạn tại địa chỉ `http://127.0.0.1:5000`.

### Cách 2: Chạy từ mã nguồn Python
Yêu cầu hệ thống đã cài đặt Python 3.10 trở lên.
1. Cài đặt các thư viện cần thiết:
   ```bash
   pip install fastapi uvicorn playwright jinja2 python-multipart pydantic
   playwright install chromium
   ```
2. Chạy ứng dụng:
   ```bash
   python main.py
   ```
3. Mở trình duyệt truy cập `http://127.0.0.1:5000`.

---

## 🛠 Hướng Dẫn Sử Dụng Chi Tiết

### Bước 1: Đăng nhập & Thiết lập ban đầu (Setup)
*   **Tài khoản đăng nhập công cụ (mặc định):**
    *   Tên đăng nhập: `admin`
    *   Mật khẩu: `123456`
*   **Thiết lập Thông tin cá nhân & AI:**
    *   **Họ và tên / Vai trò:** Nhập đúng tên của bạn (Ví dụ: *Chu Văn Mai*) và vai trò (*Developer*). AI sẽ dựa vào thông tin này để lọc tin nhắn chỉ liên quan tới bạn.
    *   **AI Provider & API Key:** Chọn nhà cung cấp AI mong muốn (Gemini, DeepSeek, OpenAI) và dán API Key tương ứng.
    *   **Tài khoản WorkAI:** Điền email và mật khẩu đăng nhập trang WorkAI của bạn (mật khẩu này dùng cho script tự động tạo task).
*   **Thiết lập các Nền tảng đồng bộ (Platforms):**
    *   **Rocket.Chat**: Điền Server URL, User ID, và Auth Token của bạn.
    *   **Email (IMAP)**: Nhập IMAP Server (VD: `imap.gmail.com` cho Gmail, `outlook.office365.com` cho Outlook) và địa chỉ email kèm **Mật khẩu ứng dụng** (App Password).
    *   **Git (Local)**: Chọn thư mục code local và tên tác giả commit (VD: `Chu Văn Mai`) để quét lịch sử thay đổi code trong ngày.
    *   **Telegram / Slack**: Điền các Chat ID, Token tương ứng (nếu cần quét).
*   *Lưu ý:* Mọi thông tin cấu hình đều được lưu an toàn tại file cục bộ `config.json` và `.env` trong thư mục chạy của bạn.

---

## 🔄 Quy Trình Làm Việc Hàng Ngày (Workflow)

Quy trình làm việc hàng ngày gồm 3 bước chính tương ứng trên giao diện:

### 1️⃣ Bước 1: Tổng hợp (Scan & Summarize)
*   Bấm nút **1. Tổng hợp** trên giao diện chính.
*   Hệ thống sẽ chạy các script ngầm để quét tin nhắn mới, email mới và git commit trong ngày (tính từ 0h sáng hôm nay, có kèm 2 phút bù đệm lệch giờ).
*   AI sẽ tóm tắt tất cả các nội dung cào được và đề xuất danh sách task thô tại **Tab 1: Công việc thô (Chưa xử lý)**.

### 2️⃣ Bước 2: Xem xét & Gán dự án (Review & Edit)
*   **Gán dự án:** Tại danh sách công việc ở **Tab 1**, bạn cần chọn dự án (Project Code) tương ứng cho từng task từ menu dropdown. Hệ thống sẽ tự động lưu lại dự án bạn chọn.
*   **Quản lý nhóm loại trừ (Blacklist):** Đối với Rocket.Chat, bạn có thể click nút **Quản lý Nhóm loại trừ** trong màn hình cài đặt để bỏ qua các phòng chat không liên quan (ví dụ phòng phiếm, tin tức chung).
*   **Chỉnh sửa nhanh bằng AI Chat:**
    *   Sử dụng thanh Chat ở bên phải màn hình để yêu cầu AI chỉnh sửa danh sách task.
    *   *Ví dụ câu lệnh:* `"Xóa task số 3"`, `"Sửa nội dung task 1 thành nghiên cứu API"`, hoặc lệnh tách nhỏ phức tạp: `"Tách task số 1 thành 50 task nhỏ, mỗi task tương ứng 1 level từ 1 đến 50"`.
    *   Hệ thống hỗ trợ tự động sửa lỗi và tách nhỏ với giới hạn đầu ra mở rộng lên tới 65,536 tokens.
    *   Sau khi danh sách ở Tab 1 đã chuẩn, bấm nút **2. Tạo việc** để chuyển đổi toàn bộ danh sách sang **Tab 2: Bộ nhớ công việc (Đã xử lý)** dưới dạng tiêu đề đạt chuẩn WorkAI (`[Hành động] - [Mục tiêu]`, tối thiểu 50 ký tự) và lưu vào file `memorytask.md`.

### 3️⃣ Bước 3: Nhập việc lên WorkAI (Auto Submit)
*   Nhấp chọn **3. Nhập việc**.
*   Một bảng overlay hiển thị tiến độ thời gian thực (Progress Bar) sẽ xuất hiện trên màn hình.
*   Hệ thống sẽ chạy trình duyệt ảo Playwright đăng nhập trực tiếp vào tài khoản WorkAI của bạn, tự động tạo các Issue trong các dự án tương ứng, điền thông tin chi tiết và chuyển trạng thái thẻ từ **To Do** sang **Done**.
*   **Lưu ý sau khi chạy:** Sau khi quá trình nhập việc hoàn tất, bạn cần truy cập thủ công vào trang WorkAI để tự căn chỉnh số giờ làm việc (allocated hours) cho từng task theo đúng thực tế công việc trong ngày của mình.

---

## 🔒 Quy Tắc Bảo Mật & An Toàn Dữ Liệu
*   Công cụ này hoạt động hoàn toàn **cục bộ (Local)** trên máy tính của bạn.
*   Không có bất kỳ dữ liệu nhạy cảm nào (mật khẩu, API key, nội dung chat, email cá nhân) bị gửi ra ngoài ngoại trừ việc kết nối trực tiếp đến API của nhà cung cấp AI mà bạn cấu hình và trang WorkAI của công ty.
*   Tuyệt đối **không chia sẻ** file cấu hình `.env` hoặc `config.json` cho người khác vì chúng chứa thông tin đăng nhập của bạn.
