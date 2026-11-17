"""开机自启：写/删 HKCU\\...\\Run\\Elisubs（只影响当前用户，不用管理员权限）。

打包版指向 Elisubs.exe；源码版指向 pythonw + Elisubs.pyw。
"""
import os
import sys
import winreg

from . import paths

# 测试时用 ELISUBS_RUN_KEY 指到别的注册表位置，别动真的开机自启
KEY = os.environ.get("ELISUBS_RUN_KEY", r"Software\Microsoft\Windows\CurrentVersion\Run")
NAME = "Elisubs"


def command():
    if paths.FROZEN:
        return f'"{sys.executable}"'
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{pyw}" "{paths.ROOT / "Elisubs.pyw"}"'


def enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
            winreg.QueryValueEx(k, NAME)
            return True
    except OSError:
        return False


def set_enabled(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(k, NAME)
            except FileNotFoundError:
                pass
