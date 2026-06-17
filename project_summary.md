# Athena Assistant — Tổng quan Dự án (Rút gọn)

> **Phiên bản**: 1.0.50 | **Ngày tổng hợp**: 2026-06-17
> **Người dùng**: Chu Văn Mai — Team Lead Game Designer & PM @ Horus Production

---

## 1. Mục đích

Athena Assistant là ứng dụng **Desktop tự động hóa quy trình làm việc hàng ngày**: quét tin nhắn (Rocket.Chat, email, Git, GitLab, Calendar), dùng AI lọc & tóm tắt thành đầu việc, rồi tự động nhập lên cổng **WorkAI** (chấm công/KPI).

---

## 2. Kiến trúc Tổng thể

```
Athena.exe (PyInstaller ~476MB, chứa Python runtime + launcher)
  → Nạp code .py từ ổ đĩa (cho phép cập nhật nóng không cần build lại EXE)
  → Backend: FastAPI (port 8000) 
  → Frontend: pywebview (WebView2) hiển thị static/index.html
```

**Nguyên lý cập nhật**: `Athena.exe` chỉ là launcher. Code thực thi (`app_core.py`, `submitter.py`...) nằm ngoài ổ đĩa, ưu tiên import qua `sys.path.insert(0, RUNNING_DIR)`. Khi cập nhật, chỉ tải ~100KB ZIP từ GitHub ghi đè file `.py`, không cần build lại EXE.

---

## 3. Cấu trúc thư mục

| File/Thư mục | Vai trò |
|---|---|
| `main.py` | Entry-point launcher, đóng gói trong EXE |
| `app_core.py` | **Core**: FastAPI server + toàn bộ API endpoints + logic nghiệp vụ |
| `updater.py` | Kiểm tra & tải cập nhật từ GitHub (REST API + ZIP) |
| `ai_processor.py` | Prompt builder, gọi AI API (Gemini/OpenAI/DeepSeek) để lọc chat, sinh task, sửa KPI |
| `submitter.py` | Tự động tạo issue trên WorkAI qua HTTP API + chuyển trạng thái Done |
| `workai_api.py` | Wrapper HTTP client cho toàn bộ WorkAI REST API |
| `sync_rocket.py` | Đồng bộ tin nhắn Rocket.Chat (subscriptions + messages) |
| `sync_git.py` | Quét git log local (theo author + since) |
| `sync_gitlab.py` | Quét commit GitLab qua REST API (theo author email) |
| `sync_email.py` | Đọc email qua IMAP SSL, clean HTML, gom nhóm thread |
| `sync_calendar.py` | Lấy lịch họp từ WorkAI Calendar API |
| `preview_helper.py` | Helper tạo preview giao diện (subprocess của main.py) |
| `static/` | Frontend: `index.html`, `app.js`, `style.css` |
| `config.json` | Cấu hình người dùng (AI provider, WorkAI credentials, platforms) |
| `.env` | Token & password nhạy cảm (KHÔNG đẩy lên Git) |
| `version.json` | Phiên bản hiện tại + changelog |
| `projects.json` | Cache danh sách dự án WorkAI |
| `CompanySkills/` | MCP skills: scripts JS + memories + credentials |

### Thư mục phụ trợ

| Thư mục | Mô tả |
|---|---|
| `scratch/` | Script thử nghiệm |
| `build/main/` | Artifacts build PyInstaller |

---

## 4. Luồng Hoạt động Chính (3 bước)

### Bước 1: `/tonghop` — Quét & Lọc

```
sync_rocket.py ──→ chat_raw.json
sync_git.py    ──→ git_raw.json
sync_gitlab.py ──→ (append to chat_raw.json)
sync_calendar.py ─→ (append to chat_raw.json)
sync_email.py  ──→ (append to chat_raw.json)
         ↓
   ai_processor.py (AI lọc noise, trích xuất task)
         ↓
   saved_raw_tasks.json  ←  Lưu trạng thái (active/hide)
         ↓
   User review → approved_tasks.json
```

### Bước 2: `/taoviec` — Viết nội dung

```
approved_tasks.json  →  AI sinh tiêu đề chuẩn (≥50 ký tự)
                    →  memorytask.md
```

### Bước 3: `/nhapviec` — Nhập WorkAI

```
memorytask.md  →  tasks.json (thêm metadata: status=Done, sprint=latest, date=...)
              →  submitter.py (tạo issue qua API → chuyển Done)
              →  submitted.json (chống duplicate)
```

---

## 5. Các Module Chi tiết

### 5.1 `app_core.py` — Backend Core
- **Framework**: FastAPI + uvicorn + pywebview
- **Auth**: Hardcode `admin / 123456` (bảo vệ cục bộ)
- **API Endpoints chính**:

| Endpoint | Method | Chức năng |
|---|---|---|
| `/api/login` | POST | Xác thực người dùng |
| `/api/projects` | GET | Đọc danh sách dự án từ cache |
| `/api/projects/scan` | GET | Quét dự án mới từ WorkAI API |
| `/api/run/tonghop` | POST | Chạy luồng tổng hợp (tất cả sync + AI) |
| `/api/raw_tasks/hide` | POST | Ẩn task không liên quan |
| `/api/raw_tasks/update_project` | POST | Gán project cho task |
| `/api/raw_tasks/restore` | POST | Khôi phục task đã ẩn |
| `/api/kpi/scan_and_fix` | POST | Quét & sửa KPI "Không đạt" |
| `/api/update/check` | GET | Kiểm tra phiên bản mới |
| `/api/update/apply` | POST | Tải & cài bản cập nhật |
| `/api/config/load` | GET | Đọc cấu hình |
| `/api/config/save` | POST | Lưu cấu hình |

- **Sync lock**: Dùng `threading.Lock()` chống chạy đồng thời
- **Timezone**: Luôn dùng UTC+7 (Việt Nam)

### 5.2 `ai_processor.py` — AI Engine
- **Providers**: Google Gemini (`gemini-1.5-flash`), OpenAI (`gpt-4o-mini`), DeepSeek (`deepseek-chat`)
- **Hàm chính**:
  - `summarize_raw_chat()`: Nhận raw chat JSON → trả về JSON array các task ứng viên (đã lọc noise)
  - `generate_tasks()`: Từ danh sách task → sinh `memorytask.md`
  - `fix_kpi_tasks()`: Đọc lý do KPI "Không đạt" → sửa tiêu đề (bỏ qua suggestion)
  - `get_system_rules()`: Đọc `instructions.md` + `.agent_rules.md` nhúng vào prompt

### 5.3 `submitter.py` — WorkAI Submitter
- Dùng **HTTP API thuần** (không Playwright)
- Quy trình mỗi task:
  1. Gọi API `suggest-description` để AI sinh mô tả
  2. Gọi API `quick-create` tạo issue
  3. Gọi API `transitions` chuyển trạng thái → Done
- Chống duplicate: hash `project|title|date` → `submitted.json`
- Mapping project: `projects.json` + legacy map (`PROJECT_CODE_MAP`)

### 5.4 `workai_api.py` — WorkAI API Client
- **Base URL**: `https://workai-be.horus.io.vn/api`
- **Methods**: `login`, `get_projects`, `suggest_description`, `quick_create_issue`, `get_kpi_compliance`, `get_kpi_score`, `get_calendar`, `update_issue_summary`

### 5.5 `sync_rocket.py` — Rocket.Chat Sync
- Dùng REST API (`X-User-Id` + `X-Auth-Token`)
- Lấy subscriptions → lọc theo `lm`/`_updatedAt` → fetch messages từng room active
- **Blacklist**: `excluded_rooms` từ `config.json` + `.env` (`ROCKET_EXCLUDED_ROOMS`)
- Tự động lấy tên/username từ `/api/v1/me`

### 5.6 `sync_git.py` — Git Local Sync
- Chạy `git log --author=... --since=...` trong thư mục local
- Lọc bỏ merge commits

### 5.7 `sync_gitlab.py` — GitLab API Sync
- Dùng GitLab REST API + Personal Access Token
- Lấy commits theo branch, lọc theo author email

### 5.8 `sync_email.py` — Email IMAP Sync
- Kết nối IMAP SSL, tìm email trong ngày
- Clean HTML → text, decode MIME words
- Gom nhóm theo thread (normalize subject, bỏ Re:/Fw:)

### 5.9 `sync_calendar.py` — WorkAI Calendar Sync
- Gọi WorkAI Calendar API (7 ngày gần nhất)
- Merge vào `chat_raw.json` dưới dạng room "WorkAI Calendar"

### 5.10 `updater.py` — Auto Updater
- GitHub repo: `SlaMakeGameNoCode/athena-tool` (branch `main`)
- Check version qua `raw.githubusercontent.com` (kèm timestamp `?t=...` để bypass CDN cache)
- Tải ZIP, giải nén, copy file theo whitelist (`UPDATE_INCLUDES`)
- **Không ghi đè** file dữ liệu user (`UPDATE_EXCLUDES`)
- Restart an toàn: dùng `ping -n 3` delay 2s + `os._exit(0)`

---

## 6. Quy tắc Lọc & Định dạng (Rules A-M)

| Rule | Mô tả |
|---|---|
| **A** | Chỉ lấy chat liên quan đến user (task, troubleshooting, business, HR, meeting) → lọc bỏ gossip, đồ ăn, xe cộ |
| **B** | Tiêu đề: `[Hành động] - [Mục tiêu]`, **≥50 ký tự** |
| **E** | **Không tự đoán project** → luôn hỏi user |
| **F** | Luôn quét phòng "Notification" / "Petition" (lịch họp, đơn từ) |
| **G** | Luôn quét DM / private chat có hoạt động trong ngày |
| **H** | Blacklist phòng: `HorusXamF`, `ComNuoc`, `CoThucMoiVucDcDao`, `CungNhauGiamCan` (+ tùy chỉnh) |
| **I** | Tất cả task đánh `status: "Done"` |
| **J** | Sprint: `"latest"` (Sprint mới nhất) |
| **K** | Date: `YYYY-MM-DD` (ngày làm việc) |
| **L** | Tổng giờ = 8.0h, phân bổ đều |
| **M** | Sửa KPI: chỉ dựa vào "Lý do chưa đạt", **bỏ qua "Gợi ý"** |

---

## 7. Công nghệ & Phụ thuộc

| Công nghệ | Vai trò |
|---|---|
| **Python 3.10/3.12** | Ngôn ngữ chính |
| **FastAPI + uvicorn** | Backend REST API |
| **pywebview + WebView2** | Desktop UI (nhúng browser) |
| **requests** | HTTP client (API calls) |
| **PyInstaller** | Đóng gói thành `.exe` |
| **Google Gemini / OpenAI / DeepSeek** | AI providers để lọc & sinh nội dung |

---

## 8. File Dữ liệu & Trạng thái

| File | Mục đích |
|---|---|
| `chat_raw.json` | Dữ liệu chat thô sau sync (tạm, reset mỗi lần chạy) |
| `git_raw.json` | Dữ liệu git commit thô (tạm) |
| `saved_raw_tasks.json` | Task đã AI trích xuất + trạng thái (active/hide), giữ trong ngày |
| `approved_tasks.json` | Danh sách task đã user duyệt + gán project |
| `memorytask.md` | Nội dung task chuẩn bị nhập WorkAI |
| `tasks.json` | Task object có metadata (status, sprint, date) → input cho submitter |
| `submitted.json` | Hash fingerprint các task đã nộp (chống duplicate) |
| `submission_status.json` | Trạng thái tiến trình nộp (real-time) |
| `last_sync.txt` | Timestamp lần sync cuối |

---

## 9. Luồng Cập nhật Ứng dụng

```
[User click "Cập nhật"]
  → GET version.json từ GitHub (có timestamp bypass CDN)
  → So sánh version → nếu mới hơn:
      → GET ZIP từ github.com/.../archive/main.zip (~100KB)
      → Giải nén → copy file .py + static/ đè lên thư mục gốc
      → Bỏ qua .env, config.json, projects.json...
      → Restart app (ping delay 2s + os._exit)
```

---

## 10. Bảo mật

- `.env` và `config.json` nằm trong `.gitignore`, **không bao giờ** bị ghi đè khi cập nhật
- Token Rocket.Chat, password WorkAI lưu local, không lộ ra ngoài
- `UPDATE_EXCLUDES` đảm bảo dữ liệu cá nhân không bị xóa khi update
- App chỉ chạy local (`127.0.0.1:8000`), không expose ra mạng
