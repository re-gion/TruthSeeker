from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    page.goto("http://localhost:3000/login")
    page.wait_for_load_state("networkidle")
    page.locator('input[name="email"]').fill("gionre98@gmail.com")
    page.locator('input[name="password"]').fill("@Zhangyujing0906")
    page.locator('button[type="submit"]').click()
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    page.goto("http://localhost:3000/dashboard")
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    page.screenshot(path="dashboard-fixes-full.png", full_page=True)
    print("Saved: dashboard-fixes-full.png")

    sections = [
        ("arc-progress", "生成式 AI 普及态势"),
        ("digital-cards", "AI + 视听创作规模"),
        ("polar-bar", "生成式 AI 备案进展"),
        ("funnel", "网络法治与治理力度"),
        ("radar", "生成式 AI 生态扩张"),
        ("sankey", "证据流向"),
    ]

    for cls, title in sections:
        try:
            el = page.locator(f"text={title}").first
            if el.is_visible():
                el.scroll_into_view_if_needed()
                time.sleep(0.5)
                page.screenshot(path=f"dashboard-fix-{cls}.png")
                print(f"Saved: dashboard-fix-{cls}.png")
        except Exception as e:
            print(f"Skip {cls}: {e}")

    browser.close()
