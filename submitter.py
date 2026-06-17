"""
submitter.py — WorkAI Issue Creator + Status Done
===================================================
1. Tạo issue trên WorkAI bằng HTTP API (project, title, description, AC, sprint)
2. Auto set status Done bằng API
3. Chống duplicate: lưu submitted.json, skip nếu đã tạo
User sẽ tự chỉnh giờ phân bổ.
"""
import os
import sys
import json
import hashlib
import time as _time
import requests
from workai_api import WorkAIAPI

if sys.stdout:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


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


def update_status(status, current, total, msg):
    status_file = "submission_status.json"
    try:
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump({"status": status, "current": current, "total": total, "msg": msg}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARNING] Failed to write status: {e}")


PROJECT_CODE_MAP = {
    "RPG":                  "GRPG",
    "Sandy Jam":            "GSSP",
    "ViecChungNgoaiDuAn":   "VCNDA",
    "RndGame":              "RNDG",
    "TrainingGD":           "GTG",
}

def get_project_code(project_str):
    base_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
    projects_file = os.path.join(base_dir, "projects.json")
    
    projects_data = []
    if os.path.exists(projects_file):
        try:
            with open(projects_file, "r", encoding="utf-8") as f:
                projects_data = json.load(f)
        except Exception as e:
            print(f"[WARNING] Failed to load projects.json: {e}")
            
    default_code = "GRPG"
    if projects_data:
        for p in projects_data:
            if p.get("code"):
                default_code = p.get("code").strip()
                break

    if not project_str:
        return default_code
        
    project_str = project_str.strip()
    proj_upper = project_str.upper()
    
    valid_codes = {}
    name_to_code = {}
    for p in projects_data:
        code = p.get("code")
        name = p.get("name")
        if code:
            valid_codes[code.strip().upper()] = code.strip()
            if name:
                name_to_code[name.strip().upper()] = code.strip()
                
    if proj_upper in valid_codes:
        return valid_codes[proj_upper]
        
    legacy_map_upper = {k.upper(): v for k, v in PROJECT_CODE_MAP.items()}
    if proj_upper in legacy_map_upper:
        return legacy_map_upper[proj_upper]
        
    if proj_upper in name_to_code:
        return name_to_code[proj_upper]
        
    for p_name_upper, p_code in name_to_code.items():
        if proj_upper in p_name_upper or p_name_upper in proj_upper:
            return p_code
            
    for legacy_key, legacy_val in PROJECT_CODE_MAP.items():
        if proj_upper in legacy_key.upper() or legacy_key.upper() in proj_upper:
            return legacy_val
            
    return default_code


SUBMITTED_FILE = "submitted.json"

def task_fingerprint(task):
    key = f"{task.get('project','')}|{task.get('title','')}|{task.get('date','')}"
    return hashlib.md5(key.encode('utf-8')).hexdigest()


def load_submitted():
    if os.path.exists(SUBMITTED_FILE):
        try:
            with open(SUBMITTED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARNING] Failed to load submitted.json: {e}")
    return {}


def save_submitted(data):
    try:
        with open(SUBMITTED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARNING] Failed to save submitted.json: {e}")


def process_task(api: WorkAIAPI, task, idx, total, hours_per_task=0.1):
    project = task.get("project", "RPG")
    title = task.get("title", "")
    pc = get_project_code(project)

    print(f"[{idx}/{total}] [{pc}] {title[:65]}...")
    update_status("running", idx - 1, total, f"Task {idx}/{total}: Đang tạo issue cho dự án {pc}...")

    # 1. Gọi API gợi ý mô tả từ AI của WorkAI
    desc = ""
    ac = ""
    suggest_ok, suggest_data = api.suggest_description(pc, title)
    if suggest_ok:
        desc = suggest_data.get("description", "")
        ac = suggest_data.get("acceptance_criteria", "")
        print("         ✓ AI Description generated")
    else:
        print("         ⚠ Failed to generate AI description, creating empty description.")

    # 2. Tạo issue
    create_ok, res_data = api.quick_create_issue(
        project_key=pc,
        summary=title,
        description=desc,
        acceptance_criteria=ac
    )
    
    if not create_ok:
        raise Exception(f"Không thể tạo issue qua API: {res_data}")

    created_key = res_data.get("key") or res_data.get("issue_key") or ""
    issue_id = res_data.get("id") or res_data.get("issue_id") or ""
    print(f"         ✓ Created Issue: {created_key}")

    # 3. Chuyển trạng thái sang Done qua Transitions API
    update_status("running", idx - 1, total, f"Task {idx}/{total}: Đang chuyển trạng thái sang Done...")
    
    # Thứ tự ưu tiên: Done → Review Approved → In Progress
    PREFERRED_STATUSES = ["Done", "Review Approved", "In Progress"]
    
    try:
        # Bước 3a: Lấy danh sách transitions khả dụng
        transitions_url = f"{api.base_url}/issues/{issue_id}/transitions"
        trans_res = requests.get(transitions_url, headers=api.headers, timeout=10)
        
        if trans_res.status_code == 200:
            trans_data = trans_res.json()
            transitions = trans_data.get("transitions", [])
            
            # Tìm transition phù hợp theo thứ tự ưu tiên
            chosen_transition = None
            for preferred in PREFERRED_STATUSES:
                for t in transitions:
                    if t.get("name", "").strip().lower() == preferred.lower():
                        chosen_transition = t
                        break
                if chosen_transition:
                    break
            
            if chosen_transition:
                # Bước 3b: Thực hiện transition
                trans_id = chosen_transition.get("id", "")
                trans_name = chosen_transition.get("name", "")
                post_res = requests.post(
                    transitions_url,
                    json={"transition_id": trans_id},
                    headers=api.headers,
                    timeout=10
                )
                if post_res.status_code in (200, 201, 204):
                    print(f"         ✓ Status set to '{trans_name}' (transition_id: {trans_id})")
                else:
                    print(f"         ⚠ Transition '{trans_name}' thất bại (HTTP {post_res.status_code}): {post_res.text[:150]}")
            else:
                avail = [t.get('name') for t in transitions]
                print(f"         ⚠ Không tìm thấy transition Done/Review Approved/In Progress. Có: {avail}")
        else:
            print(f"         ⚠ Không lấy được transitions (HTTP {trans_res.status_code})")
    except Exception as e:
        print(f"         ⚠ Lỗi chuyển trạng thái: {str(e)}")

    # 4. Thêm issue vào Daily Time Allocation
    update_status("running", idx - 1, total, f"Task {idx}/{total}: Đang đưa issue vào bảng phân bổ thời gian...")
    task_date = task.get("date", _time.strftime("%Y-%m-%d"))
    alloc_ok, alloc_res = api.create_time_allocation(
        issue_id=issue_id,
        allocation_date=task_date,
        planned_hours=hours_per_task
    )
    if alloc_ok:
        print(f"         ✓ Added to Time Allocation ({hours_per_task}h)")
    else:
        print(f"         ⚠ Time Allocation failed: {alloc_res}")

    print()
    return created_key, issue_id


def main():
    start = _time.time()
    input_file = "tasks.json"
    if not os.path.exists(input_file):
        print(f"[ERROR] '{input_file}' not found.")
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    env = load_env()
    username = env.get("WORKAI_USERNAME")
    password = env.get("WORKAI_PASSWORD")
    if not username or not password:
        print("[ERROR] Missing credentials in .env")
        sys.exit(1)

    # ── Duplicate check ──
    submitted = load_submitted()
    new_tasks = []
    skipped = 0
    for t in tasks:
        fp = task_fingerprint(t)
        if fp in submitted:
            title = t.get("title", "")
            print(f"  [SKIP] Already submitted: {title[:60]}...")
            skipped += 1
        else:
            new_tasks.append(t)

    if skipped > 0:
        print(f"\n  Skipped {skipped} duplicate(s).\n")

    if not new_tasks:
        print("All tasks already submitted. Nothing to do.")
        sys.exit(0)

    total = len(new_tasks)
    print(f"{'='*55}")
    print(f"  WORKAI ISSUE CREATOR (API MODE) — {total} new issues")
    print(f"{'='*55}\n")

    # Khởi tạo API
    api = WorkAIAPI()
    update_status("running", 0, total, "Đang đăng nhập vào hệ thống WorkAI...")
    login_ok, login_msg = api.login(username, password)
    if not login_ok:
        print(f"[ERROR] Đăng nhập WorkAI thất bại: {login_msg}")
        update_status("error", 0, total, f"Đăng nhập thất bại: {login_msg}")
        sys.exit(1)

    # Chia đều 8h cho các task
    total_hours = 8.0
    hours_per_task = round(total_hours / total, 1)
    print(f"  [Time Allocation] Auto distribution: {hours_per_task}h per task")

    ok = 0
    fail = 0

    for idx, task in enumerate(new_tasks, 1):
        fp = task_fingerprint(task)
        try:
            created_key, issue_id = process_task(api, task, idx, total, hours_per_task)
            ok += 1
            # Mark as submitted
            submitted[fp] = {
                "title": task.get("title", ""),
                "project": task.get("project", ""),
                "date": task.get("date", ""),
                "submitted_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
                "issue_key": created_key,
                "issue_id": issue_id,
            }
            save_submitted(submitted)
            update_status("running", idx, total, f"Đã hoàn thành Task {idx}/{total}")
        except Exception as e:
            print(f"         Epic Error: {e}\n")
            fail += 1
            update_status("error", idx - 1, total, f"Lỗi ở Task {idx}: {str(e)}")


    elapsed = _time.time() - start
    print(f"{'='*55}")
    print(f"  RESULT: {ok}/{total} created via API  ({elapsed:.1f}s)")
    if fail > 0:
        print(f"  FAILED: {fail}")
    if skipped > 0:
        print(f"  SKIPPED: {skipped} duplicate(s)")
    print(f"{'='*55}")
    
    if fail == 0:
        update_status("success", total, total, "Đã hoàn thành nhập việc lên WorkAI!")
        sys.exit(0)
    else:
        update_status("error", ok, total, f"Đã nhập {ok}/{total} task, có {fail} task bị lỗi.")
        sys.exit(1)


if __name__ == "__main__":
    main()
