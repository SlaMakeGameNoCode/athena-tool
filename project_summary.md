# Tổng quan Dự án & Lịch sử Sửa lỗi Gần đây

Tài liệu này cung cấp cái nhìn tổng quan về kiến trúc của công cụ Athena Assistant và danh sách các lỗi nghiêm trọng đã được khắc phục gần đây từ phiên bản `v1.0.25` đến `v1.0.29`.

---

## 1. Tổng quan Dự án (Project Overview)

Athena Assistant là một ứng dụng Desktop (chạy ngầm giao diện web thông qua PyWebView + FastAPI) giúp tự động hóa quy trình quản lý công việc hàng ngày của PM trên hệ thống **WorkAI (Jira)**.

### Kiến trúc Kỹ thuật (Tech Stack):
* **Backend**: Python 3.12, FastAPI (web framework), Uvicorn (web server), Playwright (tự động hóa trình duyệt/crawler).
* **Frontend**: HTML5, Vanilla CSS (thiết kế theo phong cách sleek dark mode / glassmorphism), Javascript (ES6).
* **Desktop Wrapper**: PyWebView (nhúng web browser chạy ứng dụng cục bộ dưới dạng App Desktop).
* **AI Integration**: Hỗ trợ tích hợp OpenAI và Gemini AI để chuẩn hóa tiêu đề công việc, tự động tóm tắt chat từ Rocket.Chat/Git/Email và sửa các tiêu đề KPI chưa đạt chuẩn.

### Các Quy trình & Tính năng Chính:
1. **Tổng hợp Công việc (Tab 1)**: Đồng bộ tin nhắn Rocket.Chat, lịch sử Git log, Email trong ngày và sử dụng AI để tự động trích xuất các công việc thô (raw tasks).
2. **Tạo việc (Tab 2)**: Sử dụng AI để sinh chi tiết tiêu đề, mô tả và tiêu chí nghiệm thu theo đúng tiêu chuẩn JIRA/WorkAI, xuất ra file `memorytask.md`.
3. **Nhập việc (Tab 3)**: Sử dụng Playwright chạy ngầm đăng nhập WorkAI và nhập toàn bộ danh sách công việc đã duyệt lên Daily Time Allocation (Timeline).
4. **Sửa KPI (Tab 4)**: 
   * Quét toàn bộ danh sách các issue JIRA bị đánh dấu "Không đạt" / "Chưa đạt chuẩn" từ trang `/kpi/user`.
   * Sử dụng AI đề xuất tiêu đề mới đạt chuẩn theo quy định.
   * Cho phép chỉnh sửa trực tiếp trên giao diện và tự động cập nhật ngược tiêu đề mới lên WorkAI qua Playwright.

---

## 2. Nhật ký Sửa lỗi Gần đây (Recent Bug Fixes)

Dưới đây là chi tiết phân tích và cách khắc phục các sự cố phát sinh gần đây:

### Phiên bản v1.0.25 & v1.0.26: Tránh gộp chung các đầu việc KPI lỗi
* **Sự cố**: Khi quét trang `/kpi/user`, toàn bộ 11 issue lỗi bị gộp chung thành một đầu việc duy nhất trên giao diện.
* **Nguyên nhân**: Tool nhận diện nhầm khối thống kê điểm số ở đầu trang (chứa text báo cáo tổng quan có chữ "Không đạt") làm hàng dữ liệu, dẫn đến bỏ qua các hàng issue thật sự do trùng lặp vân tay.
* **Khắc phục**: 
  * Cải tiến giải thuật Javascript định vị hàng `TR`: Yêu cầu hàng dữ liệu bắt buộc phải chứa mã khóa JIRA dạng `[A-Z0-9]+-\d+` và có chiều dài text dưới 800 ký tự.
  * Bỏ qua hoàn toàn khối thống kê điểm số ở đầu trang để quét chính xác 11 issue lỗi JIRA riêng biệt.

### Phiên bản v1.0.27: Triển khai Cập nhật tiêu đề KPI an toàn
* **Sự cố**: Khi cập nhật tiêu đề KPI mới lên WorkAI, các thông tin mô tả (Description) và tiêu chí nghiệm thu (Acceptance Criteria) hiện có của issue trên WorkAI bị xóa trắng.
* **Nguyên nhân**: API cập nhật tiêu đề chỉ lấy thông tin tiêu đề mới, các trường mô tả bị truyền dạng chuỗi rỗng (`""`), làm Playwright ghi đè xóa sạch dữ liệu cũ.
* **Khắc phục**:
  * Thiết lập giá trị `null` cho `description` và `acceptance_criteria` trong API cập nhật KPI.
  * Nâng cấp Playwright trong `preview_helper.py` để kiểm tra: chỉ ghi đè dữ liệu lên WorkAI nếu giá trị truyền vào khác `null` và `undefined`. Nhờ đó bảo toàn nguyên vẹn mô tả cũ của người dùng.

### Phiên bản v1.0.28: Sửa lỗi Quét KPI trả về 0 kết quả
* **Sự cố**: Tool báo tìm thấy 11 nhãn lỗi nhưng kết quả thu thập được sau khi quét hoàn tất lại bằng 0.
* **Nguyên nhân**: Bảng issue trên trang KPI cá nhân của WorkAI hoạt động theo cơ chế **Accordion** (chỉ cho phép mở rộng chi tiết của 1 dòng tại một thời điểm). Khi click mở rộng dòng `i+1`, dòng `i` sẽ tự động thu gọn và phần tử HTML chi tiết lỗi của nó bị xóa khỏi DOM. Giải thuật cũ mở rộng tất cả các hàng trước rồi mới cào đồng loạt dẫn đến các dòng trước đó bị ẩn hết.
* **Khắc phục**:
  * Thay đổi sang cơ chế **Quét tuần tự và tức thời**: Đối với mỗi dòng lỗi $\rightarrow$ click mở rộng $\rightarrow$ đợi 800ms $\rightarrow$ cào ngay thông tin từ dòng chi tiết kế tiếp (`nextElementSibling` của TR) $\rightarrow$ lưu trữ rồi mới chuyển sang dòng sau.
  * Sử dụng bộ định vị động `nth(idx)` của Playwright để tránh lỗi `stale element reference` khi DOM thay đổi trạng thái đóng/mở hàng liên tục.

### Phiên bản v1.0.29: Khắc phục lỗi Sập nguồn (Reset) & Thiếu module greenlet trên EXE
* **Sự cố**: Ở bản đóng gói `.exe` chạy độc lập, khi người dùng bấm "Cập nhật tiêu đề lên WorkAI", ứng dụng đột ngột biến mất (sập nguồn). Khi mở lại app và quét KPI thì báo lỗi thiếu module `greenlet._greenlet`.
* **Nguyên nhân**:
  * **Lỗi sập nguồn**: Do `sys.executable` trong file `.exe` trỏ tới `Athena.exe`. Tiến trình con chạy ngầm gọi `Athena.exe preview_helper.py` nhưng file `main.py` thiếu logic đánh chặn (intercept) tham số này. Do đó, tiến trình con tiếp tục chạy app GUI thứ hai, phát hiện cổng `8000` bị chiếm dụng bởi app cha và gọi lệnh `taskkill` ép buộc tắt tiến trình cha (app chính của người dùng).
  * **Lỗi thiếu greenlet**: Khi app cha bị force-kill đột ngột, các đường dẫn thư mục tạm của PyInstaller bị lỗi. Đồng thời, cấu hình đóng gói `main.spec` chưa khai báo `greenlet` là `hiddenimports` dẫn đến thiếu file compiled C-extension `_greenlet.pyd` của Playwright.
* **Khắc phục**:
  * Thêm logic đánh chặn CLI cho `preview_helper.py` trong `main.py` để tiến trình con chỉ chạy script ngầm rồi thoát, không khởi động GUI và không tranh chấp cổng.
  * Khai báo `'greenlet'` vào `hiddenimports` trong file [main.spec](file:///f:/prototype/Agent/main.spec#L9) để cam kết đóng gói đầy đủ thư viện.
