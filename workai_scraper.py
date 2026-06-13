import os
import sys
import re

# Set browsers path for PyInstaller frozen app or local execution
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(bundle_dir, "ms-playwright")
else:
    local_ms_playwright = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ms-playwright")
    if os.path.exists(local_ms_playwright):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = local_ms_playwright

from playwright.sync_api import sync_playwright

def scan_workai_projects(username, password):
    projects = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # 1. Login
            page.goto("https://workai.horus.io.vn/", timeout=15000)
            page.wait_for_load_state("networkidle")
            page.fill('input[name="login"]', username)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"]')
            
            # Chờ API đăng nhập
            page.wait_for_timeout(3000)

            # 2. Go directly to the Projects page
            page.goto("https://workai.horus.io.vn/projects", timeout=15000)
            page.wait_for_timeout(3000)
            
            # Extract from Next.js payload or HTML
            html = page.content()
            import re
            # Lọc các đoạn JSON payload của Next.js chứa danh sách dự án
            matches = re.findall(r'\\?"name\\?":\s*\\?"([^"\\]+)\\?",\s*\\?"jira_project_key\\?":\s*\\?"([^"\\]+)\\?"', html)
            
            seen = set()
            for name, code in matches:
                # Đôi khi có thể lọt các object không phải project, ta check mã code thường là chữ in hoa
                if code.isupper() and code not in seen:
                    projects.append({"name": name, "code": code})
                    seen.add(code)
            
            if not projects:
                # Fallback if regex fails, try to look for project cards
                cards = page.locator('div:has-text("Đang thực hiện")').all()
                for c in cards:
                    text = c.inner_text()
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    if len(lines) >= 2:
                        projects.append({"name": lines[0], "code": lines[-1]})
            
        except Exception as e:
            print(f"Error scanning projects: {e}")
            try:
                page.screenshot(path="debug_scan_fail.png")
            except:
                pass
            raise Exception(f"Lỗi khi quét: {str(e)}. Vui lòng xem ảnh debug_scan_fail.png")
        finally:
            browser.close()

    return projects

def scan_workai_kpis(username, password):
    from playwright.sync_api import sync_playwright
    import time
    
    kpi_tasks = []
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kpi_scan.log")
    
    def log_kpi(msg):
        print(f"[KPI_SCAN] {msg}")
        try:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"{msg}\n")
        except:
            pass

    # Clear old log file
    try:
        if os.path.exists(log_file):
            os.remove(log_file)
    except:
        pass

    log_kpi("Khởi động trình duyệt Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            # 1. Login
            log_kpi("Đang truy cập trang đăng nhập WorkAI...")
            page.goto("https://workai.horus.io.vn/", timeout=15000)
            page.wait_for_load_state("networkidle")
            page.fill('input[name="login"]', username)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"]')
            log_kpi("Đã điền thông tin đăng nhập, đang chờ xử lý...")
            page.wait_for_timeout(3000)

            # 2. Go directly to Personal KPIs page, with fallback to sidebar clicking
            log_kpi("Đang truy cập trực tiếp trang KPI cá nhân: /kpi/user...")
            try:
                page.goto("https://workai.horus.io.vn/kpi/user", timeout=15000)
                log_kpi("Đang đợi trang load dữ liệu (networkidle)...")
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception as ne:
                    log_kpi(f"Chờ load mạng bị timeout (vẫn tiếp tục): {ne}")
                page.wait_for_timeout(2000)
            except Exception as e:
                log_kpi(f"Truy cập trực tiếp /kpi/user thất bại: {e}. Thử click qua sidebar...")
                page.goto("https://workai.horus.io.vn/timeline-schedule", timeout=15000)
                page.wait_for_timeout(3000)

                # Click KPIs link in sidebar (matching 'KPIs cá nhân', 'KPI cá nhân', 'KPIs', 'Báo cáo KPI', href='/kpi')
                kpi_link = None
                for selector in ['a[href*="kpi"]', 'a[href*="KPI"]', 'text="KPI cá nhân"', 'text="KPIs cá nhân"', 'text="KPIs"', 'text="Báo cáo KPI"']:
                    loc = page.locator(selector).first
                    if loc.count() > 0 and loc.is_visible():
                        kpi_link = loc
                        break
                if kpi_link:
                    log_kpi(f"Tìm thấy link KPI qua selector '{selector}', đang click...")
                    kpi_link.click()
                    page.wait_for_timeout(4000)
                else:
                    raise Exception("Không tìm thấy link 'KPI cá nhân' hoặc 'KPIs' trên sidebar")
            
            log_kpi("Đang quét danh sách các nhãn chưa đạt chuẩn trên màn hình...")
            # 4. Tìm tất cả các dòng có trạng thái "Không đạt" hoặc các trạng thái không đạt chuẩn khác
            failed_pattern = re.compile(
                r"^\s*(Không đạt|Chưa đạt|Chưa đạt chuẩn|Không đạt chuẩn|Chưa chuẩn|Không chuẩn|Lỗi tiêu đề|Cảnh báo|Không đạt yêu cầu|Chưa đạt yêu cầu)\s*$", 
                re.IGNORECASE
            )
            failed_badges = page.get_by_text(failed_pattern).all()
            
            log_kpi(f"Tìm thấy {len(failed_badges)} nhãn trạng thái chưa đạt chuẩn.")
            if not failed_badges:
                log_kpi("Không có đầu việc nào bị đánh giá chưa đạt chuẩn trên trang này.")
                return []
                
            # Duyệt qua từng badge/nút trạng thái lỗi để mở rộng thông tin chi tiết
            for idx, badge in enumerate(failed_badges):
                # Sử dụng JavaScript để tìm chính xác phần tử hàng (row container) chứa badge này
                # Tránh lấy nhầm container lớn bao ngoài
                try:
                    row_id = badge.evaluate("""badge => {
                        let current = badge;
                        while (current && current !== document.body) {
                            const text = current.innerText || "";
                            const hasJiraKey = /[A-Z0-9]+-\\d+/.test(text);
                            
                            const isRowLike = current.tagName === 'TR' || 
                                              current.getAttribute('role') === 'row' || 
                                              current.classList.contains('border-b') ||
                                              current.classList.contains('border') ||
                                              (current.tagName === 'DIV' && (current.classList.contains('flex') || current.classList.contains('grid')) && text.length < 800);
                                              
                            if (isRowLike && (hasJiraKey || text.length < 800)) {
                                const badgeText = badge.innerText || "";
                                if (text.length > badgeText.length + 5) {
                                    const tempId = 'kpi-row-' + Math.random().toString(36).substr(2, 9);
                                    current.classList.add(tempId);
                                    return tempId;
                                }
                            }
                            current = current.parentElement;
                        }
                        const tempId = 'kpi-row-' + Math.random().toString(36).substr(2, 9);
                        badge.parentElement.classList.add(tempId);
                        return tempId;
                    }""")
                    row = page.locator(f".{row_id}")
                except Exception as eval_err:
                    log_kpi(f"Lỗi khi tìm hàng bằng JS: {eval_err}. Dùng fallback xpath...")
                    row = badge.locator("xpath=./ancestor::div[contains(@class, 'flex') or contains(@class, 'grid') or @role='row']").first
                
                if row.count() == 0:
                    continue
                
                # Tránh click trùng lặp một hàng nhiều lần (làm nó đóng lại)
                try:
                    is_expanded = row.evaluate("el => el.getAttribute('data-expanded-by-tool') === 'true'")
                    if is_expanded:
                        continue
                except:
                    pass
                
                # Lấy tiêu đề sơ bộ để ghi log
                row_text_preview = ""
                try:
                    row_text_preview = row.inner_text().split("\n")[0][:40]
                except:
                    pass
                
                log_kpi(f"[{idx+1}/{len(failed_badges)}] Đang mở rộng chi tiết hàng: '{row_text_preview}...'")
                
                # Expand row bằng cách click vào vùng row hoặc nút chevron
                chevron = row.locator("svg").first
                if chevron.count() > 0:
                    try:
                        chevron.click()
                    except:
                        try:
                            badge.click()
                        except:
                            pass
                else:
                    try:
                        badge.click()
                    except:
                        pass
                
                try:
                    row.evaluate("el => el.setAttribute('data-expanded-by-tool', 'true')")
                except:
                    pass
                
                page.wait_for_timeout(500) # Đợi animation mở rộng
                
            log_kpi("Đang trích xuất nội dung chi tiết lỗi của các việc đã mở rộng...")
            
            # Cào trực tiếp thông tin từ các hàng đã đánh dấu mở rộng
            all_rows = page.locator("[data-expanded-by-tool='true']").all()
            seen_kpi_tasks = set()
            
            log_kpi(f"Tìm thấy {len(all_rows)} hàng đang mở rộng thành công. Bắt đầu phân tích text...")
            for idx, parent_row in enumerate(all_rows):
                full_parent_text = parent_row.inner_text()
                lines = [l.strip() for l in full_parent_text.split('\n') if l.strip()]
                
                if len(lines) < 2:
                    continue
                
                # Xác định JIRA key và title
                title = "Unknown Task"
                if lines[0].startswith("G") or "-" in lines[0]:
                    title = f"{lines[0]} - {lines[1]}"
                else:
                    title = lines[0]
                
                log_kpi(f"Phân tích hàng {idx+1}: {title}")
                
                # Tìm vị trí nhãn trạng thái chưa đạt
                status_idx = -1
                for i, line in enumerate(lines):
                    if failed_pattern.match(line) or any(s in line.lower() for s in ["không đạt", "chưa đạt", "đạt chuẩn"]):
                        status_idx = i
                        break
                
                reason = "Không tìm thấy lý do cụ thể"
                suggestion = ""
                
                if status_idx != -1 and status_idx < len(lines) - 1:
                    detail_text = "\n".join(lines[status_idx + 1:])
                    # Tách lý do và gợi ý bằng regex
                    reason_match = re.search(r'(?:Summary|Lý do(?: chưa đạt)?|Lý do chính|Nội dung đánh giá):\s*(.*?)(?=\n(?:Gợi ý|Suggestion|Sửa Summary):|$)', detail_text, re.DOTALL | re.IGNORECASE)
                    suggestion_match = re.search(r'(?:Gợi ý|Suggestion|Sửa Summary):\s*(.*?)$', detail_text, re.DOTALL | re.IGNORECASE)
                    
                    if reason_match:
                        reason = reason_match.group(1).strip()
                    else:
                        # Nếu không có nhãn chỉ định, lấy toàn bộ phần detail_text làm lý do
                        reason = detail_text.strip()
                        
                    if suggestion_match:
                        suggestion = suggestion_match.group(1).strip()
                else:
                    log_kpi(f"Cảnh báo: Không tìm thấy dòng chi tiết lỗi cho {title}")
                
                # Tránh trùng lặp đầu việc đã quét
                task_fingerprint = (title.strip(), reason.strip())
                if task_fingerprint in seen_kpi_tasks:
                    continue
                seen_kpi_tasks.add(task_fingerprint)
                
                kpi_tasks.append({
                    "title": title,
                    "reason": reason,
                    "suggestion": suggestion
                })
                log_kpi(f"-> Đã ghi nhận: {title} | Lý do: {reason[:60]}...")
            
            log_kpi(f"Hoàn thành quét KPI! Tổng số đầu việc bị lỗi thu thập được: {len(kpi_tasks)}")
                
        except Exception as e:
            log_kpi(f"LỖI quét KPI: {e}")
            try:
                page.screenshot(path="debug_kpi_fail.png")
                log_kpi("Đã chụp ảnh màn hình lỗi tại debug_kpi_fail.png")
            except:
                pass
            raise Exception(f"Lỗi khi quét KPI: {str(e)}")
        finally:
            browser.close()
            log_kpi("Trình duyệt Playwright đã đóng.")

    return kpi_tasks

def test_workai_login(username, password):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto("https://workai.horus.io.vn/", timeout=15000)
            page.wait_for_load_state("networkidle")
            page.fill('input[name="login"]', username)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"]')
            
            # Đợi một chút để hệ thống xử lý (3 giây)
            page.wait_for_timeout(3000)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass
            
            # Kiểm tra xem ô đăng nhập có còn trên màn hình không
            # Nếu biến mất, tức là đã vượt qua màn hình đăng nhập thành công
            if page.locator('input[name="login"]').count() == 0 or not page.locator('input[name="login"]').is_visible():
                return True, "Đăng nhập thành công!"
            else:
                # Nếu vẫn còn ô đăng nhập -> Sai pass hoặc có lỗi captcha
                page.screenshot(path="debug_login_fail.png")
                return False, "Sai tài khoản, mật khẩu hoặc mạng chậm. (Đã lưu ảnh debug_login_fail.png)"
        except Exception as e:
            return False, f"Lỗi kết nối: {str(e)}"
        finally:
            browser.close()
