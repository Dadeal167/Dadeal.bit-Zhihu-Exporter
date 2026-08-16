import sys
import os
import time
import json
import random
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLineEdit, QPushButton, QCheckBox, 
                               QTextBrowser, QLabel, QProgressBar, QFileDialog,
                               QDialog, QSystemTrayIcon, QMenu)
from PySide6.QtCore import QThread, Signal, Qt, QEvent, QTimer
from PySide6.QtGui import QFont, QIcon, QAction

from core.auth_manager import AuthManager
from core.spider_engine import SpiderEngine
from core.format_converter import FormatConverter
from core.paths import get_resource_path, get_cookie_file, get_history_file, setup_console

setup_console()

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

class WorkerThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal(bool)

    def __init__(self, input_text, export_md, export_pdf):
        super().__init__()
        self.input_text = input_text 
        self.export_md = export_md
        self.export_pdf = export_pdf

    def run(self):
        try:
            self.log_signal.emit("🚀 初始化核心引擎...")
            
            auth = AuthManager()
            if not auth.has_valid_cookies():
                self.log_signal.emit("❌ 致命错误：登录凭证缺失或已过期，请重新扫码登录！")
                self.finished_signal.emit(False)
                return

            spider = SpiderEngine()
            converter = FormatConverter()
            
            # 读取断点续传历史记录
            history_file = get_history_file()
            downloaded_urls = set()
            if os.path.exists(history_file):
                try:
                    with open(history_file, 'r', encoding='utf-8') as f:
                        downloaded_urls = set(json.load(f))
                    self.log_signal.emit(f"📖 成功加载本地历史记录，共包含 {len(downloaded_urls)} 条已下载文章。")
                except Exception as e:
                    self.log_signal.emit(f"⚠️ 历史记录文件损坏，已重置。({e})")
            
            urls_to_process = []
            if self.input_text.endswith('.txt') and os.path.exists(self.input_text):
                self.log_signal.emit("📂 正在读取本地 TXT 文件中的链接...")
                with open(self.input_text, 'r', encoding='utf-8') as f:
                    urls_to_process = [line.strip() for line in f if line.strip()]
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
            
            for index, url in enumerate(urls_to_process):
                current_task_num = index + 1
                base_progress = int((index / total_tasks) * 100)
                
                # 去重拦截
                if url in downloaded_urls:
                    self.log_signal.emit(f"\n--- 第 {current_task_num}/{total_tasks} 篇 ---")
                    self.log_signal.emit(f"⏭️ 已在历史记录中，触发秒级跳过: {url}")
                    self.progress_signal.emit(int((current_task_num / total_tasks) * 100))
                    continue

                self.log_signal.emit(f"\n--- 正在处理第 {current_task_num}/{total_tasks} 篇 ---")
                self.log_signal.emit(f"🌐 目标链接: {url}")
                
                self.progress_signal.emit(base_progress + 5)
                try:
                    result = spider.fetch_and_parse(url)

                    if result["status"] == "success":
                        html_content = result["html_content"]
                        title = result["title"]
                        metadata = result.get("metadata")
                        self.log_signal.emit(f"✅ 成功获取: 《{title}》")
                        self.progress_signal.emit(base_progress + max(1, int(40 / total_tasks)))

                        if self.export_md:
                            self.log_signal.emit("📝 生成 Markdown 中...")
                            converter.to_markdown(html_content, title, metadata)
                            
                        if self.export_pdf:
                            self.log_signal.emit("🖨️ 渲染 PDF 中...")
                            converter.to_pdf(html_content, title)
                            
                        downloaded_urls.add(url)
                        with open(history_file, 'w', encoding='utf-8') as f:
                            json.dump(list(downloaded_urls), f, indent=4, ensure_ascii=False)
                    else:
                        self.log_signal.emit(f"❌ 抓取失败，跳过此篇: {result.get('message')}")
                except Exception as e:
                    self.log_signal.emit(f"❌ 处理本篇时发生异常，已跳过: {e}")

                self.progress_signal.emit(int((current_task_num / total_tasks) * 100))

                if current_task_num < total_tasks:
                    sleep_time = random.uniform(2.5, 5.5)
                    self.log_signal.emit(f"🛡️ 防火墙规避：随机休眠 {sleep_time:.2f} 秒...")
                    time.sleep(sleep_time)

            self.log_signal.emit("\n🎉 所有任务执行完毕！")
            self.finished_signal.emit(True)

        except Exception as e:
            self.log_signal.emit(f"❌ 发生系统异常: {str(e)}")
            self.finished_signal.emit(False)

# ==========================================
# 身份认证拦截弹窗
# ==========================================
class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("知乎提取器 - 身份认证")
        self.resize(350, 180)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(self)

        self.info_label = QLabel("欢迎使用！\n\n初次运行，请先唤起浏览器绑定知乎账号。")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(self.info_label)

        self.login_btn = QPushButton("📱 点击唤起浏览器扫码登录")
        self.login_btn.setMinimumHeight(45)
        self.login_btn.setStyleSheet("background-color: #0084FF; color: white; font-weight: bold; font-size: 14px; border-radius: 5px;")
        self.login_btn.clicked.connect(self.start_login)
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
# 主界面工作区
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("知乎文章导出神器 Pro (纯净版)")
        self.resize(650, 500)
        self.init_ui()
        self.init_tray()

    def init_ui(self):
        self.setWindowIcon(QIcon(get_resource_path("icon.ico")))
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        title_label = QLabel("Dadeal.bit——知乎高阶内容提取器")
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        layout.addWidget(title_label)

        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴单篇/回答/专栏 URL，或导入包含网址的 txt 文件...")
        
        self.import_btn = QPushButton("📁 导入 TXT")
        self.import_btn.clicked.connect(self.import_txt_file)
        
        url_layout.addWidget(QLabel("目标:"))
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.import_btn)
        layout.addLayout(url_layout)

        option_layout = QHBoxLayout()
        self.cb_md = QCheckBox("生成 Markdown")
        self.cb_md.setChecked(True)
        self.cb_pdf = QCheckBox("生成 高清 PDF")
        self.cb_pdf.setChecked(True)
        option_layout.addWidget(self.cb_md)
        option_layout.addWidget(self.cb_pdf)
        option_layout.addStretch()

        self.clear_history_btn = QPushButton("🗑️ 清空历史记录")
        self.clear_history_btn.clicked.connect(self.clear_history)
        option_layout.addWidget(self.clear_history_btn)
        
        self.logout_btn = QPushButton("🚪 退出登录")
        self.logout_btn.setStyleSheet("color: #d9534f; font-weight: bold;")
        self.logout_btn.clicked.connect(self.logout)
        option_layout.addWidget(self.logout_btn)
        
        layout.addLayout(option_layout)

        self.start_btn = QPushButton("🚀 开始提取")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self.start_processing)
        layout.addWidget(self.start_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.log_console = QTextBrowser()
        self.log_console.setStyleSheet("background-color: #1e1e1e; color: #4af626; font-family: Consolas;")
        self.log_console.append("系统就绪，当前账号凭证有效。")
        layout.addWidget(self.log_console)

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

    def changeEvent(self, event):
        """拦截窗口最小化事件：隐藏到底部托盘"""
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                self.hide() 
                self.tray_icon.showMessage(
                    "知乎提取器", 
                    "已最小化到系统托盘，后台将继续为您下载文章。", 
                    QSystemTrayIcon.MessageIcon.Information, 
                    2000
                )
        super().changeEvent(event)

    def closeEvent(self, event):
        """拦截关闭事件：最小化到托盘"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "知乎提取器", 
            "程序已隐藏到右下角托盘运行。如需完全退出，请右键托盘图标选择'完全退出'。", 
            QSystemTrayIcon.MessageIcon.Warning, 
            2000
        )

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
        self.log_console.append(text)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def task_finished(self, success):
        self.start_btn.setEnabled(True)
        self.import_btn.setEnabled(True)
        self.url_input.setEnabled(True)
        if not success:
            self.progress_bar.setValue(0)

    def clear_history(self):
        history_file = get_history_file()
        self.clear_history_btn.setEnabled(False)
        
        if os.path.exists(history_file):
            try:
                os.remove(history_file)
                self.append_log("\n🗑️ 历史记录已成功清空！下次提取将重新下载所有文章。")
            except Exception as e:
                self.append_log(f"\n⚠️ 清空历史记录失败: {e}")
        else:
            self.append_log("\nℹ️ 缓存干干净净，当前没有任何历史记录。")
            
        self.clear_history_btn.setEnabled(True)

    def logout(self):
        """销毁本地 Cookie 凭证"""
        cookie_file = get_cookie_file()
        
        self.logout_btn.setEnabled(False)
        
        if os.path.exists(cookie_file):
            try:
                os.remove(cookie_file)
                self.append_log("\n🚪 退出成功！本地登录凭证已彻底销毁，您的账号信息已清除。")
                self.append_log("⚠️ 为了安全，已锁定抓取功能。请【重启本软件】以切换其他账号登录。")
                
                self.start_btn.setEnabled(False)
                self.start_btn.setText("请重启软件以重新登录")
                self.start_btn.setStyleSheet("background-color: #555; color: #888;")
                
            except Exception as e:
                self.append_log(f"\n⚠️ 退出登录失败: {e}")
                self.logout_btn.setEnabled(True)
        else:
            self.append_log("\nℹ️ 凭证已不存在，无需重复退出。")

    def start_processing(self):
        input_text = self.url_input.text().strip()
        if not input_text:
            self.append_log("⚠️ 错误：请输入 URL 或导入 txt 文件！")
            return

        export_md = self.cb_md.isChecked()
        export_pdf = self.cb_pdf.isChecked()

        if not export_md and not export_pdf:
            self.append_log("⚠️ 错误：请至少勾选一种导出格式！")
            return

        self.start_btn.setEnabled(False)
        self.import_btn.setEnabled(False)
        self.url_input.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_console.clear()

        self.thread = WorkerThread(input_text, export_md, export_pdf)
        self.thread.log_signal.connect(self.append_log)
        self.thread.progress_signal.connect(self.update_progress)
        self.thread.finished_signal.connect(self.task_finished)
        self.thread.start()

# ==========================================
# 应用初始化
# ==========================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    auth = AuthManager()
    if not auth.has_valid_cookies():
        login_dialog = LoginDialog()
        if login_dialog.exec() != QDialog.Accepted:
            sys.exit(0)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())