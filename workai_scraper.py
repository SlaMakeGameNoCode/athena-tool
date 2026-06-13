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
            # Lọc các badge nằm trong thẻ TR (bảng issue) để loại bỏ card tổng quan ở đầu trang
            badge_locator = page.locator('tr').get_by_text(failed_pattern)
            total_failed = badge_locator.count()
            log_kpi(f"Tìm thấy {total_failed} nhãn trạng thái chưa đạt chuẩn trong bảng công việc.")
            
            if total_failed == 0:
                log_kpi("Không có đầu việc nào bị đánh giá chưa đạt chuẩn trên trang này.")
                return []
                
            seen_kpi_tasks = set()
            
            # Duyệt qua từng hàng lỗi theo index để tránh stale element reference khi DOM thay đổi
            for idx in range(total_failed):
                try:
                    badge = badge_locator.nth(idx)
                    
                    # Lấy thông tin hiển thị trước khi click và thêm class định danh tạm thời
                    row_info = badge.evaluate("""badge => {
                        let cur = badge;
                        while (cur && cur !== document.body) {
                            if (cur.tagName === 'TR') {
                                const tempId = 'kpi-row-' + Math.random().toString(36).substr(2, 9);
                                cur.classList.add(tempId);
                                return {
                                    tempId: tempId,
                                    text_preview: cur.innerText.split('\\n')[0].replace(/\\t/g, ' ').trim()
                                };
                            }
                            cur = cur.parentElement;
                        }
                        return null;
                    }""")
                    
                    if not row_info:
                        continue
                        
                    temp_class = row_info["tempId"]
                    row_text_preview = row_info["text_preview"]
                    row_locator = page.locator(f".{temp_class}")
                    
                    log_kpi(f"[{idx+1}/{total_failed}] Đang mở rộng chi tiết hàng: '{row_text_preview}'")
                    
                    # Mở rộng hàng bằng cách click chevron (nút svg đầu tiên) hoặc click badge
                    chevron = row_locator.locator("svg").first
                    if chevron.count() > 0:
                        chevron.click()
                    else:
                        badge.click()
                        
                    # Đợi animation mở rộng (800ms)
                    page.wait_for_timeout(800)
                    
                    # Cào thông tin chi tiết bằng JS ngay lập tức từ dòng detail-row vừa được hiển thị
                    parsed_task = badge.evaluate("""badge => {
                        let cur = badge;
                        let row = null;
                        while (cur && cur !== document.body) {
                            if (cur.tagName === 'TR') {
                                row = cur;
                                break;
                            }
                            cur = cur.parentElement;
                        }
                        if (!row) return null;
                        
                        let jiraKey = "";
                        let mainTitle = "";
                        const jiraLink = row.querySelector('a[href*="/issues/"]');
                        if (jiraLink) {
                            jiraKey = jiraLink.innerText.trim();
                        }
                        
                        const titleCell = row.querySelector('td.max-w-\\\\[300px\\\\], td.truncate');
                        if (titleCell) {
                            mainTitle = titleCell.innerText.trim();
                        } else {
                            const cells = Array.from(row.querySelectorAll('td'));
                            if (cells.length >= 3) {
                                mainTitle = cells[2].innerText.trim();
                            }
                        }
                        
                        if (!jiraKey) {
                            const match = row.innerText.match(/([A-Z0-9]+-\\d+)/);
                            if (match) jiraKey = match[1];
                        }
                        
                        const nextRow = row.nextElementSibling;
                        let reason = "";
                        let suggestion = "";
                        
                        if (nextRow) {
                            const paragraphs = Array.from(nextRow.querySelectorAll('p'));
                            for (let p of paragraphs) {
                                const text = p.innerText.trim();
                                if (text.startsWith("Summary:") || text.includes("Lý do:")) {
                                    reason = text.replace(/^(Summary:|Lý do:)/i, '').trim();
                                } else if (text.startsWith("Gợi ý:") || text.includes("Suggestion:")) {
                                    suggestion = text.replace(/^(Gợi ý:|Suggestion:)/i, '').trim();
                                }
                            }
                        }
                        
                        return {
                            jiraKey: jiraKey,
                            mainTitle: mainTitle,
                            reason: reason,
                            suggestion: suggestion
                        };
                    }""")
                    
                    if parsed_task and parsed_task.get("jiraKey"):
                        jira_key = parsed_task["jiraKey"]
                        main_title = parsed_task["mainTitle"]
                        reason = parsed_task["reason"] or "Không tìm thấy lý do cụ thể"
                        suggestion = parsed_task["suggestion"]
                        
                        full_title = f"{jira_key} - {main_title}"
                        task_fingerprint = (full_title.strip(), reason.strip())
                        
                        if task_fingerprint not in seen_kpi_tasks:
                            seen_kpi_tasks.add(task_fingerprint)
                            kpi_tasks.append({
                                "title": full_title,
                                "reason": reason,
                                "suggestion": suggestion
                            })
                            log_kpi(f"   ✓ Đã ghi nhận: {full_title} | Lý do: {reason[:60]}...")
                    else:
                        log_kpi(f"   ⚠ Lỗi: Không trích xuất được thông tin chi tiết hàng {idx+1}")
                        
                except Exception as row_err:
                    log_kpi(f"   ⚠ Lỗi khi xử lý hàng {idx+1}: {row_err}")
                    
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
