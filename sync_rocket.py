import os
import json
import requests
from datetime import datetime, timezone

import sys
def load_env(path=".env"):
    # Thử tìm file .env trong thư mục chứa file chạy (.exe khi đóng gói)
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
        path = os.path.join(base_dir, ".env")
        
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

def parse_ejson_date(date_field):
    """
    Parses a Rocket.Chat EJSON date field which can be:
    - A dictionary: {"$date": epoch_ms}
    - An integer/float: epoch_ms
    - A string: ISO date string
    Returns epoch milliseconds or None if invalid.
    """
    if not date_field:
        return None
    if isinstance(date_field, dict):
        return date_field.get("$date")
    if isinstance(date_field, (int, float)):
        return int(date_field)
    if isinstance(date_field, str):
        try:
            # Simple ISO parse fallback (strip Z and parse)
            dt_str = date_field.replace("Z", "+00:00")
            dt = datetime.fromisoformat(dt_str)
            return int(dt.timestamp() * 1000)
        except Exception:
            return None
    return None

def main(last_sync_ms=None):
    env = load_env()
    server_url = env.get("ROCKET_SERVER_URL", "").rstrip("/")
    user_id = env.get("ROCKET_USER_ID")
    auth_token = env.get("ROCKET_AUTH_TOKEN")

    if not server_url or not user_id or not auth_token:
        print("[ERROR] Rocket.Chat configurations are missing in .env file.")
        return

    # Load excluded rooms blacklist from config.json
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(base_dir, "config.json")
    
    excluded_rooms = []
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                excluded_rooms = [r.strip().lower() for r in cfg.get("excluded_rooms", []) if r.strip()]
        except Exception as e:
            print(f"[WARNING] Failed to load config.json: {e}")

    # Merge with ROCKET_EXCLUDED_ROOMS from .env for backward compatibility
    excluded_rooms_raw = env.get("ROCKET_EXCLUDED_ROOMS", "")
    if excluded_rooms_raw:
        for r in excluded_rooms_raw.split(","):
            r_clean = r.strip().lower()
            if r_clean and r_clean not in excluded_rooms:
                excluded_rooms.append(r_clean)

    print(f"Loaded {len(excluded_rooms)} excluded rooms from blacklist: {excluded_rooms}")

    headers = {
        "X-User-Id": user_id,
        "X-Auth-Token": auth_token,
        "Content-Type": "application/json"
    }

    # Fetch logged-in user details to get exact name and username
    me_url = f"{server_url}/api/v1/me"
    me_name = ""
    me_username = ""
    try:
        me_res = requests.get(me_url, headers=headers, timeout=10)
        if me_res.status_code == 200:
            me_data = me_res.json()
            if me_data.get("success"):
                me_name = me_data.get("name", "")
                me_username = me_data.get("username", "")
                print(f"[INFO] Logged in Rocket.Chat user: {me_name} (@{me_username})")
                
                # Update config.json with Rocket.Chat name if it's currently empty, default, or doesn't match
                if os.path.exists(config_file):
                    with open(config_file, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    
                    cfg_changed = False
                    if not cfg.get("name") or cfg.get("name") == "Chu Văn Mai":
                        cfg["name"] = me_name
                        cfg_changed = True
                    if cfg.get("rocket_username") != me_username:
                        cfg["rocket_username"] = me_username
                        cfg_changed = True
                        
                    if cfg_changed:
                        with open(config_file, "w", encoding="utf-8") as f:
                            json.dump(cfg, f, ensure_ascii=False, indent=2)
                        print(f"[INFO] Updated config.json name to: {cfg['name']}, rocket_username to: {me_username}")
    except Exception as e:
        print(f"[WARNING] Failed to fetch user details from /api/v1/me: {e}")

    
    local_tz = datetime.now().astimezone().tzinfo
    
    if last_sync_ms:
        # Giảm 2 phút (120,000 ms) buffer để chống lệch múi giờ/lệch đồng hồ client-server
        start_ms = last_sync_ms - 120000
        start_dt = datetime.fromtimestamp(start_ms / 1000.0, tz=local_tz)
    else:
        # Default: từ 0h sáng hôm nay
        start_dt = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        start_ms = int(start_dt.timestamp() * 1000)
        
    oldest_iso = start_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    print(f"Filtering active rooms since {start_dt.isoformat()}...")

    # 1. Get subscriptions (all rooms the user is in)
    sub_url = f"{server_url}/api/v1/subscriptions.get"
    try:
        response = requests.get(sub_url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"[ERROR] Failed to fetch subscriptions. HTTP {response.status_code}: {response.text}")
            return
        
        data = response.json()
        if not data.get("success"):
            print(f"[ERROR] Rocket.Chat API returned success=false: {data}")
            return
            
        subscriptions = data.get("update", [])
        print(f"Successfully retrieved {len(subscriptions)} subscriptions/rooms.")
    except Exception as e:
        print(f"[ERROR] Network error connecting to Rocket.Chat: {e}")
        return

    collected_chats = []
    active_rooms = []

    for sub in subscriptions:
        rid = sub.get("rid")
        room_name = sub.get("name") or sub.get("fname") or f"Room_{rid}"
        room_type = sub.get("t") # 'c' channel, 'd' DM, 'p' private group
        
        if not rid:
            continue
            
        # Parse names for blacklisting
        name_lower = (sub.get("name") or "").lower()
        fname_lower = (sub.get("fname") or "").lower()
        rid_lower = (sub.get("rid") or "").lower()
        
        # Apply Blacklist Filter
        is_blacklisted = False
        for ex in excluded_rooms:
            if ex in name_lower or ex in fname_lower or ex in rid_lower:
                is_blacklisted = True
                break
                
        if is_blacklisted:
            # Skip blacklisted room silently
            continue
            
        # Parse Last Message (lm) and Updated At (_updatedAt)
        lm = sub.get("lm")
        updated_at = sub.get("_updatedAt")
        
        lm_ms = parse_ejson_date(lm)
        updated_ms = parse_ejson_date(updated_at)
        
        # Check if the room had messages today or was updated today
        had_activity_today = False
        if lm_ms and lm_ms >= start_ms:
            had_activity_today = True
        elif updated_ms and updated_ms >= start_ms:
            had_activity_today = True
            
        # Additional Fallback: Let's also include notification and petition channels explicitly to be 100% safe
        if "notification" in name_lower or "notification" in fname_lower or "petition" in name_lower or "petition" in fname_lower:
            had_activity_today = True

        if had_activity_today:
            active_rooms.append(sub)

    print(f"Identified {len(active_rooms)} active rooms today (after applying blacklist). Fetching history...")

    for sub in active_rooms:
        rid = sub.get("rid")
        room_name = sub.get("name") or sub.get("fname") or f"Room_{rid}"
        room_type = sub.get("t")
        
        # Determine history API endpoint based on room type
        if room_type == 'c':
            history_url = f"{server_url}/api/v1/channels.history"
        elif room_type == 'p':
            history_url = f"{server_url}/api/v1/groups.history"
        elif room_type == 'd':
            history_url = f"{server_url}/api/v1/im.history"
        else:
            continue

        params = {
            "roomId": rid,
            "oldest": oldest_iso,
            "count": 200
        }

        try:
            res = requests.get(history_url, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                history_data = res.json()
                if history_data.get("success"):
                    messages = history_data.get("messages", [])
                    if messages:
                        print(f"   [+] Fetched {len(messages)} messages from '{room_name}' ({room_type})")
                        formatted_messages = []
                        for msg in reversed(messages):
                            msg_user = msg.get("u", {}).get("name") or msg.get("u", {}).get("username") or "Unknown"
                            msg_text = msg.get("msg", "")
                            msg_ts = msg.get("ts", "")
                            
                            if not msg_text and msg.get("t"):
                                continue
                                
                            formatted_messages.append({
                                "sender": msg_user,
                                "text": msg_text,
                                "timestamp": msg_ts
                            })
                        
                        if formatted_messages:
                            collected_chats.append({
                                "room_id": rid,
                                "room_name": room_name,
                                "room_type": room_type,
                                "messages": formatted_messages
                            })
            else:
                # Skip silent restrictions
                pass
        except Exception as e:
            print(f"[WARNING] Failed to fetch history for room {room_name}: {e}")

    # Save to JSON file
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(base_dir, "chat_raw.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(collected_chats, f, ensure_ascii=False, indent=2)
        
    print(f"\n[SUCCESS] Sync completed! Saved raw chat history to '{output_file}'.")
    print(f"Total active rooms today captured: {len(collected_chats)}")

if __name__ == "__main__":
    main()
