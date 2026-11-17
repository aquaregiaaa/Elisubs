# Elisubs · 看视频时一键识别字幕

看视频时想记下某句字幕？点一下悬浮条上的按钮，字幕框里的字就进了剪贴板，在笔记软件里直接粘贴。
双语字幕也行：出来就是「中文一行、外文一行」。

- **识别一次**：点一下，当前字幕进剪贴板，同时记进当天的 md 文件。
- **录制**：开着它看视频，每换一句字幕自动识别；停止时整段放进剪贴板，不用一句句截、也不用删换行。
- **只留一种语言**：双语字幕可以只要中文或只要外文。
- **写进 Notion**（可选）：识别结果直接追加到你指定的 Notion 页面。
- 完全在本地识别，不上传截图（只有「检查更新」会访问 GitHub）。

![悬浮条](docs/bar.png)

## 下载和使用（Windows 10 2004 及以上 / Windows 11）

1. 到 [Releases](../../releases) 下载 `Elisubs-windows.zip`，解压到任意位置（比如 `D:\Tools\Elisubs`）。
2. 双击 `Elisubs.exe`。屏幕右下角会出现悬浮条，任务栏右侧也会多一个托盘图标
   （Windows 11 可能把它收在 ^ 里，拖到任务栏上就能常驻显示）。
3. 第一次用：点 **取景框** 按钮，在视频字幕的位置拖一个框。框会被记住，以后就不用再拖了。
4. 之后每句字幕点 **鼠标** 按钮（或按 **Alt+S**），右上角提示「已复制」，粘贴即可。

不需要安装 Python 或其他任何东西。第一次运行如果弹出「Windows 已保护你的电脑」，
这是因为程序没有数字签名：点「更多信息」→「仍要运行」就行。

### 悬浮条

| 按钮 | 作用 |
|---|---|
| 伊丽莎白 / 悬浮条四周的边 | 按住拖动悬浮条（鼠标会变成四向箭头），位置会记住 |
| 鼠标 | 识别一次（热键 **Alt+S**） |
| 取景框 | 换字幕区，换完马上识别一次（热键 **Alt+D**） |
| 中A / 中 / A | 识别语言：双语 → 只留中文 → 只留外文，点一下换一种 |
| 红色圆点 | 开始录制，变成「● REC n」（n = 已录几句），再点停止 |

点按钮不会抢走视频播放器的焦点，空格暂停照常能用。

### 托盘菜单（左键或右键点托盘图标）

重新框选字幕区、录制字幕、识别语言、隐藏悬浮窗、写入 Notion、目标页面、暂停快捷键、**开机自启**、
打开今天的记录、打开记录文件夹、更改记录保存位置…、**设置…**、检查更新、退出。

- **设置…**：改快捷键、记录保存位置、Notion 令牌和总页面链接，保存后立即生效。
- **暂停快捷键**：Alt+S / Alt+D 归还给其他程序（比如浏览器里 Alt+D 是跳到地址栏）。
- **检查更新**：启动时也会悄悄查一次，有新版本会提示，托盘里点「下载新版本」打开下载页。

### 识别结果去哪了

- **剪贴板**：单次识别是这一句；录制是停止时的整段。
- **当天记录**：默认在 `data\logs\年-月-日.md`（设置里可以改到任何文件夹，比如笔记软件的库），
  换了视频会自动写一个 `## 视频标题` 小标题。
- **去重**：同一个视频里记过的句子不会再记（OCR 差一两个字也认得出是同一句）。
- 程序放在没有写入权限的文件夹（比如 `C:\Program Files`）时，配置和记录会自动改存到 `%APPDATA%\Elisubs`。

### 录制

- 每 0.3 秒看一眼字幕框，只有字幕真的换了才识别，暂停视频时几乎不耗电。
- 录制时不弹提示，悬浮条上的数字会一直涨。
- **点停止时，整段放进剪贴板**，当天记录和 Notion 里也只写这一段。双语字幕是中文一段、外文一段：
  ```
  晚期的哥特艺术充满人文关怀 斯特凡·洛克纳的作品《最后的审判》

  Late Gothic art is full of humanism The Last Judgment by Stefan Lochner
  ```
- 2 分钟没有新字幕会自动停止（也会整段复制）。
- 录制中程序意外退出（崩溃、关机），录到的句子下次启动时会自动补存进当天记录。
- 逐词滚动出现的字幕（比如 YouTube 自动生成字幕）会存下很多半句，这种视频建议直接下载字幕文件。

### 能认哪些语言

实测全对：简体中文、繁体中文、英语、法语、德语、西班牙语、意大利语、葡萄牙语、日语。
**认不了：俄语、韩语。** 带 DRM 的视频（Netflix 等）截图是黑的，也认不了。

「只留中文 / 只留外文」按每行有没有汉字来分（两个以上汉字算中文行），所以**中日双语分不开**（日文里也有汉字）。

## 写进 Notion（可选）

1. 打开 [notion.so/my-integrations](https://www.notion.so/my-integrations)，新建一个「内部」集成，
   勾上「读取内容 / 更新内容 / 插入内容」，复制它的 API 令牌。
2. 在 Notion 里建一个总页面（例如「视频笔记」），页面右上角 ··· →「集成」→ 在搜索框输入你的集成名字 → 选中。
   （或者在集成设置页的「内容访问权限」里勾选这个页面。）
   权限会往下继承：以后在总页面下新建的子页面都能直接写，不用再连。
3. 托盘 →「设置…」，填「令牌」和「总页面链接」，保存。
4. 托盘里「写入 Notion」会自动打勾（不想写时点掉）。

- **目标页面**：默认「自动：最新建的子页面」——你在 Notion 里新建一个页面，字幕就自动写进去；
  也可以在托盘里固定选总页面或某个子页面。
- 写失败（断网、令牌不对、页面没连集成）会弹红色提示，内容存在 `data/pending.jsonl`，每分钟自动重试，重启也不丢。
- `config.json` 里有你的令牌，**不要把它发给别人**。

---

## 开发

```
pip install -r requirements.txt
pythonw Elisubs.pyw                                        # 运行
python -m PyInstaller Elisubs.spec --noconfirm             # 打包到 dist/Elisubs/
dist\Elisubs\Elisubs.exe --selftest 图片.png               # 自检：识别结果写到 dist\Elisubs\data\selftest.txt
```

### 技术要点

- 识别：RapidOCR 3.x，默认模型 PP-OCRv6 small（一个模型覆盖中日英和带重音的拉丁字母）。
  打包只带 det_small / rec_small / cls 三个模型（约 32MB）。
- **检测参数用 `Det.limit_type=max, limit_side_len=1280`**（只缩不放）：默认的 min/736 会把 140 像素高的字幕截图
  放大 5 倍，反而整行漏检。实测 33 张：默认 58 行漏 7 行、全对 24 张、每张 1.06 秒；改后 58 行全检出、全对 32 张、每张 0.16 秒。
- 拼行（`lines.py`）：上下重叠的框拼成一行；相邻两行同种文字（都是中文 / 都是西文）再并成一行；破折号开头的行不并。
- 录制（`watch.py`）：只比较「很亮且旁边有深色」的像素（白字黄字 + 黑边），背景画面怎么动都基本不影响；
  笔画图稳定（相邻两帧差异 ≤ 0.15）且和上次识别时明显不同（> 0.35）才识别；识别结果和上一句相似度 ≥ 0.9 就跳过。
  用背景平移 + 明暗起伏 + 字幕淡入的模拟视频测：60 帧只在 4 句字幕各自稳定时触发识别。
- 截图：Pillow ImageGrab（多显示器、DPI 感知、物理像素）。提示框设了 `WDA_EXCLUDEFROMCAPTURE`（截图时透明）；
  悬浮条不设（系统截图里要能看到它），自己识别时把悬浮条所在位置涂黑（`capture.mask`）。
  两者都不抢焦点（`WS_EX_NOACTIVATE`）。
  录制中每句先进内存 + `data/recording.jsonl`，停止时用 `lines.paragraph` 拼成「中文一段 / 外文一段」；
  启动时发现 recording.jsonl 就补存（有读不出的行时原文件另存为 recording.broken-*.jsonl，不删）。
- 热键：RegisterHotKey（独立线程 + 消息循环），暂停时真正注销；设置里改了快捷键会重建热键线程。
  托盘：pystray（子类化让左键也弹菜单）。界面：tkinter。
- 数据位置：exe 旁边写不了（`paths._writable` 实际建一个文件试）就用 `%APPDATA%\Elisubs`。
- 检查更新：`api.github.com/repos/aquaregiaaa/Elisubs/releases/latest` 的 tag 和 `elisubs.__version__` 比。
- Notion：标准库 urllib，API 版本 2022-06-28；发送队列落盘，失败重试。
- 改名：1.0 / 1.1 叫 subsnap，1.2 起叫 Elisubs。新版第一次启动时（`migrate.py`）把旧的开机自启项换成新的；
  如果是解压到新文件夹，会去旧开机自启指向的文件夹和 `%APPDATA%\subsnap` 找旧设置和记录复制过来（不删旧的）。
- 开机自启：`HKCU\Software\Microsoft\Windows\CurrentVersion\Run\Elisubs`（只影响当前用户）。
- 图标：`make_icon.py` 从 `assets/elizabeth_src.png` 生成（把牌子上的字换成 COPIED，透视贴合）；
  `python make_icon.py variants` 出不同字体的对比图。

### 文件

| 路径 | 作用 |
|---|---|
| `Elisubs.pyw` | 入口；`--selftest` 自检 |
| `Elisubs.spec` | PyInstaller 打包配置 |
| `config.json` | 首次运行自动生成：Notion 令牌、总页面链接、快捷键、记录位置（不入库）；格式写坏了会提示，保存设置时把坏文件另存 |
| `data/` | 字幕框位置、记录、待发队列、录制暂存、运行日志 `elisubs.log`（不入库） |
| `elisubs/settings.py` / `updater.py` | 设置窗口、检查更新 |
| `elisubs/app.py` | 主流程；线程分工写在文件头 |
| `elisubs/bar.py` | 悬浮条和它的图标 |
| `elisubs/watch.py` | 录制：变化检测 + 录制线程 |
| `elisubs/capture.py` | 截图、框选层、涂黑 |
| `elisubs/ocr.py` | RapidOCR 封装（后台加载、预热、加锁） |
| `elisubs/lines.py` | 文字框拼行 |
| `elisubs/notion.py` | Notion 客户端 + 发送队列 |
| `elisubs/logbook.py` | 当天 md 记录、去重 |
| `docs/使用说明.txt` | 打包时放进压缩包的简短说明 |
| `elisubs/hotkey.py` / `tray.py` / `toast.py` / `autostart.py` | 热键、托盘、提示框、开机自启 |
| `elisubs/winutil.py` | DPI、窗口标题、剪贴板、单实例、截图隐身、圆角 |

测试时可用环境变量 `ELISUBS_DATA` / `ELISUBS_CONFIG` / `ELISUBS_NOTION_API` 把数据、配置、Notion 地址指到别处
（不同数据目录的实例可以同时运行）。

## 致谢

- 文字识别：[RapidOCR](https://github.com/RapidAI/RapidOCR)（PaddleOCR 模型）
- 托盘和悬浮条里的伊丽莎白出自空知英秋《银魂》，仅作个人非商业使用。
