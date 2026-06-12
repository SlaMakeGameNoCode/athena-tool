import os
import json
import subprocess
from datetime import datetime

import sys

if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(base_dir, "config.json")
GIT_RAW_FILE = os.path.join(base_dir, "git_raw.json")

def main(last_sync_ms=None):
    if not os.path.exists(CONFIG_FILE):
        with open(GIT_RAW_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    platforms = config.get("platforms", [])
    git_platforms = [p for p in platforms if p.get("type") == "git"]
    
    if not git_platforms:
        with open(GIT_RAW_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return
        
    # Calculate since_str
    if last_sync_ms:
        from datetime import timezone, timedelta
        # Chuyển đổi timestamp sang timezone-aware datetime ở múi giờ Việt Nam (UTC+7)
        tz_vn = timezone(timedelta(hours=7))
        start_dt = datetime.fromtimestamp(last_sync_ms / 1000.0, tz=tz_vn)
        # Định dạng ISO 8601 có timezone (ví dụ: 2026-06-12T00:00:00+07:00)
        since_str = start_dt.strftime('%Y-%m-%dT%H:%M:%S%z')
        if len(since_str) >= 5 and (since_str[-5] == '+' or since_str[-5] == '-'):
            since_str = since_str[:-2] + ':' + since_str[-2:]
    else:
        since_str = "midnight"

    git_rooms = []
    
    for plat in git_platforms:
        folder_path = plat.get("url", "").strip()
        author = plat.get("uid", "").strip()
        
        if not folder_path or not os.path.exists(folder_path):
            continue
            
        try:
            # Chạy lệnh git log
            cmd = ['git', 'log', f'--author={author}', f'--since={since_str}', '--pretty=format:%s']
            
            result = subprocess.run(cmd, cwd=folder_path, capture_output=True, check=False)
            
            if result.returncode == 0 and result.stdout:
                stdout_str = result.stdout.decode('utf-8', errors='ignore')
                # Tách từng dòng commit
                commits = [line.strip() for line in stdout_str.split('\n') if line.strip()]
                
                if commits:
                    room_name = f"Git - {os.path.basename(folder_path)}"
                    messages = []
                    for c in commits:
                        # Bỏ qua các commit rác tự động của git như Merge branch
                        if c.startswith("Merge branch") or c.startswith("Merge pull request"):
                            continue
                        messages.append({
                            "sender": f"Git Commit ({author})",
                            "text": c
                        })
                    
                    if messages:
                        git_rooms.append({
                            "room_name": room_name,
                            "messages": messages
                        })
        except Exception as e:
            print(f"Lỗi khi quét Git tại {folder_path}: {e}")
            
    with open(GIT_RAW_FILE, "w", encoding="utf-8") as f:
        json.dump(git_rooms, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
