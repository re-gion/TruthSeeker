from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 监听控制台日志以帮助调试
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
        
        print("导航到检测页面...")
        # 去一个特定的检测 URL，比如传个参数
        page.goto('http://localhost:3000/detect/test-task-123?type=video&url=mock://test.mp4')
        
        # 等待页面加载（SSE 自动开始）
        print("等待检测控制台加载...")
        page.wait_for_selector('text=四智能体协同检测控制台', timeout=10000)
        
        # 给它 15 秒钟去跑完流程（预估）
        print("等待 15 秒让所有的 Agent 跑完...")
        time.sleep(15)
        
        # 截图看看 4 个 Agent 的状态
        screenshot_path = 'd:/a311/系统赛/2026系统赛/信安/truthseeker-web/detect_4agents_result.png'
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"已保存截图至: {screenshot_path}")
        
        browser.close()

if __name__ == '__main__':
    run()
