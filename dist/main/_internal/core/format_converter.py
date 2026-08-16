import os
import re
import uuid
from pathlib import Path

import html2text
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from core.paths import get_output_dir, setup_console

setup_console()

class FormatConverter:
    def __init__(self, output_dir=None):
        self.output_dir = output_dir or get_output_dir()
        os.makedirs(self.output_dir, exist_ok=True)

    def _sanitize_filename(self, filename):
        # 移除 Windows 非法字符，并去掉结尾的空格/点号（否则会导致文件名无效）
        cleaned = re.sub(r'[\\/*?:"<>|]', "", filename).strip().rstrip(". ")
        return cleaned or "未命名文章"

    # ==========================================
    # 提取并清理数学公式
    # ==========================================
    def _extract_and_clean_math(self, html_content, for_markdown=False):
        soup = BeautifulSoup(html_content, 'html.parser')
        math_map = {} 
        
        def fix_latex(code):
            if not code: return ""
            # 1. 修复知乎的 \\ 转义问题
            code = code.replace(r'\\{', r'\{').replace(r'\\}', r'\}')
            
            # 2. 清除不可见零宽字符
            code = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', code)
            
            # 3. 修复结尾悬空的 ^ 或 _ 
            code = re.sub(r'\^(\s*)$', r'^{}', code)
            code = re.sub(r'_(\s*)$', r'_{}', code)
            
            # 4. 纠正 \color 导致的上标/下标缺括号问题 
            code = re.sub(r'(\^|_)\s*(\\color\{[^\}]+\})\s*(\{[^\}]+\}|\\[a-zA-Z]+|[a-zA-Z0-9+\-])', r'\1{\2\3}', code)
            
            # 5. 替换 MathJax 默认不支持的波浪线和删除线
            code = code.replace(r'\uwave', r'\underline').replace(r'\xout', r'\cancel')
            
            return code.strip()
            
        # 处理知乎新版公式
        for span in soup.find_all('span', class_='ztext-math'):
            raw_latex = span.get('data-tex')
            if raw_latex:
                clean_latex = fix_latex(raw_latex)
                formatted_latex = f"\n$$\n{clean_latex}\n$$\n" if span.get('data-block') else f" ${clean_latex}$ "
                
                if for_markdown:
                    placeholder = f"PLACEHOLDERMATH{uuid.uuid4().hex}"
                    math_map[placeholder] = formatted_latex
                    span.replace_with(placeholder)
                else:
                    span.replace_with(formatted_latex)

        # 处理知乎旧版图片公式
        for img in soup.find_all('img', class_='eeimg'):
            raw_latex = img.get('alt')
            if raw_latex:
                clean_latex = fix_latex(raw_latex)
                formatted_latex = f" ${clean_latex}$ "
                
                if for_markdown:
                    placeholder = f"PLACEHOLDERMATH{uuid.uuid4().hex}"
                    math_map[placeholder] = formatted_latex
                    img.replace_with(placeholder)
                else:
                    img.replace_with(formatted_latex)
                    
        return str(soup), math_map

    def to_markdown(self, html_content, title, metadata=None):
        clean_html, math_map = self._extract_and_clean_math(html_content, for_markdown=True)
        
        h = html2text.HTML2Text()
        h.ignore_links = False     
        h.body_width = 0           
        
        print("📝 正在生成 Markdown 文件...")
        md_content = h.handle(clean_html)
        
        for placeholder, latex_str in math_map.items():
            md_content = md_content.replace(placeholder, latex_str)
            
        safe_title = self._sanitize_filename(title)
        filepath = os.path.join(self.output_dir, f"{safe_title}.md")
        
        yaml_header = ""
        if metadata:
            yaml_header += "---\n"
            yaml_header += f"title: \"{metadata.get('title', title)}\"\n"
            yaml_header += f"author: \"{metadata.get('author', '未知')}\"\n"
            yaml_header += f"date: {metadata.get('date', '1970-01-01')}\n"
            
            if metadata.get('tags'):
                tags_formatted = ", ".join([f'"{t}"' for t in metadata['tags']])
                yaml_header += f"tags: [{tags_formatted}]\n"
            else:
                yaml_header += "tags: [知乎备份]\n"
                
            yaml_header += f"url: \"{metadata.get('url', '')}\"\n"
            yaml_header += "---\n\n"
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(yaml_header)
            f.write(f"# {title}\n\n")
            f.write(md_content)
            
        print(f"✅ Markdown 已保存至: {filepath}")
        return filepath

    def to_pdf(self, html_content, title):
        print("🖨️ 正在渲染 PDF...")
        
        clean_html, _ = self._extract_and_clean_math(html_content, for_markdown=False)
        
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{title}</title>
            <script>
            MathJax = {{
              loader: {{load: ['[tex]/noerrors', '[tex]/noundefined', '[tex]/physics', '[tex]/cancel', '[tex]/color']}},
              tex: {{ 
                packages: {{'[+]': ['noerrors', 'noundefined', 'physics', 'cancel', 'color']}},
                inlineMath: [['$', '$']], 
                displayMath: [['$$', '$$']] 
              }},
              svg: {{ fontCache: 'global' }}
            }};
            </script>
            <script type="text/javascript" id="MathJax-script" async
              src="https://registry.npmmirror.com/mathjax/3.2.2/files/es5/tex-svg.js">
            </script>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.8; padding: 2em; max-width: 900px; margin: 0 auto; color: #333; }}
                img {{ max-width: 100%; height: auto; border-radius: 8px; margin: 20px 0; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                h1, h2, h3 {{ color: #111; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
                pre {{ background: #f6f8fa; padding: 16px; border-radius: 8px; overflow-x: auto; font-family: Consolas, monospace; }}
                code {{ background: rgba(27,31,35,0.05); padding: 0.2em 0.4em; border-radius: 3px; }}
                blockquote {{ border-left: 4px solid #dfe2e5; padding-left: 1em; color: #6a737d; margin-left: 0; }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            {clean_html}
        </body>
        </html>
        """
        
        safe_title = self._sanitize_filename(title)
        filepath = os.path.join(self.output_dir, f"{safe_title}.pdf")

        # 关键修复: 把完整 HTML 写入 outputs 目录下的临时文件, 再用 file:// 打开该文件。
        # 若用 page.set_content() 注入, 页面源是 about:blank, 浏览器会拦截所有本地
        # 图片(相对路径和 file:// 绝对路径都加载不出来), 导致 PDF 里没有文章图片。
        # 文档本身是 file:// 页面时, 相对路径 assets/... 才能正常解析并嵌入 PDF。
        temp_html = os.path.join(self.output_dir, f"._render_{uuid.uuid4().hex}.html")
        try:
            with open(temp_html, "w", encoding="utf-8") as f:
                f.write(full_html)

            with sync_playwright() as p:
                browser = p.chromium.launch(channel="msedge", headless=True)
                try:
                    page = browser.new_page()

                    try:
                        page.goto(Path(temp_html).as_uri(), wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception as e:
                        print(f"⚠️ [警告] 部分外部资源加载超时，已强制跳过...")

                    page.wait_for_timeout(3000)

                    page.pdf(
                        path=filepath, 
                        format="A4", 
                        margin={"top": "20px", "bottom": "20px", "left": "20px", "right": "20px"},
                        print_background=True
                    )
                finally:
                    browser.close()
        finally:
            try:
                os.remove(temp_html)
            except OSError:
                pass

        print(f"📕 PDF 已保存至: {filepath}")
        return filepath