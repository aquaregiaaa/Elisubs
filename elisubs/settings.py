"""设置窗口：快捷键、记录保存位置、Notion 令牌和总页面、开机自启、版本和检查更新。

保存时逐项检查，有问题就在窗口里标红，不保存；全部没问题才一次写进 config.json
（其他字段原样保留；原文件格式坏了会先另存一份）。
"""
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from . import __version__, autostart, hotkey, notion, paths, store

BG = "#202020"
FIELD = "#2c2c2c"
FG = "#F2F2F2"
SUB = "#B4B2A9"
ERR = "#F09595"
ACCENT = "#185FA5"
FONT = ("Microsoft YaHei UI", 10)


class Settings:
    def __init__(self, root, on_saved, on_check_update=None, get_update=None):
        self.root = root
        self.on_saved = on_saved  # on_saved(旧配置, 新配置)
        self.on_check_update = on_check_update  # 点「检查更新」/「下载新版本」
        self.get_update = get_update or (lambda: None)  # 有新版本时返回版本号
        self.win = None

    def open(self):
        if self.win is not None and self.win.winfo_exists():
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            return
        cfg = store.load_config()
        w = self.win = tk.Toplevel(self.root)
        w.title("Elisubs 设置")
        w.configure(bg=BG)
        w.attributes("-topmost", True)
        w.resizable(False, False)
        w.protocol("WM_DELETE_WINDOW", self.close)
        pad = 16
        body = tk.Frame(w, bg=BG, padx=pad, pady=pad)
        body.pack(fill="both")

        self.err_top = tk.Label(body, bg=BG, fg=ERR, font=FONT, justify="left", anchor="w", wraplength=460)
        if store.config_error:
            self.err_top.configure(text=f"config.json 读不出来：{store.config_error}。现在显示的是默认值，保存时会把旧文件另存一份。")
            self.err_top.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.vars = {}
        row = 1
        row = self._section(body, row, "快捷键")
        row = self._field(body, row, "hotkey_capture", "单次识别", cfg["hotkey_capture"])
        row = self._field(body, row, "hotkey_reselect", "重新框选", cfg["hotkey_reselect"])
        row = self._field(body, row, "hotkey_record", "连续识别", cfg["hotkey_record"])
        row = self._section(body, row, "识别记录")
        current_dir = cfg["log_dir"].strip() or str(paths.LOGS)
        row = self._field(body, row, "log_dir", "保存位置", current_dir, button=("选择…", self._pick_dir))
        row = self._section(body, row, "Notion")
        row = self._field(body, row, "notion_token", "令牌", cfg["notion_token"], secret=True)
        row = self._field(body, row, "notion_parent_page", "总页面链接", cfg["notion_parent_page"])

        row = self._section(body, row, "程序")
        tk.Label(body, text="开机自启", bg=BG, fg=FG, font=FONT, anchor="w", width=9).grid(row=row, column=0, sticky="w", pady=3)
        self.autostart_var = tk.BooleanVar(value=autostart.enabled())
        tk.Checkbutton(body, variable=self.autostart_var, bg=BG, activebackground=BG, fg=FG, selectcolor=FIELD,
                       bd=0, highlightthickness=0, cursor="hand2").grid(row=row, column=1, sticky="w", pady=3)
        row += 1
        tk.Label(body, text="版本", bg=BG, fg=FG, font=FONT, anchor="w", width=9).grid(row=row, column=0, sticky="w", pady=3)
        self.ver_label = tk.Label(body, bg=BG, fg=FG, font=FONT, anchor="w")
        self.ver_label.grid(row=row, column=1, sticky="w", pady=3)
        self.update_btn = self._button(body, "检查更新", lambda: self.on_check_update and self.on_check_update())
        self.update_btn.grid(row=row, column=2, sticky="w", padx=(8, 0))
        row += 1
        self.refresh_update()

        self.err = tk.Label(body, bg=BG, fg=ERR, font=FONT, justify="left", anchor="w", wraplength=460)
        self.err.grid(row=row, column=0, columnspan=3, sticky="w", pady=(10, 0))
        row += 1
        btns = tk.Frame(body, bg=BG)
        btns.grid(row=row, column=0, columnspan=3, sticky="e", pady=(12, 0))
        self._button(btns, "取消", self.close).pack(side="left", padx=(0, 8))
        self._button(btns, "保存", self._save, primary=True).pack(side="left")

        w.bind("<Return>", lambda e: self._save())
        w.bind("<Escape>", lambda e: self.close())
        w.update_idletasks()
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        w.geometry(f"+{(sw - w.winfo_reqwidth()) // 2}+{(sh - w.winfo_reqheight()) // 3}")
        w.focus_force()

    # ---------- 组件 ----------
    def _section(self, parent, row, text):
        tk.Label(parent, text=text, bg=BG, fg=SUB, font=FONT, anchor="w").grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(10 if row > 1 else 0, 4))
        return row + 1

    def _field(self, parent, row, key, label, value, secret=False, button=None):
        tk.Label(parent, text=label, bg=BG, fg=FG, font=FONT, anchor="w", width=9).grid(row=row, column=0, sticky="w", pady=3)
        var = tk.StringVar(value=value)
        self.vars[key] = var
        e = tk.Entry(parent, textvariable=var, width=40, bg=FIELD, fg=FG, insertbackground=FG, relief="flat",
                     font=FONT, highlightthickness=1, highlightbackground="#3a3a3a", highlightcolor=SUB,
                     show="•" if secret else "")
        e.grid(row=row, column=1, sticky="we", pady=3, ipady=3)
        if secret:
            def toggle():
                e.configure(show="" if e.cget("show") else "•")
                b.configure(text="隐藏" if not e.cget("show") else "显示")
            b = self._button(parent, "显示", toggle)
            b.grid(row=row, column=2, sticky="w", padx=(8, 0))
        elif button:
            self._button(parent, button[0], button[1]).grid(row=row, column=2, sticky="w", padx=(8, 0))
        return row + 1

    def _button(self, parent, text, cmd, primary=False):
        bg = ACCENT if primary else "#383838"
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=FG, activebackground=bg, activeforeground=FG,
                         relief="flat", font=FONT, padx=14, pady=3, cursor="hand2", bd=0)

    def _pick_dir(self):
        chosen = filedialog.askdirectory(parent=self.win, initialdir=self.vars["log_dir"].get(),
                                         title="识别记录保存到哪个文件夹", mustexist=False)
        if chosen:
            self.vars["log_dir"].set(os.path.normpath(chosen))

    def refresh_update(self):
        """查到新版本后按钮变成「下载 x」（窗口没开就什么都不做）。"""
        if self.win is None or not self.win.winfo_exists():
            return
        ver = self.get_update()
        self.ver_label.configure(text=f"{__version__}（有新版本 {ver}）" if ver else __version__)
        if ver:
            self.update_btn.configure(text=f"下载 {ver}", bg=ACCENT, activebackground=ACCENT)

    def close(self):
        if self.win is not None:
            self.win.destroy()
            self.win = None

    # ---------- 保存 ----------
    def _validate(self, v):
        keys = (("hotkey_capture", "单次识别"), ("hotkey_reselect", "重新框选"), ("hotkey_record", "连续识别"))
        parsed = {}
        for key, name in keys:
            try:
                parsed[key] = hotkey.parse(v[key])
            except ValueError as e:
                return f"{name}的快捷键不对：{e}（写法例子：alt+s、ctrl+shift+f2）"
        if len(set(parsed.values())) < len(parsed):
            return "三个快捷键不能有一样的"
        d = Path(os.path.expandvars(v["log_dir"])) if v["log_dir"] else paths.LOGS
        try:
            d.mkdir(parents=True, exist_ok=True)
            if not os.access(d, os.W_OK):
                return f"保存位置没有写入权限：{d}"
        except OSError as e:
            return f"保存位置用不了：{d}（{e.strerror or e}）"
        token, page = v["notion_token"], v["notion_parent_page"]
        if bool(token) != bool(page):
            return "Notion 的令牌和总页面链接要一起填（不用 Notion 就都留空）"
        if page:
            try:
                notion.page_id(page)
            except notion.NotionError:
                return "总页面链接认不出来：请从 Notion 页面右上角「分享 → 复制链接」粘贴过来"
        return None

    def _save(self):
        v = {k: var.get().strip() for k, var in self.vars.items()}
        problem = self._validate(v)
        if problem:
            self.err.configure(text=problem)
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
