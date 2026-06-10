import os
from playwright.sync_api import sync_playwright

env_path = os.path.join('.', '.env')
username = ''
password = ''
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('WORKAI_USERNAME='): username = line.split('=', 1)[1].strip()
            elif line.startswith('WORKAI_PASSWORD='): password = line.split('=', 1)[1].strip()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://workai.horus.io.vn/')
    page.fill('input[name="login"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_timeout(3000)
    
    page.goto('https://workai.horus.io.vn/timeline-schedule', timeout=15000)
    page.wait_for_timeout(3000)
    
    # Click KPI cá nhân
    kpi_loc = page.locator('text="KPI cá nhân"')
    if kpi_loc.count() > 0:
        kpi_loc.first.click()
        page.wait_for_timeout(5000)
        
        # Dump HTML
        with open('kpi_personal.html', 'w', encoding='utf-8') as f: f.write(page.content())
        
        # Dump text
        with open('kpi_personal.txt', 'w', encoding='utf-8') as f: f.write(page.locator('body').inner_text())
        print("Dumped kpi_personal")
    else:
        print("Could not find KPI cá nhân link")
    browser.close()
