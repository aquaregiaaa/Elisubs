"""所有文件位置集中在这里。测试时用环境变量指到临时目录。

打包成 exe（PyInstaller）后：
- 配置、记录放在 exe 旁边（ROOT = exe 所在文件夹），用户看得到、改得了；
- 图片等资源打在包里（ASSETS = 解包目录下的 assets）。
"""
import os
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
ASSETS = (Path(getattr(sys, "_MEIPASS", ROOT)) if FROZEN else ROOT) / "assets"
CONFIG = Path(os.environ.get("SUBSNAP_CONFIG", ROOT / "config.json"))
DATA = Path(os.environ.get("SUBSNAP_DATA", ROOT / "data"))
LOGS = DATA / "logs"          # 每天的识别记录 md
STATE = DATA / "state.json"   # 程序自己维护：字幕框、Notion 开关、目标页面……
PENDING = DATA / "pending.jsonl"  # 还没写进 Notion 的条目
APPLOG = DATA / "subsnap.log"     # 运行日志（出错看这里）

for d in (DATA, LOGS):
    d.mkdir(parents=True, exist_ok=True)
