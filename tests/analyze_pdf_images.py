# -*- coding: utf-8 -*-
"""分析 PDF 中实际嵌入的图片（与源图对比），精确判断图片是否真的进入 PDF"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.paths import setup_console
setup_console()

import fitz  # PyMuPDF


def analyze(pdf_path, label):
    print(f"\n===== {label} =====")
    print(f"文件: {pdf_path} ({os.path.getsize(pdf_path)} bytes)")
    doc = fitz.open(pdf_path)
    total = 0
    for page in doc:
        for img in page.get_images(full=True):
            # img: (xref, smask, width, height, bpc, cs, altcs, filter, name, ...)
            xref, width, height, bpc, cs, filt = img[0], img[2], img[3], img[4], img[5], img[7]
            raw = doc.extract_image(xref)
            total += 1
            print(f"  图片: {width}x{height}px, {raw['ext']}, {len(raw['image'])} bytes, filter={filt}")
    print(f"共嵌入 {total} 个图片对象")
    doc.close()


if __name__ == "__main__":
    t = os.path.join(ROOT, "outputs", "_pdftest")
    analyze(os.path.join(t, "相对路径测试.pdf"), "A. 相对路径(现状做法)")
    analyze(os.path.join(t, "绝对路径测试.pdf"), "B. 绝对 file:// 路径(对照)")
    src = os.path.join(
        os.environ["LOCALAPPDATA"], "DadealZhihuExporter", "outputs",
        "assets", "两个有意思的三角函数强基计划题目", "img_001.jpg")
    d = fitz.open(src)
    print(f"\n===== 源图片 =====")
    print(f"img_001.jpg: {d[0].rect.width}x{d[0].rect.height}px, {os.path.getsize(src)} bytes")
    d.close()
