import os
import json
import datetime
from workai_api import WorkAIAPI

def load_config():
    config_file = "config.json"
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def load_env(path=".env"):
    env = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

def main(last_sync_ms=None, output_path=None):
    print("Bắt đầu đồng bộ Calendar từ WorkAI...")
    config = load_config()
    env = load_env()
    
    username = config.get("workai_user") or env.get("WORKAI_USERNAME")
    password = config.get("workai_pass") or env.get("WORKAI_PASSWORD")
    
    if not username or not password:
        print("[Calendar Sync] Thiếu thông tin tài khoản WorkAI.")
        return
        
    api = WorkAIAPI()
    success, msg = api.login(username, password)
    if not success:
        print(f"[Calendar Sync] Đăng nhập thất bại: {msg}")
        return
        
    # Tính khoảng ngày đồng bộ: từ 7 ngày trước đến hôm nay
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    
    print(f"[Calendar Sync] Fetching calendar từ {start_date} đến {end_date}")
    success, cal_res = api.get_calendar(start_date, end_date)
    if not success:
        print(f"[Calendar Sync] Lấy calendar thất bại: {cal_res}")
        return
        
    cal_data = cal_res.get("data", []) if isinstance(cal_res, dict) else []
    if not isinstance(cal_data, list) and isinstance(cal_data, dict):
        cal_data = cal_data.get("requests", [])
        
    events = []
    # Parse calendar events
    for item in cal_data:
        title = item.get("title") or item.get("summary") or ""
        date = item.get("start_date") or item.get("date") or ""
        if title and date:
            # Format event sang định dạng tin nhắn để AI dễ đọc và tóm tắt
            events.append({
                "sender": "Lịch họp",
                "text": f"Lịch họp: {title} vào ngày {date}",
                "date": date
            })
            
    if output_path and events:
        calendar_room = {
            "room_name": "WorkAI Calendar",
            "messages": events
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump([calendar_room], f, ensure_ascii=False, separators=(",", ":"))
        print(f"[Calendar Sync] Đã đồng bộ thành công {len(events)} sự kiện lịch.")
        return

    if output_path:
        return

    # Ghi nhận vào file chat_raw.json (gộp chung với các nguồn tin nhắn khác)
    chat_raw_path = "chat_raw.json"
    existing_chat = []
    if os.path.exists(chat_raw_path):
        try:
            with open(chat_raw_path, "r", encoding="utf-8") as f:
                existing_chat = json.load(f)
        except Exception:
            pass
            
    # Tạo cấu trúc room cho Lịch họp
    if events:
        calendar_room = {
            "room_name": "WorkAI Calendar",
            "messages": events
        }
        existing_chat.append(calendar_room)
        
        try:
            with open(chat_raw_path, "w", encoding="utf-8") as f:
                json.dump(existing_chat, f, ensure_ascii=False, separators=(",", ":"))
            print(f"[Calendar Sync] Đã đồng bộ thành công {len(events)} sự kiện lịch.")
        except Exception as e:
            print(f"[Calendar Sync] Lỗi lưu chat_raw.json: {e}")

if __name__ == "__main__":
    main()
