"""
submitter.py — WorkAI Issue Creator + Status Done
===================================================
1. Tạo issue trên WorkAI (project, title, description, AC, sprint)
2. Mở sheet → auto set status Done
3. Chống duplicate: lưu submitted.json, skip nếu đã tạo
User sẽ tự chỉnh giờ phân bổ.
"""
import os
import sys
import json
import hashlib
import subprocess
import time as _time

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


# Set browsers path for PyInstaller frozen app or local execution
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(bundle_dir, "ms-playwright")
else:
    local_ms_playwright = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ms-playwright")
    if os.path.exists(local_ms_playwright):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = local_ms_playwright

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    if not getattr(sys, 'frozen', False):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
            subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        except:
            pass
    from playwright.sync_api import sync_playwright


PROJECT_CODE_MAP = {
    "RPG":                  "GRPG",
    "Sandy Jam":            "GSSP",
    "ViecChungNgoaiDuAn":   "VCNDA",
    "RndGame":              "RNDG",
    "TrainingGD":           "GTG",
}

def get_project_code(project_str):
    # 1. Try to load projects.json dynamically to get valid codes and names
    base_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
    projects_file = os.path.join(base_dir, "projects.json")
    
    projects_data = []
    if os.path.exists(projects_file):
        try:
            with open(projects_file, "r", encoding="utf-8") as f:
                projects_data = json.load(f)
        except Exception as e:
            print(f"[WARNING] Failed to load projects.json: {e}")
            
    # Determine the default fallback code dynamically from projects.json
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
                
    # 2. Check if project is directly a valid code (case-insensitive)
    if proj_upper in valid_codes:
        return valid_codes[proj_upper]
        
    # 3. Check legacy static mapping
    legacy_map_upper = {k.upper(): v for k, v in PROJECT_CODE_MAP.items()}
    if proj_upper in legacy_map_upper:
        return legacy_map_upper[proj_upper]
        
    # 4. Check if project matches any project name (case-insensitive)
    if proj_upper in name_to_code:
        return name_to_code[proj_upper]
        
    # 5. Check if project matches a substring of a project name
    for p_name_upper, p_code in name_to_code.items():
        if proj_upper in p_name_upper or p_name_upper in proj_upper:
            return p_code
            
    # 6. Check if project matches a substring of a legacy key
    for legacy_key, legacy_val in PROJECT_CODE_MAP.items():
        if proj_upper in legacy_key.upper() or legacy_key.upper() in proj_upper:
            return legacy_val
            
    # Default fallback
    return default_code


SUBMITTED_FILE = "submitted.json"


# ─── Duplicate Detection ──────────────────────────────────

def task_fingerprint(task):
    """Generate a unique hash from task title + project + date."""
    key = f"{task.get('project','')}|{task.get('title','')}|{task.get('date','')}"
    return hashlib.md5(key.encode('utf-8')).hexdigest()


def load_submitted():
    """Load set of already-submitted task fingerprints."""
    if os.path.exists(SUBMITTED_FILE):
        with open(SUBMITTED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_submitted(submitted):
    with open(SUBMITTED_FILE, "w", encoding="utf-8") as f:
        json.dump(submitted, f, ensure_ascii=False, indent=2)


# ─── Browser Helpers ──────────────────────────────────────

def login(page, username, password):
    print("Logging in...")
    page.goto("https://workai.horus.io.vn/", timeout=15000)
    page.wait_for_load_state("networkidle")
    page.fill('input[name="login"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_timeout(3000)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    print("[OK] Logged in.\n")



def navigate_to_timeline(page):
    page.goto("https://workai.horus.io.vn/timeline-schedule", timeout=15000)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    print("[OK] On Daily Time Allocation page.\n")


def close_all_overlays(page):
    for _ in range(2):
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)


# ─── Step 1: Create Issue ─────────────────────────────────

def create_issue(page, task, col_index, idx, total):
    project = task.get("project", "RPG")
    project_code = get_project_code(project)
    title = task.get("title", "")
    description = task.get("description", "")

    desc_body = description
    acceptance_criteria = ""
    if "4. Acceptance Criteria:" in description:
        parts = description.split("4. Acceptance Criteria:", 1)
        desc_body = parts[0].strip()
        acceptance_criteria = "4. Acceptance Criteria:" + parts[1]

    # Try to load projects.json to get the project name
    project_name = ""
    base_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
    projects_file = os.path.join(base_dir, "projects.json")
    if os.path.exists(projects_file):
        try:
            with open(projects_file, "r", encoding="utf-8") as f:
                projects = json.load(f)
                for p in projects:
                    if p.get("code") and p.get("code").strip().upper() == project_code.upper():
                        project_name = p.get("name", "").strip()
                        break
        except Exception:
            pass

    # Open modal - wait for at least one "Thêm issue" button
    page.wait_for_selector('button:has-text("Th\u00eam issue")', timeout=15000)
    
    count = page.locator('button:has-text("Th\u00eam issue")').count()
    if col_index >= count:
        col_index = count - 1
        
    btn = page.locator('button:has-text("Th\u00eam issue")').nth(col_index)
    dialog = page.locator('[role="dialog"][data-state="open"]')
    
    dialog_opened = False
    for click_attempt in range(3):
        try:
            # Scroll to the button to make sure it's in view
            btn.scroll_into_view_if_needed()
            btn.click(timeout=3000)
            
            # Wait up to 3 seconds for the dialog to become visible
            dialog.wait_for(state="visible", timeout=3000)
            dialog_opened = True
            break
        except Exception as ce:
            print(f"[WARNING] Click attempt {click_attempt + 1} failed to open dialog: {ce}. Retrying...")
            page.wait_for_timeout(1000)
            
    if not dialog_opened:
        raise Exception("Could not open 'Thêm issue' dialog after multiple click attempts.")

    # Wait for the dialog to be fully stable and finished animating
    page.wait_for_timeout(800)

    # Select project — multi-strategy approach
    project_selected = False
    
    # Build list of search terms to try (code, full name, clean name)
    search_terms = [project_code]
    if project_name:
        search_terms.append(project_name)
        clean_name = project_name
        if clean_name.startswith("G - "):
            clean_name = clean_name[4:]
        elif clean_name.startswith("G- "):
            clean_name = clean_name[3:]
        if clean_name != project_name:
            search_terms.append(clean_name)

    for attempt in range(3):
        try:
            combobox = dialog.locator('button[role="combobox"]').first
            combobox.wait_for(state="visible", timeout=5000)
            combobox.click(timeout=5000)
            
            # Wait for dropdown options to load
            try:
                page.locator('[role="option"]').first.wait_for(state="visible", timeout=8000)
            except Exception:
                pass
            page.wait_for_timeout(300)
            
            # Strategy 1: Direct click (works when all options are rendered in DOM)
            option = None
            for term in search_terms:
                loc = page.locator(f'[role="option"]:has-text("{term}")').first
                if loc.count() > 0:
                    option = loc
                    break
            
            # Strategy 2: Use search input to filter (for virtualized/large lists)
            if option is None or option.count() == 0:
                search_input = page.locator('input[placeholder*="T\u00ecm"], input[placeholder*="Search"], input[placeholder*="d\u1ef1 \u00e1n"], input[cmdk-input]').first
                if search_input.count() > 0:
                    for term in search_terms:
                        search_input.fill("")
                        page.wait_for_timeout(200)
                        search_input.fill(term)
                        page.wait_for_timeout(800)
                        
                        loc = page.locator('[role="option"]').first
                        if loc.count() > 0 and loc.is_visible():
                            option = loc
                            print(f"         Found project via search: '{term}'")
                            break
            
            if option is None or option.count() == 0:
                raise Exception(f"Option not found for {project_code} / {project_name}")
                
            option.click(timeout=3000)
            page.wait_for_timeout(500)
            project_selected = True
            break
        except Exception as e:
            print(f"[WARNING] Project selection attempt {attempt + 1} failed: {e}. Retrying...")
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)
            
            # If the dialog got closed, open it again!
            if dialog.count() == 0 or not dialog.is_visible():
                print("Dialog was closed. Re-opening dialog...")
                try:
                    btn.scroll_into_view_if_needed()
                    btn.click(timeout=3000)
                    dialog.wait_for(state="visible", timeout=3000)
                    page.wait_for_timeout(800)
                except Exception as re_open_ex:
                    print(f"[WARNING] Failed to re-open dialog: {re_open_ex}")

    if not project_selected:
        raise Exception(f"Could not select project {project_code} ({project_name}) after multiple attempts.")

    # Fill fields (no wait needed between fills)
    page.fill('input[name="summary"]', title)
    
    # Click "Gợi ý bằng AI" button
    ai_button = dialog.locator('button:has-text("G\u1ee3i \u00fd b\u1eb1ng AI")').first
    try:
        ai_button.wait_for(state="attached", timeout=3000)
    except Exception:
        pass
        
    if ai_button.count() > 0:
        update_status("running", idx - 1, total, f"Task {idx}/{total}: Đang chạy gợi ý bằng AI...")
        print("Clicking 'G\u1ee3i \u00fd b\u1eb1ng AI'...")
        ai_button.click()
        page.wait_for_timeout(1000) # wait for generation to start

        
        # Wait for description to be generated and button to be active again
        try:
            print("Waiting for AI generation to complete (up to 45s)...")
            page.wait_for_function("""
                () => {
                    const desc = document.querySelector('textarea[name="description"]');
                    const btns = Array.from(document.querySelectorAll('button'));
                    const btn = btns.find(b => b.textContent.includes('G\u1ee3i \u00fd b\u1eb1ng AI'));
                    const is_done = desc && desc.value.trim().length > 10;
                    const is_not_disabled = btn && !btn.disabled && !btn.getAttribute('disabled');
                    return is_done && is_not_disabled;
                }
            """, timeout=45000)
            print("[OK] AI description generated successfully.")
        except Exception as e:
            print(f"[WARNING] Timeout waiting for AI content generation: {e}")

    if desc_body:
        page.fill('textarea[name="description"]', desc_body)
    if acceptance_criteria:
        page.fill('textarea[name="acceptance_criteria"]', acceptance_criteria)

    # Select Sprint (latest) via JS — fixed selector
    sprint_text = ""
    sprint_result = page.evaluate("""
        () => {
            const dialog = document.querySelector('[role="dialog"][data-state="open"]');
            if (!dialog) return 'no-dialog';
            
            // FIX 1: Find Sprint label using loose match (leaf text node, no children elements)
            const allEls = Array.from(dialog.querySelectorAll('*'));
            const sprintLabel = allEls.find(el => 
                el.children.length === 0 && el.textContent.trim() === 'Sprint'
            );
            if (!sprintLabel) return 'no-sprint-label';
            
            // FIX 2: Find the button that belongs to Sprint specifically
            // Walk up to the form-group container, then find a combobox/popover button
            let container = sprintLabel.parentElement;
            for (let i = 0; i < 5; i++) {
                if (!container) break;
                // Look for a button with combobox role or popover trigger (Sprint dropdown)
                const btn = container.querySelector('button[role="combobox"], button[data-slot="popover-trigger"]');
                if (btn) {
                    btn.scrollIntoView({behavior: 'instant', block: 'center'});
                    btn.click();
                    return 'ok:' + btn.textContent.trim().substring(0, 30);
                }
                // Also try: direct child button of this container
                const directBtn = Array.from(container.children).find(
                    c => c.tagName === 'BUTTON' || c.querySelector(':scope > button')
                );
                if (directBtn) {
                    const actualBtn = directBtn.tagName === 'BUTTON' ? directBtn : directBtn.querySelector('button');
                    if (actualBtn) {
                        actualBtn.scrollIntoView({behavior: 'instant', block: 'center'});
                        actualBtn.click();
                        return 'ok:' + actualBtn.textContent.trim().substring(0, 30);
                    }
                }
                container = container.parentElement;
            }
            return 'no-btn';
        }
    """)

    if sprint_result.startswith('ok'):
        page.wait_for_timeout(600)
        options = page.locator('[role="option"], [role="menuitem"]').all()
        for opt in options:
            try:
                if opt.is_visible():
                    txt = opt.evaluate("el => el.textContent").strip()
                    if txt and "Không chọn" not in txt:
                        sprint_text = txt
                        opt.click()
                        # FIX 3: Wait for React state to update after selection
                        page.wait_for_timeout(500)
                        break
            except Exception:
                pass
        if not sprint_text:
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)

    # Submit — use expect_response to wait for actual API completion
    created_issue_key = None
    with page.expect_response(
        lambda r: r.status in (200, 201) and ("quick-create" in r.url or "issue" in r.url or "task" in r.url or "create" in r.url),
        timeout=10000
    ) as resp_info:
        dialog.locator('button:has-text("T\u1ea1o issue")').click()

    try:
        resp = resp_info.value  # wait for response
        try:
            body = resp.json()
            if body.get("success") and "data" in body:
                created_issue_key = body["data"].get("issue_key")
        except Exception:
            pass
    except Exception:
        # Fallback: just wait a bit
        page.wait_for_timeout(1500)

    page.wait_for_timeout(300)
    return project_code, sprint_text, created_issue_key



# ─── Step 2: Set Status Done ──────────────────────────────

def set_status_done(page, project_code, created_issue_key=None):
    page.wait_for_timeout(300)

    target_id = created_issue_key
    if not target_id:
        # Find newest issue (fallback)
        try:
            page.wait_for_selector(f'span:has-text("{project_code}-")', timeout=10000)
        except Exception:
            pass
        issue_spans = page.locator(f'span:has-text("{project_code}-")').all()
        issue_ids = []
        for sp in issue_spans:
            try:
                txt = sp.inner_text().strip()
                num_part = txt.replace(f"{project_code}-", "")
                if num_part.isdigit():
                    issue_ids.append((int(num_part), txt))
            except Exception:
                pass

        if not issue_ids:
            return False, "no cards found"

        issue_ids.sort(reverse=True)
        target_id = issue_ids[0][1]

    # Wait specifically for the target issue card to appear on the timeline board
    print(f"Waiting for card {target_id} to render on board...")
    try:
        page.wait_for_selector(f'span:has-text("{target_id}")', timeout=15000)
    except Exception as e:
        return False, f"card {target_id} not found: {e}"

    # Click to open sheet
    card_loc = page.locator(f'span:has-text("{target_id}")').first
    try:
        card_loc.click(timeout=3000)
    except Exception:
        card_loc.evaluate("el => el.click()")
    # Wait for the sheet to load and look for status button (with retry to handle animation lag)
    status_result = 'no-btn'
    for attempt in range(5):
        page.wait_for_timeout(600)
        status_result = page.evaluate("""
            () => {
                const sheet = document.querySelector('[data-slot="sheet-content"]')
                            || document.querySelector('[data-state="open"][role="dialog"]');
                if (!sheet) return 'no-sheet';
                const btns = Array.from(sheet.querySelectorAll('button'));
                const statusBtn = btns.find(b => {
                    const t = b.textContent.trim();
                    return t.includes('To Do') || t.includes('In Progress') || t.includes('Open') || t.includes('Todo');
                });
                if (!statusBtn) return 'no-btn';
                statusBtn.click();
                return 'ok';
            }
        """)
        if status_result == 'ok':
            break

    if status_result != 'ok':
        close_all_overlays(page)
        return False, f"status btn not found ({status_result})"

    page.wait_for_timeout(500)

    # Click Done
    done_opt = None
    for txt in ["Done", "Hoàn thành", "Complete", "Completed"]:
        loc = page.locator(f'[role="menuitem"]:has-text("{txt}")').first
        if loc.count() > 0:
            done_opt = loc
            break
        loc = page.locator(f'[role="option"]:has-text("{txt}")').first
        if loc.count() > 0:
            done_opt = loc
            break

    if done_opt:
        done_opt.click()
        page.wait_for_timeout(300)
        close_all_overlays(page)
        return True, target_id
    else:
        close_all_overlays(page)
        return False, "Done option not found"


# ─── Main Pipeline ────────────────────────────────────────

def process_task(page, task, col_index, idx, total):
    project = task.get("project", "RPG")
    title = task.get("title", "")
    pc = get_project_code(project)

    print(f"[{idx}/{total}] [{pc}] {title[:65]}...")
    update_status("running", idx - 1, total, f"Task {idx}/{total}: Đang tạo issue cho dự án {pc}...")

    project_code, sprint, created_key = create_issue(page, task, col_index, idx, total)
    sprint_info = f" | Sprint: {sprint}" if sprint else ""
    created_info = f" | Key: {created_key}" if created_key else ""
    print(f"         ✓ Created{sprint_info}{created_info}")

    update_status("running", idx - 1, total, f"Task {idx}/{total}: Đang chuyển trạng thái sang Done...")
    done_ok, done_info = set_status_done(page, project_code, created_key)
    if done_ok:
        print(f"         ✓ Done ({done_info})")
    else:
        print(f"         ⚠ Status: {done_info}")

    print()
    return True



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
    print(f"  WORKAI ISSUE CREATOR — {total} new issues")
    print(f"{'='*55}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        update_status("running", 0, total, "Đang đăng nhập vào hệ thống WorkAI...")
        login(page, username, password)
        navigate_to_timeline(page)

        ok = 0
        fail = 0

        for idx, task in enumerate(new_tasks, 1):
            task_date = task.get("date", "2026-06-02")
            try:
                from datetime import datetime as dt_class
                col_index = dt_class.strptime(task_date, "%Y-%m-%d").weekday()
            except Exception as e:
                print(f"         ⚠ Failed to parse date {task_date}: {e}. Defaulting to Tuesday (1).")
                col_index = 1
            fp = task_fingerprint(task)
            try:
                process_task(page, task, col_index, idx, total)
                ok += 1
                # Mark as submitted
                submitted[fp] = {
                    "title": task.get("title", ""),
                    "project": task.get("project", ""),
                    "date": task_date,
                    "submitted_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                save_submitted(submitted)
                update_status("running", idx, total, f"Đã hoàn thành Task {idx}/{total}")
            except Exception as e:
                print(f"         ✗ Error: {e}\n")
                page.screenshot(path=f"error_task_{idx}.png")
                fail += 1
                update_status("error", idx - 1, total, f"Lỗi ở Task {idx}: {str(e)}")
                close_all_overlays(page)

        elapsed = _time.time() - start
        page.screenshot(path="submission_complete.png")
        print(f"{'='*55}")
        print(f"  RESULT: {ok}/{total} created + Done  ({elapsed:.0f}s)")
        if fail > 0:
            print(f"  FAILED: {fail}")
        if skipped > 0:
            print(f"  SKIPPED: {skipped} duplicate(s)")
        print(f"{'='*55}")
        print(f"\n  → Bạn hãy chỉnh giờ phân bổ trên WorkAI.")
        browser.close()
        
        if fail == 0:
            update_status("success", total, total, "Đã hoàn thành nhập việc lên WorkAI!")
            sys.exit(0)
        else:
            update_status("error", ok, total, f"Đã nhập {ok}/{total} task, có {fail} task bị lỗi.")
            sys.exit(1)


if __name__ == "__main__":
    main()
