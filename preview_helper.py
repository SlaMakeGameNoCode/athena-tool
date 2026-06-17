"""
preview_helper.py — WorkAI Preview & Edit Helper via HTTP REST API
==================================================================
1. Chạy ngầm thay cho Playwright để quét/đồng bộ dữ liệu thực tế từ WorkAI (scan)
2. Cập nhật các thay đổi trực tiếp lên WorkAI thông qua REST API (update)
"""
import os
import sys
import json
import argparse
import time as _time
import hashlib
from workai_api import WorkAIAPI

if sys.stdout:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

STATUS_FILE = "preview_status.json"
PREVIEW_DATA_FILE = "preview_tasks.json"
PREVIEW_EDIT_FILE = "preview_tasks_edit.json"

def update_status(status, current, total, msg):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump({"status": status, "current": current, "total": total, "msg": msg}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARNING] Failed to write status: {e}")

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

def do_scan(api: WorkAIAPI, tasks):
    total = len(tasks)
    print(f"Bắt đầu quét {total} công việc...")
    
    # Lấy thông tin phân bổ thực tế từ WorkAI
    # Sử dụng start_date và end_date phù hợp dựa trên danh sách task
    import datetime
    dates = [t.get("date") for t in tasks if t.get("date")]
    if dates:
        dates.sort()
        start_date = dates[0]
        end_date = dates[-1]
    else:
        today = datetime.date.today()
        start_date = (today - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = (today + datetime.timedelta(days=7)).strftime("%Y-%m-%d")

    print(f"Quét phân bổ từ {start_date} đến {end_date}...")
    success, cal_res = api.get_calendar(start_date, end_date)
    
    # Hỗ trợ cache hoặc mapping danh sách issue
    scanned_results = []
    
    # Map issue key và ID bằng get_calendar hoặc query
    cal_data = cal_res.get("data", []) if success and isinstance(cal_res, dict) else []
    if not isinstance(cal_data, list) and isinstance(cal_data, dict):
        cal_data = cal_data.get("requests", [])
        
    # Tạo dictionary chứa thông tin chi tiết từng issue
    issue_details = {}
    # Lấy chi tiết issue từ calendar response nếu có
    for item in cal_data:
        # Tùy cấu trúc trả về, map issue key với description/acceptance criteria
        issue = item.get("issue") or item.get("issue_details") or {}
        if issue:
            key = issue.get("jira_issue_key") or issue.get("key") or ""
            if key:
                issue_details[key] = {
                    "description": issue.get("description") or "",
                    "acceptance_criteria": issue.get("acceptance_criteria") or ""
                }
                
    for idx, t in enumerate(tasks, 1):
        key = t.get("issue_key")
        title = t.get("title")
        print(f"[{idx}/{total}] Đang quét chi tiết công việc {key}...")
        update_status("running", idx - 1, total, f"Đang quét chi tiết công việc {idx}/{total}: {key}...")
        
        desc = t.get("description", "")
        ac = t.get("acceptance_criteria", "")
        
        # Nếu có thông tin từ lịch
        if key in issue_details:
            desc = issue_details[key].get("description") or desc
            ac = issue_details[key].get("acceptance_criteria") or ac
            
        scanned_results.append({
            "project": t.get("project", ""),
            "title": title,
            "description": desc,
            "acceptance_criteria": ac,
            "issue_key": key
        })
        
    with open(PREVIEW_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(scanned_results, f, ensure_ascii=False, indent=2)
        
    update_status("success", total, total, "Đã quét xong dữ liệu từ WorkAI!")
    print("[SUCCESS] Hoàn thành quét.")

def do_update(api: WorkAIAPI, tasks):
    total = len(tasks)
    print(f"Bắt đầu cập nhật {total} công việc...")
    
    import requests
    
    for idx, t in enumerate(tasks, 1):
        key = t.get("issue_key")
        title = t.get("title")
        summary_valid = t.get("summary_valid", True)
        description_valid = t.get("description_valid", True)
        
        if not key:
            print(f"[{idx}/{total}] Bỏ qua task không có issue_key")
            continue
            
        print(f"[{idx}/{total}] Đang cập nhật {key}...")
        update_status("running", idx - 1, total, f"Đang cập nhật công việc {idx}/{total}: {key}...")
        
        # Lấy ID của issue (để fallback nếu cập nhật qua key thất bại)
        issue_id = ""
        submitted_file = "submitted.json"
        if os.path.exists(submitted_file):
            try:
                with open(submitted_file, "r", encoding="utf-8") as sf:
                    submitted = json.load(sf)
                for fp, val in submitted.items():
                    if val.get("issue_key") == key:
                        issue_id = val.get("issue_id") or val.get("id") or ""
                        break
            except Exception:
                pass

        # ── BƯỚC 1: SỬA LỖI SUMMARY (NẾU CÓ) ──
        # Nếu summary không hợp lệ hoặc title bị thay đổi, tiến hành sửa
        # Ở tab sửa KPI, title gửi sang luôn là title mới của task.
        current_title = title
        if not summary_valid and title:
            print(f"         → Bước 1: Sửa lại Summary...")
            payload = {"summary": title}
            url = f"{api.base_url}/issues/{key}"
            try:
                response = requests.put(url, json=payload, headers=api.headers, timeout=15)
                if response.status_code not in (200, 204) and issue_id:
                    # Fallback qua ID
                    response = requests.put(f"{api.base_url}/issues/{issue_id}", json=payload, headers=api.headers, timeout=15)
                
                if response.status_code in (200, 204):
                    print("         ✓ Sửa Summary thành công")
                else:
                    print(f"         ⚠ Sửa Summary thất bại (HTTP {response.status_code})")
            except Exception as e:
                print(f"         ⚠ Lỗi sửa Summary: {e}")

        # ── BƯỚC 2: SỬA LỖI DESCRIPTION (NẾU CÓ) ──
        # Nếu mô tả trống hoặc không đạt yêu cầu
        if not description_valid:
            print(f"         → Bước 2: Bổ sung Description (Dùng AI suggest)...")
            
            # 1. Gọi API suggest description của WorkAI bằng Summary mới
            project_key = key.split("-")[0] if "-" in key else "GRPG"
            suggest_ok, suggest_data = api.suggest_description(project_key, current_title)
            
            if suggest_ok:
                desc = suggest_data.get("description", "")
                ac = suggest_data.get("acceptance_criteria", "")
                
                if desc:
                    payload = {
                        "description": desc,
                        "acceptance_criteria": ac
                    }
                    url = f"{api.base_url}/issues/{key}"
                    try:
                        response = requests.put(url, json=payload, headers=api.headers, timeout=15)
                        if response.status_code not in (200, 204) and issue_id:
                            # Fallback qua ID
                            response = requests.put(f"{api.base_url}/issues/{issue_id}", json=payload, headers=api.headers, timeout=15)
                        
                        if response.status_code in (200, 204):
                            print("         ✓ Bổ sung Description thành công")
                        else:
                            print(f"         ⚠ Bổ sung Description thất bại (HTTP {response.status_code})")
                    except Exception as e:
                        print(f"         ⚠ Lỗi bổ sung Description: {e}")
                else:
                    print("         ⚠ API suggest-description trả về mô tả trống.")
            else:
                print(f"         ⚠ Không thể lấy gợi ý mô tả từ WorkAI: {suggest_data}")

        print()
            
    update_status("success", total, total, "Đã hoàn thành cập nhật các công việc lên WorkAI!")
    print("[SUCCESS] Hoàn thành cập nhật.")


def main():
    parser = argparse.ArgumentParser(description="WorkAI Preview Helper (API mode)")
    parser.add_argument("--mode", choices=["scan", "update"], required=True, help="Chế độ quét (scan) hoặc cập nhật (update)")
    args = parser.parse_args()
    
    if args.mode == "scan":
        input_file = "tasks.json"
        if not os.path.exists(input_file):
            print(f"[ERROR] '{input_file}' not found.")
            sys.exit(1)
            
        with open(input_file, "r", encoding="utf-8") as f:
            local_tasks = json.load(f)
            
        submitted_file = "submitted.json"
        submitted = {}
        if os.path.exists(submitted_file):
            with open(submitted_file, "r", encoding="utf-8") as sf:
                submitted = json.load(sf)
                
        tasks_to_scan = []
        for t in local_tasks:
            # Hash fingerprint
            key_str = f"{t.get('project','')}|{t.get('title','')}|{t.get('date','')}"
            fp = hashlib.md5(key_str.encode('utf-8')).hexdigest()
            
            issue_key = ""
            if fp in submitted:
                issue_key = submitted[fp].get("issue_key", "")
            tasks_to_scan.append({
                "project": t.get("project", ""),
                "title": t.get("title", ""),
                "description": t.get("description", ""),
                "acceptance_criteria": t.get("acceptance_criteria", ""),
                "date": t.get("date", ""),
                "issue_key": issue_key
            })
            
        total = len(tasks_to_scan)
        if total == 0:
            print("Không có task nào để quét.")
            update_status("success", 0, 0, "Không có công việc nào cần quét.")
            sys.exit(0)
        tasks = tasks_to_scan
    else:
        if not os.path.exists(PREVIEW_EDIT_FILE):
            print(f"[ERROR] '{PREVIEW_EDIT_FILE}' not found.")
            sys.exit(1)
        with open(PREVIEW_EDIT_FILE, "r", encoding="utf-8") as f:
            tasks = json.load(f)
        total = len(tasks)
        if total == 0:
            print("Không có task nào cần cập nhật.")
            update_status("success", 0, 0, "Không có công việc nào cần cập nhật.")
            sys.exit(0)

    env = load_env()
    username = env.get("WORKAI_USERNAME")
    password = env.get("WORKAI_PASSWORD")
    if not username or not password:
        print("[ERROR] Missing credentials in .env")
        update_status("error", 0, total, "Thiếu thông tin tài khoản WorkAI trong cấu hình.")
        sys.exit(1)

    api = WorkAIAPI()
    login_ok, login_msg = api.login(username, password)
    if not login_ok:
        print(f"[ERROR] Đăng nhập WorkAI thất bại: {login_msg}")
        update_status("error", 0, total, f"Đăng nhập thất bại: {login_msg}")
        sys.exit(1)

    try:
        if args.mode == "scan":
            do_scan(api, tasks)
        else:
            do_update(api, tasks)
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        update_status("error", 0, total, f"Lỗi: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
