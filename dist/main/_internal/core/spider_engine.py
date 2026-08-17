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

class SpiderEngine:
    def __init__(self, cookie_file=None, output_dir=None, image_workers=4):
        self.cookie_file = cookie_file or get_cookie_file()
        self.output_dir = output_dir or get_output_dir()
        self.image_workers = max(1, int(image_workers))
        self.headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.zhihu.com/",
        "Connection": "keep-alive"
        }
        self.cookies_dict = self._load_and_convert_cookies()

    def _load_and_convert_cookies(self):
        from core.auth_manager import AuthManager
        cookies = AuthManager(cookie_file=self.cookie_file).get_cookies()
        if not cookies:
            raise FileNotFoundError(f"找不到有效凭证 {self.cookie_file}，请先运行 auth_manager.py 登录。")

        requests_cookies = {}
        for cookie in cookies:
            requests_cookies[cookie['name']] = cookie['value']
        return requests_cookies

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

                response = requests.get(img_url, headers=img_headers, timeout=15)
                if response.status_code == 200:
                    content = response.content
                    # 按文件内容识别 GIF: 知乎部分动图链接没有 .gif 后缀,
                    # 仅凭 URL 会被误存成 .jpg 导致查看器不按动图播放
                    if content[:6] in (b"GIF89a", b"GIF87a"):
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
        """带重试的 GET 请求；403/429 视为被风控拦截，直接抛出明确错误"""
        last_error = None
        for attempt in range(retries):
            try:
                response = requests.get(url, headers=self.headers, cookies=self.cookies_dict,
                                        params=params, timeout=15)
                if response.status_code == 200:
                    return response
                if response.status_code in (403, 429):
                    raise RuntimeError(f"HTTP {response.status_code}: 请求被知乎拦截 (Cookie 可能已过期或触发风控)")
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

            content_node = soup.select_one('.RichText')
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