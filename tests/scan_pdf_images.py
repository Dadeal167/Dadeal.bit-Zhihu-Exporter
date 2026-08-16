# -*- coding: utf-8 -*-
"""扫描用户已生成 PDF 中是否包含图片对象"""
import glob
import os

out = os.path.join(os.environ["LOCALAPPDATA"], "DadealZhihuExporter", "outputs")
pdfs = sorted(glob.glob(out + "/*.pdf"))
total = len(pdfs)
with_img = 0
for p in pdfs[:5]:
    data = open(p, "rb").read()
    has = b"/Image" in data
    with_img += has
    print(f"{os.path.basename(p)}: {len(data)} bytes, 含图片对象: {has}")
print("...")
print(f"共 {total} 个 PDF，含图片对象的: {sum(b'/Image' in open(p, 'rb').read() for p in pdfs)} 个")
