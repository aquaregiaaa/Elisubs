"""从旧名字 subsnap（1.0 / 1.1）升级到 Elisubs（1.2 起）。启动时跑一次，出错也不影响启动。

1. 开机自启：旧的注册表项叫 subsnap、指向旧的 subsnap.exe。删掉它；用户原来开着的话，换成新的 Elisubs 项。
2. 设置和记录：新程序第一次启动（自己的 data 里还没有 state.json）时，去旧版的位置找——
   旧开机自启项指向的那个文件夹、%APPDATA%\\subsnap——找到就把 config.json 和 data 复制过来（不删旧的）。
   新解压到别的文件夹的人靠这一步接上原来的设置和记录；直接覆盖旧文件夹的人本来就在同一个 data 里。
"""
import json
import logging
import os
import re
import shutil
import winreg
from pathlib import Path

from . import autostart, paths, store

log = logging.getLogger("elisubs")
OLD_NAME = "subsnap"


def _old_run_command():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, autostart.KEY) as k:
            return winreg.QueryValueEx(k, OLD_NAME)[0]
    except OSError:
        return None


def _old_homes(cmd):
    """旧版可能放数据的文件夹，按可能性排序。"""
    homes = []
    if cmd:
        quoted = re.findall(r'"([^"]+)"', cmd) or [cmd]
        homes.append(Path(quoted[-1]).parent)  # exe 本身，或 pythonw 后面的 .pyw
    appdata = os.environ.get("APPDATA")
    if appdata:
        homes.append(Path(appdata) / OLD_NAME)
    return homes


def _config_is_blank():
    if not paths.CONFIG.exists():
        return True
    try:
        data = json.loads(paths.CONFIG.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False  # 读不出来的不碰，交给 store 去提示
    return all(data.get(k, v) == v for k, v in store.CONFIG_DEFAULTS.items())


def run():
    """返回要提示给用户的话（列表）。"""
    notes = []
    cmd = _old_run_command()

    if not paths.STATE.exists():
        for home in _old_homes(cmd):
            old_data = home / "data"
            try:
                same = old_data.resolve() == paths.DATA.resolve()  # 直接覆盖在旧文件夹上：本来就是同一份
            except OSError:
                same = False
            if same or not (old_data / "state.json").exists():
                continue
            try:
                if (home / "config.json").exists() and _config_is_blank():
                    shutil.copy2(home / "config.json", paths.CONFIG)
                shutil.copytree(old_data, paths.DATA, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns(f"{OLD_NAME}.log", "*.tmp", "selftest.txt"))
                notes.append(f"已从旧版搬来设置和记录（{home}，旧文件没删）")
                log.info("迁移：从 %s 复制设置和记录", home)
            except OSError:
                log.exception("迁移旧数据失败：%s", home)
                notes.append(f"旧版的设置和记录没搬过来，可以手动把 {old_data} 复制到 {paths.DATA}")
            break

    if cmd is not None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, autostart.KEY, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, OLD_NAME)
            autostart.set_enabled(True)
            notes.append("开机自启已换成 Elisubs")
            log.info("迁移：开机自启 %s → %s", OLD_NAME, autostart.NAME)
        except OSError:
            log.exception("迁移开机自启失败")
    return notes
