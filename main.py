import sys
import os
import glob
import time
import random
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QGridLayout, QLineEdit, QPushButton,
                               QCheckBox, QTextBrowser, QLabel, QProgressBar,
                               QFileDialog, QDialog, QSystemTrayIcon, QMenu,
                               QTabWidget, QFormLayout, QSpinBox, QDoubleSpinBox,
                               QGroupBox, QFrame, QSizeGrip, QMessageBox,
                               QColorDialog)
from PySide6.QtCore import (QThread, Signal, Qt, QEvent, QTimer,
                            QPropertyAnimation, QEasingCurve)
from PySide6.QtGui import QFont, QIcon, QAction, QColor, QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import (QGraphicsDropShadowEffect)  # noqa: F401  # 位于 QtWidgets

from core.auth_manager import AuthManager
from core.spider_engine import SpiderEngine
from core.format_converter import FormatConverter, PDFRenderer
from core.history import load_history, save_history
from core.settings import SettingsManager
from core.ui_effects import GlowBackground, apply_glow
from core.version import APP_NAME, __version__
from core.paths import (get_resource_path, get_cookie_file, get_legacy_cookie_file,
                        get_history_file, get_output_dir, get_log_file, get_data_dir,
                        setup_console)

setup_console()

# ==========================================
# 现代 Windows 风 · 低饱和浅蓝 QSS 主题
# ==========================================
STYLE_QSS = """
QMainWindow, QDialog {
    background-color: #EFF6FC;
    font-family: "Microsoft YaHei";
}
QFrame#card {
    background: #F7FBFF;
    border: 1px solid rgba(186, 218, 244, 0.9);
    border-radius: 20px;
}
QLabel { color: #4A7396; }
QLabel#appTitle {
    color: #3E6E9C;
    font-size: 15px;
    font-weight: bold;
}
QPushButton#winBtn {
    background: transparent;
    border: none;
    color: #5E86A8;
    font-size: 14px;
    border-radius: 6px;
    padding: 0;
}
QPushButton#winBtn:hover { background: rgba(150, 200, 240, 0.35); color: #2E6CA6; }
QPushButton#closeBtn { background: transparent; border: none; color: #5E86A8; font-size: 13px; border-radius: 6px; padding: 0; }
QPushButton#closeBtn:hover { background: rgba(235, 120, 120, 0.25); color: #C94F4F; }
QLineEdit {
    background: #FFFFFF;
    border: 1px solid #C9E3F5;
    border-radius: 10px;
    padding: 6px 8px;
    color: #000000;
}
QLineEdit:focus { border: 1px solid #8CC4EE; }
QComboBox {
    background: #FFFFFF;
    color: #000000;
    border: 1px solid #C9E3F5;
    border-radius: 8px;
    padding: 3px 8px;
}
QComboBox:hover { border-color: #A5D0EF; }
QComboBox QAbstractItemView {
    background: #FFFFFF;
    color: #000000;
    border: 1px solid #C9E3F5;
    selection-background-color: #D8ECFA;
    selection-color: #000000;
}
QPushButton {
    background: #FFFFFF;
    color: #3772A3;
    border: 1px solid #B9DBF2;
    border-radius: 10px;
    padding: 6px 14px;
}
QPushButton:hover { background: #F0F9FF; border-color: #A5D0EF; }
QPushButton:pressed { background: #E2F3FD; }
QPushButton:disabled { color: #A9C2D8; border-color: #DEEBF5; background: #F7FBFD; }
QPushButton#primaryButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #A5D4F3, stop:1 #7FBEEC);
    color: #FFFFFF;
    border: 1px solid #6FB2E6;
    font-weight: bold;
    padding: 8px 14px;
}
QPushButton#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #B7DEF7, stop:1 #93CAF1);
}
QPushButton#primaryButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8FC4EE, stop:1 #6FB2E6);
}
QPushButton#primaryButton:disabled { background: #D3E8F8; color: #F2F9FE; border: 1px solid #BFDDF2; }
QPushButton#dangerButton { color: #D9534F; border-color: #F0B9B7; }
QCheckBox { color: #4A7396; spacing: 6px; }
QProgressBar {
    background: #EAF5FC;
    border: 1px solid #B9DBF2;
    border-radius: 9px;
    text-align: center;
    color: #3E6E9C;
    font-weight: bold;
    min-height: 14px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #A5D4F3, stop:1 #7FBEEC);
    border-radius: 9px;
}
QTextBrowser#logConsole {
    background: #14314B;
    color: #3772A3;
    border: 1px solid #6FA9D8;
    border-radius: 12px;
    padding: 8px;
    font-family: Consolas;
}
QTabWidget::pane { border: 1px solid #C9E3F5; border-radius: 12px; background: #FFFFFF; }
QTabBar::tab { padding: 7px 18px; color: #4A7396; background: transparent; }
QTabBar::tab:selected { color: #3E6E9C; font-weight: bold; border-bottom: 2px solid #8CC4EE; }
QGroupBox {
    border: 1px solid #C9E3F5;
    border-radius: 12px;
    margin-top: 10px;
    background: #FBFDFF;
    color: #3E6E9C;
    font-weight: bold;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QSpinBox, QDoubleSpinBox {
    background: #FFFFFF;
    color: #000000;
    border: 1px solid #C9E3F5;
    border-radius: 8px;
    padding: 3px 6px;
}
"""

# 深色模式主题
STYLE_QSS_DARK = """
QMainWindow, QDialog {
    background-color: #17222E;
    font-family: "Microsoft YaHei";
}
QFrame#card {
    background: #1E2C3C;
    border: 1px solid #33506B;
    border-radius: 20px;
}
QLabel { color: #A9C4DC; }
QLabel#appTitle { color: #C5DDF2; font-size: 15px; font-weight: bold; }
QPushButton#winBtn { background: transparent; border: none; color: #8FA9C0; font-size: 14px; border-radius: 6px; padding: 0; }
QPushButton#winBtn:hover { background: rgba(90, 140, 190, 0.3); color: #C5DDF2; }
QPushButton#closeBtn { background: transparent; border: none; color: #8FA9C0; font-size: 13px; border-radius: 6px; padding: 0; }
QPushButton#closeBtn:hover { background: rgba(200, 90, 90, 0.3); color: #E8A0A0; }
QLineEdit {
    background: #243648;
    border: 1px solid #3A5878;
    border-radius: 10px;
    padding: 6px 8px;
    color: #E8F2FA;
}
QLineEdit:focus { border: 1px solid #5FA8E0; }
QComboBox {
    background: #243648;
    color: #E8F2FA;
    border: 1px solid #3A5878;
    border-radius: 8px;
    padding: 3px 8px;
}
QComboBox:hover { border-color: #5FA8E0; }
QComboBox QAbstractItemView {
    background: #243648;
    color: #E8F2FA;
    border: 1px solid #3A5878;
    selection-background-color: #33506B;
    selection-color: #FFFFFF;
}
QPushButton {
    background: #243648;
    color: #BFD9EE;
    border: 1px solid #3A5878;
    border-radius: 10px;
    padding: 6px 14px;
}
QPushButton:hover { background: #2C4258; border-color: #5FA8E0; }
QPushButton:pressed { background: #1F3042; }
QPushButton:disabled { color: #5F7A92; border-color: #2C4258; background: #1E2C3C; }
QPushButton#primaryButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3D7FB8, stop:1 #2E6392);
    color: #FFFFFF;
    border: 1px solid #4E90C8;
    font-weight: bold;
    padding: 8px 14px;
}
QPushButton#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4A8FC6, stop:1 #3772A3);
}
QPushButton#primaryButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2E6392, stop:1 #244E73);
}
QPushButton#primaryButton:disabled { background: #2C4258; color: #7A93A8; border: 1px solid #3A5878; }
QPushButton#dangerButton { color: #E08585; border-color: #7A4A4A; }
QCheckBox { color: #A9C4DC; spacing: 6px; }
QProgressBar {
    background: #243648;
    border: 1px solid #3A5878;
    border-radius: 9px;
    text-align: center;
    color: #C5DDF2;
    font-weight: bold;
    min-height: 14px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3D7FB8, stop:1 #2E6392);
    border-radius: 9px;
}
QTextBrowser#logConsole {
    background: #101B26;
    color: #8FB8D8;
    border: 1px solid #3A5878;
    border-radius: 12px;
    padding: 8px;
    font-family: Consolas;
}
QTabWidget::pane { border: 1px solid #3A5878; border-radius: 12px; background: #1E2C3C; }
QTabBar::tab { padding: 7px 18px; color: #8FA9C0; background: transparent; }
QTabBar::tab:selected { color: #C5DDF2; font-weight: bold; border-bottom: 2px solid #5FA8E0; }
QGroupBox {
    border: 1px solid #3A5878;
    border-radius: 12px;
    margin-top: 10px;
    background: #223144;
    color: #C5DDF2;
    font-weight: bold;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QSpinBox, QDoubleSpinBox {
    background: #243648;
    color: #E8F2FA;
    border: 1px solid #3A5878;
    border-radius: 8px;
    padding: 3px 6px;
}
"""


def build_theme_qss(bg_hex):
    """从根上派生整套配色: 由单一背景色生成协调的完整 QSS。

    背景色的色相与亮度决定文字/边框/按钮/输入框/进度条/日志面板等所有颜色:
    浅色背景自动配深色文字, 深色背景自动配浅色文字, 主按钮/进度条跟随背景色相,
    不再残留原蓝色主题的任何颜色。
    """
    bg = QColor(bg_hex)
    if not bg.isValid():
        return None
    h, s, l, _ = bg.getHslF()
    dark = l < 0.5

    def c(light, sat=None):
        sat = s if sat is None else sat
        sat = max(0.0, min(1.0, sat))
        light = max(0.0, min(1.0, light))
        col = QColor()
        col.setHslF(h, sat, light)
        return col.name()

    if dark:
        text = c(0.88, s * 0.30)
        text_dim = c(0.70, s * 0.22)
        title = c(0.93, s * 0.32)
        border = c(min(l + 0.14, 0.96), s * 0.42)
        border_soft = c(min(l + 0.08, 0.90), s * 0.35)
        input_bg = c(min(l + 0.08, 0.93), s * 0.45)
        input_text = c(0.90, s * 0.25)
        btn_bg = c(min(l + 0.07, 0.92), s * 0.40)
        btn_text = c(0.85, s * 0.42)
        btn_border = c(min(l + 0.12, 0.94), s * 0.38)
        btn_hover = c(min(l + 0.13, 0.96), s * 0.42)
        btn_pressed = c(max(l - 0.04, 0.02), s * 0.38)
        disabled_text = c(0.50, s * 0.12)
        disabled_border = c(min(l + 0.07, 0.85), s * 0.20)
        disabled_bg = c(max(l - 0.02, 0.03), s * 0.18)
        primary_from = c(0.58, max(s, 0.50))
        primary_to = c(0.40, max(s, 0.50))
        primary_hfrom = c(0.66, max(s, 0.50))
        primary_hto = c(0.48, max(s, 0.50))
        primary_pfrom = c(0.36, max(s, 0.50))
        primary_pto = c(0.24, max(s, 0.50))
        primary_disabled = c(min(l + 0.08, 0.80), s * 0.22)
        progress_bg = c(min(l + 0.05, 0.88), s * 0.30)
        log_bg = c(max(l - 0.12, 0.02), s * 0.42)
        log_text = c(0.80, s * 0.35)
        danger = "#E08585"
        danger_border = "#7A4A4A"
    else:
        text = c(0.26, s * 0.50)
        text_dim = c(0.45, s * 0.35)
        title = c(0.22, s * 0.55)
        border = c(max(l - 0.14, 0.04), s * 0.55)
        border_soft = c(max(l - 0.08, 0.05), s * 0.45)
        input_bg = c(min(l + 0.04, 0.99), s * 0.30)
        input_text = c(0.15, s * 0.40)
        btn_bg = c(min(l + 0.03, 0.99), s * 0.25)
        btn_text = c(0.32, s * 0.60)
        btn_border = c(max(l - 0.12, 0.05), s * 0.50)
        btn_hover = c(min(l + 0.06, 0.99), s * 0.30)
        btn_pressed = c(max(l - 0.05, 0.05), s * 0.30)
        disabled_text = c(0.60, s * 0.15)
        disabled_border = c(min(l + 0.02, 0.95), s * 0.20)
        disabled_bg = c(min(l + 0.04, 0.98), s * 0.12)
        primary_from = c(0.72, max(s, 0.45))
        primary_to = c(0.58, max(s, 0.45))
        primary_hfrom = c(0.78, max(s, 0.45))
        primary_hto = c(0.64, max(s, 0.45))
        primary_pfrom = c(0.55, max(s, 0.45))
        primary_pto = c(0.44, max(s, 0.45))
        primary_disabled = c(min(l + 0.05, 0.95), s * 0.18)
        progress_bg = c(max(l - 0.06, 0.05), s * 0.35)
        log_bg = c(0.15, s * 0.30)
        log_text = c(0.72, s * 0.30)
        danger = "#D9534F"
        danger_border = "#F0B9B7"

    return f"""
QMainWindow, QDialog {{
    background-color: {bg.name()};
    font-family: "Microsoft YaHei";
}}
QFrame#card {{
    background: {bg.name()};
    border: 1px solid {border};
    border-radius: 20px;
}}
QLabel {{ color: {text}; }}
QLabel#appTitle {{ color: {title}; font-size: 15px; font-weight: bold; }}
QPushButton#winBtn {{
    background: transparent;
    border: none;
    color: {text_dim};
    font-size: 14px;
    border-radius: 6px;
    padding: 0;
}}
QPushButton#winBtn:hover {{ background: {btn_hover}; color: {title}; }}
QPushButton#closeBtn {{ background: transparent; border: none; color: {text_dim}; font-size: 13px; border-radius: 6px; padding: 0; }}
QPushButton#closeBtn:hover {{ background: rgba(235, 120, 120, 0.25); color: {danger}; }}
QLineEdit {{
    background: {input_bg};
    border: 1px solid {border_soft};
    border-radius: 10px;
    padding: 6px 8px;
    color: {input_text};
}}
QLineEdit:focus {{ border: 1px solid {border}; }}
QComboBox {{
    background: {input_bg};
    color: {input_text};
    border: 1px solid {border_soft};
    border-radius: 8px;
    padding: 3px 8px;
}}
QComboBox:hover {{ border-color: {border}; }}
QComboBox QAbstractItemView {{
    background: {input_bg};
    color: {input_text};
    border: 1px solid {border_soft};
    selection-background-color: {btn_hover};
    selection-color: {input_text};
}}
QPushButton {{
    background: {btn_bg};
    color: {btn_text};
    border: 1px solid {btn_border};
    border-radius: 10px;
    padding: 6px 14px;
}}
QPushButton:hover {{ background: {btn_hover}; border-color: {border}; }}
QPushButton:pressed {{ background: {btn_pressed}; }}
QPushButton:disabled {{ color: {disabled_text}; border-color: {disabled_border}; background: {disabled_bg}; }}
QPushButton#primaryButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary_from}, stop:1 {primary_to});
    color: #FFFFFF;
    border: 1px solid {primary_to};
    font-weight: bold;
    padding: 8px 14px;
}}
QPushButton#primaryButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary_hfrom}, stop:1 {primary_hto});
}}
QPushButton#primaryButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary_pfrom}, stop:1 {primary_pto});
}}
QPushButton#primaryButton:disabled {{ background: {primary_disabled}; color: {disabled_text}; border: 1px solid {disabled_border}; }}
QPushButton#dangerButton {{ color: {danger}; border-color: {danger_border}; }}
QCheckBox {{ color: {text}; spacing: 6px; }}
QProgressBar {{
    background: {progress_bg};
    border: 1px solid {border_soft};
    border-radius: 9px;
    text-align: center;
    color: {text};
    font-weight: bold;
    min-height: 14px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {primary_from}, stop:1 {primary_to});
    border-radius: 9px;
}}
QTextBrowser#logConsole {{
    background: {log_bg};
    color: {log_text};
    border: 1px solid {border};
    border-radius: 12px;
    padding: 8px;
    font-family: Consolas;
}}
QTabWidget::pane {{ border: 1px solid {border_soft}; border-radius: 12px; background: {input_bg}; }}
QTabBar::tab {{ padding: 7px 18px; color: {text_dim}; background: transparent; }}
QTabBar::tab:selected {{ color: {title}; font-weight: bold; border-bottom: 2px solid {border}; }}
QGroupBox {{
    border: 1px solid {border_soft};
    border-radius: 12px;
    margin-top: 10px;
    background: {btn_bg};
    color: {title};
    font-weight: bold;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
QSpinBox, QDoubleSpinBox {{
    background: {input_bg};
    color: {input_text};
    border: 1px solid {border_soft};
    border-radius: 8px;
    padding: 3px 6px;
}}
"""


class LoginThread(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(bool)

    def run(self):
        try:
            self.log_signal.emit("🚀 正在唤起浏览器，请准备扫描知乎登录二维码...")
            auth = AuthManager()
            auth.login_and_save_cookies() 
            
            if auth.has_valid_cookies():
                self.log_signal.emit("✅ 登录成功！凭证已安全保存在本地。现在可以开始提取文章了。")
                self.finished_signal.emit(True)
            else:
                self.log_signal.emit("❌ 登录失败或被手动取消。")
                self.finished_signal.emit(False)
        except Exception as e:
            self.log_signal.emit(f"❌ 登录时发生异常: {str(e)}")
            self.finished_signal.emit(False)


class ProfileThread(QThread):
    """后台获取知乎账号头像与昵称, 避免阻塞界面启动"""
    result_signal = Signal(dict)

    def run(self):
        from core.extras import fetch_profile, download_avatar
        result = {"name": None, "avatar_bytes": None}
        try:
            profile = fetch_profile()
            if profile:
                result["name"] = profile.get("name")
                result["avatar_bytes"] = download_avatar(profile.get("avatar_url"))
        except Exception as e:
            print(f"⚠️ 账号信息加载异常: {e}")
        self.result_signal.emit(result)


class WorkerThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal(bool)
    eta_signal = Signal(str)

    def __init__(self, input_text, export_md, export_pdf, export_html, settings):
        super().__init__()
        self.input_text = input_text 
        self.export_md = export_md
        self.export_pdf = export_pdf
        self.export_html = export_html
        self.settings = settings
        self._stop_requested = False

    def request_stop(self):
        """请求优雅停止：完成当前篇后中止，断点续传保证不丢进度"""
        self._stop_requested = True

    def _interruptible_sleep(self, seconds):
        """可被停止请求打断的休眠；返回 True 表示完整睡完"""
        end = time.time() + seconds
        while time.time() < end:
            if self._stop_requested:
                return False
            time.sleep(0.2)
        return True

    @staticmethod
    def _fmt_duration(seconds):
        seconds = max(0, int(seconds))
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours}小时{minutes}分"
        if minutes:
            return f"{minutes}分{secs}秒"
        return f"{secs}秒"

    def run(self):
        spider = None
        try:
            self.log_signal.emit("🚀 初始化核心引擎...")
            
            auth = AuthManager()
            if not auth.has_valid_cookies():
                self.log_signal.emit("❌ 致命错误：登录凭证缺失或已过期，请重新扫码登录！")
                self.finished_signal.emit(False)
                return

            # 读取设置
            output_dir = self.settings.resolve_output_dir()
            image_workers = int(self.settings.get("image_workers", 4))
            render_wait_ms = int(float(self.settings.get("pdf_render_wait", 3.0)) * 1000)
            fname_tpl = str(self.settings.get("filename_template", "")).strip() or None

            spider = SpiderEngine(
                output_dir=output_dir,
                image_workers=image_workers,
                status_callback=self.log_signal.emit)
            converter = FormatConverter(output_dir=output_dir)
            
            # 读取断点续传历史记录(按格式分别记录 md/pdf, 兼容旧版列表)
            history_file = get_history_file()
            downloaded = load_history(history_file)
            if downloaded:
                self.log_signal.emit(f"📖 已加载断点续传记录: {len(downloaded)} 篇文章。")
            
            urls_to_process = []
            if self.input_text.endswith('.txt') and os.path.exists(self.input_text):
                self.log_signal.emit("📂 正在读取本地 TXT 文件中的链接...")
                with open(self.input_text, 'r', encoding='utf-8') as f:
                    urls_to_process = [line.strip() for line in f if line.strip()]
            elif 'collection' in self.input_text:
                self.log_signal.emit("🕵️ 检测到收藏夹链接！正在获取收藏内容...")
                result = spider.get_collection_article_urls(self.input_text)
                if result["status"] == "success":
                    urls_to_process = result["urls"]
                    self.log_signal.emit(f"✅ 收藏夹解析完毕，共挖掘出 {len(urls_to_process)} 条内容！")
                else:
                    self.log_signal.emit(f"❌ 收藏夹解析失败: {result['message']}")
                    self.finished_signal.emit(False)
                    return
            elif 'column' in self.input_text or ('zhuanlan.zhihu.com' in self.input_text and '/p/' not in self.input_text):
                self.log_signal.emit("🕵️ 检测到专栏主页链接！正在获取文章目录...")
                result = spider.get_column_article_urls(self.input_text)
                if result["status"] == "success":
                    urls_to_process = result["urls"]
                    self.log_signal.emit(f"✅ 专栏解析完毕，共挖掘出 {len(urls_to_process)} 篇文章！")
                else:
                    self.log_signal.emit(f"❌ 专栏解析失败: {result['message']}")
                    self.finished_signal.emit(False)
                    return
            elif self.input_text.startswith('http') and ('/p/' in self.input_text or '/answer/' in self.input_text):
                urls_to_process = [self.input_text]
            else:
                self.log_signal.emit("⚠️ 错误：无法识别的输入内容。")
                self.finished_signal.emit(False)
                return

            total_tasks = len(urls_to_process)
            if total_tasks == 0:
                self.log_signal.emit("⚠️ 没有找到任何需要处理的链接。")
                self.finished_signal.emit(False)
                return
                
            self.log_signal.emit(f"\n📦 构建任务队列成功，即将开始处理 {total_tasks} 篇文章。")

            stats = {"success": 0, "skipped": 0, "failed": 0, "remaining": 0}
            failed_urls = []
            category_entries = []
            renderer = None
            task_start = time.time()

            try:
                for index, url in enumerate(urls_to_process):
                    if self._stop_requested:
                        self.log_signal.emit("🛑 检测到停止请求，正在收尾...")
                        stats["remaining"] = total_tasks - index
                        break

                    current_task_num = index + 1
                    base_progress = int((index / total_tasks) * 100)

                    # 按格式判断是否需要处理(md/pdf 分别记录, 只补缺失的格式)
                    record = downloaded.get(url)
                    record = record if isinstance(record, dict) else {}
                    need_md = self.export_md and not record.get("md")
                    need_pdf = self.export_pdf and not record.get("pdf")
                    need_html = self.export_html and not record.get("html")

                    if not need_md and not need_pdf and not need_html:
                        self.log_signal.emit(f"\n--- 第 {current_task_num}/{total_tasks} 篇 ---")
                        self.log_signal.emit(f"⏭️ 所需格式均已完成，秒级跳过: {url}")
                        stats["skipped"] += 1
                        self.progress_signal.emit(int((current_task_num / total_tasks) * 100))
                        continue

                    self.log_signal.emit(f"\n--- 正在处理第 {current_task_num}/{total_tasks} 篇 ---")
                    self.log_signal.emit(f"🌐 目标链接: {url}")
                    
                    self.progress_signal.emit(base_progress + 5)

                    # 风控号首次提取常不完整(缺 PDF / 动图异常), 会话预热后第二次才完整。
                    # 因此对每篇最多尝试两次, 首次不完整则从抓取开始整篇重试一次。
                    new_record = dict(record)
                    still_md, still_pdf, still_html = need_md, need_pdf, need_html
                    last_metadata = {}
                    last_title = ""

                    for attempt in (1, 2):
                        if attempt > 1:
                            self.log_signal.emit("🔁 首次提取不完整，自动重新提取一次...")

                        try:
                            result = spider.fetch_and_parse(url)
                        except Exception as e:
                            result = {"status": "error", "message": str(e)}

                        if result.get("status") != "success":
                            self.log_signal.emit(f"❌ 抓取失败: {result.get('message')}")
                            if attempt == 1:
                                continue  # 会话可能尚未建立, 再试一次
                            break  # 两次都失败

                        html_content = result["html_content"]
                        last_title = result["title"]
                        last_metadata = result.get("metadata") or {}
                        self.log_signal.emit(f"✅ 成功获取: 《{last_title}》")
                        self.progress_signal.emit(base_progress + max(1, int(40 / total_tasks)))

                        # 本地 AI 只在第一次执行(避免重复调用)
                        if attempt == 1 and self.settings.get("ai_enabled", False):
                            from core.extras import summarize, classify, html_to_text
                            plain_text = html_to_text(html_content)
                            ai_model = str(self.settings.get("ai_model", "qwen2.5:7b"))
                            ai_timeout = int(self.settings.get("ai_timeout", 120))
                            if self.settings.get("ai_summary", True):
                                self.log_signal.emit("🤖 AI 生成摘要中...")
                                summary = summarize(plain_text, model=ai_model, timeout=ai_timeout)
                                if summary:
                                    last_metadata["summary"] = summary
                                else:
                                    self.log_signal.emit("⚠️ AI 摘要失败(请确认 Ollama 已启动)...")
                            if self.settings.get("ai_classify", True):
                                self.log_signal.emit("🤖 AI 分类中...")
                                category = classify(plain_text, model=ai_model, timeout=ai_timeout)
                                if category:
                                    last_metadata["category"] = category

                        if still_md:
                            self.log_signal.emit("📝 生成 Markdown 中...")
                            try:
                                md_path = converter.to_markdown(html_content, last_title,
                                                                last_metadata,
                                                                filename_template=fname_tpl)
                                new_record["md"] = True
                                self.log_signal.emit("✅ Markdown 已保存。")
                                # Obsidian 同步
                                if self.settings.get("obsidian_enabled", False):
                                    vault = str(self.settings.get("obsidian_vault", "")).strip()
                                    if vault and os.path.isdir(vault):
                                        from core.extras import sync_to_obsidian
                                        folder = str(self.settings.get("obsidian_folder", "知乎收藏"))
                                        if sync_to_obsidian(md_path, output_dir, vault, folder):
                                            self.log_signal.emit("📚 已同步到 Obsidian。")
                                        else:
                                            self.log_signal.emit("⚠️ Obsidian 同步失败。")
                                    else:
                                        self.log_signal.emit("⚠️ Obsidian 库路径无效，已跳过同步。")
                            except Exception as e:
                                self.log_signal.emit(f"⚠️ Markdown 生成失败: {e}")

                        if still_html:
                            self.log_signal.emit("🌐 生成 HTML 中...")
                            try:
                                converter.to_html(html_content, last_title, last_metadata,
                                                  filename_template=fname_tpl)
                                new_record["html"] = True
                                self.log_signal.emit("✅ HTML 已保存。")
                            except Exception as e:
                                self.log_signal.emit(f"⚠️ HTML 生成失败: {e}")

                        if still_pdf:
                            self.log_signal.emit("🖨️ 渲染 PDF 中...")
                            try:
                                # 关键: PDF 渲染必须与蜘蛛引擎共用同一个 Playwright 实例,
                                # 否则同一线程里再启动第二个 Playwright 会触发
                                # "Sync API inside the asyncio loop" 异常导致 PDF 崩溃/程序卡死。
                                pw, browser, context = spider.get_pdf_bundle()
                                if renderer is None:
                                    self.log_signal.emit("🖥️ 启动共享渲染引擎(复用浏览器，大幅提速)...")
                                    renderer = PDFRenderer(render_wait_ms=render_wait_ms,
                                                           playwright=pw, browser=browser, context=context)
                                converter.to_pdf(html_content, last_title, renderer=renderer,
                                                 filename_template=fname_tpl)
                                new_record["pdf"] = True
                                self.log_signal.emit("✅ PDF 已保存。")
                            except Exception as e:
                                self.log_signal.emit(f"⚠️ PDF 渲染失败(将自动重试): {e}")

                        # 重新计算仍缺失的格式
                        still_md = self.export_md and not new_record.get("md")
                        still_pdf = self.export_pdf and not new_record.get("pdf")
                        still_html = self.export_html and not new_record.get("html")
                        if not (still_md or still_pdf or still_html):
                            break  # 全部完成

                    # ---- 收尾: 记录结果 ----
                    any_ok = new_record.get("md") or new_record.get("pdf") or new_record.get("html")
                    if any_ok:
                        # 记录分类(任务结束时统一重建分类索引)
                        if last_metadata.get("category"):
                            safe_name = converter._sanitize_filename(last_title)
                            if new_record.get("md"):
                                index_file = f"{safe_name}.md"
                            elif new_record.get("pdf"):
                                index_file = f"{safe_name}.pdf"
                            else:
                                index_file = f"{safe_name}.html"
                            category_entries.append({
                                "title": last_title,
                                "category": last_metadata["category"],
                                "file": index_file,
                            })
                        downloaded[url] = new_record
                        save_history(history_file, downloaded)
                        stats["success"] += 1
                        if still_md or still_pdf or still_html:
                            self.log_signal.emit(
                                "💡 提示：部分格式未能生成。若该链接本可正常打开，"
                                "可能是账号被知乎风控（如未绑定手机号）。建议绑定手机号、"
                                "通过手机知乎 App 摇一摇反馈，或更换正常账号后再试。")
                    else:
                        stats["failed"] += 1
                        failed_urls.append(url)
                        self.log_signal.emit(
                            "💡 提示：本篇未能生成任何文件。若该链接本可正常打开，"
                            "可能是账号被知乎风控（如未绑定手机号）。建议绑定手机号、"
                            "通过手机知乎 App 摇一摇反馈，或更换正常账号后再试。")

                    self.progress_signal.emit(int((current_task_num / total_tasks) * 100))

                    # 进度 ETA 估算
                    if current_task_num < total_tasks:
                        elapsed = time.time() - task_start
                        avg = elapsed / current_task_num
                        remaining = total_tasks - current_task_num
                        self.eta_signal.emit(
                            f"⏱️ 已用 {self._fmt_duration(elapsed)} | 剩余 {remaining} 篇 | "
                            f"预计还需 ~{self._fmt_duration(avg * remaining)}")

                    if current_task_num < total_tasks and not self._stop_requested:
                        if self.settings.get("sleep_enabled", True):
                            sleep_min = float(self.settings.get("sleep_min", 2.5))
                            sleep_max = float(self.settings.get("sleep_max", 5.5))
                            if sleep_max < sleep_min:
                                sleep_max = sleep_min
                            sleep_time = random.uniform(sleep_min, sleep_max)
                            self.log_signal.emit(f"🛡️ 防火墙规避：随机休眠 {sleep_time:.2f} 秒...")
                            if not self._interruptible_sleep(sleep_time):
                                stats["remaining"] = total_tasks - current_task_num
                                break
                        else:
                            self.log_signal.emit("⚡ 反爬休眠已禁用(可在设置中重新开启)...")
                            if not self._interruptible_sleep(0.3):
                                stats["remaining"] = total_tasks - current_task_num
                                break
            finally:
                if renderer is not None:
                    self.log_signal.emit("🧹 关闭共享渲染引擎...")
                    renderer.close()

            # 任务汇总报告
            summary = (f"\n🎉 任务结束！成功 {stats['success']} 篇 / 跳过 {stats['skipped']} 篇 / "
                       f"失败 {stats['failed']} 篇")
            if stats["remaining"]:
                summary += f" / 停止后剩余 {stats['remaining']} 篇"
            self.log_signal.emit(summary)
            self.eta_signal.emit(f"✅ 任务完成，总耗时 {self._fmt_duration(time.time() - task_start)}")

            if failed_urls:
                fail_file = os.path.join(output_dir, "失败清单.txt")
                try:
                    with open(fail_file, "w", encoding="utf-8") as f:
                        f.write("\n".join(failed_urls))
                    self.log_signal.emit(f"📄 失败链接清单已保存: {fail_file}")
                except OSError as e:
                    self.log_signal.emit(f"⚠️ 写入失败清单出错: {e}")

            if category_entries:
                try:
                    from core.extras import record_category
                    from core.paths import get_data_dir
                    idx_path = record_category(get_data_dir(), output_dir, category_entries)
                    self.log_signal.emit(f"🗂️ 分类索引已更新: {idx_path}")
                except Exception as e:
                    self.log_signal.emit(f"⚠️ 分类索引更新失败: {e}")

            if self._stop_requested:
                self.log_signal.emit("🛑 任务已手动停止。已完成的进度已保存，可随时继续。")
            self.finished_signal.emit(True)

        except Exception as e:
            self.log_signal.emit(f"❌ 发生系统异常: {str(e)}")
            self.finished_signal.emit(False)
        finally:
            if spider is not None:
                spider.close()


# ==========================================
# 身份认证拦截弹窗
# ==========================================
class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - 身份认证")
        self.resize(360, 200)
        # 显式声明原生标题栏(带可点击的关闭按钮)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint |
                            Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)

        self.info_label = QLabel("欢迎使用！\n\n初次运行，请先唤起浏览器绑定知乎账号。")
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)

        self.login_btn = QPushButton("📱 点击唤起浏览器扫码登录")
        self.login_btn.setMinimumHeight(45)
        self.login_btn.setObjectName("primaryButton")
        self.login_btn.clicked.connect(self.start_login)
        apply_glow(self.login_btn, QColor(120, 195, 245, 120), 18, 4)
        layout.addWidget(self.login_btn)
        
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)

    def start_login(self):
        self.login_btn.setEnabled(False)
        self.login_btn.setText("⏳ 正在唤起系统自带浏览器...")
        self.status_label.setText("请在弹出的窗口中扫码 (有效期2分钟)")
        
        self.login_thread = LoginThread()
        self.login_thread.finished_signal.connect(self.on_login_finished)
        self.login_thread.start()

    def on_login_finished(self, success):
        if success:
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.status_label.setText("✅ 认证成功！即将进入系统...")
            QTimer.singleShot(1000, self.accept)
        else:
            self.login_btn.setEnabled(True)
            self.login_btn.setText("📱 重新唤起浏览器登录")
            self.status_label.setStyleSheet("color: red;")
            self.status_label.setText("❌ 登录失败或超时，请重试")


# ==========================================
# 设置面板
# ==========================================
class SettingsDialog(QDialog):
    def __init__(self, settings, main_window=None):
        super().__init__()
        self.settings = settings
        self.main_window = main_window
        self.setWindowTitle("⚙️ 设置")
        self.resize(500, 460)
        # 显式声明原生标题栏(带可点击的关闭按钮)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint |
                            Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # ---------- 通用 ----------
        tab_general = QWidget()
        gv = QVBoxLayout(tab_general)

        g1 = QGroupBox("默认导出格式")
        g1f = QFormLayout(g1)
        self.cb_default_md = QCheckBox("默认勾选")
        self.cb_default_pdf = QCheckBox("默认勾选")
        self.cb_default_html = QCheckBox("默认勾选")
        g1f.addRow("Markdown:", self.cb_default_md)
        g1f.addRow("高清 PDF:", self.cb_default_pdf)
        g1f.addRow("HTML:", self.cb_default_html)
        gv.addWidget(g1)

        g2 = QGroupBox("窗口行为")
        g2f = QFormLayout(g2)
        self.cb_close_tray = QCheckBox("关闭窗口时最小化到托盘(任务运行中始终强制生效)")
        self.cb_auto_open = QCheckBox("任务完成后自动打开输出目录")
        self.cb_clipboard_watch = QCheckBox("监听剪贴板中的知乎链接(自动填入输入框)")
        self.cb_autostart = QCheckBox("开机自动启动(后台托盘运行)")
        g2f.addRow("", self.cb_close_tray)
        g2f.addRow("", self.cb_auto_open)
        g2f.addRow("", self.cb_clipboard_watch)
        g2f.addRow("", self.cb_autostart)
        gv.addWidget(g2)

        g3 = QGroupBox("外观与文件")
        g3f = QFormLayout(g3)
        self.cb_dark_mode = QCheckBox("深色模式")
        self.bg_color = ""  # 当前选择的背景色(十六进制), 空=使用主题默认
        self.bg_preview = QLabel("默认")
        self.bg_preview.setFixedSize(64, 22)
        self.bg_preview.setAlignment(Qt.AlignCenter)
        self.bg_preview.setStyleSheet(
            "background: transparent; border: 1px solid #C9E3F5; "
            "border-radius: 4px; color: #4A7396;")
        self.btn_bg_color = QPushButton("选择颜色...")
        self.btn_bg_color.clicked.connect(self._pick_bg_color)
        self.btn_bg_reset = QPushButton("恢复默认")
        self.btn_bg_reset.clicked.connect(self._reset_bg_color)
        bg_row = QHBoxLayout()
        bg_row.addWidget(self.bg_preview)
        bg_row.addWidget(self.btn_bg_color)
        bg_row.addWidget(self.btn_bg_reset)
        bg_row.addStretch()
        self.le_filename_template = QLineEdit()
        self.le_filename_template.setPlaceholderText("空 = 用原标题; 支持 {title} {date} {author}")
        hint0 = QLabel("示例模板: {date}_{title}  或  {title}_{author}")
        hint0.setWordWrap(True)
        hint0.setStyleSheet("color: gray;")
        g3f.addRow("", self.cb_dark_mode)
        g3f.addRow("背景颜色:", bg_row)
        g3f.addRow("文件名模板:", self.le_filename_template)
        g3f.addRow("", hint0)
        gv.addWidget(g3)
        gv.addStretch()
        self.tabs.addTab(tab_general, "通用")

        # ---------- 下载 ----------
        tab_dl = QWidget()
        dv2 = QVBoxLayout(tab_dl)

        d1 = QGroupBox("反爬休眠")
        d1f = QFormLayout(d1)
        self.cb_sleep = QCheckBox("启用反爬随机休眠")
        self.sp_sleep_min = QDoubleSpinBox()
        self.sp_sleep_min.setRange(0, 60)
        self.sp_sleep_min.setDecimals(1)
        self.sp_sleep_min.setSingleStep(0.5)
        self.sp_sleep_min.setSuffix(" 秒")
        self.sp_sleep_max = QDoubleSpinBox()
        self.sp_sleep_max.setRange(0, 60)
        self.sp_sleep_max.setDecimals(1)
        self.sp_sleep_max.setSingleStep(0.5)
        self.sp_sleep_max.setSuffix(" 秒")
        d1f.addRow("", self.cb_sleep)
        d1f.addRow("休眠下限:", self.sp_sleep_min)
        d1f.addRow("休眠上限:", self.sp_sleep_max)
        dv2.addWidget(d1)

        d2 = QGroupBox("图片下载")
        d2f = QFormLayout(d2)
        self.sp_workers = QSpinBox()
        self.sp_workers.setRange(1, 8)
        d2f.addRow("并发线程:", self.sp_workers)
        hint1 = QLabel("提示: 休眠是降低账号风控概率的关键，仅在你确认安全时才建议关闭。")
        hint1.setWordWrap(True)
        hint1.setStyleSheet("color: gray;")
        d2f.addRow("", hint1)
        dv2.addWidget(d2)
        dv2.addStretch()
        self.tabs.addTab(tab_dl, "下载")

        # ---------- PDF ----------
        tab_pdf = QWidget()
        pv = QVBoxLayout(tab_pdf)
        p1 = QGroupBox("渲染设置")
        p1f = QFormLayout(p1)
        self.sp_render_wait = QDoubleSpinBox()
        self.sp_render_wait.setRange(0.5, 15)
        self.sp_render_wait.setDecimals(1)
        self.sp_render_wait.setSingleStep(0.5)
        self.sp_render_wait.setSuffix(" 秒")
        p1f.addRow("渲染后等待:", self.sp_render_wait)
        hint2 = QLabel("数值越大公式/图片渲染越充分，批量任务越慢；一般 2~4 秒比较均衡。")
        hint2.setWordWrap(True)
        hint2.setStyleSheet("color: gray;")
        p1f.addRow("", hint2)
        pv.addWidget(p1)
        pv.addStretch()
        self.tabs.addTab(tab_pdf, "PDF")

        # ---------- 同步 ----------
        tab_sync = QWidget()
        sv = QVBoxLayout(tab_sync)

        ob = QGroupBox("Obsidian 直通")
        obf = QFormLayout(ob)
        self.cb_obsidian_enabled = QCheckBox("导出 Markdown 时同步到 Obsidian 库")
        self.le_obsidian_vault = QLineEdit()
        self.le_obsidian_vault.setPlaceholderText("库根目录路径(如 D:\\Notes)")
        vault_row = QHBoxLayout()
        vault_row.addWidget(self.le_obsidian_vault)
        self.btn_vault_browse = QPushButton("浏览...")
        self.btn_vault_browse.clicked.connect(self._browse_vault)
        vault_row.addWidget(self.btn_vault_browse)
        self.le_obsidian_folder = QLineEdit("知乎收藏")
        obf.addRow("", self.cb_obsidian_enabled)
        obf.addRow("库根目录:", vault_row)
        obf.addRow("库内子文件夹:", self.le_obsidian_folder)
        sv.addWidget(ob)

        ai = QGroupBox("本地 AI(需安装 Ollama)")
        aif = QFormLayout(ai)
        self.cb_ai_enabled = QCheckBox("启用 AI 摘要与分类")
        self.le_ai_model = QLineEdit("qwen2.5:7b")
        self.cb_ai_summary = QCheckBox("生成摘要写入 YAML")
        self.cb_ai_classify = QCheckBox("学科分类并生成分类索引")
        self.sp_ai_timeout = QSpinBox()
        self.sp_ai_timeout.setRange(30, 600)
        self.sp_ai_timeout.setSuffix(" 秒")
        aif.addRow("", self.cb_ai_enabled)
        aif.addRow("模型名:", self.le_ai_model)
        aif.addRow("", self.cb_ai_summary)
        aif.addRow("", self.cb_ai_classify)
        aif.addRow("调用超时:", self.sp_ai_timeout)
        ai_hint = QLabel("AI 在本地运行, 文章内容不出本机。Ollama 未启动时自动跳过, 不影响导出。")
        ai_hint.setWordWrap(True)
        ai_hint.setStyleSheet("color: gray;")
        aif.addRow("", ai_hint)
        sv.addWidget(ai)
        sv.addStretch()
        self.tabs.addTab(tab_sync, "同步")

        # ---------- 数据管理 ----------
        tab_data = QWidget()
        dv = QVBoxLayout(tab_data)

        out_group = QGroupBox("输出目录")
        og = QVBoxLayout(out_group)
        out_row = QHBoxLayout()
        self.le_output = QLineEdit()
        self.le_output.setPlaceholderText("留空 = 使用默认目录")
        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.clicked.connect(self.browse_output)
        self.btn_reset_out = QPushButton("恢复默认")
        self.btn_reset_out.clicked.connect(lambda: self.le_output.clear())
        out_row.addWidget(self.le_output)
        out_row.addWidget(self.btn_browse)
        out_row.addWidget(self.btn_reset_out)
        og.addLayout(out_row)
        dv.addWidget(out_group)

        data_group = QGroupBox("数据管理")
        dg = QVBoxLayout(data_group)
        self.btn_open_out = QPushButton("📂 打开输出目录")
        self.btn_open_out.clicked.connect(self.open_output)
        self.btn_clear_hist = QPushButton("🗑️ 清空下载历史记录")
        self.btn_clear_hist.clicked.connect(self.clear_history)
        self.btn_logout = QPushButton("🚪 退出登录(删除本地凭证)")
        self.btn_logout.setObjectName("dangerButton")
        self.btn_logout.clicked.connect(self.logout)
        dg.addWidget(self.btn_open_out)
        dg.addWidget(self.btn_clear_hist)
        dg.addWidget(self.btn_logout)
        dv.addWidget(data_group)
        dv.addStretch()
        self.tabs.addTab(tab_data, "数据管理")

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("保存设置")
        self.btn_save.setObjectName("primaryButton")
        self.btn_save.clicked.connect(self.accept)
        apply_glow(self.btn_save, QColor(120, 195, 245, 110), 16, 3)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_save)
        layout.addLayout(btn_row)

        self._load_values()

    def _load_values(self):
        s = self.settings
        self.cb_default_md.setChecked(bool(s.get("default_md", True)))
        self.cb_default_pdf.setChecked(bool(s.get("default_pdf", True)))
        self.cb_default_html.setChecked(bool(s.get("default_html", True)))
        self.cb_close_tray.setChecked(bool(s.get("close_to_tray", True)))
        self.cb_auto_open.setChecked(bool(s.get("auto_open_output", False)))
        self.cb_dark_mode.setChecked(bool(s.get("dark_mode", False)))
        self.bg_color = str(s.get("bg_color", "")).strip()
        self._update_bg_preview()
        self.le_filename_template.setText(str(s.get("filename_template", "")))
        self.cb_autostart.setChecked(bool(s.get("autostart", False)))
        self.cb_sleep.setChecked(bool(s.get("sleep_enabled", True)))
        self.sp_sleep_min.setValue(float(s.get("sleep_min", 2.5)))
        self.sp_sleep_max.setValue(float(s.get("sleep_max", 5.5)))
        self.sp_workers.setValue(int(s.get("image_workers", 4)))
        self.sp_render_wait.setValue(float(s.get("pdf_render_wait", 3.0)))
        self.le_output.setText(str(s.get("output_dir", "")))

        # 同步与 AI
        self.cb_clipboard_watch.setChecked(bool(s.get("clipboard_watch", True)))
        self.cb_obsidian_enabled.setChecked(bool(s.get("obsidian_enabled", False)))
        self.le_obsidian_vault.setText(str(s.get("obsidian_vault", "")))
        self.le_obsidian_folder.setText(str(s.get("obsidian_folder", "知乎收藏")))
        self.cb_ai_enabled.setChecked(bool(s.get("ai_enabled", False)))
        self.le_ai_model.setText(str(s.get("ai_model", "qwen2.5:7b")))
        self.cb_ai_summary.setChecked(bool(s.get("ai_summary", True)))
        self.cb_ai_classify.setChecked(bool(s.get("ai_classify", True)))
        self.sp_ai_timeout.setValue(int(s.get("ai_timeout", 120)))

    def _pick_bg_color(self):
        current = QColor(self.bg_color) if self.bg_color else QColor("#F7FBFF")
        color = QColorDialog.getColor(current, self, "选择背景颜色")
        if color.isValid():
            self.bg_color = color.name()
            self._update_bg_preview()

    def _reset_bg_color(self):
        self.bg_color = ""
        self._update_bg_preview()

    def _update_bg_preview(self):
        if self.bg_color:
            self.bg_preview.setText("")
            self.bg_preview.setStyleSheet(
                f"background: {self.bg_color}; border: 1px solid #C9E3F5; "
                "border-radius: 4px;")
        else:
            self.bg_preview.setText("默认")
            self.bg_preview.setStyleSheet(
                "background: transparent; border: 1px solid #C9E3F5; "
                "border-radius: 4px; color: #4A7396;")

    def save_settings(self):
        self.settings.update({
            "default_md": self.cb_default_md.isChecked(),
            "default_pdf": self.cb_default_pdf.isChecked(),
            "default_html": self.cb_default_html.isChecked(),
            "close_to_tray": self.cb_close_tray.isChecked(),
            "auto_open_output": self.cb_auto_open.isChecked(),
            "dark_mode": self.cb_dark_mode.isChecked(),
            "bg_color": self.bg_color,
            "filename_template": self.le_filename_template.text().strip(),
            "autostart": self.cb_autostart.isChecked(),
            "sleep_enabled": self.cb_sleep.isChecked(),
            "sleep_min": self.sp_sleep_min.value(),
            "sleep_max": self.sp_sleep_max.value(),
            "image_workers": self.sp_workers.value(),
            "pdf_render_wait": self.sp_render_wait.value(),
            "clipboard_watch": self.cb_clipboard_watch.isChecked(),
            "obsidian_enabled": self.cb_obsidian_enabled.isChecked(),
            "obsidian_vault": self.le_obsidian_vault.text().strip(),
            "obsidian_folder": self.le_obsidian_folder.text().strip(),
            "ai_enabled": self.cb_ai_enabled.isChecked(),
            "ai_model": self.le_ai_model.text().strip(),
            "ai_summary": self.cb_ai_summary.isChecked(),
            "ai_classify": self.cb_ai_classify.isChecked(),
            "ai_timeout": self.sp_ai_timeout.value(),
            "output_dir": self.le_output.text().strip(),
        })
        try:
            self.settings.save()
            return True
        except OSError:
            return False

    def _browse_vault(self):
        start_dir = self.le_obsidian_vault.text().strip() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "选择 Obsidian 库根目录", start_dir)
        if path:
            self.le_obsidian_vault.setText(path)

    def browse_output(self):
        start_dir = self.le_output.text().strip() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", start_dir)
        if path:
            self.le_output.setText(path)

    def open_output(self):
        if self.main_window is not None:
            self.main_window.open_output_dir()
        else:
            os.startfile(get_output_dir())

    def clear_history(self):
        if self.main_window is not None:
            self.main_window.clear_history()
        else:
            path = get_history_file()
            if os.path.exists(path):
                os.remove(path)

    def logout(self):
        if self.main_window is not None:
            self.main_window.logout()
        else:
            path = get_cookie_file()
            if os.path.exists(path):
                os.remove(path)


# ==========================================
# 自定义标题栏(无边框窗口的拖动与窗口按钮)
# ==========================================
class TitleBar(QWidget):
    def __init__(self, window, title):
        super().__init__()
        self._window = window
        self._drag_offset = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 2, 2)

        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(28, 28)
        self.avatar_label.setPixmap(self._default_avatar())
        layout.addWidget(self.avatar_label)

        self.profile_name_label = QLabel("加载中...")
        self.profile_name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.profile_name_label)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("appTitle")
        layout.addWidget(self.title_label)
        layout.addStretch()

        self.settings_btn = QPushButton("⚙️ 设置")
        self.settings_btn.clicked.connect(window.open_settings)
        layout.addWidget(self.settings_btn)

        self.min_btn = QPushButton("—")
        self.min_btn.setObjectName("winBtn")
        self.min_btn.setFixedSize(30, 26)
        self.min_btn.clicked.connect(self._window.showMinimized)
        layout.addWidget(self.min_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setFixedSize(30, 26)
        self.close_btn.clicked.connect(self._window.close)
        layout.addWidget(self.close_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = (event.globalPosition().toPoint()
                                 - self._window.frameGeometry().topLeft())

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

    @staticmethod
    def _default_avatar(size=28):
        """默认占位头像: 浅蓝圆底 + 白色"知"字"""
        out = QPixmap(size, size)
        out.fill(Qt.transparent)
        painter = QPainter(out)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#8CC4EE"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        painter.drawText(out.rect(), Qt.AlignCenter, "知")
        painter.end()
        return out

    def set_avatar(self, pixmap):
        self.avatar_label.setPixmap(pixmap)

    def set_profile_name(self, name):
        self.profile_name_label.setText(name)


# ==========================================
# 主界面工作区
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = SettingsManager()
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.resize(760, 600)
        # 无边框窗口(不透明, 由内部圆角卡片呈现窗口)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAcceptDrops(True)
        self._build_card()
        self.init_tray()
        self.init_clipboard_watch()
        # 账号头像与昵称: 先读本地缓存, 再后台联网刷新
        self._load_cached_profile()
        if AuthManager().has_valid_cookies():
            self._profile_thread = ProfileThread()
            self._profile_thread.result_signal.connect(self._on_profile_loaded)
            self._profile_thread.start()
        else:
            self.title_bar.set_profile_name("未登录")
        self._apply_theme()
        self._log_export_stats()

    def _apply_theme(self):
        bg = str(self.settings.get("bg_color", "")).strip()
        if bg:
            qss = build_theme_qss(bg)
            QApplication.instance().setStyleSheet(qss or STYLE_QSS)
            self._set_custom_background(True, bg)
            email_color = self._derive_muted_color(bg)
        else:
            dark = bool(self.settings.get("dark_mode", False))
            QApplication.instance().setStyleSheet(STYLE_QSS_DARK if dark else STYLE_QSS)
            self._set_custom_background(False, None)
            email_color = "#8FA9C0" if dark else "#6B8FAE"
        self._update_email_color(email_color)

    @staticmethod
    def _derive_muted_color(bg_hex):
        """由背景色派生一个柔和的次要文字色(用于左下角邮箱等提示文字)"""
        c = QColor(bg_hex)
        if not c.isValid():
            return "#6B8FAE"
        h, s, l, _ = c.getHslF()
        light = 0.72 if l < 0.5 else 0.42
        sat = s * (0.30 if l < 0.5 else 0.45)
        col = QColor()
        col.setHslF(h, max(0.0, min(1.0, sat)), light)
        return col.name()

    def _update_email_color(self, color_hex):
        if hasattr(self, "email_label"):
            self.email_label.setText(
                '<a href="mailto:dadealbit@gmail.com" '
                f'style="color:{color_hex}; text-decoration:none;">'
                '📧 问题反馈: dadealbit@gmail.com</a>')

    def _set_custom_background(self, is_custom, bg):
        """自定义背景时: 去掉蓝色光晕叠加、阴影改中性、主按钮光晕跟随背景色相"""
        if is_custom:
            if self.glow_bg is not None:
                self.glow_bg.hide()
            if self.card_shadow is not None:
                self.card_shadow.setColor(QColor(0, 0, 0, 60))
            color = QColor(bg)
            if color.isValid() and self.start_btn_glow is not None:
                h, s, l, _ = color.getHslF()
                glow = QColor()
                glow.setHslF(h, max(s, 0.45), 0.72)
                glow.setAlphaF(0.40)
                self.start_btn_glow.setColor(glow)
        else:
            if self.glow_bg is not None:
                self.glow_bg.show()
            if self.card_shadow is not None:
                self.card_shadow.setColor(QColor(70, 130, 180, 70))
            if self.start_btn_glow is not None:
                self.start_btn_glow.setColor(QColor(120, 195, 245, 140))

    def apply_autostart(self):
        """按设置写入/删除开机自启注册表项"""
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        enabled = bool(self.settings.get("autostart", False))
        try:
            if enabled:
                if getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    cmd = f'"{sys.executable}" "{os.path.abspath("main.py")}"'
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                    winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, "DadealbitZhihuExporter", 0,
                                      winreg.REG_SZ, cmd)
            else:
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                        winreg.KEY_SET_VALUE) as key:
                        winreg.DeleteValue(key, "DadealbitZhihuExporter")
                except FileNotFoundError:
                    pass
        except Exception as e:
            print(f"⚠️ 开机自启设置失败: {e}")

    def _log_export_stats(self):
        """启动时统计已导出的文件数量"""
        try:
            out = self.settings.resolve_output_dir()
            md = len(glob.glob(os.path.join(out, "*.md")))
            pdf = len(glob.glob(os.path.join(out, "*.pdf")))
            html = len(glob.glob(os.path.join(out, "*.html")))
            if md or pdf or html:
                self.append_log(f"📊 已导出统计: Markdown {md} 篇 / PDF {pdf} 篇 / HTML {html} 篇")
        except Exception:
            pass

    @staticmethod
    def _round_avatar(pixmap, size=28):
        """把方形头像裁成圆形"""
        target = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding,
                               Qt.SmoothTransformation)
        out = QPixmap(size, size)
        out.fill(Qt.transparent)
        painter = QPainter(out)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, size, size, target)
        painter.end()
        return out

    def _load_cached_profile(self):
        cache_dir = get_data_dir()
        cached_name = os.path.join(cache_dir, "profile_name.txt")
        cached_avatar = os.path.join(cache_dir, "avatar.jpg")
        if os.path.isfile(cached_name):
            try:
                with open(cached_name, encoding="utf-8") as f:
                    name = f.read().strip()
                if name:
                    self.title_bar.set_profile_name(name)
            except OSError:
                pass
        if os.path.isfile(cached_avatar):
            pix = QPixmap(cached_avatar)
            if not pix.isNull():
                self.title_bar.set_avatar(self._round_avatar(pix))

    def _on_profile_loaded(self, result):
        cache_dir = get_data_dir()
        name = result.get("name")
        if name:
            self.title_bar.set_profile_name(name)
            try:
                with open(os.path.join(cache_dir, "profile_name.txt"), "w",
                          encoding="utf-8") as f:
                    f.write(name)
            except OSError:
                pass
        else:
            self.title_bar.set_profile_name("知乎用户")
        avatar_bytes = result.get("avatar_bytes")
        if avatar_bytes:
            pix = QPixmap()
            if pix.loadFromData(avatar_bytes):
                self.title_bar.set_avatar(self._round_avatar(pix))
                try:
                    with open(os.path.join(cache_dir, "avatar.jpg"), "wb") as f:
                        f.write(avatar_bytes)
                except OSError:
                    pass

    def _build_card(self):
        # 外容器四周留白, 用于展示阴影
        outer = QWidget()
        self.setCentralWidget(outer)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(16, 16, 16, 16)

        self.card = QFrame()
        self.card.setObjectName("card")
        outer_layout.addWidget(self.card)

        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(70, 130, 180, 70))
        self.card.setGraphicsEffect(shadow)
        self.card_shadow = shadow

        grid = QGridLayout(self.card)
        grid.setContentsMargins(16, 8, 16, 14)
        grid.setSpacing(0)

        # 动态光晕背景(底层)
        self.glow_bg = GlowBackground(self.card)

        # 内容层(透明, 叠加在光晕之上)
        content = QWidget(self.card)
        content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(10)

        # 标题栏
        self.title_bar = TitleBar(self, f"{APP_NAME} v{__version__}")
        self.settings_btn = self.title_bar.settings_btn
        lay.addWidget(self.title_bar)

        # 目标输入
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴单篇/回答/专栏 URL，或导入包含网址的 txt 文件...")
        self.url_input.setAcceptDrops(False)
        self.import_btn = QPushButton("📁 导入 TXT")
        self.import_btn.clicked.connect(self.import_txt_file)
        url_layout.addWidget(QLabel("目标:"))
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.import_btn)
        lay.addLayout(url_layout)

        # 格式选项(默认值来自设置)
        option_layout = QHBoxLayout()
        self.cb_md = QCheckBox("生成 Markdown")
        self.cb_md.setChecked(bool(self.settings.get("default_md", True)))
        self.cb_pdf = QCheckBox("生成 高清 PDF")
        self.cb_pdf.setChecked(bool(self.settings.get("default_pdf", True)))
        self.cb_html = QCheckBox("生成 HTML")
        self.cb_html.setChecked(bool(self.settings.get("default_html", True)))
        option_layout.addWidget(self.cb_md)
        option_layout.addWidget(self.cb_pdf)
        option_layout.addWidget(self.cb_html)
        option_layout.addStretch()
        lay.addLayout(option_layout)

        # 开始/停止
        action_layout = QHBoxLayout()
        self.start_btn = QPushButton("🚀 开始提取")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn_glow = apply_glow(self.start_btn, QColor(120, 195, 245, 140), 22, 5)
        action_layout.addWidget(self.start_btn, 3)

        self.stop_btn = QPushButton("🛑 停止任务")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.request_stop)
        action_layout.addWidget(self.stop_btn, 1)
        lay.addLayout(action_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        lay.addWidget(self.progress_bar)

        self.eta_label = QLabel("")
        lay.addWidget(self.eta_label)

        # 进度平滑微动画
        self._progress_anim = QPropertyAnimation(self.progress_bar, b"value")
        self._progress_anim.setDuration(350)
        self._progress_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.log_console = QTextBrowser()
        self.log_console.setObjectName("logConsole")
        self.log_console.setAcceptDrops(False)
        self.log_console.append(f"系统就绪 (v{__version__})。点击右上角 ⚙️ 设置 调整选项。")
        lay.addWidget(self.log_console, 1)

        # 底部左下角: 问题反馈邮箱(点击直接唤起邮件客户端)
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        self.email_label = QLabel()
        self.email_label.setTextFormat(Qt.RichText)
        self.email_label.setText(
            '<a href="mailto:dadealbit@gmail.com" '
            'style="color:#6B8FAE; text-decoration:none;">'
            '📧 问题反馈: dadealbit@gmail.com</a>')
        self.email_label.setOpenExternalLinks(True)
        footer.addWidget(self.email_label)
        footer.addStretch()
        lay.addLayout(footer)

        # 网格叠放: 光晕(底) → 内容(顶)
        grid.addWidget(self.glow_bg, 0, 0)
        grid.addWidget(content, 0, 0)

        # 右下角缩放把手(无边框窗口)
        grip = QSizeGrip(self.card)
        grid.addWidget(grip, 0, 0, Qt.AlignRight | Qt.AlignBottom)

    def init_clipboard_watch(self):
        """监听剪贴板中的知乎链接"""
        self._last_clip_text = ""
        try:
            self._last_clip_text = QApplication.clipboard().text().strip()
        except Exception:
            pass
        QApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self):
        if not self.settings.get("clipboard_watch", True):
            return
        worker = getattr(self, "worker", None)
        if worker is not None and worker.isRunning():
            return
        try:
            text = QApplication.clipboard().text().strip()
        except Exception:
            return
        if not text or text == self._last_clip_text:
            return
        if text.startswith("http") and ("zhihu.com" in text or "zhuanlan" in text):
            self._last_clip_text = text
            self.url_input.setText(text)
            self.append_log(f"🔗 检测到剪贴板知乎链接: {text[:60]}...")
            self.showNormal()
            self.activateWindow()
            self.tray_icon.showMessage(
                APP_NAME,
                "检测到知乎链接，已填入输入框，点击「开始提取」即可。",
                QSystemTrayIcon.MessageIcon.Information, 3000)

    def init_tray(self):
        # 创建托盘图标对象
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(get_resource_path("icon.ico")))
        
        tray_menu = QMenu()
        
        show_action = QAction("🖥️ 显示主界面", self)
        show_action.triggered.connect(self.showNormal)
        
        quit_action = QAction("❌ 完全退出", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        
        tray_menu.addAction(show_action)
        tray_menu.addSeparator() 
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        self.tray_icon.activated.connect(self.tray_icon_activated)

    def _should_hide_to_tray(self):
        """任务运行中强制入托盘; 否则按设置决定"""
        worker = getattr(self, "worker", None)
        if worker is not None and worker.isRunning():
            return True
        return bool(self.settings.get("close_to_tray", True))

    def changeEvent(self, event):
        """拦截窗口最小化事件：静默隐藏到托盘(不再弹提示)"""
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized() and self._should_hide_to_tray():
                self.hide()
        super().changeEvent(event)

    def closeEvent(self, event):
        """关闭事件：点 × 直接静默最小化到托盘(不弹提示), 完全退出走托盘菜单"""
        if self._should_hide_to_tray():
            event.ignore()
            self.hide()
        else:
            event.accept()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal() 
            self.activateWindow() 

    def import_txt_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择包含网址的 TXT 文件", "", "Text Files (*.txt)")
        if file_path:
            self.url_input.setText(file_path)
            self.append_log(f"已加载文件路径: {file_path}")

    def append_log(self, text):
        """界面显示 + 同步写入按天滚动的日志文件"""
        self.log_console.append(text)
        try:
            with open(get_log_file(), "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError:
            pass

    def open_output_dir(self):
        """在资源管理器中打开输出目录"""
        out_dir = self.settings.resolve_output_dir()
        try:
            os.startfile(out_dir)
            self.append_log(f"📂 已打开输出目录: {out_dir}")
        except Exception as e:
            self.append_log(f"⚠️ 无法打开输出目录: {e}")

    def open_settings(self):
        dialog = SettingsDialog(self.settings, main_window=self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.save_settings():
                self.append_log("⚙️ 设置已保存，下次任务立即生效。")
                self.cb_md.setChecked(bool(self.settings.get("default_md", True)))
                self.cb_pdf.setChecked(bool(self.settings.get("default_pdf", True)))
                self.cb_html.setChecked(bool(self.settings.get("default_html", True)))
                self._apply_theme()
                self.apply_autostart()
            else:
                self.append_log("⚠️ 设置保存失败。")

    def update_progress(self, value):
        """平滑动画过渡到目标进度"""
        self._progress_anim.stop()
        self._progress_anim.setStartValue(self.progress_bar.value())
        self._progress_anim.setEndValue(value)
        self._progress_anim.start()

    def update_eta(self, text):
        self.eta_label.setText(text)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if path and path.lower().endswith(".txt") and os.path.isfile(path):
                    self.url_input.setText(path)
                    self.append_log(f"📂 已拖入 TXT 文件: {path}")
                    event.acceptProposedAction()
                    return
                link = url.toString()
                if link.startswith("http"):
                    self.url_input.setText(link)
                    self.append_log(f"🔗 已拖入链接: {link[:60]}...")
                    event.acceptProposedAction()
                    return
        if mime.hasText():
            text = mime.text().strip()
            if text:
                self.url_input.setText(text)
                self.append_log(f"🔗 已拖入内容: {text[:60]}")
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def request_stop(self):
        """请求停止当前任务(完成当前篇后优雅中止)"""
        worker = getattr(self, "worker", None)
        if worker is not None and worker.isRunning():
            self.append_log("\n🛑 正在请求停止任务，请稍候(完成当前篇后中止，进度已保存)...")
            worker.request_stop()
            self.stop_btn.setEnabled(False)
        else:
            self.append_log("\nℹ️ 当前没有正在运行的任务。")

    def task_finished(self, success):
        self.start_btn.setEnabled(True)
        self.import_btn.setEnabled(True)
        self.url_input.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if not success:
            self.progress_bar.setValue(0)
        if success and self.settings.get("auto_open_output", False):
            self.open_output_dir()

    def clear_history(self):
        history_file = get_history_file()
        if os.path.exists(history_file):
            try:
                os.remove(history_file)
                self.append_log("\n🗑️ 历史记录已成功清空！下次提取将重新下载所有文章。")
            except Exception as e:
                self.append_log(f"\n⚠️ 清空历史记录失败: {e}")
        else:
            self.append_log("\nℹ️ 缓存干干净净，当前没有任何历史记录。")

    def logout(self):
        """销毁本地 Cookie 凭证(加密文件 + 旧版明文)"""
        cookie_file = get_cookie_file()
        legacy_file = get_legacy_cookie_file()
        removed = False
        for path in (cookie_file, legacy_file):
            if os.path.exists(path):
                try:
                    os.remove(path)
                    removed = True
                except Exception as e:
                    self.append_log(f"\n⚠️ 退出登录失败: {e}")
        if removed:
            self.append_log("\n🚪 退出成功！本地登录凭证已彻底销毁，您的账号信息已清除。")
            self.append_log("⚠️ 为了安全，已锁定抓取功能。请【重启本软件】以切换其他账号登录。")
            self.start_btn.setEnabled(False)
            self.start_btn.setText("请重启软件以重新登录")
        else:
            self.append_log("\nℹ️ 凭证已不存在，无需重复退出。")

    def start_processing(self):
        input_text = self.url_input.text().strip()
        if not input_text:
            self.append_log("⚠️ 错误：请输入 URL 或导入 txt 文件！")
            return

        export_md = self.cb_md.isChecked()
        export_pdf = self.cb_pdf.isChecked()
        export_html = self.cb_html.isChecked()

        if not export_md and not export_pdf and not export_html:
            self.append_log("⚠️ 错误：请至少勾选一种导出格式！")
            return

        self.start_btn.setEnabled(False)
        self.import_btn.setEnabled(False)
        self.url_input.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.eta_label.setText("")
        self.log_console.clear()

        self.worker = WorkerThread(input_text, export_md, export_pdf, export_html, self.settings)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.task_finished)
        self.worker.eta_signal.connect(self.update_eta)
        self.worker.start()


# ==========================================
# 应用初始化
# ==========================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_QSS)

    # 空白电脑自检: 缺少 Edge 时给出中文引导
    from core.extras import edge_available
    if not edge_available():
        QMessageBox.warning(
            None, "缺少 Microsoft Edge 浏览器",
            "检测到系统未安装 Microsoft Edge。\n\n"
            "本工具的扫码登录与 PDF 渲染依赖 Edge，请先安装：\n"
            "https://www.microsoft.com/edge\n\n"
            "安装完成后重新运行本程序。")
        sys.exit(0)
    
    auth = AuthManager()
    if not auth.has_valid_cookies():
        login_dialog = LoginDialog()
        if login_dialog.exec() != QDialog.Accepted:
            sys.exit(0)

    window = MainWindow()
    window.show()
    window.apply_autostart()
    sys.exit(app.exec())
