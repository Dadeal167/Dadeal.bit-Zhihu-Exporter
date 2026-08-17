# -*- coding: utf-8 -*-
"""统一管理数据/输出目录与资源路径。

- 源码运行时：使用项目根目录下的 data/ 与 outputs/
- PyInstaller 打包运行时：使用 %LOCALAPPDATA%\\DadealZhihuExporter\\
  （安装目录通常在 Program Files，普通用户无写权限，数据不能写在安装目录里）
"""
import os
import sys

APP_DIR_NAME = "DadealZhihuExporter"


def get_project_root():
    """项目根目录（core 的上一级）"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_base_dir():
    """运行时数据根目录"""
    if getattr(sys, "frozen", False):
        base = os.path.join(
            os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
            APP_DIR_NAME,
        )
    else:
        base = get_project_root()
    os.makedirs(base, exist_ok=True)
    return base


def get_data_dir():
    path = os.path.join(get_base_dir(), "data")
    os.makedirs(path, exist_ok=True)
    return path


def get_output_dir():
    path = os.path.join(get_base_dir(), "outputs")
    os.makedirs(path, exist_ok=True)
    return path


def get_cookie_file():
    """DPAPI 加密凭证文件路径"""
    return os.path.join(get_data_dir(), "cookies.dat")


def get_legacy_cookie_file():
    """旧版明文 Cookie 路径(仅用于兼容迁移)"""
    return os.path.join(get_data_dir(), "cookies.json")


def get_history_file():
    return os.path.join(get_data_dir(), "download_history.json")


def get_logs_dir():
    path = os.path.join(get_base_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    return path


def get_log_file():
    """按天滚动的运行日志文件路径"""
    import datetime
    return os.path.join(get_logs_dir(), f"运行日志_{datetime.date.today():%Y%m%d}.log")


def get_resource_path(relative_path):
    """获取资源文件（图标等）的绝对路径，兼容源码与打包两种运行方式"""
    if getattr(sys, "_MEIPASS", None):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(get_project_root(), relative_path)


def setup_console():
    """强制 stdout/stderr 使用 UTF-8。

    中文 Windows 控制台默认 GBK 编码，print 表情符号(如 🔍)会抛
    UnicodeEncodeError 导致程序崩溃；打包版(sys.stdout 为 NullWriter)则自动跳过。
    """
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
