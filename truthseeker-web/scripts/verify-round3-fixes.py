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
    time.sleep(3)
    page.goto("http://localhost:3000/dashboard", wait_until="domcontentloaded")
    time.sleep(3)

    # 全页截图
    page.screenshot(path="dashboard-round3-full.png", full_page=True)
    print("Saved: dashboard-round3-full.png")

    targets = [
        ("生成式 AI 普及态势", "round3-arc-progress.png"),
        ("生成式 AI 备案进展", "round3-polar-bar.png"),
        ("生成式 AI 生态扩张", "round3-radar.png"),
        ("威胁分布", "round3-rose-pie.png"),
    ]

    for title, filename in targets:
        try:
            heading = page.locator(f"h3:has-text('{title}')").first
            if heading.count() == 0:
                print(f"Skip {title}: heading not found")
                continue
            heading.scroll_into_view_if_needed()
            time.sleep(0.5)
            article = heading.locator("xpath=ancestor::article | ancestor::div[contains(@class, 'rounded-[28px]') or contains(@class, 'rounded-[30px]')]")
            if article.count() == 0:
                box = heading.bounding_box()
                if box:
                    page.screenshot(path=filename, clip={"x": max(0, box["x"]-20), "y": max(0, box["y"]-20), "width": min(page.viewport_size["width"] - box["x"] + 20, box["width"]+600), "height": min(500, page.viewport_size["height"] - box["y"])})
                    print(f"Saved: {filename} (viewport clip)")
                else:
                    print(f"Skip {title}: no bounding box")
                continue
            article.screenshot(path=filename)
            print(f"Saved: {filename}")
        except Exception as e:
            print(f"Skip {title}: {e}")

    browser.close()
