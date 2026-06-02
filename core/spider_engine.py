import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

class SpiderEngine:
    def __init__(self, cookie_file="data/cookies.json"):
        self.cookie_file = cookie_file
        self.headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive"
        }
        self.cookies_dict = self._load_and_convert_cookies()

    def _load_and_convert_cookies(self):
        if not os.path.exists(self.cookie_file):
            raise FileNotFoundError(f"找不到凭证文件 {self.cookie_file}，请先运行 auth_manager.py 登录。")
            
        with open(self.cookie_file, "r", encoding="utf-8") as f:
            playwright_cookies = json.load(f)
            
        requests_cookies = {}
        for cookie in playwright_cookies:
            requests_cookies[cookie['name']] = cookie['value']
        return requests_cookies

    def _sanitize_filename(self, filename):
        return re.sub(r'[\\/*?:"<>|]', "", filename).strip()

    # ==========================================
    # 图片本地化下载器
    # ==========================================
    def _download_and_replace_images(self, html_content, title):
        soup = BeautifulSoup(html_content, 'html.parser')
        safe_title = self._sanitize_filename(title)
        
        assets_dir = os.path.join("outputs", "assets", safe_title)
        
        img_headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": "https://www.zhihu.com/" 
        }

        img_tags = soup.find_all('img')
        total_imgs = len(img_tags)
        
        if total_imgs > 0:
            os.makedirs(assets_dir, exist_ok=True)
            
        for index, img in enumerate(img_tags):
            img_url = img.get('data-original') or img.get('data-actualsrc') or img.get('src')
            
            # 过滤非外部链接
            if not img_url or not img_url.startswith('http') or 'equation' in img_url:
                continue
                
            try:
                ext = os.path.splitext(urlparse(img_url).path)[1]
                if ext.lower() not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    ext = '.jpg'
                    
                local_filename = f"img_{index+1:03d}{ext}" 
                local_filepath = os.path.join(assets_dir, local_filename)
                relative_path = f"assets/{safe_title}/{local_filename}"

                response = requests.get(img_url, headers=img_headers, timeout=10)
                if response.status_code == 200:
                    with open(local_filepath, 'wb') as f:
                        f.write(response.content)
                        
                    img['src'] = relative_path
                    
                    # 清理多余属性
                    for attr in ['data-original', 'data-actualsrc', 'data-size', 'data-rawwidth', 'data-rawheight', 'class']:
                        if img.get(attr):
                            del img[attr]
                
                time.sleep(0.2)
                
            except Exception as e:
                pass
                
        return str(soup)

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
                response = requests.get(api_url, headers=self.headers, cookies=self.cookies_dict, params=params, timeout=10)
                if response.status_code != 200:
                    break
                    
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

    def fetch_and_parse(self, url):
        try:
            response = requests.get(url, headers=self.headers, cookies=self.cookies_dict, timeout=10)
            response.raise_for_status() 
            
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
                return {"status": "error", "message": "无法找到文章正文内容"}
            
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