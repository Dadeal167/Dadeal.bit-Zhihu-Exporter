# -*- coding: utf-8 -*-
"""修复后代码的冒烟/单元测试（无需 pytest，直接 python 运行）

覆盖：core.paths / auth_manager / spider_engine / format_converter / main(GUI 离屏)
用本地 HTTP 服务器模拟知乎页面，不依赖外网，不依赖真实知乎 Cookie。
"""
import json
import os
import shutil
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.paths import setup_console

setup_console()

PASS = []
FAIL = []


def check(name, cond, extra=""):
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name} {extra}")


# 1x1 像素 PNG
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da6360000002000151a8a5f00000000049454e44ae426082"
)

PORT = 0  # 由服务器启动时回填
HITS = {"img": 0}

ARTICLE_HTML = """<html><body>
<h1 class="Post-Title">测试文章</h1>
<div class="AuthorInfo-name">测试作者</div>
<div class="ContentItem-time">发布于 2024-01-01</div>
<a class="TopicLink" href="#">标签甲</a>
<div class="RichText">
<p>正文段落</p>
<img data-original="http://127.0.0.1:PORT/test.png">
<img class="eeimg" alt="x^2" src="http://127.0.0.1:PORT/equation/1">
</div>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/test.png":
            HITS["img"] += 1
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            self.wfile.write(PNG_BYTES)
        elif self.path == "/deny":
            self.send_response(403)
            self.end_headers()
        elif self.path == "/missing":
            self.send_response(404)
            self.end_headers()
        elif self.path == "/article" or self.path.startswith("/question"):
            html = ARTICLE_HTML.replace("PORT", str(PORT))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def start_server():
    global PORT
    server = HTTPServer(("127.0.0.1", 0), Handler)
    PORT = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


# ================= 1. core.paths =================
print("\n== 1. core.paths 路径模块 ==")
from core import paths

check("dev 模式 data 目录在项目根", paths.get_data_dir() == os.path.join(ROOT, "data"))
check("dev 模式 outputs 目录在项目根", paths.get_output_dir() == os.path.join(ROOT, "outputs"))
check("cookie 文件路径", paths.get_cookie_file().endswith("cookies.json"))
check("history 文件路径", paths.get_history_file().endswith("download_history.json"))
check("资源路径 icon.ico", os.path.basename(paths.get_resource_path("icon.ico")) == "icon.ico")

# ================= 2. auth_manager =================
print("\n== 2. auth_manager Cookie 校验 ==")
from core.auth_manager import AuthManager

tmpdir = os.path.join(ROOT, "data", "_test_tmp")
os.makedirs(tmpdir, exist_ok=True)
future = int(time.time()) + 3600
past = int(time.time()) - 3600


def write_cookie(data, name):
    p = os.path.join(tmpdir, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return p


check("文件不存在 → False",
      AuthManager(cookie_file=os.path.join(tmpdir, "none.json")).has_valid_cookies() is False)

bad = os.path.join(tmpdir, "corrupt.json")
with open(bad, "w") as f:
    f.write("{not valid json")
check("损坏文件 → False", AuthManager(cookie_file=bad).has_valid_cookies() is False)

p = write_cookie([{"name": "z_c0", "value": "x", "expires": future}], "valid.json")
check("有效凭证(z_c0+未过期) → True", AuthManager(cookie_file=p).has_valid_cookies() is True)

p = write_cookie([{"name": "z_c0", "value": "x", "expires": -1}], "session.json")
check("会话级 Cookie(expires=-1) → True", AuthManager(cookie_file=p).has_valid_cookies() is True)

p = write_cookie([{"name": "d_c0", "value": "x", "expires": future}], "no_zc0.json")
check("缺少 z_c0 → False", AuthManager(cookie_file=p).has_valid_cookies() is False)

p = write_cookie([{"name": "z_c0", "value": "x", "expires": past}], "expired.json")
check("z_c0 已过期 → False", AuthManager(cookie_file=p).has_valid_cookies() is False)

# ================= 3. spider_engine =================
print("\n== 3. spider_engine 爬虫引擎 ==")
server = start_server()
from core.spider_engine import SpiderEngine

cookie_p = write_cookie([{"name": "z_c0", "value": "abc", "expires": future}], "spider_cookie.json")
eng = SpiderEngine(cookie_file=cookie_p)
check("构造 + Cookie 转换", eng.cookies_dict.get("z_c0") == "abc")
check("文件名清洗(非法字符+尾点)", eng._sanitize_filename('a/b:c*?"<>|. ') == "abc")
check("空标题兜底", eng._sanitize_filename("   ") == "未命名文章")

r = eng._http_get(f"http://127.0.0.1:{PORT}/ok")
check("_http_get 200 正常", r.status_code == 200)

t0 = time.time()
try:
    eng._http_get(f"http://127.0.0.1:{PORT}/missing")
    check("404 应抛异常", False)
except RuntimeError as e:
    check("404 重试后抛 RuntimeError", "404" in str(e), f"e={e}")
check("404 场景包含退避重试(>=1.5s)", time.time() - t0 >= 1.5)

t0 = time.time()
try:
    eng._http_get(f"http://127.0.0.1:{PORT}/deny")
    check("403 应抛异常", False)
except RuntimeError as e:
    check("403 明确提示被拦截", "拦截" in str(e), f"e={e}")
check("403 不重试(立即抛出)", time.time() - t0 < 1.0)


class FakeResp:
    def __init__(self, data):
        self._d = data

    def json(self):
        return self._d


orig_http_get = eng._http_get

eng._http_get = lambda url, params=None, retries=2: FakeResp(
    {"data": [{"type": "article", "id": 111}, {"type": "answer", "id": 222}],
     "paging": {"is_end": True}})
res = eng.get_column_article_urls("https://zhuanlan.zhihu.com/c_12345")
check("专栏目录解析(过滤回答)", res == {"status": "success",
                                 "urls": ["https://zhuanlan.zhihu.com/p/111"]}, f"got={res}")

res = eng.get_column_article_urls("https://zhuanlan.zhihu.com/p/999")
check("单篇链接误入专栏 → 报错", res["status"] == "error")

calls = {"n": 0}


def fake_paging(url, params=None, retries=2):
    calls["n"] += 1
    if calls["n"] == 1:
        return FakeResp({"data": [{"type": "article", "id": 1}], "paging": {"is_end": False}})
    return FakeResp({"data": [{"type": "article", "id": 2}], "paging": {"is_end": True}})


eng._http_get = fake_paging
res = eng.get_column_article_urls("https://zhuanlan.zhihu.com/c_999")
check("专栏 API 自动翻页", res["urls"] == ["https://zhuanlan.zhihu.com/p/1",
                                    "https://zhuanlan.zhihu.com/p/2"] and calls["n"] == 2, f"got={res}")

# 恢复真实 _http_get，进行真实抓取解析测试
eng._http_get = orig_http_get

result = eng.fetch_and_parse(f"http://127.0.0.1:{PORT}/article")
ok = result.get("status") == "success"
check("文章解析成功", ok, f"got={result.get('message')}")
if ok:
    check("标题提取", result["title"] == "测试文章")
    check("作者提取", result["metadata"]["author"] == "测试作者")
    check("时间提取(去前缀)", result["metadata"]["date"] == "2024-01-01")
    check("标签提取", result["metadata"]["tags"] == ["标签甲"])
    check("URL 写入元数据", result["metadata"]["url"].endswith("/article"))

    img_file = os.path.join(ROOT, "outputs", "assets", "测试文章", "img_001.png")
    check("图片已下载到本地", os.path.exists(img_file) and os.path.getsize(img_file) == len(PNG_BYTES))
    check("图片 src 已替换为相对路径", "assets/测试文章/img_001.png" in result["html_content"])
    check("公式图(equation)被跳过", "http://127.0.0.1" in result["html_content"] and HITS["img"] == 1)

    res2 = eng.fetch_and_parse(f"http://127.0.0.1:{PORT}/question/1/answer/2")
    if res2.get("status") == "success":
        check("回答标题拼接(防覆盖)", res2["title"] == "测试文章 - 测试作者的回答",
              f"got={res2['title']}")
    else:
        check("回答标题拼接(防覆盖)", False, f"got={res2.get('message')}")
else:
    for name in ["标题提取", "作者提取", "时间提取(去前缀)", "标签提取", "URL 写入元数据",
                 "图片已下载到本地", "图片 src 已替换为相对路径", "公式图(equation)被跳过",
                 "回答标题拼接(防覆盖)"]:
        print(f"  [SKIP] {name}")

# ================= 4. format_converter =================
print("\n== 4. format_converter 格式转换 ==")
from core.format_converter import FormatConverter

conv = FormatConverter()
check("输出目录为统一 outputs", conv.output_dir == os.path.join(ROOT, "outputs"))
check("文件名清洗", conv._sanitize_filename('a/b:c*?"<>|. ') == "abc")

math_html = '''<div class="RichText">
<span class="ztext-math" data-tex="\\frac{a}{b}">?</span>
<span class="ztext-math" data-block="true" data-tex="E = mc^2">?</span>
<img class="eeimg" alt="x^2" src="http://x/equation/1">
</div>'''

clean, _ = conv._extract_and_clean_math(math_html, for_markdown=False)
check("行内公式 → $...$", "$\\frac{a}{b}$" in clean)
check("块级公式 → $$...$$", "$$\nE = mc^2" in clean)
check("旧版公式 img.eeimg → $...$", "$x^2$" in clean)

clean2, m2 = conv._extract_and_clean_math(math_html, for_markdown=True)
check("Markdown 占位符保护", len(m2) == 3 and "PLACEHOLDERMATH" in clean2)

md_path = conv.to_markdown(math_html, "测试导出",
                           {"title": "测试导出", "author": "作者A", "date": "2024-01-01",
                            "tags": ["T1"], "url": "http://x"})
check("Markdown 文件生成", os.path.exists(md_path))
if os.path.exists(md_path):
    content = open(md_path, encoding="utf-8").read()
    check("YAML Front Matter", content.startswith("---") and 'author: "作者A"' in content)
    check("公式在 Markdown 中还原", "\\frac{a}{b}" in content and "$$" in content)

print("    (渲染 PDF，约 5-15 秒，请稍候...)")
try:
    pdf_path = conv.to_pdf(math_html, "测试导出PDF")
    check("PDF 文件生成", os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1000,
          f"path={pdf_path}")
except Exception as e:
    check("PDF 文件生成", False, f"异常: {type(e).__name__}: {e}")

# 关键回归: PDF 必须嵌入相对路径的本地图片(曾有 bug: about:blank 拦截本地图片)
print("    (验证 PDF 图片嵌入，约 5-15 秒，请稍候...)")
img_tmp = os.path.join(ROOT, "outputs", "assets", "PDF图片测试")
os.makedirs(img_tmp, exist_ok=True)
with open(os.path.join(img_tmp, "img_001.png"), "wb") as f:
    f.write(PNG_BYTES)
img_html = ('<div class="RichText"><p>图片嵌入测试</p>'
            '<img src="assets/PDF图片测试/img_001.png"></div>')
pdf2_path = None
try:
    pdf2_path = conv.to_pdf(img_html, "PDF图片嵌入测试")
    embedded = False
    try:
        import fitz
        doc = fitz.open(pdf2_path)
        for page in doc:
            if page.get_images():
                embedded = True
        doc.close()
    except ImportError:
        embedded = os.path.getsize(pdf2_path) > 30000
    check("PDF 嵌入本地相对路径图片", embedded, f"pdf={pdf2_path}")
except Exception as e:
    check("PDF 嵌入本地相对路径图片", False, f"异常: {type(e).__name__}: {e}")

# ================= 5. GUI 离屏构建 =================
print("\n== 5. main GUI 离屏构建 ==")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

app = QApplication([])
from main import MainWindow, LoginDialog

try:
    w = MainWindow()
    check("主窗口构建", bool(w.windowTitle()))
    check("输入框存在", w.url_input is not None)
    check("默认勾选 MD+PDF", w.cb_md.isChecked() and w.cb_pdf.isChecked())
    w.url_input.setText("")
    w.start_processing()
    check("空输入被拦截并提示", "错误" in w.log_console.toPlainText())
    w.close()
except Exception as e:
    check("主窗口构建", False, f"异常: {type(e).__name__}: {e}")

try:
    d = LoginDialog()
    check("登录弹窗构建", bool(d.login_btn.text()))
    d.close()
except Exception as e:
    check("登录弹窗构建", False, f"异常: {type(e).__name__}: {e}")

# ================= 清理测试产物 =================
print("\n== 清理测试产物 ==")
shutil.rmtree(tmpdir, ignore_errors=True)
for p in [os.path.join(ROOT, "outputs", "测试导出.md"),
          os.path.join(ROOT, "outputs", "测试导出PDF.pdf"),
          os.path.join(ROOT, "outputs", "PDF图片嵌入测试.pdf"),
          os.path.join(ROOT, "outputs", "assets", "PDF图片测试"),
          os.path.join(ROOT, "outputs", "assets", "测试文章"),
          os.path.join(ROOT, "outputs", "assets", "测试文章 - 测试作者的回答"),
          os.path.join(ROOT, "outputs", "_pdftest")]:
    if os.path.isdir(p):
        shutil.rmtree(p, ignore_errors=True)
    elif os.path.exists(p):
        os.remove(p)
print("   清理完成")

# ================= 汇总 =================
print("\n" + "=" * 50)
print(f"测试结果: 通过 {len(PASS)} 项, 失败 {len(FAIL)} 项")
if FAIL:
    print("失败项:")
    for name in FAIL:
        print(f"  - {name}")
    sys.exit(1)
print("🎉 全部通过！")
