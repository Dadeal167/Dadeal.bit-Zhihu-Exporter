# -*- coding: utf-8 -*-
"""一次性修复脚本: 用现有登录凭证重新抓取文章并只补生成 PDF(带图片)。

背景: 旧版本渲染 PDF 时本地图片无法嵌入(about:blank 拦截), 导致已生成的
PDF 缺少文章配图。本脚本读取已保存的 Cookie 与下载历史, 重新抓取每篇文章,
只重新渲染 PDF 覆盖旧文件, 不重复生成 Markdown。

用法:
    python scripts\\repair_pdfs.py            # 修复全部
    python scripts\\repair_pdfs.py --limit 5  # 先试 5 篇
"""
import argparse
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.paths import setup_console

setup_console()

from core.auth_manager import AuthManager
from core.spider_engine import SpiderEngine
from core.format_converter import FormatConverter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 篇(用于先试跑)")
    args = parser.parse_args()

    local = os.path.join(os.environ["LOCALAPPDATA"], "DadealZhihuExporter")
    cookie_file = os.path.join(local, "data", "cookies.json")
    history_file = os.path.join(local, "data", "download_history.json")
    outputs = os.path.join(local, "outputs")

    auth = AuthManager(cookie_file=cookie_file)
    if not auth.has_valid_cookies():
        print("❌ 登录凭证缺失或已过期，请先运行程序重新扫码登录")
        return 1

    if not os.path.exists(history_file):
        print("❌ 找不到下载历史记录")
        return 1
    with open(history_file, encoding="utf-8") as f:
        urls = json.load(f)
    if args.limit:
        urls = urls[:args.limit]
    print(f"📋 待修复 PDF: {len(urls)} 篇")

    spider = SpiderEngine(cookie_file=cookie_file)
    converter = FormatConverter(output_dir=outputs)

    ok = fail = 0
    for i, url in enumerate(urls, 1):
        print(f"\n--- [{i}/{len(urls)}] {url}")
        try:
            result = spider.fetch_and_parse(url)
            if result.get("status") != "success":
                print(f"❌ 抓取失败: {result.get('message')}")
                fail += 1
                continue
            converter.to_pdf(result["html_content"], result["title"])
            ok += 1
        except Exception as e:
            print(f"❌ 异常: {e}")
            fail += 1
        if i < len(urls):
            time.sleep(random.uniform(1.5, 3.0))

    print(f"\n🎉 完成: 成功 {ok} 篇, 失败 {fail} 篇")
    print(f"输出目录: {outputs}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
