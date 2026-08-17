# -*- coding: utf-8 -*-
"""断点续传历史记录的读写。

v1.1.0 起历史记录升级为按格式记录: {url: {"md": bool, "pdf": bool}}
旧版是纯 URL 列表(视为 md/pdf 均已完成), 读取时自动兼容迁移。
"""
import json
import os


def load_history(path):
    """读取历史记录, 兼容旧版列表格式; 文件不存在/损坏时返回空字典"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}

    if isinstance(data, list):  # 旧版: URL 列表 → 视为两种格式都已完成
        return {url: {"md": True, "pdf": True} for url in data if isinstance(url, str)}

    if isinstance(data, dict):
        return data

    return {}


def save_history(path, data):
    """保存历史记录(自动创建目录)"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
