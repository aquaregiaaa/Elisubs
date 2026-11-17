"""全局热键：单独一个线程注册 RegisterHotKey，自己跑消息循环。

暂停时真的把热键注销掉，这样 Alt+S 在 Word 等程序里恢复原来的作用。
"""
import ctypes
import logging
import threading
from ctypes import wintypes as wt

from .winutil import kernel32, user32

log = logging.getLogger("subsnap")

WM_HOTKEY = 0x0312
WM_APP = 0x8000
_PAUSE, _RESUME, _QUIT = WM_APP + 1, WM_APP + 2, WM_APP + 3
MODS = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000

user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]


def parse(spec):
    """'alt+shift+s' → (修饰键, 虚拟键码)。支持字母、数字、F1–F24。"""
    mods, key = 0, None
    for part in spec.lower().replace(" ", "").split("+"):
        if part in MODS:
            mods |= MODS[part]
        elif len(part) == 1 and part.isalnum():
            key = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            key = 0x70 + int(part[1:]) - 1
        else:
            raise ValueError(f"认不出的按键：{part}")
    if key is None:
        raise ValueError(f"热键里没有主键：{spec}")
    return mods, key


class Hotkeys(threading.Thread):
    def __init__(self, bindings, on_hotkey, paused=False):
        """bindings: {名字: 'alt+s'}；on_hotkey(名字) 在热键线程里被调用。"""
        super().__init__(name="hotkeys", daemon=True)
        self.bindings = list(bindings.items())
        self.on_hotkey = on_hotkey
        self.paused = paused
        self.failed = []  # 注册失败（被别的程序占了）的热键
        self.ready = threading.Event()
        self._tid = None

    def _register(self):
        self.failed = []
        for i, (name, spec) in enumerate(self.bindings, 1):
            mods, vk = parse(spec)
            if not user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                self.failed.append(spec)
                log.warning("热键注册失败：%s（err %s）", spec, ctypes.get_last_error())

    def _unregister(self):
        for i in range(1, len(self.bindings) + 1):
            user32.UnregisterHotKey(None, i)

    def run(self):
        self._tid = kernel32.GetCurrentThreadId()
        if not self.paused:
            self._register()
        self.ready.set()
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                idx = msg.wParam - 1
                if 0 <= idx < len(self.bindings):
                    try:
                        self.on_hotkey(self.bindings[idx][0])
                    except Exception:  # noqa: BLE001
                        log.exception("热键回调出错")
            elif msg.message == _PAUSE:
                self._unregister()
            elif msg.message == _RESUME:
                self._register()
            elif msg.message == _QUIT:
                break
        self._unregister()

    def set_paused(self, paused):
        self.paused = paused
        self.ready.wait()
        user32.PostThreadMessageW(self._tid, _PAUSE if paused else _RESUME, 0, 0)

    def stop(self):
        if self._tid:
            user32.PostThreadMessageW(self._tid, _QUIT, 0, 0)
