# -*- coding: utf-8 -*-
"""扩展功能: 本地 AI(摘要/分类) / Obsidian 同步 / 分类索引 / HTML→文本。

- AI 通过 Ollama HTTP API 调用本地模型, Ollama 未启动/超时时优雅降级(返回 None)
- Obsidian 同步: 复制 MD 与图片资源到库的指定子文件夹(相对路径结构保持一致)
"""
import json
import os
import shutil

import requests
from bs4 import BeautifulSoup

AI_CATEGORIES = ["数学", "物理", "计算机", "英语", "语文", "化学", "生物", "历史", "其他"]

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


def html_to_text(html_content):
    """HTML → 纯文本(供 AI 使用)"""
    try:
        return BeautifulSoup(html_content, "html.parser").get_text(" ", strip=True)
    except Exception:
        return ""


def ollama_generate(prompt, model="qwen2.5:7b", timeout=120):
    """调用 Ollama 生成文本; 失败返回 None"""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        if resp.status_code == 200:
            return resp.json().get("response", "").strip() or None
        print(f"⚠️ Ollama 返回 HTTP {resp.status_code}")
    except Exception as e:
        print(f"⚠️ Ollama 调用失败(请确认已安装并运行 Ollama): {e}")
    return None


def summarize(text, model="qwen2.5:7b", timeout=120):
    """一句话摘要; 失败返回 None"""
    if not text:
        return None
    prompt = ("请用一句话概括以下文章的核心内容，直接输出摘要，"
              "不超过60字，不要任何前缀或解释：\n\n" + text[:2500])
    result = ollama_generate(prompt, model=model, timeout=timeout)
    if result:
        return result.replace("\n", " ").strip()[:120]
    return None


def classify(text, model="qwen2.5:7b", timeout=120):
    """学科分类; 识别失败回退"其他", Ollama 不可用返回 None"""
    if not text:
        return None
    prompt = ("请判断以下文章最接近的学科分类，只输出以下词语之一，"
              f"不要任何解释：{'、'.join(AI_CATEGORIES)}\n\n" + text[:2500])
    result = ollama_generate(prompt, model=model, timeout=timeout)
    if not result:
        return None
    for category in AI_CATEGORIES:
        if category in result:
            return category
    return "其他"


def sync_to_obsidian(md_path, output_dir, vault, folder):
    """把文章 MD 及其图片资源同步到 Obsidian 库; 成功返回 True"""
    try:
        vault = os.path.abspath(vault)
        dest_dir = os.path.join(vault, folder.strip() or "知乎收藏")
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(md_path, os.path.join(dest_dir, os.path.basename(md_path)))

        safe_title = os.path.splitext(os.path.basename(md_path))[0]
        src_assets = os.path.join(output_dir, "assets", safe_title)
        if os.path.isdir(src_assets):
            dst_assets = os.path.join(dest_dir, "assets", safe_title)
            shutil.rmtree(dst_assets, ignore_errors=True)
            shutil.copytree(src_assets, dst_assets)
        return True
    except Exception as e:
        print(f"⚠️ Obsidian 同步失败: {e}")
        return False


def record_category(data_dir, output_dir, entries):
    """记录文章分类并重建 outputs/分类索引.md

    entries: [{"title": str, "category": str, "file": str}, ...]
    索引持久化在 data_dir/category_index.json, 每次按全量重建 MD 索引。
    """
    idx_path = os.path.join(data_dir, "category_index.json")
    index = {}
    if os.path.exists(idx_path):
        try:
            with open(idx_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                index = loaded
        except (OSError, ValueError):
            index = {}

    for entry in entries:
        index[entry["title"]] = {"category": entry.get("category", "其他"),
                                 "file": entry.get("file", "")}

    os.makedirs(data_dir, exist_ok=True)
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    by_category = {}
    for title, info in index.items():
        by_category.setdefault(info.get("category", "其他"), []).append(
            (title, info.get("file", "")))

    md_path = os.path.join(output_dir, "分类索引.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 文章分类索引\n\n")
        for category in sorted(by_category):
            f.write(f"## {category}\n\n")
            for title, filename in sorted(by_category[category]):
                f.write(f"- [{title}]({filename})\n")
            f.write("\n")
    return md_path


def edge_available():
    """检测系统是否安装 Microsoft Edge(扫码登录与 PDF 渲染依赖它)"""
    candidates = [
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft",
                     "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft",
                     "Edge", "Application", "msedge.exe"),
    ]
    return any(c and os.path.isfile(c) for c in candidates)


def fetch_profile(timeout=10):
    """通过知乎 API 获取当前登录账号信息 {name, avatar_url}; 失败/未登录返回 None"""
    try:
        from core.auth_manager import AuthManager
        cookies = AuthManager().get_cookies()
    except Exception:
        cookies = None
    if not cookies:
        return None
    cookie_dict = {c["name"]: c["value"] for c in cookies
                   if isinstance(c, dict) and "name" in c and "value" in c}
    if not cookie_dict.get("z_c0"):
        return None
    try:
        resp = requests.get(
            "https://www.zhihu.com/api/v4/me",
            cookies=cookie_dict,
            headers={
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"),
                "Referer": "https://www.zhihu.com/",
            },
            timeout=timeout,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {"name": data.get("name") or "知乎用户",
                    "avatar_url": data.get("avatar_url") or ""}
    except Exception as e:
        print(f"⚠️ 获取账号信息失败: {e}")
    return None


def download_avatar(url, timeout=10):
    """下载头像图片字节; 失败返回 None"""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception:
        pass
    return None
