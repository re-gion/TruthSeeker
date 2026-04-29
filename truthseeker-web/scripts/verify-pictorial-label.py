from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    page.goto("http://localhost:3000/login", wait_until="domcontentloaded")
    time.sleep(2)
    page.locator('input[name="email"]').fill("gionre98@gmail.com")
    page.locator('input[name="password"]').fill("@Zhangyujing0906")
    page.locator('button[type="submit"]').click()
    time.sleep(4)
    page.goto("http://localhost:3000/dashboard", wait_until="domcontentloaded")
    time.sleep(4)

    # 滚动到网络视听传播土壤区域
    for attempt in range(3):
        try:
            el = page.locator("text=网络视听传播土壤").first
            if el.count() == 0:
                print("heading not found, retry...")
                time.sleep(2)
                continue
            el.scroll_into_view_if_needed()
            time.sleep(1)
            page.screenshot(path="round3-pictorial-bar.png")
            print("Saved: round3-pictorial-bar.png")
            break
        except Exception as e:
            print(f"attempt {attempt} failed: {e}")
            time.sleep(2)

    browser.close()
