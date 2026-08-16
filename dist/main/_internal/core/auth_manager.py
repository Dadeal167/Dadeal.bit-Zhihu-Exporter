# -*- coding: utf-8 -*-
import json
import os
import time
from playwright.sync_api import sync_playwright

from core.paths import get_cookie_file, setup_console

setup_console()

# 知乎的核心登录凭证，缺少它等于未登录
REQUIRED_COOKIE_NAMES = {"z_c0"}


class AuthManager:
    def __init__(self, cookie_file=None):
        self.cookie_file = cookie_file or get_cookie_file()

    def _load_cookies(self):
        """读取本地 Cookie，文件不存在或损坏时返回 None"""
        try:
            with open(self.cookie_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            return cookies if isinstance(cookies, list) else None
        except (OSError, ValueError):
            return None

    def has_valid_cookies(self):
        """校验本地凭证是否真实可用：存在、结构合法、包含核心凭证、未过期"""
        cookies = self._load_cookies()
        if not cookies:
            return False

        now = time.time()
        names = set()
        for cookie in cookies:
            if not isinstance(cookie, dict) or "name" not in cookie:
                continue
            names.add(cookie["name"])
            # Playwright 的 expires 为秒级时间戳；-1 表示会话级 Cookie，视为不过期
            expires = cookie.get("expires")
            if isinstance(expires, (int, float)) and expires != -1 and expires < now:
                return False

        return REQUIRED_COOKIE_NAMES.issubset(names)

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
                
                os.makedirs(os.path.dirname(self.cookie_file), exist_ok=True)
                with open(self.cookie_file, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=4)
                    
                print(f"📁 Cookie 已成功提取并保存至: {self.cookie_file}")
                
            except Exception as e:
                print(f"❌ 登录超时或发生错误: {e}")
            finally:
                browser.close()

    def get_cookies(self):
        """获取本地 Cookie（无效时返回 None）"""
        if self.has_valid_cookies():
            return self._load_cookies()
        return None


if __name__ == "__main__":
    auth = AuthManager()
    
    if not auth.has_valid_cookies():
        print("未检测到本地凭证，启动初次认证流程...")
        auth.login_and_save_cookies()
    else:
        print("✨ 检测到已存在 cookies.json，可直接运行后续抓取。")
