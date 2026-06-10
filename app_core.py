import threading
import uvicorn
import webview
from fastapi import FastAPI, HTTPException, Body, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import sys
import json

APP_VERSION = "1.0.0"

app = FastAPI(title="Athena Assistant App")

# Cấu hình đường dẫn
if getattr(sys, 'frozen', False):
    RESOURCE_DIR = sys._MEIPASS
    RUNNING_DIR = os.path.dirname(sys.executable)
    # Đảm bảo thư mục làm việc hiện tại là thư mục chứa file .exe
    os.chdir(RUNNING_DIR)
else:
    RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
    RUNNING_DIR = RESOURCE_DIR

BASE_DIR = RUNNING_DIR

# Static: ưu tiên thư mục local (cập nhật qua GitHub) > bundled
_local_static = os.path.join(RUNNING_DIR, "static")
if os.path.isdir(_local_static):
    STATIC_DIR = _local_static
else:
    STATIC_DIR = os.path.join(RESOURCE_DIR, "static")

CONFIG_FILE = os.path.join(RUNNING_DIR, "config.json")

# Gắn thư mục static (CSS, JS)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        return {"error": "index.html not found in static folder."}
    return FileResponse(index_path)

# --- Các model dữ liệu ---
class LoginRequest(BaseModel):
    username: str
    password: str

class UpdateProjectRequest(BaseModel):
    id: str
    project_code: str

# --- API Endpoints ---
@app.post("/api/login")
def login(req: LoginRequest):
    # Tạm thời hardcode pass để khóa app, hoặc lưu trong config
    if req.username == "admin" and req.password == "123456":
        return {"status": "success"}
    raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

PROJECTS_FILE = os.path.join(BASE_DIR, "projects.json")

@app.get("/api/projects")
def get_projects():
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
            return {"projects": json.load(f)}
    return {"projects": []}

@app.get("/api/projects/scan")
def scan_projects():
    # To fetch from actual WorkAI, we need credentials from config.json or .env
    # For now, let's load from .env
    env_path = os.path.join(BASE_DIR, ".env")
    username = ""
    password = ""
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("WORKAI_USERNAME="):
                    username = line.split("=", 1)[1].strip()
                elif line.startswith("WORKAI_PASSWORD="):
                    password = line.split("=", 1)[1].strip()
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Thiếu WorkAI Username/Password trong .env hoặc Setup")

    from workai_scraper import scan_workai_projects
    try:
        projects = scan_workai_projects(username, password)
        with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)
        return {"projects": projects}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_current_day_tasks():
    import time
    from datetime import datetime
    local_tz = datetime.now().astimezone().tzinfo
    today_midnight = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    today_midnight_ms = int(today_midnight.timestamp() * 1000)

    saved_tasks_file = os.path.join(BASE_DIR, "saved_raw_tasks.json")
    tasks = []
    if os.path.exists(saved_tasks_file):
        try:
            with open(saved_tasks_file, "r", encoding="utf-8") as f:
                tasks = json.load(f)
        except Exception as e:
            print("Lỗi đọc file saved_raw_tasks.json:", e)

    # Filter out tasks from previous days
    current_tasks = []
    has_old_tasks = False
    for t in tasks:
        t_id = t.get("id", "")
        if t_id.startswith("task_"):
            try:
                parts = t_id.split("_")
                if len(parts) >= 2:
                    ts = int(parts[1])
                    if ts >= today_midnight_ms:
                        current_tasks.append(t)
                    else:
                        has_old_tasks = True
                else:
                    has_old_tasks = True
            except ValueError:
                has_old_tasks = True
        else:
            has_old_tasks = True

    # If there were old tasks, clean them up from the file
    if has_old_tasks and os.path.exists(saved_tasks_file):
        try:
            with open(saved_tasks_file, "w", encoding="utf-8") as f:
                json.dump(current_tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Lỗi dọn dẹp task cũ:", e)

    return current_tasks

sync_lock = threading.Lock()

@app.post("/api/run/tonghop")
def run_tonghop(force: bool = False):
    if not sync_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Tiến trình tổng hợp đang chạy, vui lòng đợi.")
    try:
        import time
        from datetime import datetime, timezone
        
        local_tz = datetime.now().astimezone().tzinfo
        now_ms = int(time.time() * 1000)
        today_midnight = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        today_midnight_ms = int(today_midnight.timestamp() * 1000)
        
        last_sync_ms = today_midnight_ms
        sync_file = os.path.join(BASE_DIR, "last_sync.txt")
        
        if force:
            if os.path.exists(sync_file):
                try:
                    os.remove(sync_file)
                except:
                    pass
        else:
            if os.path.exists(sync_file):
                try:
                    with open(sync_file, "r") as f:
                        stored_ms = int(f.read().strip())
                    if stored_ms > today_midnight_ms:
                        last_sync_ms = stored_ms
                except:
                    pass
                
        # Update last_sync.txt with current time BEFORE fetching so we don't miss incoming messages while fetching
        with open(sync_file, "w") as f:
            f.write(str(now_ms))

        import sync_rocket
        sync_rocket.main(last_sync_ms)
        
        # Run sync_git
        try:
            import sync_git
            sync_git.main(last_sync_ms)
        except Exception as e:
            print("Lỗi chạy sync_git:", e)

        # Run sync_email
        try:
            import sync_email
            sync_email.main(last_sync_ms)
        except Exception as e:
            print("Lỗi chạy sync_email:", e)
        
        # Read the generated chat_raw.json and git_raw.json

        raw_path = os.path.join(BASE_DIR, "chat_raw.json")
        git_path = os.path.join(BASE_DIR, "git_raw.json")
        
        raw_data = []
        if os.path.exists(raw_path):
            with open(raw_path, "r", encoding="utf-8") as f:
                raw_data.extend(json.load(f))
                
        if os.path.exists(git_path):
            with open(git_path, "r", encoding="utf-8") as f:
                git_data = json.load(f)
                if isinstance(git_data, list):
                    raw_data.extend(git_data)
        
        # Load saved state (chỉ lấy task trong ngày hiện tại)
        saved_tasks = get_current_day_tasks()
        saved_tasks_file = os.path.join(BASE_DIR, "saved_raw_tasks.json")

        config = load_config()
        if raw_data:
            # Use AI to summarize the raw data into candidate tasks
            from ai_processor import summarize_raw_chat
            provider = config.get("ai_provider", "gemini")
            api_key = config.get("ai_key", "")
            user_name = config.get("name", "Chu Văn Mai")
            user_role = config.get("role", "PM")
            rocket_username = config.get("rocket_username", "")
            
            # Read projects
            projects_list = []
            if os.path.exists(PROJECTS_FILE):
                with open(PROJECTS_FILE, "r", encoding="utf-8") as pf:
                    projects_list = json.load(pf)
            
            try:
                summarized_json_str = summarize_raw_chat(raw_data, provider, api_key, projects_list, user_name, user_role, rocket_username)
                new_tasks = json.loads(summarized_json_str)
                # Assign unique ID (just timestamp + index) and status active
                for i, t in enumerate(new_tasks):
                    t["id"] = f"task_{now_ms}_{i}"
                    t["status"] = "active"
                saved_tasks.extend(new_tasks)
            except Exception as e:
                # Fallback to flattening if AI fails
                print(f"Lỗi khi tóm tắt AI: {e}")
                for i, room in enumerate(raw_data):
                    for j, msg in enumerate(room.get("messages", [])):
                        saved_tasks.append({
                            "id": f"task_{now_ms}_{i}_{j}",
                            "status": "active",
                            "room_name": room.get("room_name"),
                            "sender": msg.get("sender"),
                            "text": msg.get("text"),
                            "original_chat": f"{msg.get('sender')}: {msg.get('text')}"
                        })
                        
        # Save back the state
        with open(saved_tasks_file, "w", encoding="utf-8") as f:
            json.dump(saved_tasks, f, ensure_ascii=False, indent=2)
            
        # Return only active tasks
        active_tasks = [t for t in saved_tasks if t.get("status") != "hide"]
        
        return {"status": "success", "tasks": active_tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        sync_lock.release()

@app.post("/api/raw_tasks/hide")
def hide_raw_task(request: dict):
    task_id = request.get("id")
    if not task_id:
        raise HTTPException(status_code=400, detail="Missing task id")
    
    tasks = get_current_day_tasks()
    for t in tasks:
        if t.get("id") == task_id:
            t["status"] = "hide"
            break
    saved_tasks_file = os.path.join(BASE_DIR, "saved_raw_tasks.json")
    with open(saved_tasks_file, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    return {"status": "success"}

@app.post("/api/raw_tasks/update_project")
def update_raw_task_project(req: UpdateProjectRequest):
    tasks = get_current_day_tasks()
    for t in tasks:
        if t.get("id") == req.id:
            t["project_code"] = req.project_code
            break
    saved_tasks_file = os.path.join(BASE_DIR, "saved_raw_tasks.json")
    with open(saved_tasks_file, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    return {"status": "success"}

@app.post("/api/raw_tasks/restore")
def restore_raw_tasks():
    tasks = get_current_day_tasks()
    for t in tasks:
        t["status"] = "active"
    saved_tasks_file = os.path.join(BASE_DIR, "saved_raw_tasks.json")
    with open(saved_tasks_file, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    
    active_tasks = [t for t in tasks if t.get("status") != "hide"]
    return {"status": "success", "tasks": active_tasks}

@app.post("/api/kpi/scan_and_fix")
def scan_and_fix_kpi():
    try:
        config = load_config()
        # Fallback to .env if config is empty
        username = config.get("workai_user", "")
        password = config.get("workai_pass", "")
        
        if not username or not password:
            env_path = os.path.join(BASE_DIR, ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("WORKAI_USERNAME="):
                            username = line.split("=", 1)[1].strip()
                        elif line.startswith("WORKAI_PASSWORD="):
                            password = line.split("=", 1)[1].strip()
                            
        if not username or not password:
            raise HTTPException(status_code=400, detail="Thiếu WorkAI Username/Password. Vui lòng cài đặt trước.")

        from workai_scraper import scan_workai_kpis
        from ai_processor import fix_kpi_tasks
        
        # 1. Quét KPI
        raw_kpi_tasks = scan_workai_kpis(username, password)
        
        if not raw_kpi_tasks:
            return {"status": "success", "tasks": []}
            
        # 2. Gọi AI sửa
        provider = config.get("ai_provider", "gemini")
        api_key = config.get("ai_key", "")
        user_name = config.get("name", "Chu Văn Mai")
        user_role = config.get("role", "PM")
        
        fixed_tasks = fix_kpi_tasks(raw_kpi_tasks, provider, api_key, user_name, user_role)
        
        # Lưu vào saved_kpi_tasks.json
        kpi_file = os.path.join(BASE_DIR, "saved_kpi_tasks.json")
        with open(kpi_file, "w", encoding="utf-8") as f:
            json.dump(fixed_tasks, f, ensure_ascii=False, indent=2)
            
        return {"status": "success", "tasks": fixed_tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/setup")
def save_setup(data: dict):
    platforms = data.get("platforms", [])

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Also write WORKAI_USERNAME and PASSWORD to .env so old scripts work
    env_path = os.path.join(BASE_DIR, ".env")
    env_data = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.split("=", 1)
                    env_data[k.strip()] = v.strip()
                    
    if "workai_user" in data:
        env_data["WORKAI_USERNAME"] = data["workai_user"]
    if "workai_pass" in data:
        env_data["WORKAI_PASSWORD"] = data["workai_pass"]
        
    for p in platforms:
        if p.get("type") == "rocket":
            if "url" in p: env_data["ROCKET_SERVER_URL"] = p["url"]
            if "uid" in p: env_data["ROCKET_USER_ID"] = p["uid"]
            if "token" in p: env_data["ROCKET_AUTH_TOKEN"] = p["token"]
        elif p.get("type") == "email":
            if "url" in p: env_data["EMAIL_IMAP_SERVER"] = p["url"]
            if "uid" in p: env_data["EMAIL_USER"] = p["uid"]
            if "token" in p: env_data["EMAIL_PASS"] = p["token"]
        elif p.get("type") == "slack":
            if "token" in p: env_data["SLACK_BOT_TOKEN"] = p["token"]
        elif p.get("type") == "telegram":
            if "url" in p: env_data["TELEGRAM_CHAT_ID"] = p["url"]
            if "token" in p: env_data["TELEGRAM_BOT_TOKEN"] = p["token"]
        
    excluded_rooms = data.get("excluded_rooms", [])
    if excluded_rooms:
        env_data["ROCKET_EXCLUDED_ROOMS"] = ",".join(excluded_rooms)
    else:
        env_data["ROCKET_EXCLUDED_ROOMS"] = ""

    with open(env_path, "w", encoding="utf-8") as f:
        for k, v in env_data.items():
            f.write(f"{k}={v}\n")
            
    return {"status": "success"}

# --- Microsoft Teams OAuth Endpoints removed ---

@app.get("/api/raw_tasks")

def get_raw_tasks():
    try:
        tasks = get_current_day_tasks()
        active_tasks = [t for t in tasks if t.get("status") != "hide"]
        return {"status": "success", "tasks": active_tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/taoviec/content")
def get_taoviec_content():
    file_path = os.path.join(BASE_DIR, "memorytask.md")
    if not os.path.exists(file_path):
        return {"status": "success", "content": "Chưa có dữ liệu. Hãy bấm \"2. Tạo việc\"."}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"status": "success", "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/kpi/content")
def get_kpi_content():
    kpi_file = os.path.join(BASE_DIR, "saved_kpi_tasks.json")
    if os.path.exists(kpi_file):
        try:
            with open(kpi_file, "r", encoding="utf-8") as f:
                tasks = json.load(f)
            return {"status": "success", "tasks": tasks}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {"status": "success", "tasks": []}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@app.get("/api/config")
def get_config():
    return load_config()

@app.post("/api/run/taoviec")
def run_taoviec():
    config = load_config()
    provider = config.get("ai_provider", "gemini")
    api_key = config.get("ai_key", "")
    
    raw_path = os.path.join(BASE_DIR, "saved_raw_tasks.json")
    if not os.path.exists(raw_path):
        raise HTTPException(status_code=400, detail="Không tìm thấy saved_raw_tasks.json. Hãy Tổng hợp trước.")
        
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    tasks_to_process = [t for t in raw_data if t.get("status") != "hide"]
            
    if not tasks_to_process:
        return {"status": "success", "content": "Không có task nào để xử lý."}
        
    from ai_processor import generate_tasks
    try:
        markdown_content = generate_tasks(tasks_to_process, provider, api_key)
        
        # Save to memorytask.md
        with open(os.path.join(BASE_DIR, "memorytask.md"), "w", encoding="utf-8") as f:
            f.write(markdown_content)
            
        return {"status": "success", "content": markdown_content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def run_submitter_process():
    import subprocess
    import sys
    try:
        status_file = os.path.join(BASE_DIR, "submission_status.json")
        result = subprocess.run([sys.executable, "submitter.py"], cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            # Check if it didn't write error status
            has_error = False
            if os.path.exists(status_file):
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data.get("status") == "error":
                            has_error = True
                except:
                    pass
            if not has_error:
                error_msg = result.stderr or result.stdout or "Lỗi không xác định"
                with open(status_file, "w", encoding="utf-8") as f:
                    json.dump({"status": "error", "current": 0, "total": 0, "msg": f"Lỗi thực thi: {error_msg}"}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        status_file = os.path.join(BASE_DIR, "submission_status.json")
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump({"status": "error", "current": 0, "total": 0, "msg": f"Lỗi khởi chạy: {str(e)}"}, f, ensure_ascii=False, indent=2)

@app.post("/api/run/nhapviec")
def run_nhapviec():
    try:
        memory_path = os.path.join(BASE_DIR, "memorytask.md")
        if not os.path.exists(memory_path):
            raise Exception("Không tìm thấy memorytask.md. Hãy Tạo việc trước.")
            
        with open(memory_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # Very basic parser for memorytask.md -> tasks.json
        parsed_tasks = []
        current_task = {}
        for line in lines:
            line = line.strip()
            if line.startswith("## Task"):
                if current_task and "title" in current_task:
                    current_task["status"] = "Done"
                    current_task["sprint"] = "latest"
                    from datetime import datetime
                    current_task["date"] = datetime.now().strftime("%Y-%m-%d")
                    parsed_tasks.append(current_task)
                current_task = {}
            elif line.startswith("- **Project**:"):
                current_task["project"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **Title**:"):
                current_task["title"] = line.split(":", 1)[1].strip()
                    
        if current_task and "title" in current_task:
            current_task["status"] = "Done"
            current_task["sprint"] = "latest"
            from datetime import datetime
            current_task["date"] = datetime.now().strftime("%Y-%m-%d")
            parsed_tasks.append(current_task)
            
        with open(os.path.join(BASE_DIR, "tasks.json"), "w", encoding="utf-8") as f:
            json.dump(parsed_tasks, f, ensure_ascii=False, indent=2)

        # Reset status file
        status_file = os.path.join(BASE_DIR, "submission_status.json")
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump({"status": "running", "current": 0, "total": len(parsed_tasks), "msg": "Đang chuẩn bị khởi động kịch bản..."}, f, ensure_ascii=False, indent=2)

        # Run submitter in a separate thread
        thread = threading.Thread(target=run_submitter_process, daemon=True)
        thread.start()
        
        return {"status": "success", "message": "Tiến trình nhập việc đã được khởi chạy ngầm."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/run/nhapviec/status")
def run_nhapviec_status():
    status_file = os.path.join(BASE_DIR, "submission_status.json")
    if os.path.exists(status_file):
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"status": "error", "current": 0, "total": 0, "msg": f"Không thể đọc file trạng thái: {str(e)}"}
    return {"status": "idle", "current": 0, "total": 0, "msg": "Chưa chạy tiến trình nhập việc."}

class ChatRequest(BaseModel):
    message: str
    active_tab: str

def try_repair_json(broken_json_str):
    """Cố gắng sửa chữa JSON bị cắt ngắn (truncated) từ AI.
    Trả về parsed object nếu sửa được, None nếu không."""
    import re
    s = broken_json_str.strip()
    
    # Loại bỏ markdown code fences nếu có
    if s.startswith("```json"):
        s = s[7:]
    elif s.startswith("```"):
        s = s[3:]
    if s.endswith("```"):
        s = s[:-3]
    s = s.strip()
    
    # Thử parse trực tiếp trước
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    
    # Cố gắng sửa JSON Array bị cắt ngắn
    # Tìm vị trí object cuối cùng hoàn chỉnh (kết thúc bằng "}")
    if s.startswith("["):
        # Tìm vị trí "}" cuối cùng
        last_brace = s.rfind("}")
        if last_brace > 0:
            # Cắt đến "}" cuối cùng và đóng mảng
            candidate = s[:last_brace + 1].rstrip().rstrip(",") + "\n]"
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
    
    # Cố gắng sửa JSON Object bị cắt ngắn (patch mode)
    if s.startswith("{"):
        # Tìm new_tasks array
        new_tasks_idx = s.find('"new_tasks"')
        if new_tasks_idx > 0:
            # Tìm vị trí "}" cuối cùng của object cuối trong new_tasks
            last_brace = s.rfind("}")
            if last_brace > 0:
                # Đóng mảng new_tasks và đóng object cha
                candidate = s[:last_brace + 1].rstrip().rstrip(",") + "\n]\n}"
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
    
    return None

@app.post("/api/chat")
def ai_chat(req: ChatRequest):
    config = load_config()
    provider = config.get("ai_provider", "gemini")
    api_key = config.get("ai_key", "")
    
    # Depending on active tab, we edit raw_tasks or memorytask
    from ai_processor import edit_task_with_ai, edit_raw_tasks_with_ai
    
    try:
        if req.active_tab == "tab-processed":
            file_path = os.path.join(BASE_DIR, "memorytask.md")
            if not os.path.exists(file_path):
                return {"reply": "Chưa có file memorytask.md để sửa."}
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            new_content = edit_task_with_ai(content, req.message, provider, api_key)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
                
            return {"reply": "Đã cập nhật lại nội dung ở Tab 2. Bạn hãy tải lại/chuyển tab để xem."}
        elif req.active_tab == "tab-raw":
            file_path = os.path.join(BASE_DIR, "saved_raw_tasks.json")
            if not os.path.exists(file_path):
                return {"reply": "Chưa có file saved_raw_tasks.json để sửa. Hãy Tổng hợp trước."}
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            new_content = edit_raw_tasks_with_ai(content, req.message, provider, api_key)
            
            # Thử parse JSON
            try:
                parsed = json.loads(new_content)
            except json.JSONDecodeError:
                # Thử sửa chữa JSON bị cắt ngắn (truncated)
                parsed = try_repair_json(new_content)
                if parsed is None:
                    print(f"Lỗi AI trả về JSON không hợp lệ. Nội dung: {new_content[:500]}...")
                    return {"reply": "Lỗi: AI trả về định dạng dữ liệu không hợp lệ. Vui lòng thử lại với yêu cầu rõ ràng hơn."}
            
            # Xử lý 2 chế độ phản hồi
            import time
            now_ms = int(time.time() * 1000)
            
            if isinstance(parsed, dict) and parsed.get("mode") == "patch":
                # CHẾ ĐỘ 2: Patch mode - AI chỉ trả về thay đổi
                existing_tasks = json.loads(content)
                
                # Ẩn các task gốc
                hide_ids = parsed.get("hide_ids", [])
                for t in existing_tasks:
                    if t.get("id") in hide_ids:
                        t["status"] = "hide"
                
                # Thêm các task mới
                new_tasks = parsed.get("new_tasks", [])
                for i, nt in enumerate(new_tasks):
                    nt["id"] = f"task_{now_ms}_{i}"
                    nt["status"] = "active"
                    existing_tasks.append(nt)
                
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(existing_tasks, f, ensure_ascii=False, indent=2)
                return {"reply": f"Đã tách/tạo thành công {len(new_tasks)} task mới ở Tab 1. Bạn hãy làm mới nội dung để xem."}
            
            elif isinstance(parsed, list):
                # CHẾ ĐỘ 1: Full array mode - AI trả về toàn bộ mảng
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(parsed, f, ensure_ascii=False, indent=2)
                return {"reply": "Đã cập nhật xong danh sách ở Tab 1. Bạn hãy làm mới nội dung để xem."}
            
            else:
                print(f"AI trả về kiểu dữ liệu không mong đợi: {type(parsed)}")
                return {"reply": "Lỗi: AI trả về định dạng dữ liệu không hợp lệ. Vui lòng thử lại với yêu cầu rõ ràng hơn."}
        else:
            return {"reply": "Tính năng sửa Tab này đang được phát triển."}
            
    except Exception as e:
        return {"reply": f"Lỗi AI: {str(e)}"}

class TestAIRequest(BaseModel):
    provider: str
    api_key: str

@app.post("/api/test/ai")
def test_ai(req: TestAIRequest):
    from ai_processor import call_ai_provider
    try:
        reply = call_ai_provider(req.provider, req.api_key, "Hãy trả lời ngắn gọn là 'Kết nối thành công!'", "Hello")
        return {"status": "success", "message": f"Thành công! Trả lời từ AI: {reply}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class TestWorkAIRequest(BaseModel):
    username: str
    password: str

@app.post("/api/test/workai")
def test_workai(req: TestWorkAIRequest):
    from workai_scraper import test_workai_login
    success, msg = test_workai_login(req.username, req.password)
    if success:
        return {"status": "success", "message": msg}
    else:
        return {"status": "error", "message": msg}

# ============================================================
# UPDATE API ENDPOINTS
# ============================================================

@app.get("/api/version")
def get_version(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    local_ver = APP_VERSION
    try:
        import updater
        local_ver = updater.get_local_version(BASE_DIR) or APP_VERSION
    except Exception:
        pass
    return {"version": local_ver}

@app.get("/api/update/check")
def check_for_update(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    try:
        import updater
        current = updater.get_local_version(BASE_DIR) or APP_VERSION
        return updater.check_update(current)
    except Exception as e:
        return {"has_update": False, "error": str(e)}

@app.post("/api/update/apply")
def apply_update_endpoint():
    try:
        import updater
        result = updater.apply_update(BASE_DIR)
        if result.get("success"):
            # Schedule restart sau 2 giây
            def do_restart():
                import time
                import subprocess
                time.sleep(2)
                
                exe_path = sys.executable
                args_str = " ".join([f'"{a}"' for a in sys.argv[1:]])
                
                if os.name == 'nt':
                    cmd = f'timeout /t 2 & start "" "{exe_path}" {args_str}'
                    subprocess.Popen(cmd, shell=True)
                else:
                    os.execv(exe_path, [exe_path] + sys.argv)
                os._exit(0)
            threading.Thread(target=do_restart, daemon=True).start()
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

def run(running_dir, app_version):
    global BASE_DIR, APP_VERSION
    BASE_DIR = running_dir
    APP_VERSION = app_version

    # Khởi chạy FastAPI trong một thread riêng để không block pywebview
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Khởi tạo cửa sổ Desktop bằng pywebview
    webview.create_window(
        title="Athena Assistant", 
        url="http://127.0.0.1:8000/",
        width=1200, 
        height=800,
        min_size=(1024, 768)
    )
    # Block thread chính cho đến khi cửa sổ bị đóng
    webview.start()
