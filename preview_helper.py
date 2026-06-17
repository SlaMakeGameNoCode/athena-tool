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
    
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
    log_path = os.path.join(base_dir, "kpi_update_result.log")
    # Khởi tạo hoặc xóa log cũ
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"=== BẮT ĐẦU TIẾN TRÌNH CẬP NHẬT KPI ({total} ĐẦU VIỆC) ===\n\n")
    except Exception as le:
        print(f"⚠ Không thể tạo file log: {le}")

    log_fh = open(log_path, "a", encoding="utf-8")

    def append_log(msg):
        print(msg)
        try:
            log_fh.write(msg + "\n")
            log_fh.flush()
        except:
            pass

    for idx, t in enumerate(tasks, 1):
        key = t.get("issue_key")
        title = t.get("title")
        summary_valid = t.get("summary_valid", True)
        description_valid = t.get("description_valid", True)
        
        if not key:
            append_log(f"[{idx}/{total}] Bỏ qua task không có issue_key")
            continue
            
        append_log(f"[{idx}/{total}] Đang xử lý issue: {key}")
        append_log(f"   - Trạng thái lỗi: Summary Valid={summary_valid}, Description Valid={description_valid}")
        update_status("running", idx - 1, total, f"Đang cập nhật công việc {idx}/{total}: {key}...")
        
        # Lấy ID của issue (để fallback nếu cập nhật qua key thất bại)
        issue_id = t.get("id") or t.get("issue_id") or ""
        if not issue_id:
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
        append_log(f"   - Mã ID số của JIRA: '{issue_id}'")

        # ── BƯỚC 1: SỬA LỖI SUMMARY (NẾU CÓ) ──
        # Nếu summary không hợp lệ hoặc title bị thay đổi, tiến hành sửa
        current_title = title
        if not summary_valid and title:
            append_log(f"   → [Bước 1/2] Sửa Summary lỗi. Tiêu đề mới đề xuất: \"{title}\"")
            payload = {"summary": title}
            url = f"{api.base_url}/issues/{key}"
            
            # Ghi nhận payload gửi đi
            append_log(f"     * Gửi PUT đến {url} | Payload: {json.dumps(payload, ensure_ascii=False)}")
            try:
                response = requests.put(url, json=payload, headers=api.headers, timeout=15)
                append_log(f"     * Phản hồi qua Key: HTTP {response.status_code} | Body: {response.text[:150]}")
                
                if response.status_code not in (200, 204) and issue_id:
                    fallback_url = f"{api.base_url}/issues/{issue_id}"
                    append_log(f"     * Lỗi Key. Chuyển sang Fallback dùng ID. Gửi PUT đến {fallback_url}")
                    response = requests.put(fallback_url, json=payload, headers=api.headers, timeout=15)
                    append_log(f"     * Phản hồi qua ID: HTTP {response.status_code} | Body: {response.text[:150]}")
                
                if response.status_code in (200, 204):
                    append_log("     ✓ Kết quả: Sửa Summary THÀNH CÔNG")
                else:
                    append_log(f"     ⚠ Kết quả: Sửa Summary THẤT BẠI (HTTP {response.status_code})")
            except Exception as e:
                append_log(f"     ⚠ Lỗi kết nối khi sửa Summary: {e}")
        else:
            append_log("   → [Bước 1/2] Bỏ qua sửa Summary (Tiêu đề đã đạt chuẩn hoặc không đổi)")

        # ── BƯỚC 2: SỬA LỖI DESCRIPTION (NẾU CÓ) ──
        if not description_valid:
            append_log(f"   → [Bước 2/2] Bổ sung Description. Gọi API suggest-description của WorkAI...")
            project_key = key.split("-")[0] if "-" in key else "GRPG"
            
            suggest_ok, suggest_data = api.suggest_description(project_key, current_title)
            
            if suggest_ok:
                desc = suggest_data.get("description", "")
                ac = suggest_data.get("acceptance_criteria", "")
                append_log(f"     * Đã lấy gợi ý từ AI thành công. Mô tả nhận được dài {len(desc)} ký tự.")
                
                if desc:
                    payload = {
                        "description": desc,
                        "acceptance_criteria": ac
                    }
                    url = f"{api.base_url}/issues/{key}"
                    append_log(f"     * Gửi PUT cập nhật mô tả đến {url}")
                    try:
                        response = requests.put(url, json=payload, headers=api.headers, timeout=15)
                        append_log(f"     * Phản hồi qua Key: HTTP {response.status_code} | Body: {response.text[:150]}")
                        
                        if response.status_code not in (200, 204) and issue_id:
                            fallback_url = f"{api.base_url}/issues/{issue_id}"
                            append_log(f"     * Lỗi Key. Chuyển sang Fallback dùng ID. Gửi PUT đến {fallback_url}")
                            response = requests.put(fallback_url, json=payload, headers=api.headers, timeout=15)
                            append_log(f"     * Phản hồi qua ID: HTTP {response.status_code} | Body: {response.text[:150]}")
                        
                        if response.status_code in (200, 204):
                            append_log("     ✓ Kết quả: Bổ sung Description THÀNH CÔNG")
                        else:
                            append_log(f"     ⚠ Kết quả: Bổ sung Description THẤT BẠI (HTTP {response.status_code})")
                    except Exception as e:
                        append_log(f"     ⚠ Lỗi kết nối khi cập nhật Description: {e}")
                else:
                    append_log("     ⚠ API suggest-description trả về mô tả trống.")
            else:
                append_log(f"     ⚠ Không thể lấy gợi ý mô tả từ WorkAI: {suggest_data}")
        else:
            append_log("   → [Bước 2/2] Bỏ qua bổ sung Description (Mô tả đã đạt chuẩn)")

        append_log("")
            
    append_log("Đã hoàn thành cập nhật tất cả công việc lên WorkAI!")
    update_status("success", total, total, "Đã hoàn thành cập nhật các công việc lên WorkAI!")
    print("[SUCCESS] Hoàn thành cập nhật.")
    try:
        log_fh.close()
    except:
        pass


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
