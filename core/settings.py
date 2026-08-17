# -*- coding: utf-8 -*-
"""应用设置: 持久化到 data/settings.json, 用户配置与缺省值自动合并。"""
import json
import os

from core.paths import get_data_dir

DEFAULTS = {
    # ---- 下载 ----
    "sleep_enabled": True,       # 反爬随机休眠开关
    "sleep_min": 2.5,            # 休眠下限(秒)
    "sleep_max": 5.5,            # 休眠上限(秒)
    "image_workers": 4,          # 图片并发下载线程数
    # ---- PDF ----
    "pdf_render_wait": 3.0,      # 页面渲染后的等待秒数(确保公式/图片加载完成)
    # ---- 通用行为 ----
    "default_md": True,          # 默认勾选 Markdown
    "default_pdf": True,         # 默认勾选高清 PDF
    "default_html": True,        # 默认勾选 HTML(网页原排版保真)
    "close_to_tray": True,       # 关闭窗口时最小化到托盘
    "auto_open_output": False,   # 任务完成后自动打开输出目录
    "dark_mode": False,          # 深色模式
    "filename_template": "",     # 文件名模板: 支持 {title} {date} {author}, 空=原标题
    "autostart": False,          # 开机自启
    # ---- AI(本地 Ollama) ----
    "ai_enabled": False,          # 启用 AI 摘要/分类
    "ai_model": "qwen2.5:7b",     # Ollama 模型名
    "ai_summary": True,           # 生成摘要写入 YAML
    "ai_classify": True,          # 学科分类写入 YAML 并生成索引
    "ai_timeout": 120,            # 单次调用超时(秒)
    # ---- Obsidian 同步 ----
    "obsidian_enabled": False,    # 启用 Obsidian 同步
    "obsidian_vault": "",         # 库根目录
    "obsidian_folder": "知乎收藏",  # 库内子文件夹
    # ---- 便捷 ----
    "clipboard_watch": True,      # 剪贴板监听知乎链接
    # ---- 数据 ----
    "output_dir": "",            # 自定义输出目录, 空 = 使用默认目录
}


class SettingsManager:
    def __init__(self, path=None):
        self.path = path or os.path.join(get_data_dir(), "settings.json")
        self._data = dict(DEFAULTS)
        self.load()
        if not os.path.exists(self.path):
            # 首次运行写出默认配置文件, 方便用户查看/手动修改
            self.save()

    def load(self):
        """读取用户设置, 仅接受 DEFAULTS 中存在的键; 文件损坏/不存在时用默认值"""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                for key, value in user.items():
                    if key in DEFAULTS:
                        self._data[key] = value
        except (OSError, ValueError):
            pass

    def get(self, key, default=None):
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key, value):
        self._data[key] = value

    def update(self, mapping):
        for key, value in mapping.items():
            if key in DEFAULTS:
                self._data[key] = value

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4, ensure_ascii=False)

    def resolve_output_dir(self):
        """返回实际使用的输出目录(自定义为空时用默认目录), 并确保存在"""
        from core.paths import get_output_dir
        custom = str(self.get("output_dir", "")).strip()
        path = custom if custom else get_output_dir()
        os.makedirs(path, exist_ok=True)
        return path
