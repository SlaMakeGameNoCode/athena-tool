# Athena Assistant - Tài liệu Dự án & Hướng dẫn Phát triển

Athena Assistant là một ứng dụng Desktop WebUI (FastAPI + pywebview) giúp tự động hóa quy trình làm việc hàng ngày của Chu Văn Mai (PM & Team Lead): Quét tin nhắn, email và lịch sử git commit trong ngày, sử dụng AI để tổng hợp thành các đầu việc đạt chuẩn và tự động nhập chúng lên hệ thống quản lý công việc WorkAI qua REST API.

Tài liệu này được viết chi tiết nhằm giúp nhà phát triển tiếp theo tiếp quản, hiểu rõ kiến trúc, tính năng, quy trình build và các điểm kỹ thuật quan trọng của dự án.

---

## 📌 1. Kiến trúc Hệ thống & Danh sách Module

Ứng dụng sử dụng mô hình lai giữa **Python Backend (FastAPI)** và **Desktop UI (pywebview)** để hiển thị một giao diện Web hiện đại, mượt mà dưới dạng ứng dụng Desktop chạy độc lập.

```
Athena.exe (Chứa Launcher + Python Runtime + default assets)
     │
     ├── Nạp động từ ổ đĩa (nếu có bản cập nhật)
     ▼
Thư mục gốc chạy ứng dụng:
├── Athena.exe              <- Bộ chạy chính (không đổi)
├── app_core.py             <- Backend FastAPI & logic chính (Cập nhật được)
├── updater.py              <- Module xử lý cập nhật tự động (Cập nhật được)
├── submitter.py            <- Kịch bản tự động nhập việc qua WorkAI API (Cập nhật được)
├── ai_processor.py         <- Bộ xử lý Prompt & gọi API AI (Cập nhật được)
├── sync_rocket.py          <- Đồng bộ tin nhắn từ Rocket.Chat (Cập nhật được)
├── sync_git.py             <- Đồng bộ commit lịch sử Git local (Cập nhật được)
├── sync_email.py           <- Đồng bộ email qua IMAP SSL (Cập nhật được)
├── version.json            <- Lưu thông tin phiên bản hiện tại trên đĩa
├── static/                 <- Thư mục chứa giao diện HTML/CSS/JS (Cập nhật được)
├── .env                    <- [BẢO MẬT] Cấu hình mật khẩu & Token (Không đưa lên Git)
└── config.json             <- Cấu hình cài đặt của người dùng (Không đưa lên Git)
```

### Chi tiết các Module chính:
1. **`main.py` (Launcher)**: File entry-point duy nhất được đóng gói cứng trong `Athena.exe`. Nó không chứa logic nghiệp vụ mà chỉ làm nhiệm vụ khai báo thư mục làm việc vào đầu `sys.path` để ưu tiên nạp các file code bổ sung/cập nhật ngoài ổ đĩa trước khi import `app_core.py`.
2. **`app_core.py` (Core)**: Khởi chạy server FastAPI chạy ngầm và tạo cửa sổ pywebview trỏ vào `http://127.0.0.1:8000/`. Chứa toàn bộ API endpoints điều khiển nghiệp vụ.
3. **`updater.py` (Bộ cập nhật)**: Sử dụng các HTTP request trực tiếp gọi lên GitHub API để kiểm tra, tải mã nguồn và cập nhật ứng dụng.
4. **`submitter.py` (WorkAI Submitter)**: Sử dụng WorkAI REST API để tự động thêm issue và chuyển trạng thái Done.
5. **`ai_processor.py` (AI Engine)**: Xây dựng hệ thống prompt mẫu và kết nối API của Google Gemini, OpenAI, DeepSeek để tóm tắt chat, email thành task và sửa KPI.

---

## 🚀 2. Các Tính năng Nổi bật

1. **Thu thập Dữ liệu Đa kênh**:
   * **Rocket.Chat**: Quét các phòng chat, tin nhắn riêng (DM), các phòng thông báo/đơn từ. Tự động lấy tên hiển thị và username của người dùng đang đăng nhập qua API `/api/v1/me`. Hỗ trợ danh sách loại trừ (Blacklist) case-insensitive.
   * **Email (IMAP SSL)**: Kết nối hòm thư cá nhân, tự động làm sạch nội dung HTML/CSS và gom nhóm email theo luồng (Thread Grouping) dựa trên tiêu đề chuẩn hóa.
   * **Git (Local)**: Quét lịch sử commit của tác giả trong ngày trên các dự án code local.
2. **Xử lý Thông tin bằng AI**:
   * Tự động lọc nhiễu (chỉ giữ lại nội dung công việc liên quan tới user).
   * Chuẩn hóa tiêu đề task theo công thức: `[Hành động] - [Mục tiêu]` với độ dài tối thiểu 50 ký tự.
   * Hỗ trợ sửa đổi, chia nhỏ công việc hàng loạt qua khung chat AI thông minh ở thanh bên (sử dụng Patch/Full mode linh hoạt).
   * Phân tích lý do KPI "Không đạt" để sửa tiêu đề chuẩn xác mà không bị phụ thuộc vào gợi ý sai lệch của hệ thống.
3. **Tự động Nhập việc (Auto Submission)**:
   * WorkAI API tự động tạo thẻ công việc trực tiếp trên ngày hiện tại của Timesheet.
   * Tự động phân tích tên dự án từ `projects.json` để chọn đúng dự án, tự động gán vào Sprint mới nhất và chuyển trạng thái thẻ sang Done.
4. **Tự động Cập nhật Không cần Git (Gitless Auto-Update)**:
   * Cho phép máy nhân viên tự nâng cấp tính năng chỉ bằng một click chuột ngay trên giao diện mà không cần cài đặt Git hay Python trên máy tính.

---

## 🛠 3. Giải pháp Kỹ thuật Quan trọng cần Lưu ý

### 3.1. Thiết kế Tách rời Launcher và Core để Cập nhật Trực tiếp
Vì file `.exe` được build bằng PyInstaller là một file tĩnh đóng gói sẵn môi trường Python runtime (~97MB), việc phân phối lại file `.exe` mỗi khi sửa code là không khả thi.
* **Giải pháp**: File `.exe` chỉ chạy launcher `main.py`. Khi người dùng click Cập nhật, ứng dụng tải gói ZIP mã nguồn từ GitHub (~100KB) và giải nén đè trực tiếp các file Python (`app_core.py`, `updater.py`...) ra thư mục chạy của người dùng.
* Lệnh `sys.path.insert(0, RUNNING_DIR)` trong launcher sẽ khiến Python ưu tiên import các file code nằm ngoài đĩa cứng này trước code đóng gói sẵn trong exe.

### 3.2. Bỏ qua Bộ nhớ đệm của GitHub Raw CDN (Fastly CDN Cache)
Mã nguồn thô trên GitHub (`raw.githubusercontent.com`) sử dụng dịch vụ CDN Fastly để lưu đệm bộ nhớ trong **5 phút**. Nếu kiểm tra phiên bản trực tiếp bằng link tĩnh, người dùng sẽ không thấy bản cập nhật mới ngay lập tức.
* **Giải pháp**: Trong `updater.py`, khi gọi API check version từ GitHub, hệ thống tự động nối thêm tham số timestamp:
  `url = f"{VERSION_URL}?t={int(time.time())}"`
  Điều này bắt buộc CDN phải bỏ qua cache và trả về file `version.json` mới nhất tức thì.

### 3.3. Bỏ qua Cache Trình duyệt Webview
Trình duyệt nhúng trên Windows (WebView2) lưu đệm (cache) tài nguyên API rất mạnh, khiến yêu cầu gọi `/api/update/check` luôn trả về kết quả cũ (báo không có cập nhật).
* **Giải pháp**: 
  1. Giao diện (JS) gọi URL check kèm timestamp: `/api/update/check?t=' + Date.now()`.
  2. Backend FastAPI trả về response kèm HTTP Header cấm cache:
     `response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"`

### 3.4. Khởi động lại An toàn trên Windows (Tránh Errno 10048)
Trên Windows, việc dùng `os.execv` để restart tiến trình sẽ khởi chạy tiến trình con trước khi giải phóng cổng mạng của tiến trình cha. Do đó tiến trình con sẽ bị crash do cổng `8000` đang bị chiếm giữ. Lệnh `timeout` của Windows cũng bị lỗi khi chạy trong môi trường ngầm (Input redirection not supported).
* **Giải pháp**: Sử dụng lệnh `ping` kết hợp tắt tiến trình cha ngay lập tức bằng `os._exit(0)`:
  `cmd = f'ping 127.0.0.1 -n 3 > nul & start "" "{exe_path}" {args_str}'`
  Lệnh `ping` gửi 3 gói tin giúp trì hoãn chính xác 2 giây mà không cần tương tác console, tạo khoảng trống thời gian cho tiến trình cũ giải phóng hoàn toàn cổng `8000` trước khi tiến trình mới khởi động.

---

## 💻 4. Hướng dẫn Phát triển & Đóng gói (Developer Guide)

### 4.1. Thiết lập Môi trường Phát triển
1. Yêu cầu Python phiên bản `3.10` hoặc `3.12`.
2. Cài đặt các thư viện cần thiết:
   ```bash
   pip install fastapi uvicorn pywebview python-multipart pydantic requests pyinstaller
   ```
3. Chạy thử nghiệm ở chế độ phát triển:
   ```bash
   python main.py
   ```
   *(Truy cập giao diện tại `http://127.0.0.1:8000`)*

### 4.2. Quy trình Phát hành Bản Cập nhật Mới (Không cần Build lại EXE)
Nếu anh chỉ sửa đổi logic code Python (không thêm thư viện mới) hoặc sửa giao diện HTML/CSS/JS:
1. Mở file `version.json` ở thư mục gốc.
2. Nâng số phiên bản (ví dụ từ `"1.0.3"` lên `"1.0.4"`).
3. Cập nhật ngày phát hành (`released_at`) và mô tả thay đổi (`changelog`).
4. Commit và push code lên GitHub:
   ```bash
   git add .
   git commit -m "Phát hành bản cập nhật v1.0.4"
   git push
   ```
   *Ngay lập tức, tất cả người dùng cuối sẽ thấy thông báo cập nhật mới v1.0.4 khi mở app.*

### 4.3. Quy trình Đóng gói lại Bộ cài (`Athena.exe`)
Chỉ thực hiện bước này khi **thêm thư viện Python mới** (bằng `pip install ...`) vào mã nguồn:
1. Chạy lệnh build PyInstaller sử dụng file spec sẵn có:
   ```bash
   pyinstaller main.spec --noconfirm
   ```
2. Sau khi build xong, file `main.exe` mới sẽ được tạo trong thư mục `dist/`.
3. Xóa file `dist/Athena.exe` cũ và đổi tên file `dist/main.exe` thành `Athena.exe`.
4. Gửi file `Athena.exe` mới này cho người dùng cuối thay thế file cũ.

---

## 🔒 5. Các Nguyên tắc Bảo mật & Dữ liệu
* **Bảo vệ cấu hình cá nhân**: File `.gitignore` đã được cấu hình mặc định để **KHÔNG BAO GIỜ** đẩy các file chứa thông tin nhạy cảm của người dùng như `.env` (chứa password WorkAI, token Rocket.Chat) và `config.json` lên GitHub.
* **Loại trừ dữ liệu khi cập nhật**: Module cập nhật trong `updater.py` đã cấu hình mảng `UPDATE_EXCLUDES` để bỏ qua các file cá nhân khi tải code mới từ GitHub về ghi đè. Không bao giờ ghi đè lên các file cấu hình và cơ sở dữ liệu Timesheet của người dùng cuối.
* **Tự động cập nhật an toàn**: Module `updater.py` bỏ qua các file dữ liệu cá nhân khi cập nhật, chỉ ghi đè các file code và static.
