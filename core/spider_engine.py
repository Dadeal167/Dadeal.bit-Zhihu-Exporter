import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from core.paths import get_cookie_file, get_output_dir, setup_console

setup_console()

# 真实浏览器 UA(用于 Edge 兼容抓取, 与 requests 头部保持一致)
BROWSER_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0")

class SpiderEngine:
    def __init__(self, cookie_file=None, output_dir=None, image_workers=4,
                 status_callback=None):
        self.cookie_file = cookie_file or get_cookie_file()
        self.output_dir = output_dir or get_output_dir()
        self.image_workers = max(1, int(image_workers))
        self.status_callback = status_callback
        self.headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.zhihu.com/",
        "Connection": "keep-alive"
        }
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self._playwright = None
        self._browser = None
        self._browser_context = None
        self._browser_page = None
        self._pdf_browser = None
        self._pdf_context = None
        self._force_browser = False
        self._cookies = self._load_cookies()
        self.cookies_dict = {cookie["name"]: cookie["value"] for cookie in self._cookies}
        self._sync_session_cookies(self._cookies)

    def _notify(self, message):
        if self.status_callback is not None:
            self.status_callback(message)
        else:
            print(message)

    def _load_cookies(self):
        from core.auth_manager import AuthManager
        cookies = AuthManager(cookie_file=self.cookie_file).get_cookies()
        if not cookies:
            raise FileNotFoundError(f"找不到有效凭证 {self.cookie_file}，请先运行 auth_manager.py 登录。")

        return cookies

    def _sync_session_cookies(self, cookies):
        """把 Playwright Cookie 尽可能完整地同步到 requests.Session。"""
        self._session.cookies.clear()
        for cookie in cookies:
            name = cookie.get("name")
            value = cookie.get("value")
            if not name or value is None:
                continue
            kwargs = {"path": cookie.get("path") or "/"}
            domain = cookie.get("domain")
            if domain:
                kwargs["domain"] = domain
            expires = cookie.get("expires")
            if isinstance(expires, (int, float)) and expires > 0:
                kwargs["expires"] = int(expires)
            self._session.cookies.set(name, value, **kwargs)

    @staticmethod
    def _is_zhihu_url(url):
        hostname = (urlparse(url).hostname or "").lower()
        return hostname == "zhihu.com" or hostname.endswith(".zhihu.com")

    @staticmethod
    def _response_is_blocked(response):
        """识别知乎返回在 200 状态码里的账号风控 JSON(如 code 40362)。"""
        try:
            text = response.text or ""
        except Exception:
            return False
        return ("请求存在异常" in text or "限制本次访问" in text
                or "40362" in text)

    @staticmethod
    def _playwright_cookie(cookie):
        allowed = {"name", "value", "domain", "path", "expires",
                   "httpOnly", "secure", "sameSite"}
        result = {key: value for key, value in cookie.items() if key in allowed}
        if result.get("expires") == -1:
            result.pop("expires", None)
        if result.get("sameSite") not in ("Strict", "Lax", "None"):
            result.pop("sameSite", None)
        return result

    def _ensure_playwright(self):
        """确保共享 Playwright 实例已启动(每个线程只允许启动一次,
        否则会触发 'Sync API inside the asyncio loop' 异常)"""
        if self._playwright is None:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
        return self._playwright

    def _ensure_browser(self):
        if self._browser_context is not None:
            return

        try:
            self._ensure_playwright()
            self._browser = self._playwright.chromium.launch(
                channel="msedge", headless=False,
                args=["--allow-file-access-from-files", "--allow-file-access"])
            self._browser_context = self._browser.new_context(
                locale="zh-CN",
                viewport={"width": 1280, "height": 800},
                user_agent=BROWSER_USER_AGENT)
            # 隐藏 Playwright 自动化特征(navigator.webdriver), 降低被知乎识别的概率
            self._browser_context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', "
                "{get: () => undefined});")
            browser_cookies = [self._playwright_cookie(cookie) for cookie in self._cookies]
            browser_cookies = [cookie for cookie in browser_cookies
                               if cookie.get("name") and cookie.get("value") is not None
                               and cookie.get("domain")]
            if browser_cookies:
                self._browser_context.add_cookies(browser_cookies)
            self._browser_page = self._browser_context.new_page()

            self.headers["User-Agent"] = BROWSER_USER_AGENT
            self._session.headers.update({"User-Agent": BROWSER_USER_AGENT})
        except Exception as exc:
            self.close()
            raise RuntimeError(
                "知乎拒绝了普通网络请求，且无法启动 Edge 兼容抓取。"
                "请确认 Microsoft Edge 已正确安装后重试。"
            ) from exc

    @staticmethod
    def _browser_body_text(page):
        try:
            return page.locator("body").inner_text(timeout=3000).strip()
        except Exception:
            return ""

    @staticmethod
    def _browser_json_text(page):
        """用页面内 fetch 读取原始 JSON 文本, 避免浏览器 JSON 查看器干扰解析。"""
        try:
            return page.evaluate(
                "async () => { const r = await fetch(window.location.href, "
                "{credentials: 'include'}); return await r.text(); }")
        except Exception:
            return ""

    @staticmethod
    def _browser_content_ready(page, url):
        if "/api/" in urlparse(url).path:
            try:
                data = json.loads(SpiderEngine._browser_json_text(page))
                # 知乎风控错误也返回合法 JSON, 但并不是有效数据
                if isinstance(data, dict) and data.get("error"):
                    return False
                return True
            except (TypeError, ValueError):
                return False
        try:
            return page.locator(".RichText, .Post-RichText, .Post-Content").count() > 0
        except Exception:
            return False

    @staticmethod
    def _page_has_verification_ui(page):
        current_url = page.url.lower()
        if any(word in current_url for word in (
                "signin", "captcha", "verify", "account/unhuman")):
            return True
        body_text = SpiderEngine._browser_body_text(page)
        return any(word in body_text for word in (
            "安全验证", "验证码", "异常流量", "登录后继续", "请完成验证", "访问受限"))

    @staticmethod
    def _looks_like_verification(page, status_code):
        return status_code in (403, 429) or SpiderEngine._page_has_verification_ui(page)

    def _save_browser_cookies(self):
        try:
            cookies = self._browser_context.cookies()
            if not cookies:
                return
            from core.auth_manager import AuthManager
            AuthManager(cookie_file=self.cookie_file).save_cookies(cookies)
            self._cookies = cookies
            self.cookies_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
            self._sync_session_cookies(cookies)
        except Exception:
            pass

    def _browser_get(self, url, params=None):
        """使用真实 Edge 会话加载被知乎拦截的页面，并允许用户完成官方验证。

        若本次获取不完整(风控号常见), 由上层 WorkerThread 自动整篇重试,
        届时会话已预热, 第二次通常能拿到完整内容。
        """
        self._notify("🛡️ 普通请求被知乎拦截，正在切换到真实 Edge 浏览器...")
        self._ensure_browser()

        target_url = requests.Request("GET", url, params=params).prepare().url
        page = self._browser_page

        try:
            self._load_and_scroll(page, target_url, notify_verify=True)
            self._save_browser_cookies()

            self._force_browser = True
            self._notify("🔒 已切换 Edge 模式，本次任务后续请求将全程通过真实浏览器进行。")
            self._notify("✅ Edge 已成功获取内容，继续导出...")

            if "/api/" in urlparse(target_url).path:
                text = self._browser_json_text(page)
            else:
                text = page.content()
            return _BrowserResponse(text=text, status_code=200, url=page.url)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Edge 兼容抓取失败: {exc}") from exc

    def _load_and_scroll(self, page, target_url, notify_verify=True):
        """加载页面、等待正文(必要时等人工验证), 然后平滑滚动触发懒加载。"""
        response = page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        status_code = response.status if response is not None else 0

        try:
            page.wait_for_timeout(1500)
            if "/api/" not in urlparse(target_url).path:
                page.wait_for_selector(
                    ".RichText, .Post-RichText, .Post-Content", timeout=15000)
        except Exception:
            pass

        if not self._browser_content_ready(page, target_url):
            if not self._looks_like_verification(page, status_code):
                raise RuntimeError(
                    "Edge 已打开页面，但没有找到正文。内容可能已删除、仅特定用户可见，"
                    "或当前账号没有访问权限。")

            if notify_verify:
                self._notify(
                    "🔐 Edge 中出现登录或安全验证，请在浏览器内完成；"
                    "程序会等待最多 2 分钟并自动继续。")
            deadline = time.time() + 120
            last_reload = 0
            while time.time() < deadline:
                if self._browser_content_ready(page, target_url):
                    break

                verification_visible = self._page_has_verification_ui(page)
                if not verification_visible and time.time() - last_reload >= 5:
                    last_reload = time.time()
                    try:
                        response = page.goto(
                            target_url, wait_until="domcontentloaded", timeout=30000)
                        status_code = response.status if response is not None else status_code
                        page.wait_for_timeout(1000)
                    except Exception:
                        pass
                else:
                    page.wait_for_timeout(1000)

            if not self._browser_content_ready(page, target_url):
                raise RuntimeError(
                    "Edge 验证未在 2 分钟内完成，或知乎仍拒绝当前账号访问。"
                    "请确认该链接能在弹出的 Edge 中正常打开后重试。")

        # 平滑滚动整页, 模拟真人浏览, 触发所有懒加载图片。
        # 生硬的快速跳跃会导致知乎懒加载(尤其动图)来不及加载, 拿到的还是占位图。
        if "/api/" in urlparse(target_url).path:
            return
        try:
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(400)
            viewport_height = page.evaluate("window.innerHeight") or 800
            scroll_step = max(300, int(viewport_height * 0.8))
            for _ in range(60):  # 最多滚 60 步, 足够覆盖长文
                current_y = page.evaluate("window.scrollY")
                total = page.evaluate("document.body.scrollHeight")
                if current_y + viewport_height >= total - 5:
                    break
                page.evaluate(
                    f"window.scrollBy({{top: {scroll_step}, behavior: 'smooth'}})")
                page.wait_for_timeout(350)
            # 回到顶部, 并等待图片资源加载完成
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
        except Exception:
            pass

    def get_pdf_bundle(self):
        """供 PDF 渲染复用, 返回 (playwright, browser, context):
        - 若已有可见 Edge(风控号抓取时打开) → 直接复用;
        - 否则用同一个 Playwright 实例启动一个无头 Edge(正常账号 PDF 渲染),
          避免再起第二个 Playwright 实例触发 'Sync API inside the asyncio loop' 异常。
        """
        self._ensure_playwright()
        if self._browser is not None and self._browser_context is not None:
            return self._playwright, self._browser, self._browser_context
        if self._pdf_browser is None:
            self._pdf_browser = self._playwright.chromium.launch(
                channel="msedge", headless=True,
                args=["--allow-file-access-from-files", "--allow-file-access"])
            self._pdf_context = self._pdf_browser.new_context(locale="zh-CN")
        return self._playwright, self._pdf_browser, self._pdf_context

    def close(self):
        """释放懒加载的浏览器资源；未启用兼容模式时为空操作。"""
        for resource in (self._browser_page, self._browser_context, self._browser,
                         self._pdf_context, self._pdf_browser):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._browser_page = None
        self._browser_context = None
        self._browser = None
        self._pdf_context = None
        self._pdf_browser = None
        self._playwright = None

    def _sanitize_filename(self, filename):
        # 与 format_converter 保持一致: 去除非法字符与结尾空格/点号
        cleaned = re.sub(r'[\\/*?:"<>|]', "", filename).strip().rstrip(". ")
        return cleaned or "未命名文章"

    # ==========================================
    # 图片本地化下载器
    # ==========================================
    def _download_and_replace_images(self, html_content, title, max_workers=None):
        soup = BeautifulSoup(html_content, 'html.parser')
        safe_title = self._sanitize_filename(title)
        
        assets_dir = os.path.join(self.output_dir, "assets", safe_title)
        if max_workers is None:
            max_workers = self.image_workers
        
        img_headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": "https://www.zhihu.com/" 
        }

        # 收集需要下载的图片(过滤公式图与非外部链接)
        tasks = []
        for index, img in enumerate(soup.find_all('img')):
            img_url = img.get('data-original') or img.get('data-actualsrc') or img.get('src')
            if not img_url or not img_url.startswith('http') or 'equation' in img_url:
                continue
            tasks.append((index, img, img_url))

        if not tasks:
            return str(soup)

        os.makedirs(assets_dir, exist_ok=True)

        def _fetch_one(task):
            """下载单张图片, 成功返回 (img_tag, 相对路径), 失败返回 None"""
            index, img, img_url = task
            try:
                ext = os.path.splitext(urlparse(img_url).path)[1]
                if ext.lower() not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    ext = '.jpg'

                local_filename = f"img_{index+1:03d}{ext}"
                local_filepath = os.path.join(assets_dir, local_filename)
                relative_path = f"assets/{safe_title}/{local_filename}"

                # 增量下载: 本地已存在且非空则直接复用, 不重复请求网络
                if os.path.isfile(local_filepath) and os.path.getsize(local_filepath) > 0:
                    return img, relative_path

                response = requests.get(img_url, headers=img_headers,
                                        cookies=self.cookies_dict, timeout=15)
                if response.status_code == 200:
                    content = response.content
                    content_type = (response.headers.get("Content-Type", "") or "").lower()
                    # 按文件内容/Content-Type 识别 GIF: 知乎部分动图链接没有 .gif 后缀,
                    # 仅凭 URL 会被误存成 .jpg 导致查看器不按动图播放
                    if content[:6] in (b"GIF89a", b"GIF87a") or "image/gif" in content_type:
                        ext = ".gif"
                        local_filename = f"img_{index+1:03d}{ext}"
                        local_filepath = os.path.join(assets_dir, local_filename)
                        relative_path = f"assets/{safe_title}/{local_filename}"
                    with open(local_filepath, 'wb') as f:
                        f.write(content)
                    return img, relative_path
                print(f"⚠️ 图片下载失败(HTTP {response.status_code}): {img_url}")
            except Exception as e:
                print(f"⚠️ 图片下载失败，已跳过: {img_url} ({e})")
            return None

        # 并发下载, 主线程统一回写 HTML(避免多线程修改 BeautifulSoup 树)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for result in executor.map(_fetch_one, tasks):
                if result:
                    img, relative_path = result
                    img['src'] = relative_path
                    # 清理多余属性
                    for attr in ['data-original', 'data-actualsrc', 'data-size',
                                 'data-rawwidth', 'data-rawheight', 'class']:
                        if img.get(attr):
                            del img[attr]

        return str(soup)

    def _http_get(self, url, params=None, retries=2):
        """带重试的 GET 请求。

        正常账号优先走 requests(速度快, 与旧版一致); 知乎返回 403/429
        (常见于风控/新号)时自动切换到真实 Edge 浏览器, 且切换后本次任务
        全程走浏览器, 避免反复回到 requests 再次触发风控。
        """
        if self._force_browser and self._is_zhihu_url(url):
            return self._browser_get(url, params=params)

        last_error = None
        for attempt in range(retries):
            try:
                response = self._session.get(url, params=params, timeout=15)
                if response.status_code == 200:
                    # 知乎风控可能返回 200 + 错误 JSON(如 code 40362), 同样切 Edge
                    if self._is_zhihu_url(url) and self._response_is_blocked(response):
                        return self._browser_get(url, params=params)
                    return response
                if response.status_code in (403, 429):
                    if self._is_zhihu_url(url):
                        return self._browser_get(url, params=params)
                    raise RuntimeError(f"HTTP {response.status_code}: 请求被拦截")
                last_error = RuntimeError(f"HTTP {response.status_code}")
            except requests.RequestException as e:
                last_error = e
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
        raise last_error

    def get_column_article_urls(self, column_url):
        """通过 API 获取专栏下的所有文章链接"""
        match = re.search(r'(?:column/|zhuanlan\.zhihu\.com/)(c_[a-zA-Z0-9_-]+|[a-zA-Z0-9_-]+)', column_url)
        if not match:
            return {"status": "error", "message": "无法从链接中识别出专栏 ID"}
            
        column_id = match.group(1)
        if column_id == 'p': 
            return {"status": "error", "message": "这是单篇文章链接，不是专栏链接"}
            
        api_url = f"https://www.zhihu.com/api/v4/columns/{column_id}/items"
        
        article_urls = []
        offset = 0
        limit = 20
        
        print(f"🔍 识别到专栏 ID: [{column_id}]，正在获取文章目录...")
        
        while True:
            params = {"limit": limit, "offset": offset}
            try:
                response = self._http_get(api_url, params=params)
                data = response.json()
                items = data.get("data", [])
                
                if not items: 
                    break
                    
                for item in items:
                    if item.get("type") == "article":
                        article_id = item.get("id")
                        if article_id:
                            article_urls.append(f"https://zhuanlan.zhihu.com/p/{article_id}")
                            
                is_end = data.get("paging", {}).get("is_end", True)
                if is_end:
                    break
                    
                offset += limit
                time.sleep(0.5) 
                
            except Exception as e:
                print(f"获取专栏列表时发生异常: {e}")
                break
                
        return {"status": "success", "urls": article_urls}

    def get_collection_article_urls(self, collection_url):
        """通过 API 获取收藏夹下的全部文章/回答链接"""
        match = re.search(r'(?:collection/|collections/)(\d+)', collection_url)
        if not match:
            return {"status": "error", "message": "无法从链接中识别出收藏夹 ID"}

        collection_id = match.group(1)
        api_url = f"https://www.zhihu.com/api/v4/collections/{collection_id}/items"

        article_urls = []
        offset = 0
        limit = 20

        print(f"🔖 识别到收藏夹 ID: [{collection_id}]，正在获取收藏内容...")

        while True:
            params = {"limit": limit, "offset": offset}
            try:
                response = self._http_get(api_url, params=params)
                data = response.json()
                items = data.get("data", [])

                if not items:
                    break

                for item in items:
                    content = item.get("content") or {}
                    ctype = content.get("type")
                    cid = content.get("id")
                    if ctype == "article" and cid:
                        article_urls.append(f"https://zhuanlan.zhihu.com/p/{cid}")
                    elif ctype == "answer":
                        qid = (content.get("question") or {}).get("id")
                        if qid and cid:
                            article_urls.append(
                                f"https://www.zhihu.com/question/{qid}/answer/{cid}")

                if data.get("paging", {}).get("is_end", True):
                    break

                offset += limit
                time.sleep(0.5)

            except Exception as e:
                print(f"获取收藏夹列表时发生异常: {e}")
                break

        return {"status": "success", "urls": article_urls}

    def fetch_and_parse(self, url):
        try:
            response = self._http_get(url)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            title_node = soup.select_one('.Post-Title') or soup.select_one('.QuestionHeader-title')
            title = title_node.text.strip() if title_node else "未命名文章"
            
            # ==========================================
            # 元数据提取
            # ==========================================
            author_node = soup.select_one('.AuthorInfo-name') or soup.select_one('.UserLink-link')
            author = author_node.text.strip() if author_node else "未知作者"
            
            # 防止同问题下的不同回答互相覆盖文件
            if '/answer/' in url:
                title = f"{title} - {author}的回答"
            
            time_node = soup.select_one('.ContentItem-time')
            publish_time = time_node.text.strip().replace("发布于 ", "").replace("编辑于 ", "") if time_node else "未知时间"
            
            tags = [tag.text.strip() for tag in soup.select('.TopicLink')]
            
            metadata = {
                "title": title,
                "author": author,
                "date": publish_time,
                "tags": tags,
                "url": url
            }

            content_node = (soup.select_one('.RichText')
                            or soup.select_one('.Post-RichText')
                            or soup.select_one('.Post-Content'))
            if not content_node:
                return {"status": "error",
                        "message": "无法找到文章正文内容 (可能 Cookie 已过期或内容不可见)，请尝试退出登录后重新扫码"}
            
            clean_html = str(content_node)
            clean_html = self._download_and_replace_images(clean_html, title)
            
            return {
                "status": "success",
                "title": title,
                "html_content": clean_html,
                "url": url,
                "metadata": metadata
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}


class _BrowserResponse:
    def __init__(self, text, status_code=200, url=""):
        self.text = text
        self.status_code = status_code
        self.url = url

    def json(self):
        return json.loads(self.text)
