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

    def _build_filename(self, title, metadata=None, template=None):
        """按模板生成文件名; 支持占位符 {title} {date} {author}, 空模板=原标题"""
        if not template:
            return self._sanitize_filename(title)
        try:
            name = template.replace("{title}", title)
            if metadata:
                name = name.replace("{date}", str(metadata.get("date", "")))
                name = name.replace("{author}", str(metadata.get("author", "")))
        except Exception:
            return self._sanitize_filename(title)
        return self._sanitize_filename(name)

    @staticmethod
    def _build_toc(md_content):
        """从二级及以上标题生成可跳转目录; 标题不足 3 个时返回 None"""
        toc = []
        for line in md_content.splitlines():
            match = re.match(r"^(#{2,4})\s+(.+)$", line)
            if match:
                level = len(match.group(1))
                text = match.group(2).strip()
                anchor = re.sub(r"[^\w\u4e00-\u9fff -]", "", text).strip().replace(" ", "-")
                toc.append("  " * (level - 2) + f"- [{text}](#{anchor})")
        return "\n".join(toc) if len(toc) >= 3 else None

    def to_markdown(self, html_content, title, metadata=None, filename_template=None):
        clean_html, math_map = self._extract_and_clean_math(html_content, for_markdown=True)
        
        h = html2text.HTML2Text()
        h.ignore_links = False     
        h.body_width = 0           
        
        print("📝 正在生成 Markdown 文件...")
        md_content = h.handle(clean_html)
        
        for placeholder, latex_str in math_map.items():
            md_content = md_content.replace(placeholder, latex_str)

        # 自动生成目录(标题足够多时)
        toc = self._build_toc(md_content)
        if toc:
            md_content = f"## 目录\n\n{toc}\n\n---\n\n{md_content}"
            
        safe_title = self._build_filename(title, metadata, filename_template)
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

            if metadata.get('summary'):
                yaml_header += f"summary: \"{str(metadata['summary']).replace(chr(34), chr(39))}\"\n"

            if metadata.get('category'):
                yaml_header += f"category: \"{str(metadata['category']).replace(chr(34), chr(39))}\"\n"
                
            yaml_header += f"url: \"{metadata.get('url', '')}\"\n"
            yaml_header += "---\n\n"
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(yaml_header)
            f.write(f"# {title}\n\n")
            f.write(md_content)
            
        print(f"✅ Markdown 已保存至: {filepath}")
        return filepath

    @staticmethod
    def _mathjax_src():
        """本地 MathJax 优先(公式离线可渲染), 文件缺失时回退 CDN"""
        try:
            from core.paths import get_resource_path
            local = get_resource_path("resources/mathjax/tex-svg.js")
            if os.path.isfile(local):
                return Path(local).as_uri()
        except Exception:
            pass
        return "https://registry.npmmirror.com/mathjax/3.2.2/files/es5/tex-svg.js"

    def to_pdf(self, html_content, title, renderer=None, render_wait_ms=None,
               filename_template=None):
        """渲染 PDF。renderer 为共享的 PDFRenderer(批量任务复用同一浏览器实例);
        不传时自动创建临时实例, 渲染完自动关闭。render_wait_ms 控制渲染后的等待时长。"""
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
              svg: {{ fontCache: 'global' }},
              startup: {{
                ready: () => {{
                  MathJax.startup.defaultReady();
                  MathJax.startup.promise.then(() => {{
                    MathJax.typesetPromise().then(() => {{
                      document.body.setAttribute('data-mathjax-ready', '1');
                    }}).catch(() => {{
                      document.body.setAttribute('data-mathjax-ready', '1');
                    }});
                  }});
                }}
              }}
            }};
            </script>
            <script type="text/javascript" id="MathJax-script" async
              src="{self._mathjax_src()}">
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
        
        safe_title = self._build_filename(title, None, filename_template)
        filepath = os.path.join(self.output_dir, f"{safe_title}.pdf")

        # 关键修复: 把完整 HTML 写入 outputs 目录下的临时文件, 再用 file:// 打开该文件。
        # 若用 page.set_content() 注入, 页面源是 about:blank, 浏览器会拦截所有本地
        # 图片(相对路径和 file:// 绝对路径都加载不出来), 导致 PDF 里没有文章图片。
        # 文档本身是 file:// 页面时, 相对路径 assets/... 才能正常解析并嵌入 PDF。
        temp_html = os.path.join(self.output_dir, f"._render_{uuid.uuid4().hex}.html")
        try:
            with open(temp_html, "w", encoding="utf-8") as f:
                f.write(full_html)

            own_renderer = renderer is None
            if own_renderer:
                renderer = PDFRenderer(render_wait_ms=render_wait_ms or 3000)
            try:
                renderer.render(temp_html, filepath)
            finally:
                if own_renderer:
                    renderer.close()
        finally:
            try:
                os.remove(temp_html)
            except OSError:
                pass

        print(f"📕 PDF 已保存至: {filepath}")
        return filepath

    @staticmethod
    def _ensure_local_mathjax(output_dir):
        """把本地 MathJax 完整版复制到输出目录 _mathjax/ 下, 供导出的 HTML 相对引用。

        普通浏览器打开本地 HTML 时, 绝对 file:// 脚本会被拦截; 相对路径脚本可以正常
        加载, 且完整版(tex-svg-full.js)自带全部扩展, 无需动态加载。返回相对路径,
        本地文件缺失时返回 None(调用方回退 CDN)。
        """
        try:
            from core.paths import get_resource_path
            src = get_resource_path("resources/mathjax/tex-svg-full.js")
            if not os.path.isfile(src):
                return None
            dest_dir = os.path.join(output_dir, "_mathjax")
            dest = os.path.join(dest_dir, "tex-svg-full.js")
            if not os.path.isfile(dest) or os.path.getsize(dest) != os.path.getsize(src):
                os.makedirs(dest_dir, exist_ok=True)
                import shutil
                shutil.copy2(src, dest)
            return "_mathjax/tex-svg-full.js"
        except Exception:
            return None

    def to_html(self, html_content, title, metadata=None, filename_template=None):
        """导出独立 HTML: 网页原排版 100% 保真, 公式由本地 MathJax 渲染(离线可用)"""
        print("🌐 正在生成 HTML 文件...")

        clean_html, _ = self._extract_and_clean_math(html_content, for_markdown=False)

        mathjax_src = self._ensure_local_mathjax(self.output_dir) or (
            "https://registry.npmmirror.com/mathjax/3.2.2/files/es5/tex-svg-full.js")
        cdn_fallback = ("var s=document.createElement('script');"
                        "s.src='https://registry.npmmirror.com/mathjax/3.2.2/files/es5/tex-svg-full.js';"
                        "s.async=true;document.head.appendChild(s);")

        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
<script>
MathJax = {{
  tex: {{
    packages: {{'[+]': ['noerrors', 'noundefined', 'physics', 'cancel', 'color']}},
    inlineMath: [['$', '$']],
    displayMath: [['$$', '$$']]
  }},
  svg: {{ fontCache: 'global' }}
}};
</script>
<script type="text/javascript" async src="{mathjax_src}" onerror="{cdn_fallback}"></script>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
       line-height: 1.8; max-width: 900px; margin: 0 auto; padding: 2em; color: #333; }}
img {{ max-width: 100%; height: auto; border-radius: 8px; margin: 16px 0; }}
h1, h2, h3 {{ color: #111; border-bottom: 1px solid #eaecef; padding-bottom: .3em; }}
pre {{ background: #f6f8fa; padding: 16px; border-radius: 8px; overflow-x: auto; }}
code {{ background: rgba(27,31,35,.05); padding: .2em .4em; border-radius: 3px; }}
blockquote {{ border-left: 4px solid #dfe2e5; padding-left: 1em; color: #6a737d; margin-left: 0; }}
</style>
</head>
<body>
<h1>{title}</h1>
{clean_html}
</body>
</html>"""

        safe_title = self._build_filename(title, metadata, filename_template)
        filepath = os.path.join(self.output_dir, f"{safe_title}.html")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_html)

        print(f"🌐 HTML 已保存至: {filepath}")
        return filepath


class PDFRenderer:
    """共享无头浏览器实例批量渲染 PDF。

    每篇文章启动一次 Edge 耗时数秒; 批量任务中复用同一浏览器, 仅切换页面内容,
    可将 PDF 阶段总耗时降低数倍。渲染失败自动重试一次。
    """

    def __init__(self, render_wait_ms=3000, playwright=None, browser=None, context=None):
        self._render_wait_ms = max(0, int(render_wait_ms))
        if browser is not None:
            # 复用蜘蛛引擎已打开的 Edge(避免同一个线程里再启动第二个 Playwright 实例,
            # 否则会触发 "Sync API inside the asyncio loop" 异常导致 PDF 崩溃/程序卡死)
            self._pw = playwright
            self._browser = browser
            self._context = context
            self._owns = False
            self._page = context.new_page()
        else:
            self._pw = sync_playwright().start()
            # --allow-file-access-from-files: 允许 file:// 页面加载本地脚本/资源,
            # 否则 MathJax 无法从本地文件加载扩展, 公式渲染不出来
            self._browser = self._pw.chromium.launch(
                channel="msedge", headless=True,
                args=["--allow-file-access-from-files", "--allow-file-access"])
            self._context = self._browser.new_context(locale="zh-CN")
            self._page = self._context.new_page()
            self._owns = True

    def owns_browser(self):
        """返回是否由本渲染器独占浏览器(共享模式返回 False)"""
        return self._owns

    def render(self, temp_html, pdf_path, retries=2):
        for attempt in range(1, retries + 1):
            try:
                self._page.goto(Path(temp_html).as_uri(),
                                wait_until="domcontentloaded", timeout=60000)
                self._page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                if attempt < retries:
                    print(f"⚠️ [警告] 第 {attempt} 次加载超时，正在重试...")
                    continue
                print("⚠️ [警告] 部分外部资源加载超时，已强制跳过...")

            # 关键修复: 主动等待 MathJax 完成公式渲染(慢机器上固定等待时间不够)
            # 页面在公式排版完成后会打上 data-mathjax-ready 标记
            try:
                self._page.wait_for_function(
                    "() => document.body.getAttribute('data-mathjax-ready') === '1'",
                    timeout=30000)
            except Exception:
                print("⚠️ [警告] 数学公式渲染等待超时，PDF 中公式可能显示为原始 LaTeX...")

            self._page.wait_for_timeout(self._render_wait_ms)

            # page.pdf 本身也做重试: 失败时新建页面再试一次, 避免单个页面状态异常
            for pdf_attempt in range(1, 3):
                try:
                    self._page.pdf(
                        path=pdf_path,
                        format="A4",
                        margin={"top": "20px", "bottom": "20px", "left": "20px", "right": "20px"},
                        print_background=True
                    )
                    return
                except Exception as exc:
                    if pdf_attempt == 1:
                        print(f"⚠️ [警告] PDF 生成失败，正在重试: {exc}")
                        try:
                            self._page.close()
                        except Exception:
                            pass
                        self._page = self._context.new_page()
                        try:
                            self._page.goto(Path(temp_html).as_uri(),
                                            wait_until="domcontentloaded", timeout=60000)
                            self._page.wait_for_timeout(self._render_wait_ms)
                        except Exception:
                            pass
                    else:
                        raise RuntimeError(f"PDF 渲染失败: {exc}") from exc

    def close(self):
        if not self._owns:
            # 共享模式: 只关闭自己打开的页面, 不动蜘蛛引擎的浏览器
            try:
                self._page.close()
            except Exception:
                pass
            return
        try:
            self._browser.close()
        except Exception:
            pass
        try:
            self._pw.stop()
        except Exception:
            pass