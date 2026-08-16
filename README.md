📚 Dadeal.bit——知乎高阶内容提取器
========================

> 一款基于 PySide6 的知乎文章备份桌面工具，支持将知乎文章、专栏、回答一键导出为 Markdown 和高清 PDF 格式，完整保留数学公式、图片及 YAML 元数据。

* * *

✨ 功能特性
------

| 功能             | 说明                                                 |
| -------------- | -------------------------------------------------- |
| 🔐 扫码登录        | 调用本地 Edge 浏览器扫码，Cookie 安全落盘，无需手动填写账密               |
| 📄 单篇文章提取      | 支持知乎专栏文章链接 (`zhuanlan.zhihu.com/p/...`)            |
| 💬 回答提取        | 支持知乎回答链接 (`zhihu.com/question/.../answer/...`)     |
| 📂 专栏批量提取      | 自动翻页获取专栏下全部文章，无需逐篇复制链接                             |
| 📋 TXT 批量导入    | 支持导入包含多个链接的 `.txt` 文件，批量执行                         |
| 📝 Markdown 导出 | 生成带 YAML Front Matter 的 `.md` 文件，含标题、作者、日期、标签、原文链接 |
| 🖨️ PDF 导出     | 基于 Playwright 无头浏览器渲染，排版精美、支持数学公式                  |
| 🧮 数学公式处理      | 自动修复知乎新版/旧版 LaTeX，输出标准 `$...$` / `$$...$$` 格式      |
| 🖼️ 图片本地化      | 自动下载文章内所有图片至本地 `assets/` 目录，防止图片外链失效               |
| ⏭️ 断点续传        | 下载记录持久化保存，重启后自动跳过已完成文章                             |
| 🛡️ 反爬缓解       | 请求间随机休眠 2.5–5.5 秒，降低账号触发风控的概率                      |
| 🗃️ 系统托盘       | 关闭/最小化窗口后静默后台运行，不中断下载任务                            |

* * *

🖼️ 界面预览
--------

    ┌─────────────────────────────────────────────┐
    │  Dadeal.bit——知乎高阶内容提取器              │
    ├─────────────────────────────────────────────┤
    │  目标: [ 粘贴 URL 或导入 TXT 文件... ] [📁] │
    │  ☑ 生成 Markdown   ☑ 生成高清 PDF           │
    │  [🗑️ 清空历史]     [🚪 退出登录]            │
    │  [        🚀 开始提取        ]               │
    │  ████████████░░░░░░░░  60%                  │
    ├─────────────────────────────────────────────┤
    │  🚀 初始化核心引擎...                        │
    │  🕵️ 检测到专栏主页链接！正在获取文章目录...  │
    │  ✅ 专栏解析完毕，共挖掘出 42 篇文章！       │
    │  ...                                         │
    └─────────────────────────────────────────────┘

* * *

🗂️ 项目结构
--------

    zhihu-exporter/
    │
    ├── main.py                  # 程序入口：PySide6 GUI 主窗口
    ├── icon.ico                 # 系统托盘图标
    │
    ├── core/
    │   ├── __init__.py
    │   ├── auth_manager.py      # 认证模块：浏览器扫码、Cookie 持久化
    │   ├── spider_engine.py     # 爬虫引擎：网页抓取、内容解析、图片下载
    │   └── format_converter.py  # 格式转换：HTML → Markdown / PDF
    │
    ├── data/
    │   ├── cookies.json         # 登录凭证（自动生成，勿手动编辑）
    │   └── download_history.json # 下载历史记录（自动生成）
    │
    └── outputs/
        ├── 文章标题.md           # 导出的 Markdown 文件
        ├── 文章标题.pdf          # 导出的 PDF 文件
        └── assets/
            └── 文章标题/        # 对应文章的本地化图片资源
                ├── img_001.jpg
                └── img_002.png

> `data/` 和 `outputs/` 目录均由程序自动创建，无需手动建立。
> 打包安装版运行时，数据与输出统一存放在 `%LOCALAPPDATA%\DadealZhihuExporter\` 下（安装目录通常无写权限）；源码运行时仍使用项目目录内的 `data/` 与 `outputs/`。

* * *

⚙️ 环境要求
-------

* **操作系统**：Windows 10 / 11（GUI 基于 PySide6，其他系统理论可用但未测试）
* **Python 版本**：>= 3.9
* **浏览器**：Microsoft Edge（用于扫码登录和 PDF 渲染，需已安装在系统中）

* * *

🚀 快速开始
-------

### 1. 克隆仓库

    git clone https://github.com/your-username/zhihu-exporter.git
    cd zhihu-exporter

### 2. 安装依赖

建议在虚拟环境中安装：
    python -m venv venv
    venv\Scripts\activate      # Windows
    # source venv/bin/activate  # macOS / Linux

    pip install -r requirements.txt

### 3. 安装 Playwright 浏览器驱动

    playwright install chromium

> 如果系统已安装 Microsoft Edge，Playwright 将直接调用，无需额外下载 Chromium。

### 4. 运行程序

    python main.py

* * *

📦 依赖清单
-------

请在项目根目录创建 `requirements.txt`，内容如下：
    PySide6>=6.5.0
    playwright>=1.40.0
    requests>=2.31.0
    beautifulsoup4>=4.12.0
    html2text>=2020.1.16

或直接一键安装：
    pip install PySide6 playwright requests beautifulsoup4 html2text

* * *

📖 使用说明
-------

### 首次使用：绑定账号

1. 首次运行程序，会自动弹出**身份认证**对话框
2. 点击「📱 点击唤起浏览器扫码登录」
3. 在弹出的 Edge 浏览器窗口中，使用知乎 App 扫描二维码完成登录
4. 登录成功后，Cookie 将自动保存至 `data/cookies.json`，后续运行无需重复扫码

> ⚠️ 请勿将 `cookies.json` 上传至公开代码仓库，该文件包含您的登录凭证。

### 提取单篇文章或回答

在目标输入框中粘贴链接，例如：
    https://zhuanlan.zhihu.com/p/123456789
    https://www.zhihu.com/question/123456/answer/789012

### 提取整个专栏

粘贴专栏主页链接，程序将自动获取专栏内所有文章：
    https://zhuanlan.zhihu.com/your-column-id

### 批量提取（TXT 文件导入）

1. 新建一个 `.txt` 文件，每行填写一个链接：
    https://zhuanlan.zhihu.com/p/111111111
    https://zhuanlan.zhihu.com/p/222222222
    https://www.zhihu.com/question/333/answer/444

2. 点击「📁 导入 TXT」选择文件，然后点击「🚀 开始提取」

### 选择导出格式

* **☑ 生成 Markdown**：同时生成 `.md` 文件，含 YAML Front Matter 元数据
* **☑ 生成高清 PDF**：使用 Playwright 渲染高保真 PDF，支持中文字体和数学公式

两个格式可同时勾选，也可单独选择。

* * *

📝 输出格式说明
---------

### Markdown 格式示例

    ---
    title: "浅谈扩散模型的数学原理"
    author: "某知乎用户"
    date: 2024-03-15
    tags: ["深度学习", "生成模型", "数学"]
    url: "https://zhuanlan.zhihu.com/p/123456789"
    ---
    
    # 浅谈扩散模型的数学原理
    
    正文内容...
    
    行内公式：$p_\theta(x_{t-1}|x_t)$
    
    独立公式块：
    $$
    L = \mathbb{E}_{t,x_0,\epsilon}\left[\|\epsilon - \epsilon_\theta(x_t, t)\|^2\right]
    $$

### 目录结构示例

    outputs/
    ├── 浅谈扩散模型的数学原理.md
    ├── 浅谈扩散模型的数学原理.pdf
    └── assets/
        └── 浅谈扩散模型的数学原理/
            ├── img_001.jpg
            └── img_002.png

* * *

🔧 核心模块说明
---------

### `auth_manager.py` — 认证管理器

负责知乎账号的认证与凭证管理：

* `has_valid_cookies()`：检测本地是否存在有效的 `cookies.json`
* `login_and_save_cookies()`：调用 Edge 浏览器唤起知乎扫码页，等待登录成功后提取并序列化 Cookie
* `get_cookies()`：读取并返回本地 Cookie 供爬虫使用

### `spider_engine.py` — 爬虫引擎

负责内容的抓取与解析：

* `get_column_article_urls(column_url)`：调用知乎 API (`/api/v4/columns/{id}/items`) 自动翻页获取专栏下所有文章链接
* `fetch_and_parse(url)`：请求目标页面，提取标题、作者、发布时间、标签、正文 HTML，并触发图片本地化
* `_download_and_replace_images(html, title)`：遍历正文中的 `<img>` 标签，下载图片至本地，将 `src` 替换为相对路径

### `format_converter.py` — 格式转换器

负责将 HTML 内容转换为目标格式：

* `to_markdown(html, title, metadata)`：将 HTML 转为 Markdown，处理数学公式占位符，写入带 YAML 头的 `.md` 文件
* `to_pdf(html, title)`：将 HTML 注入内置 CSS 样式和 MathJax 脚本，通过 Playwright 无头渲染为 PDF
* `_extract_and_clean_math(html)`：提取新版 `span.ztext-math` 和旧版 `img.eeimg` 公式，修复常见的 LaTeX 转义错误

### `main.py` — GUI 主程序

基于 PySide6 的图形界面主程序：

* `LoginDialog`：首次启动时的认证引导弹窗
* `LoginThread`：在独立线程中执行登录操作，防止 GUI 阻塞
* `WorkerThread`：在独立线程中执行全部抓取和转换任务，通过 Signal 向主线程回传日志和进度
* `MainWindow`：主窗口，包含输入框、格式选项、进度条、日志控制台和系统托盘

* * *

❓ 常见问题
------

**Q：程序启动后浏览器没有弹出？** A：请确认已安装 Microsoft Edge，并且 Edge 的安装路径已在系统 PATH 中。也可以修改 `auth_manager.py` 中 `channel="msedge"` 为 `channel="chrome"` 以使用 Chrome。

**Q：扫码登录成功但提示抓取失败？** A：可能是 Cookie 已过期（知乎 Cookie 有效期约 30 天），点击「🚪 退出登录」删除旧凭证，重启程序重新扫码。

**Q：PDF 中的数学公式显示为方块或空白？** A：PDF 渲染依赖 MathJax CDN（由 npmmirror 提供），请确认网络可正常访问 `registry.npmmirror.com`。

**Q：专栏只爬到了部分文章？** A：知乎 API 可能对部分付费专栏有权限限制，已登录的账号无订阅权限的文章将被跳过。

**Q：下载速度很慢？** A：为规避知乎反爬机制，每篇文章之间会随机休眠 2.5–5.5 秒，这是有意设计的。

**Q：如何重新下载已完成的文章？** A：点击主界面中的「🗑️ 清空历史记录」按钮，清除断点续传记录后，重新启动任务即可。

* * *

🔒 免责声明
-------

本工具仅供**个人学习与内容备份**使用，请勿用于商业用途。使用前请确保您遵守[知乎用户协议](https://www.zhihu.com/terms)及相关法律法规。下载的内容版权归原作者所有，请勿二次传播或用于侵权行为。

* * *

📄 License
----------

[MIT License](https://claude.ai/chat/LICENSE)

* * *

🙌 致谢
-----

本项目基于以下优秀的开源库构建：

* [PySide6](https://doc.qt.io/qtforpython/) — 跨平台 Qt GUI 框架
* [Playwright](https://playwright.dev/python/) — 现代化浏览器自动化
* [Requests](https://requests.readthedocs.io/) — Python HTTP 库
* [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML 解析器
* [html2text](https://github.com/Alir3z4/html2text) — HTML 转 Markdown
