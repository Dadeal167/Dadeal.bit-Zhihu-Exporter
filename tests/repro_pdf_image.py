# -*- coding: utf-8 -*-
"""受控实验：验证 PDF 渲染时相对图片路径是否无法解析。

用用户真实下载的图片，渲染两个最小 PDF：
  A. 相对路径 src="assets/.../img_001.jpg"（程序现在的做法）
  B. 绝对 file:// 路径 src（对照）
对比两者是否嵌入图片对象 /Image。
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.paths import setup_console
setup_console()

from core.format_converter import FormatConverter

TITLE = "图片测试"
SRC_IMG = os.path.join(
    os.environ["LOCALAPPDATA"], "DadealZhihuExporter", "outputs",
    "assets", "两个有意思的三角函数强基计划题目", "img_001.jpg")
assert os.path.exists(SRC_IMG), f"找不到源图片: {SRC_IMG}"

tmp = os.path.join(ROOT, "outputs", "_pdftest")
shutil.rmtree(tmp, ignore_errors=True)
os.makedirs(os.path.join(tmp, "assets", TITLE), exist_ok=True)
shutil.copy(SRC_IMG, os.path.join(tmp, "assets", TITLE, "img_001.jpg"))

conv = FormatConverter(output_dir=tmp)

# A. 相对路径（现状）
html_rel = f'<div class="RichText"><p>相对路径测试</p><img src="assets/{TITLE}/img_001.jpg"></div>'
p_rel = conv.to_pdf(html_rel, "相对路径测试")
d_rel = open(p_rel, "rb").read()
print(f"A. 相对路径 PDF: {len(d_rel)} bytes, 含 /Image 对象: {b'/Image' in d_rel}")

# B. 绝对 file:// 路径（对照）
uri = Path(os.path.join(tmp, "assets", TITLE, "img_001.jpg")).as_uri()
html_abs = f'<div class="RichText"><p>绝对路径测试</p><img src="{uri}"></div>'
p_abs = conv.to_pdf(html_abs, "绝对路径测试")
d_abs = open(p_abs, "rb").read()
print(f"B. 绝对路径 PDF: {len(d_abs)} bytes, 含 /Image 对象: {b'/Image' in d_abs}")

print("\n结论:", "bug 复现：相对路径图片未嵌入 PDF" if (b'/Image' not in d_rel and b'/Image' in d_abs) else "与预期不符，需进一步分析")
