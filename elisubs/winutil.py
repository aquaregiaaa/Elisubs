"""Windows 小工具：DPI、窗口标题、前台窗口、显示器工作区、单实例、剪贴板。"""
import ctypes
import re
import time
from ctypes import wintypes as wt

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetForegroundWindow.restype = wt.HWND
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetParent.argtypes = [wt.HWND]
user32.GetParent.restype = wt.HWND
user32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]
user32.MonitorFromPoint.restype = wt.HANDLE
user32.OpenClipboard.argtypes = [wt.HWND]
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.SetClipboardData.restype = wt.HANDLE
user32.GetClipboardData.argtypes = [wt.UINT]
user32.GetClipboardData.restype = wt.HANDLE
kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wt.HGLOBAL
kernel32.GlobalLock.argtypes = [wt.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wt.HGLOBAL]
kernel32.GlobalFree.argtypes = [wt.HGLOBAL]
kernel32.CreateMutexW.restype = wt.HANDLE


def set_dpi_aware():
    """按物理像素工作，否则高分屏上截图坐标和框选坐标对不上。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def virtual_screen():
    """所有显示器拼起来的大画布：(左, 上, 宽, 高)。"""
    g = user32.GetSystemMetrics
    return g(76), g(77), g(78), g(79)


def foreground():
    return user32.GetForegroundWindow()


def activate(hwnd):
    if hwnd:
        user32.SetForegroundWindow(hwnd)


def window_title(hwnd):
    if not hwnd:
        return ""
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


_TAIL = re.compile(
    r"\s*[-–—]\s*(Google Chrome|Microsoft​?\s*Edge|Mozilla Firefox|Brave|Opera|Vivaldi|"
    r"VLC media player|PotPlayer|MPC-HC|mpv|Media Player|媒体播放器|电影和电视|YouTube|"
    r"个人|Personal|Work|工作|InPrivate)\s*$",
    re.I,
)
_MORE = re.compile(r"\s*(和另外\s*\d+\s*个页面|and \d+ more pages?)\s*$", re.I)


def clean_title(t):
    """把「(3) 视频名 - YouTube 和另外 2 个页面 - 个人 - Microsoft Edge」洗成「视频名」。"""
    t = (t or "").strip()
    t = re.sub(r"^\(\d+\)\s*", "", t)
    for _ in range(5):
        new = _MORE.sub("", _TAIL.sub("", t))
        if new == t:
            break
        t = new
    return t.strip()


def work_area_at(x, y):
    """(x, y) 所在显示器的工作区（去掉任务栏）。"""

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT),
                    ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]

    mon = user32.MonitorFromPoint(wt.POINT(int(x), int(y)), 2)  # 2 = 最近的显示器
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(mi)
    user32.GetMonitorInfoW(mon, ctypes.byref(mi))
    r = mi.rcWork
    return r.left, r.top, r.right, r.bottom


user32.SetWindowDisplayAffinity.argtypes = [wt.HWND, wt.DWORD]


def toplevel_hwnd(tk_toplevel):
    return user32.GetParent(tk_toplevel.winfo_id()) or tk_toplevel.winfo_id()


def make_noactivate(tk_toplevel):
    """弹出、点击都不抢焦点（不然视频播放器会失去键盘焦点），也不进任务栏。"""
    GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = -20, 0x08000000, 0x00000080
    hwnd = toplevel_hwnd(tk_toplevel)
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)


def click_through(tk_toplevel):
    """鼠标穿透：点击和悬停都落到下面的窗口（窗口要先是分层窗口，tk 设过 -alpha 就是）。"""
    GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT = -20, 0x00080000, 0x00000020
    hwnd = toplevel_hwnd(tk_toplevel)
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)


def exclude_from_capture(tk_toplevel):
    """截图时这个窗口是透明的（Win10 2004+）：提示框、悬浮条压在字幕上也不会被识别进去。"""
    user32.SetWindowDisplayAffinity(toplevel_hwnd(tk_toplevel), 0x11)  # WDA_EXCLUDEFROMCAPTURE


def round_corners(tk_toplevel):
    """Win11 圆角。"""
    try:
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wt.HWND(toplevel_hwnd(tk_toplevel)), 33, ctypes.byref(ctypes.c_int(2)), 4)
    except Exception:
        pass


def on_some_monitor(x, y):
    return bool(user32.MonitorFromPoint(wt.POINT(int(x), int(y)), 0))  # 0 = 不在任何显示器上就返回空


_mutex = None


def single_instance(name="Local\\elisubs_kr"):
    global _mutex
    _mutex = kernel32.CreateMutexW(None, False, name)
    return ctypes.get_last_error() != 183  # 183 = 已经有一个在跑


# ---------- 剪贴板 ----------
CF_UNICODETEXT = 13


def _open_clipboard():
    for _ in range(20):
        if user32.OpenClipboard(None):
            return
        time.sleep(0.05)
    raise RuntimeError("剪贴板被别的程序占着")


def set_clipboard(text):
    data = text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-16-le") + b"\0\0"
    _open_clipboard()
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        kernel32.GlobalUnlock(h)
        if not user32.SetClipboardData(CF_UNICODETEXT, h):
            kernel32.GlobalFree(h)
            raise RuntimeError("写剪贴板失败")
    finally:
        user32.CloseClipboard()


def get_clipboard():
    _open_clipboard()
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = kernel32.GlobalLock(h)
        try:
            return ctypes.wstring_at(p)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()
