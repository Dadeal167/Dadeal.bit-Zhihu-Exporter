# -*- coding: utf-8 -*-
import json
import os
import time
from playwright.sync_api import sync_playwright

from core.crypto_dpapi import protect, unprotect
from core.paths import get_cookie_file, get_legacy_cookie_file, setup_console

setup_console()

# 知乎的核心登录凭证，缺少它等于未登录
REQUIRED_COOKIE_NAMES = {"z_c0"}


class AuthManager:
    def __init__(self, cookie_file=None):
        self.cookie_file = cookie_file or get_cookie_file()

    def _read_encrypted(self):
        """读取 DPAPI 加密凭证; 失败返回 None"""
        try:
            with open(self.cookie_file, "rb") as f:
                raw = f.read()
            data = unprotect(raw)
            cookies = json.loads(data.decode("utf-8"))
            return cookies if isinstance(cookies, list) else None
        except Exception:
            return None

    def _read_legacy_plain(self, path):
        """读取旧版明文 JSON(用于兼容迁移)"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            return cookies if isinstance(cookies, list) else None
        except Exception:
            return None

    def _load_cookies(self):
        """读取本地 Cookie: 优先加密文件, 兼容旧版明文并自动迁移为加密"""
        cookies = self._read_encrypted()
        if cookies is not None:
            return cookies

        legacy_paths = [get_legacy_cookie_file()]
        if self.cookie_file.endswith(".json"):
            legacy_paths.append(self.cookie_file)
        for legacy in legacy_paths:
            if not legacy or not os.path.isfile(legacy):
                continue
            if legacy == self.cookie_file and not legacy.endswith(".json"):
                continue
            cookies = self._read_legacy_plain(legacy)
            if cookies is not None:
                try:
                    if legacy == self.cookie_file:
                        # 自定义明文路径 → 迁移到同目录 .dat
                        self.cookie_file = os.path.splitext(legacy)[0] + ".dat"
                    self.save_cookies(cookies)   # 迁移为加密存储
                    if os.path.abspath(legacy) != os.path.abspath(self.cookie_file):
                        os.remove(legacy)        # 删除明文, 防止凭证泄露
                    print("🔐 已把旧版明文 Cookie 迁移为 DPAPI 加密存储。")
                except Exception:
                    pass
                return cookies
        return None

    def save_cookies(self, cookies):
        """加密保存 Cookie(仅当前 Windows 用户可解密)"""
        os.makedirs(os.path.dirname(self.cookie_file), exist_ok=True)
        payload = json.dumps(cookies, ensure_ascii=False).encode("utf-8")
        with open(self.cookie_file, "wb") as f:
            f.write(protect(payload))

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
                self.save_cookies(cookies)
                    
                print(f"📁 Cookie 已加密保存至: {self.cookie_file}")
                
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
        print("✨ 检测到已存在加密凭证，可直接运行后续抓取。")
