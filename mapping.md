# Bản đồ Hệ thống Mã nguồn Athena Assistant (mapping.md)

Tài liệu này ánh xạ toàn bộ các tệp tin trong hệ thống trợ lý ảo Athena, chức năng, vai trò và luồng dữ liệu tương tác để bạn dễ dàng tra cứu khi cần sửa đổi.

---

## 1. Thành phần Cốt lõi & Giao diện (Core & App Flow)

### 📌 [main.py](file:///f:/prototype/Agent/main.py)
*   **Chức năng**: Điểm khởi chạy duy nhất của ứng dụng (Entry point).
*   **Nhiệm vụ**:
    *   Tự động ghi nhật ký khởi động vào `Athena_startup.log`.
    *   Kiểm tra cấu trúc và thư mục thực thi.
    *   Nhập (`import`) module `app_core.py`.
    *   Khởi chạy server FastAPI làm backend trên tiến trình phụ, đồng thời mở giao diện cửa sổ máy tính (Desktop App) thông qua thư viện `pywebview`.
*   **Khi nào cần sửa**: Khi bạn muốn thay đổi logic khởi động tổng thể, cấu hình luồng chạy đa nhiệm hoặc thay đổi kích thước cửa sổ giao diện mặc định.

### 📌 [app_core.py](file:///f:/prototype/Agent/app_core.py)
*   **Chức năng**: Trái tim điều hướng và xử lý dịch vụ (Backend Server).
*   **Nhiệm vụ**:
    *   Định nghĩa toàn bộ các API endpoint giao tiếp giữa giao diện (HTML/JS) và các tập lệnh Python (Sync, AI, Submit).
    *   Đọc và ghi tệp cấu hình `config.json`.
    *   Điều hướng luồng công việc chính: Gọi quét dữ liệu chat, lưu trữ công việc tạm, quản lý trạng thái đồng bộ và gửi việc lên WorkAI.
*   **Khi nào cần sửa**: Khi bạn muốn thêm tính năng mới trên giao diện, thay đổi các route HTTP API, chỉnh sửa luồng logic phối hợp giữa các tệp đồng bộ dữ liệu.

### 📌 [static/index.html](file:///f:/prototype/Agent/static/index.html)
*   **Chức năng**: Cấu trúc giao diện HTML chính của phần mềm.
*   **Nhiệm vụ**: Định nghĩa các tab giao diện (Đồng bộ, Quét chat, Tạo việc, Nhập việc, KPI, Cài đặt), các nút bấm, các khung nhập liệu và bảng hiển thị dữ liệu.
*   **Khi nào cần sửa**: Khi bạn muốn thêm nút mới, thay đổi vị trí ô nhập liệu hoặc chỉnh sửa bố cục hiển thị trên giao diện.

### 📌 [static/app.js](file:///f:/prototype/Agent/static/app.js)
*   **Chức năng**: Logic xử lý sự kiện và tương tác frontend (Javascript).
*   **Nhiệm vụ**:
    *   Bắt các sự kiện click nút bấm của người dùng trên giao diện.
    *   Gửi yêu cầu (gọi API HTTP POST/GET) tới backend (`app_core.py`) để kích hoạt các script Python tương ứng.
    *   Nhận kết quả trả về từ backend để render (hiển thị) dữ liệu dạng bảng biểu, văn bản Markdown hoặc thông báo màu sắc lên giao diện.
*   **Khi nào cần sửa**: Khi bạn muốn thay đổi hành động phản hồi khi click nút, thêm logic kiểm tra dữ liệu trước khi gửi, hoặc định dạng cách hiển thị dữ liệu.

### 📌 [static/style.css](file:///f:/prototype/Agent/static/style.css)
*   **Chức năng**: Định dạng phong cách thiết kế, màu sắc giao diện (CSS).
*   **Nhiệm vụ**: Thiết lập font chữ, màu nền tối (Dark mode), hiệu ứng hover nút bấm và căn lề bố cục giao diện.
*   **Khi nào cần sửa**: Khi bạn muốn chỉnh sửa màu sắc ứng dụng, đổi font chữ hoặc căn chỉnh khoảng cách, cỡ chữ của các thành phần giao diện.

---

## 2. Kết nối và Xử lý AI (AI Integration)

### 📌 [ai_processor.py](file:///f:/prototype/Agent/ai_processor.py)
*   **Chức năng**: Trung tâm tích hợp Trí tuệ nhân tạo (Gemini, OpenAI, DeepSeek).
*   **Nhiệm vụ**:
    *   Đóng vai trò gọi API REST của Google Gemini và SDK của OpenAI/DeepSeek.
    *   `call_ai_provider(...)`: Quản lý danh sách các mô hình và tự động đổi phiên bản (`v1` / `v1beta`) kết hợp với kỹ thuật chèn prompt dự phòng khi một mô hình bị quá hạn mức hoặc không hỗ trợ `systemInstruction`.
    *   `summarize_raw_chat(...)`: Đọc dữ liệu chat thô từ `chat_raw.json` và phân tích, trích xuất thành danh sách công việc ứng viên (Candidate Tasks) dựa theo quy tắc Rules A-H trong `.agent_rules.md`.
    *   `generate_tasks(...)`: Tạo định dạng file Markdown `memorytask.md` cho các tác vụ đã chọn.
    *   `fix_kpi_tasks(...)`: Nhận diện các task không đạt KPI và viết lại tiêu đề đạt chuẩn Rule B (độ dài >= 50 ký tự, cấu trúc `[Hành động] - [Mục tiêu]`).
*   **Khi nào cần sửa**: Khi muốn điều chỉnh prompt của AI, thay đổi danh sách các mô hình ưu tiên thử nghiệm của Gemini, sửa đổi định dạng biên tập tiêu đề, hoặc tích hợp thêm nhà cung cấp AI mới.

---

## 3. Đồng bộ dữ liệu Đầu vào (Data Synchronizers)

### 📌 [sync_rocket.py](file:///f:/prototype/Agent/sync_rocket.py)
*   **Chức năng**: Đồng bộ tin nhắn từ hệ thống Rocket.Chat.
*   **Nhiệm vụ**: Tải lịch sử trò chuyện trong vòng 24 giờ qua từ các phòng chat cá nhân, phòng nhóm và phòng quét commit Git được chỉ định.
*   **Đầu ra**: Ghi đè vào tệp `chat_raw.json`.
*   **Khi nào cần sửa**: Khi muốn thay đổi thời gian quét chat (ví dụ: quét 48 giờ thay vì 24 giờ), thay đổi cách lọc kênh chat, hoặc cấu hình bổ sung kết nối API Rocket.Chat.

### 📌 [sync_git.py](file:///f:/prototype/Agent/sync_git.py) / [sync_gitlab.py](file:///f:/prototype/Agent/sync_gitlab.py)
*   **Chức năng**: Đồng bộ lịch sử commit mã nguồn từ các kho Git/GitLab.
*   **Nhiệm vụ**: Quét lịch sử các commit mới từ kho dự án đã khai báo trong cấu hình để tạo cơ sở làm việc.
*   **Đầu ra**: Ghi đè vào tệp `git_raw.json`.
*   **Khi nào cần sửa**: Khi muốn thay đổi phương thức gọi API Git, sửa đổi cơ chế kết nối bằng Token cá nhân hoặc thay đổi định dạng ghi log commit.

### 📌 [sync_email.py](file:///f:/prototype/Agent/sync_email.py)
*   **Chức năng**: Quét và đồng bộ email công việc.
*   **Khi nào cần sửa**: Sửa đổi cơ chế kết nối IMAP/POP3 để lấy danh sách email giao việc.

### 📌 [sync_calendar.py](file:///f:/prototype/Agent/sync_calendar.py)
*   **Chức năng**: Đồng bộ lịch làm việc và sự kiện.

---

## 4. Tương tác và Đẩy việc lên WorkAI (WorkAI Automation)

### 📌 [workai_api.py](file:///f:/prototype/Agent/workai_api.py)
*   **Chức năng**: Tương tác trực tiếp với API hệ thống WorkAI.
*   **Nhiệm vụ**: Thực hiện truy vấn GraphQL/REST để lấy danh sách dự án hiện có, thông tin KPIs và gửi dữ liệu công việc nhanh chóng mà không cần thông qua giao diện web.
*   **Khi nào cần sửa**: Khi API hệ thống WorkAI thay đổi endpoint, thay đổi token cấu trúc hoặc cập nhật cấu trúc dữ liệu JSON/GraphQL.

### 📌 [workai_scraper.py](file:///f:/prototype/Agent/workai_scraper.py)
*   **Chức năng**: Tự động hoá trình duyệt web thông qua thư viện Playwright.
*   **Nhiệm vụ**: Giả lập nhấp chuột, đăng nhập, quét danh sách KPI và xử lý các tác vụ phức tạp trên trang web WorkAI mà API không hỗ trợ trực tiếp.
*   **Khi nào cần sửa**: Khi cấu trúc giao diện HTML của trang web WorkAI bị thay đổi (khiến Playwright không tìm thấy nút bấm, ô nhập liệu), hoặc muốn thay đổi luồng giả lập đăng nhập.

### 📌 [submitter.py](file:///f:/prototype/Agent/submitter.py)
*   **Chức năng**: Tự động đẩy danh sách công việc chính thức lên hệ thống WorkAI.
*   **Nhiệm vụ**: Đọc tệp `tasks.json` và thực hiện cuộc gọi API hoặc Scraper để tự động đăng các task đó lên WorkAI với trạng thái "Done" cho ngày hiện tại.
*   **Khi nào cần sửa**: Thay đổi siêu dữ liệu của task khi đẩy (mặc định trạng thái, thời gian thực hiện, nhãn dán).

### 📌 [preview_helper.py](file:///f:/prototype/Agent/preview_helper.py)
*   **Chức năng**: Tạo giao diện xem trước (Preview) cho tác vụ chuẩn bị đẩy.

---

## 5. Cấu trúc Cập nhật & Tiện ích (Updates & Utilities)

### 📌 [updater.py](file:///f:/prototype/Agent/updater.py)
*   **Chức năng**: Tự động cập nhật phần mềm (Auto-updater).
*   **Nhiệm vụ**: Tải file ZIP từ GitHub của kho lưu trữ `SlaMakeGameNoCode/athena-tool` khi có phiên bản mới, giải nén và ghi đè các tệp tin được định nghĩa trong danh sách cho phép (tránh ghi đè file cấu hình cá nhân của người dùng).
*   **Khi nào cần sửa**: Khi bạn muốn thêm tệp tin mới vào danh sách cần cập nhật hoặc loại bỏ tệp khỏi chế độ cập nhật.

---

## 6. Sơ đồ Lưu trữ Dữ liệu cục bộ (Local Data Storage Files)

Các tệp tin JSON này được tạo ra và thay đổi động trong quá trình chạy ứng dụng:

*   💾 **config.json**: Lưu trữ thông tin cá nhân của bạn (Tên, vai trò, khóa AI Key, tài khoản WorkAI, danh sách phòng chat ngoại lệ, kho Git).
*   💾 **projects.json**: Danh sách tất cả các dự án của bạn được đồng bộ từ WorkAI về để làm dữ liệu gợi ý gán dự án cho task.
*   💾 **chat_raw.json**: Chứa dữ liệu chat thô chưa xử lý sau khi quét Rocket.Chat.
*   💾 **git_raw.json**: Chứa lịch sử commit Git thô chưa xử lý.
*   💾 **memorytask.md**: File Markdown chứa danh sách công việc đã được AI định dạng tiêu đề (Rule B). Bạn có thể chỉnh sửa thủ công file này trực tiếp trên giao diện của Tab 3.
*   💾 **tasks.json**: File JSON chứa danh sách công việc chính thức đã được parse từ `memorytask.md` cùng với siêu dữ liệu sẵn sàng để `submitter.py` gửi lên WorkAI.
*   💾 **version.json**: Tệp khai báo phiên bản hiện tại (Ví dụ: `1.0.53`) để updater so sánh với máy chủ GitHub.
