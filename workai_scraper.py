import os
import sys

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
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            # 1. Login
            page.goto("https://workai.horus.io.vn/", timeout=15000)
            page.wait_for_load_state("networkidle")
            page.fill('input[name="login"]', username)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"]')
            page.wait_for_timeout(3000)

            # 2. Go to Timeline to access sidebar
            page.goto("https://workai.horus.io.vn/timeline-schedule", timeout=15000)
            page.wait_for_timeout(3000)

            # 3. Click KPI cá nhân
            kpi_link = page.get_by_text("KPI cá nhân")
            if kpi_link.count() > 0:
                kpi_link.first.click()
            else:
                raise Exception("Không tìm thấy link 'KPI cá nhân' trên sidebar")
            
            page.wait_for_timeout(5000)
            
            # 4. Tìm tất cả các dòng có trạng thái "Không đạt"
            # Theo hình ảnh, nút "Không đạt" là một badge/button trong hàng.
            failed_badges = page.get_by_text("Không đạt").all()
            
            # Nếu không có "Không đạt", thì kpi hoàn hảo
            if not failed_badges:
                return []
                
            # Duyệt qua từng row không đạt
            for badge in failed_badges:
                # Tìm element chứa dòng đó (thường là thẻ cha tr/div)
                row = badge.locator("xpath=./ancestor::div[contains(@class, 'flex') or contains(@class, 'grid') or @role='row']").first
                if row.count() == 0:
                    continue
                
                # Expand row bằng cách click vào vùng row hoặc nút chevron
                # Theo hình thì chevron nằm ngoài cùng bên trái. Có thể click vào chevron hoặc click thẳng vào badge
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
                
                page.wait_for_timeout(500) # Đợi animation mở rộng
                
            # Lấy toàn bộ text của trang sau khi mở rộng
            # Vì ta đã mở rộng các hàng, nội dung chi tiết sẽ xuất hiện trong DOM
            # Tuy nhiên việc bóc tách bằng DOM phức tạp vì class tự sinh, thay vào đó ta cào text hoặc tìm các node đặc trưng
            # Ta tìm tất cả các nội dung có chữ "Summary:" và "Gợi ý:"
            
            expanded_panels = page.locator("text=/Summary:.*?/").all()
            
            for panel in expanded_panels:
                text_content = panel.inner_text()
                # Tách lấy phần Lý do (sau chữ Summary:)
                import re
                
                reason_match = re.search(r'Summary:\s*(.*?)(?=\nGợi ý:|$)', text_content, re.DOTALL | re.IGNORECASE)
                suggestion_match = re.search(r'Gợi ý:\s*(.*?)(?=\nSửa Summary|$)', text_content, re.DOTALL | re.IGNORECASE)
                
                reason = reason_match.group(1).strip() if reason_match else text_content
                suggestion = suggestion_match.group(1).strip() if suggestion_match else ""
                
                # Tìm tiêu đề task (Nằm ở row cha)
                # Tạm thời ta lấy title bằng cách lùi lên cha 2 bậc và lấy chữ đầu tiên (đây là cách an toàn nhất nếu không có class)
                parent_row = panel.locator("xpath=./ancestor::div[contains(@class, 'border') or contains(@class, 'bg-')][1]")
                title = "Unknown Task"
                if parent_row.count() > 0:
                    full_parent_text = parent_row.inner_text()
                    lines = [l.strip() for l in full_parent_text.split('\n') if l.strip()]
                    # lines[0] có thể là "GRPG-1645" và lines[1] là "Họp nhanh triển khai..."
                    if len(lines) > 1:
                        if lines[0].startswith("G") or "-" in lines[0]:
                            title = f"{lines[0]} - {lines[1]}"
                        else:
                            title = lines[0]
                
                kpi_tasks.append({
                    "title": title,
                    "reason": reason,
                    "suggestion": suggestion
                })
                
        except Exception as e:
            print(f"Error scanning KPIs: {e}")
            try:
                page.screenshot(path="debug_kpi_fail.png")
            except:
                pass
            raise Exception(f"Lỗi khi quét KPI: {str(e)}")
        finally:
            browser.close()

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
