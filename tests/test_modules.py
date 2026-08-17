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
from pathlib import Path
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

# 伪 GIF(带 GIF89a 魔数, 用于测试按内容识别动图)
GIF_BYTES = b"GIF89a" + b"\x00" * 32

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

MULTI_HTML = """<html><body>
<h1 class="Post-Title">多图测试</h1>
<div class="AuthorInfo-name">测试作者</div>
<div class="ContentItem-time">发布于 2024-01-01</div>
<div class="RichText">
<img data-original="http://127.0.0.1:PORT/test.png">
<img data-original="http://127.0.0.1:PORT/test.png">
<img data-original="http://127.0.0.1:PORT/test.png">
</div>
</body></html>"""

ANIM_HTML = """<html><body>
<h1 class="Post-Title">动图测试</h1>
<div class="AuthorInfo-name">测试作者</div>
<div class="ContentItem-time">发布于 2024-01-01</div>
<div class="RichText">
<img data-original="http://127.0.0.1:PORT/animimg">
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
        elif self.path == "/animimg":
            # 动图链接不带 .gif 后缀(模拟知乎部分 CDN 链接)
            self.send_response(200)
            self.send_header("Content-Type", "image/gif")
            self.end_headers()
            self.wfile.write(GIF_BYTES)
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
        elif self.path == "/article_multi":
            html = MULTI_HTML.replace("PORT", str(PORT))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        elif self.path == "/article_anim":
            html = ANIM_HTML.replace("PORT", str(PORT))
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
check("cookie 文件路径(加密)", paths.get_cookie_file().endswith("cookies.dat"))
check("history 文件路径", paths.get_history_file().endswith("download_history.json"))
check("资源路径 icon.ico", os.path.basename(paths.get_resource_path("icon.ico")) == "icon.ico")
check("MathJax 本地资源已打包", os.path.isfile(
    paths.get_resource_path("resources/mathjax/tex-svg.js")))
check("日志目录自动创建", os.path.isdir(paths.get_logs_dir()))
check("日志文件按天命名", "运行日志_" in os.path.basename(paths.get_log_file()))

from core.version import __version__, APP_NAME

check("版本号统一读取", __version__ == "1.1.0" and "Dadealbit" in APP_NAME and "知乎" in APP_NAME)

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
      AuthManager(cookie_file=os.path.join(tmpdir, "none.dat")).has_valid_cookies() is False)

bad = os.path.join(tmpdir, "corrupt.dat")
with open(bad, "wb") as f:
    f.write(b"garbage-not-dpapi")
check("损坏加密文件 → False", AuthManager(cookie_file=bad).has_valid_cookies() is False)


def save_enc(name, cookies):
    m = AuthManager(cookie_file=os.path.join(tmpdir, name))
    m.save_cookies(cookies)


save_enc("valid.dat", [{"name": "z_c0", "value": "x", "expires": future}])
check("有效凭证(z_c0+未过期) → True",
      AuthManager(cookie_file=os.path.join(tmpdir, "valid.dat")).has_valid_cookies() is True)

save_enc("session.dat", [{"name": "z_c0", "value": "x", "expires": -1}])
check("会话级 Cookie(expires=-1) → True",
      AuthManager(cookie_file=os.path.join(tmpdir, "session.dat")).has_valid_cookies() is True)

save_enc("no_zc0.dat", [{"name": "d_c0", "value": "x", "expires": future}])
check("缺少 z_c0 → False",
      AuthManager(cookie_file=os.path.join(tmpdir, "no_zc0.dat")).has_valid_cookies() is False)

save_enc("expired.dat", [{"name": "z_c0", "value": "x", "expires": past}])
check("z_c0 已过期 → False",
      AuthManager(cookie_file=os.path.join(tmpdir, "expired.dat")).has_valid_cookies() is False)

# 旧版明文自动迁移为加密
legacy_cookie = os.path.join(tmpdir, "legacy_cookie.json")
with open(legacy_cookie, "w", encoding="utf-8") as f:
    json.dump([{"name": "z_c0", "value": "x", "expires": future}], f)
am = AuthManager(cookie_file=legacy_cookie)
check("旧版明文自动迁移为加密", am.has_valid_cookies() is True
      and os.path.exists(os.path.join(tmpdir, "legacy_cookie.dat"))
      and not os.path.exists(legacy_cookie))

# DPAPI 加解密往返
from core.crypto_dpapi import protect, unprotect

secret = b"hello-dpapi-123"
check("DPAPI 加解密往返", unprotect(protect(secret)) == secret)

# ================= 2.5 core.history =================
print("\n== 2.5 core.history 断点续传记录 ==")
from core import history as hist_mod

h_file = os.path.join(tmpdir, "hist.json")
hist_mod.save_history(h_file, {"u1": {"md": True, "pdf": False}})
check("保存+读取(v2 格式)", hist_mod.load_history(h_file) == {"u1": {"md": True, "pdf": False}})

legacy = os.path.join(tmpdir, "legacy.json")
with open(legacy, "w", encoding="utf-8") as f:
    json.dump(["u1", "u2"], f)
check("旧版列表自动迁移", hist_mod.load_history(legacy) == {
    "u1": {"md": True, "pdf": True}, "u2": {"md": True, "pdf": True}})

bad2 = os.path.join(tmpdir, "bad_hist.json")
with open(bad2, "w") as f:
    f.write("garbage")
check("损坏文件 → 空字典", hist_mod.load_history(bad2) == {})
check("文件不存在 → 空字典", hist_mod.load_history(os.path.join(tmpdir, "nope.json")) == {})

# ================= 2.6 core.settings =================
print("\n== 2.6 core.settings 设置模块 ==")
from core.settings import SettingsManager

# 幂等: 清理可能残留的旧测试文件
_sfile = os.path.join(tmpdir, "settings.json")
if os.path.exists(_sfile):
    os.remove(_sfile)
sm = SettingsManager(path=_sfile)
check("默认值生效", sm.get("sleep_enabled") is True and sm.get("image_workers") == 4)
check("HTML 默认勾选", sm.get("default_html") is True)
check("深色模式默认关闭", sm.get("dark_mode") is False)
check("开机自启默认关闭", sm.get("autostart") is False)
check("空输出目录 → 默认 outputs", sm.resolve_output_dir() == os.path.join(ROOT, "outputs"))

sm.update({"sleep_enabled": False, "image_workers": 6,
           "output_dir": os.path.join(tmpdir, "out")})
sm.save()
sm2 = SettingsManager(path=sm.path)
check("设置持久化", sm2.get("sleep_enabled") is False and sm2.get("image_workers") == 6)
check("自定义输出目录解析", sm2.resolve_output_dir() == os.path.join(tmpdir, "out"))

bad_settings = os.path.join(tmpdir, "bad_settings.json")
with open(bad_settings, "w") as f:
    f.write("garbage")
check("损坏设置文件 → 默认值", SettingsManager(path=bad_settings).get("sleep_enabled") is True)

# ================= 2.7 core.extras =================
print("\n== 2.7 core.extras 扩展功能 ==")
from core import extras as ex


class _FakeResp:
    status_code = 200

    def __init__(self, text):
        self._t = text

    def json(self):
        return {"response": self._t}


_orig_post = ex.requests.post
ex.requests.post = lambda *a, **k: _FakeResp("测试摘要内容")
check("AI 摘要(模拟 Ollama)", ex.summarize("文章内容") == "测试摘要内容")
ex.requests.post = lambda *a, **k: _FakeResp("这篇文章属于数学")
check("AI 分类(模拟 Ollama)", ex.classify("文章内容") == "数学")
ex.requests.post = lambda *a, **k: _FakeResp("胡言乱语")
check("AI 分类(未知回退其他)", ex.classify("文章内容") == "其他")
ex.requests.post = _orig_post
check("HTML → 纯文本", "正文" in ex.html_to_text("<p>正文</p>"))
check("Edge 检测(本机已安装)", ex.edge_available() is True)

vault = os.path.join(tmpdir, "vault")
os.makedirs(vault, exist_ok=True)
src_out = os.path.join(tmpdir, "out")
os.makedirs(os.path.join(src_out, "assets", "测试文章"), exist_ok=True)
with open(os.path.join(src_out, "assets", "测试文章", "img_001.png"), "wb") as f:
    f.write(b"png")
md_src = os.path.join(src_out, "测试文章.md")
with open(md_src, "w", encoding="utf-8") as f:
    f.write("# 测试")
check("Obsidian 同步(文章+图片)", ex.sync_to_obsidian(md_src, src_out, vault, "知乎收藏") is True
      and os.path.exists(os.path.join(vault, "知乎收藏", "测试文章.md"))
      and os.path.exists(os.path.join(vault, "知乎收藏", "assets", "测试文章", "img_001.png")))

idx = ex.record_category(tmpdir, src_out,
                         [{"title": "测试文章", "category": "数学", "file": "测试文章.md"}])
check("分类索引生成", os.path.exists(idx) and "## 数学" in open(idx, encoding="utf-8").read())

# ================= 3. spider_engine =================
print("\n== 3. spider_engine 爬虫引擎 ==")
server = start_server()
from core.spider_engine import SpiderEngine

cookie_p = os.path.join(tmpdir, "spider_cookie.dat")
AuthManager(cookie_file=cookie_p).save_cookies([{"name": "z_c0", "value": "abc", "expires": future}])
eng = SpiderEngine(cookie_file=cookie_p)
check("构造 + Cookie 转换(加密凭证)", eng.cookies_dict.get("z_c0") == "abc")
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

# 收藏夹解析(文章 + 回答)
eng._http_get = lambda url, params=None, retries=2: FakeResp({
    "data": [
        {"content": {"type": "article", "id": 111}},
        {"content": {"type": "answer", "id": 222, "question": {"id": 333}}},
    ],
    "paging": {"is_end": True}})
res = eng.get_collection_article_urls("https://www.zhihu.com/collection/12345")
check("收藏夹解析(文章+回答)", res == {"status": "success", "urls": [
    "https://zhuanlan.zhihu.com/p/111",
    "https://www.zhihu.com/question/333/answer/222"]}, f"got={res}")
res = eng.get_collection_article_urls("https://zhihu.com/xxx")
check("收藏夹链接无法识别 → 报错", res["status"] == "error")

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

    # 增量图片下载: 重复抓取同一篇, 已存在的图片不再发网络请求
    hits_before = HITS["img"]
    result_again = eng.fetch_and_parse(f"http://127.0.0.1:{PORT}/article")
    check("增量图片下载(第二次复用本地不重复下载)",
          result_again.get("status") == "success" and HITS["img"] == hits_before
          and "assets/测试文章/img_001.png" in result_again["html_content"])

    res2 = eng.fetch_and_parse(f"http://127.0.0.1:{PORT}/question/1/answer/2")
    if res2.get("status") == "success":
        check("回答标题拼接(防覆盖)", res2["title"] == "测试文章 - 测试作者的回答",
              f"got={res2['title']}")
    else:
        check("回答标题拼接(防覆盖)", False, f"got={res2.get('message')}")

    # 并发多图下载
    res3 = eng.fetch_and_parse(f"http://127.0.0.1:{PORT}/article_multi")
    ok3 = res3.get("status") == "success"
    check("多图文章解析", ok3, f"got={res3.get('message')}")
    if ok3:
        mdir = os.path.join(ROOT, "outputs", "assets", "多图测试")
        files = sorted(os.listdir(mdir)) if os.path.isdir(mdir) else []
        check("并发下载全部 3 张图", files == ["img_001.png", "img_002.png", "img_003.png"],
              f"got={files}")
        check("3 张图 src 全部替换", res3["html_content"].count("assets/多图测试/") == 3)

    # 动图按内容识别(链接不带 .gif 后缀)
    res4 = eng.fetch_and_parse(f"http://127.0.0.1:{PORT}/article_anim")
    ok4 = res4.get("status") == "success"
    check("动图文章解析", ok4, f"got={res4.get('message')}")
    if ok4:
        gif_file = os.path.join(ROOT, "outputs", "assets", "动图测试", "img_001.gif")
        check("动图按内容识别为 .gif", os.path.isfile(gif_file)
              and open(gif_file, "rb").read().startswith(b"GIF89a"))
        check("动图 src 相对路径正确", "assets/动图测试/img_001.gif" in res4["html_content"])
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
                            "tags": ["T1"], "url": "http://x",
                            "summary": "测试摘要", "category": "数学"})
check("Markdown 文件生成", os.path.exists(md_path))
if os.path.exists(md_path):
    content = open(md_path, encoding="utf-8").read()
    check("YAML Front Matter", content.startswith("---") and 'author: "作者A"' in content)
    check("YAML 含 AI 摘要与分类", 'summary: "测试摘要"' in content
          and 'category: "数学"' in content)
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

# HTML 导出 / 文件名模板 / 自动目录 TOC
h_path = conv.to_html(math_html, "测试导出HTML", {"title": "测试导出HTML"})
check("HTML 文件生成", os.path.exists(h_path)
      and "<h1>测试导出HTML</h1>" in open(h_path, encoding="utf-8").read())
t_path = conv.to_markdown(math_html, "模板测试",
                          {"title": "模板测试", "author": "作者B", "date": "2024-01-01"},
                          filename_template="{date}_{title}_{author}")
check("文件名模板生效", os.path.basename(t_path) == "2024-01-01_模板测试_作者B.md",
      f"got={os.path.basename(t_path)}")

toc_html = ("<h2>第一节</h2><p>x</p><h2>第二节</h2><p>y</p>"
            "<h2>第三节</h2><p>z</p><h3>小节</h3><p>w</p>")
toc_md_path = conv.to_markdown(toc_html, "目录测试")
check("自动目录 TOC", "## 目录" in open(toc_md_path, encoding="utf-8").read())

# 公式渲染回归: PDF 文本中不应残留原始 $ 分隔符(证明 MathJax 真正渲染完成)
print("    (验证公式渲染完成标记，约 10-20 秒，请稍候...)")
try:
    formula_pdf = conv.to_pdf(math_html, "公式渲染回归")
    import fitz
    doc = fitz.open(formula_pdf)
    text = "".join(page.get_text() for page in doc)
    doc.close()
    check("PDF 公式已渲染(无原始 $ 分隔符)", "$" not in text, f"got={text[:80]!r}")
except Exception as e:
    check("PDF 公式已渲染(无原始 $ 分隔符)", False, f"异常: {type(e).__name__}: {e}")

# HTML 公式渲染回归: 普通浏览器(无任何 file 访问参数)打开本地 HTML, 公式必须渲染成 SVG
print("    (验证 HTML 公式渲染，约 10-15 秒，请稍候...)")
try:
    html_fx = conv.to_html(math_html, "HTML公式渲染回归")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)  # 不带 file 参数
        page = browser.new_page()
        page.goto(Path(html_fx).as_uri(), wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('svg').length > 0", timeout=15000)
            svg_count = page.evaluate("() => document.querySelectorAll('svg').length")
            page.wait_for_timeout(500)
            check("HTML 公式已渲染(普通浏览器)", svg_count > 0, f"svg={svg_count}")
        except Exception:
            check("HTML 公式已渲染(普通浏览器)", False, "等待 SVG 超时")
        browser.close()
except Exception as e:
    check("HTML 公式已渲染(普通浏览器)", False, f"异常: {type(e).__name__}: {e}")

# 共享渲染器复用(批量提速的关键优化)
print("    (验证共享渲染器复用，约 10-20 秒，请稍候...)")
try:
    from core.format_converter import PDFRenderer

    rnd = PDFRenderer()
    try:
        r_html = ('<div class="RichText"><p>共享渲染器测试</p>'
                  '<img src="assets/PDF图片测试/img_001.png"></div>')
        p_a = conv.to_pdf(r_html, "共享渲染器A", renderer=rnd)
        p_b = conv.to_pdf(r_html, "共享渲染器B", renderer=rnd)
        ok_ab = os.path.exists(p_a) and os.path.exists(p_b)
        check("共享渲染器连续渲染两篇", ok_ab, f"a={p_a}, b={p_b}")
        if ok_ab:
            import fitz
            doc = fitz.open(p_a)
            embedded = any(page.get_images() for page in doc)
            doc.close()
            check("共享渲染器输出同样嵌入图片", embedded)
    finally:
        rnd.close()
except Exception as e:
    check("共享渲染器连续渲染两篇", False, f"异常: {type(e).__name__}: {e}")

# ================= 5. GUI 离屏构建 =================
print("\n== 5. main GUI 离屏构建 ==")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

app = QApplication([])
from main import MainWindow, LoginDialog, SettingsDialog

try:
    w = MainWindow()
    check("主窗口构建", bool(w.windowTitle()))
    check("输入框存在", w.url_input is not None)
    check("默认勾选 MD+PDF", w.cb_md.isChecked() and w.cb_pdf.isChecked())
    check("HTML 勾选框存在", hasattr(w, 'cb_html') and w.cb_html.isChecked())
    check("停止按钮存在(初始禁用)", hasattr(w, 'stop_btn') and not w.stop_btn.isEnabled())
    check("设置按钮存在", hasattr(w, 'settings_btn'))
    check("动态光晕背景存在", hasattr(w, 'glow_bg'))
    check("自定义标题栏存在", hasattr(w, 'title_bar'))
    check("头像与昵称控件存在", hasattr(w.title_bar, 'avatar_label')
          and hasattr(w.title_bar, 'profile_name_label'))
    w._on_profile_loaded({"name": "测试用户", "avatar_bytes": None})
    check("账号昵称更新", w.title_bar.profile_name_label.text() == "测试用户")
    check("拖拽导入已启用", w.acceptDrops())
    check("ETA 标签存在", hasattr(w, 'eta_label'))
    w.url_input.setText("")
    w.start_processing()
    check("空输入被拦截并提示", "错误" in w.log_console.toPlainText())
    w.request_stop()
    check("无任务时请求停止给出提示", "没有正在运行的任务" in w.log_console.toPlainText())
    w.close()
except Exception as e:
    check("主窗口构建", False, f"异常: {type(e).__name__}: {e}")

try:
    sd = SettingsDialog(w.settings, main_window=w)
    check("设置弹窗构建(5个标签页)", sd.tabs.count() == 5, f"got={sd.tabs.count()}")
    check("同步/AI/剪贴板控件存在", hasattr(sd, 'cb_obsidian_enabled')
          and hasattr(sd, 'cb_ai_enabled') and hasattr(sd, 'cb_clipboard_watch'))
    check("HTML/深色/模板/自启控件存在", hasattr(sd, 'cb_default_html')
          and hasattr(sd, 'cb_dark_mode') and hasattr(sd, 'le_filename_template')
          and hasattr(sd, 'cb_autostart'))
    sd.close()
except Exception as e:
    check("设置弹窗构建(5个标签页)", False, f"异常: {type(e).__name__}: {e}")

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
          os.path.join(ROOT, "outputs", "测试导出HTML.html"),
          os.path.join(ROOT, "outputs", "2024-01-01_模板测试_作者B.md"),
          os.path.join(ROOT, "outputs", "目录测试.md"),
          os.path.join(ROOT, "outputs", "公式渲染回归.pdf"),
          os.path.join(ROOT, "outputs", "HTML公式渲染回归.html"),
          os.path.join(ROOT, "outputs", "_mathjax"),
          os.path.join(ROOT, "outputs", "PDF图片嵌入测试.pdf"),
          os.path.join(ROOT, "outputs", "共享渲染器A.pdf"),
          os.path.join(ROOT, "outputs", "共享渲染器B.pdf"),
          os.path.join(ROOT, "outputs", "assets", "PDF图片测试"),
          os.path.join(ROOT, "outputs", "assets", "测试文章"),
          os.path.join(ROOT, "outputs", "assets", "测试文章 - 测试作者的回答"),
          os.path.join(ROOT, "outputs", "assets", "多图测试"),
          os.path.join(ROOT, "outputs", "assets", "动图测试"),
          os.path.join(ROOT, "outputs", "_pdftest"),
          os.path.join(ROOT, "data", "profile_name.txt"),
          os.path.join(ROOT, "data", "avatar.jpg"),
          os.path.join(ROOT, "logs")]:
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
