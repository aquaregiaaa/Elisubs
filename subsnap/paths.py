"""所有文件位置集中在这里。测试时用环境变量指到临时目录。

打包成 exe（PyInstaller）后：
- 配置、记录默认放在 exe 旁边（ROOT = exe 所在文件夹），用户看得到、改得了；
  exe 放在没有写权限的地方（比如 C:\\Program Files）时，改放 %APPDATA%\\subsnap；
- 图片等资源打在包里（ASSETS = 解包目录下的 assets）。
"""
import os
import sys
import uuid
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
ASSETS = (Path(getattr(sys, "_MEIPASS", ROOT)) if FROZEN else ROOT) / "assets"


def _writable(folder):
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / f".write_test_{uuid.uuid4().hex}"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


HOME = ROOT
if not _writable(ROOT / "data"):
    HOME = Path(os.environ.get("APPDATA", Path.home())) / "subsnap"

CONFIG = Path(os.environ.get("SUBSNAP_CONFIG", HOME / "config.json"))
DATA = Path(os.environ.get("SUBSNAP_DATA", HOME / "data"))
LOGS = DATA / "logs"          # 每天的识别记录 md（默认位置；config 的 log_dir 可以改）
STATE = DATA / "state.json"   # 程序自己维护：字幕框、Notion 开关、目标页面……
PENDING = DATA / "pending.jsonl"      # 还没写进 Notion 的条目
RECORDING = DATA / "recording.jsonl"  # 录制中暂存的句子（程序中途崩了下次启动补存）
APPLOG = DATA / "subsnap.log"         # 运行日志（出错看这里）

for d in (DATA, LOGS):
    d.mkdir(parents=True, exist_ok=True)
