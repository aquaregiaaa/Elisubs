"""设置窗口：快捷键、记录保存位置、Notion 令牌和总页面、开机自启、版本和检查更新。

样式（Kr 2026-11-19 定的）：圆角卡片分节、主题色伊丽莎白黄、标签列固定宽、控件右边缘对齐；
快捷键显示成键帽，点一下按新组合键就录进去（录的时候暂停全局热键，不然 Alt+S 会直接去识别）。
保存时逐项检查，有问题就把那一项标红、底下写原因，不保存；全部没问题才一次写进 config.json
（其他字段原样保留；原文件格式坏了会先另存一份）。
"""
import ctypes
import os
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from . import __version__, autostart, hotkey, notion, paths, store, ui

HOTKEYS = (("hotkey_capture", "单次识别"), ("hotkey_reselect", "重新框选"), ("hotkey_record", "连续识别"))
MODIFIER_KEYS = {"Alt_L", "Alt_R", "Control_L", "Control_R", "Shift_L", "Shift_R", "Win_L", "Win_R",
                 "Meta_L", "Meta_R", "Super_L", "Super_R", "Caps_Lock", "Num_Lock"}
VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": (0x5B, 0x5C)}


def _down(vk):
    vks = vk if isinstance(vk, tuple) else (vk,)
    return any(ctypes.windll.user32.GetKeyState(v) & 0x8000 for v in vks)


class Settings:
    def __init__(self, root, on_saved, on_check_update=None, get_update=None, on_capture_keys=None):
        self.root = root
        self.on_saved = on_saved  # on_saved(旧配置, 新配置)
        self.on_check_update = on_check_update  # 点「检查更新」/「下载新版本」
        self.get_update = get_update or (lambda: None)  # 有新版本时返回版本号
        self.on_capture_keys = on_capture_keys or (lambda on: None)  # 录快捷键开始/结束（暂停/恢复全局热键）
        self.win = None
        self._capturing = None

    def open(self):
        if self.win is not None and self.win.winfo_exists():
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            return
        cfg = store.load_config()
        px = self.px = ui.Scale(self.root)
        label_w, cw = px(96), px(388)  # 标签列宽、控件区宽（所有控件右边缘对齐到这里）
        w = self.win = tk.Toplevel(self.root)
        w.title("Elisubs 设置")
        w.configure(bg=ui.BG)
        w.attributes("-topmost", True)
        w.resizable(False, False)
        w.protocol("WM_DELETE_WINDOW", self.close)
        body = tk.Frame(w, bg=ui.BG, padx=px(20), pady=px(20))
        body.pack(fill="both")
        wrap = label_w + cw + px(36)

        if store.config_error:
            tk.Label(body, bg=ui.BG, fg=ui.ERR, font=ui.FONT, justify="left", anchor="w", wraplength=wrap,
                     text=f"config.json 读不出来：{store.config_error}。现在显示的是默认值，保存时会把旧文件另存一份。"
                     ).pack(fill="x", pady=(0, px(12)))

        self.vars, self.widgets = {}, {}

        card = ui.Card(body, "快捷键", px)
        for key, label in HOTKEYS:
            var = self.vars[key] = tk.StringVar(value=cfg[key])
            kc = self.widgets[key] = ui.Keycaps(card.row(label, label_w), var, px, lambda k=key: self._start_capture(k))
            kc.pack(side="left")
            kc.bind("<FocusOut>", lambda e, k=key: self._capturing == k and self._stop_capture())
        card.pack(fill="x", pady=(0, px(12)))

        card = ui.Card(body, "识别记录", px)
        r = card.row("保存位置", label_w)
        pick = ui.Button(r, "选择…", self._pick_dir, px)
        var = self.vars["log_dir"] = tk.StringVar(value=cfg["log_dir"].strip() or str(paths.LOGS))
        self.widgets["log_dir"] = ui.Field(r, var, cw - px(8) - int(pick.cget("width")), px)
        self.widgets["log_dir"].pack(side="left")
        pick.pack(side="left", padx=(px(8), 0))
        card.pack(fill="x", pady=(0, px(12)))

        card = ui.Card(body, "Notion", px)
        for key, label, secret in (("notion_token", "令牌", True), ("notion_parent_page", "总页面链接", False)):
            var = self.vars[key] = tk.StringVar(value=cfg[key])
            self.widgets[key] = ui.Field(card.row(label, label_w), var, cw, px, secret=secret)
            self.widgets[key].pack(side="left")
        card.pack(fill="x", pady=(0, px(12)))

        card = ui.Card(body, "程序", px)
        self.autostart_var = tk.BooleanVar(value=autostart.enabled())
        ui.Switch(card.row("开机自启", label_w), self.autostart_var, px).pack(side="left")
        r = card.row("版本", label_w)
        self.ver_label = tk.Label(r, bg=ui.CARD, fg=ui.FG, font=ui.FONT, anchor="w")
        self.ver_label.pack(side="left")
        self.update_btn = ui.Button(r, "检查更新", lambda: self.on_check_update and self.on_check_update(), px)
        self.update_btn.pack(side="right")
        card.pack(fill="x")
        self.refresh_update()

        foot = tk.Frame(body, bg=ui.BG)
        foot.pack(fill="x", pady=(px(16), 0))
        self.err = tk.Label(foot, bg=ui.BG, fg=ui.ERR, font=ui.FONT, justify="left", anchor="w", wraplength=wrap)
        self.err.pack(fill="x")
        btns = tk.Frame(foot, bg=ui.BG)
        btns.pack(anchor="e")
        ui.Button(btns, "取消", self.close, px, kind="ghost", bg=ui.BG).pack(side="left", padx=(0, px(8)))
        ui.Button(btns, "保存", self._save, px, kind="primary", bg=ui.BG).pack(side="left")

        w.bind("<KeyPress>", self._on_key)
        w.update_idletasks()
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        w.geometry(f"+{(sw - w.winfo_reqwidth()) // 2}+{(sh - w.winfo_reqheight()) // 3}")
        w.focus_force()

    # ---------- 录快捷键 ----------
    def _start_capture(self, key):
        if self._capturing:
            self._stop_capture()
        self._capturing = key
        self.err.configure(text="")
        kc = self.widgets[key]
        kc.set_error(False)
        kc.set_recording(True)
        kc.focus_set()  # 按键落到键帽上，不会打进输入框
        self.on_capture_keys(True)

    def _stop_capture(self):
        key, self._capturing = self._capturing, None
        if key and self.win is not None:
            self.widgets[key].set_recording(False)
        self.on_capture_keys(False)

    def _on_key(self, e):
        if not self._capturing:
            if e.keysym == "Escape":
                self.close()
            elif e.keysym == "Return":
                self._save()
            return None
        if e.keysym == "Escape":
            self._stop_capture()
            return "break"
        if e.keysym in MODIFIER_KEYS:
            return "break"  # 只按了修饰键，等主键
        k = e.keysym.lower()
        fkey = re.fullmatch(r"f([1-9]|1\d|2[0-4])", k)
        if not (len(k) == 1 and k.isascii() and k.isalnum()) and not fkey:
            self.err.configure(text="只能用字母、数字或 F1–F24 做主键")
            return "break"
        mods = [m for m in ("ctrl", "alt", "shift", "win") if _down(VK[m])]
        if not mods and not fkey:
            self.err.configure(text="字母和数字要配合 Alt、Ctrl、Shift 或 Win 一起按")
            return "break"
        self.vars[self._capturing].set("+".join(mods + [k]))
        self.err.configure(text="")
        self._stop_capture()
        return "break"

    # ---------- 其他 ----------
    def _pick_dir(self):
        chosen = filedialog.askdirectory(parent=self.win, initialdir=self.vars["log_dir"].get(),
                                         title="识别记录保存到哪个文件夹", mustexist=False)
        if chosen:
            self.vars["log_dir"].set(os.path.normpath(chosen))

    def refresh_update(self):
        """查到新版本后按钮变成黄色的「下载 x」（窗口没开就什么都不做）。"""
        if self.win is None or not self.win.winfo_exists():
            return
        ver = self.get_update()
        self.ver_label.configure(text=f"{__version__}（有新版本 {ver}）" if ver else __version__,
                                 fg=ui.SUB if ver else ui.FG)
        if ver:
            self.update_btn.set(f"下载 {ver}", "primary")

    def close(self):
        if self._capturing:
            self._stop_capture()
        if self.win is not None:
            self.win.destroy()
            self.win = None

    # ---------- 保存 ----------
    def _validate(self, v):
        """有问题返回 (出问题的那一项, 原因)，没问题返回 None。"""
        parsed = {}
        for key, name in HOTKEYS:
            try:
                parsed[key] = hotkey.parse(v[key])
            except ValueError as e:
                return key, f"{name}的快捷键不对：{e}"
        seen = {}
        for key, name in HOTKEYS:
            if parsed[key] in seen:
                return key, f"「{name}」和「{seen[parsed[key]]}」的快捷键一样了"
            seen[parsed[key]] = name
        d = Path(os.path.expandvars(v["log_dir"])) if v["log_dir"] else paths.LOGS
        try:
            d.mkdir(parents=True, exist_ok=True)
            if not os.access(d, os.W_OK):
                return "log_dir", f"保存位置没有写入权限：{d}"
        except OSError as e:
            return "log_dir", f"保存位置用不了：{d}（{e.strerror or e}）"
        token, page = v["notion_token"], v["notion_parent_page"]
        if bool(token) != bool(page):
            return ("notion_parent_page" if token else "notion_token"), \
                "Notion 的令牌和总页面链接要一起填（不用 Notion 就都留空）"
        if page:
            try:
                notion.page_id(page)
            except notion.NotionError:
                return "notion_parent_page", "总页面链接认不出来：请从 Notion 页面右上角「分享 → 复制链接」粘贴过来"
        return None

    def _save(self):
        if self._capturing:
            return
        for wdg in self.widgets.values():
            wdg.set_error(False)
        v = {k: var.get().strip() for k, var in self.vars.items()}
        problem = self._validate(v)
        if problem:
            key, msg = problem
            self.widgets[key].set_error(True)
            self.err.configure(text=msg)
            return
        if os.path.normcase(os.path.normpath(v["log_dir"] or str(paths.LOGS))) == os.path.normcase(str(paths.LOGS)):
            v["log_dir"] = ""  # 选的就是默认位置
        want = self.autostart_var.get()
        if want != autostart.enabled():
            try:
                autostart.set_enabled(want)
            except OSError as e:
                self.err.configure(text=f"开机自启没设置成功：{e}")
                return
        old = store.load_config()
        store.update_config(None, **{k: v[k].lower() if k.startswith("hotkey") else v[k] for k in v})
        self.close()
        self.on_saved(old, store.load_config())
