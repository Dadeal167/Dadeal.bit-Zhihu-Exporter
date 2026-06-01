import json
import os
from playwright.sync_api import sync_playwright

class AuthManager:
    def __init__(self, cookie_file="data/cookies.json"):
        self.cookie_file = cookie_file
        os.makedirs(os.path.dirname(self.cookie_file), exist_ok=True)

    def has_valid_cookies(self):
        """检查本地是否存在 Cookie 文件"""
        return os.path.exists(self.cookie_file)

    def login_and_save_cookies(self):
        """唤起浏览器扫码并保存 Cookie"""
        print("🚀 正在启动浏览器，请准备扫描知乎登录二维码...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=False)
            context = browser.new_context()
            page = context.new_page()

            page.goto("https://www.zhihu.com/signin")
            print("⏳ 请在弹出的浏览器中扫码登录。程序将静默等待 (最长等待 2 分钟)...")

            try:
                # 等待登录成功 (检测用户头像)
                page.wait_for_selector(".AppHeader-profileAvatar", timeout=120000)
                print("✅ 检测到登录状态！")
                
                cookies = context.cookies()
                
                with open(self.cookie_file, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=4)
                    
                print(f"📁 Cookie 已成功提取并保存至: {self.cookie_file}")
                
            except Exception as e:
                print(f"❌ 登录超时或发生错误: {e}")
            finally:
                browser.close()

    def get_cookies(self):
        """获取 Cookie"""
        if self.has_valid_cookies():
            with open(self.cookie_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

if __name__ == "__main__":
    auth = AuthManager()
    
    if not auth.has_valid_cookies():
        print("未检测到本地凭证，启动初次认证流程...")
        auth.login_and_save_cookies()
    else:
        print("✨ 检测到已存在 cookies.json，可直接运行后续抓取。")