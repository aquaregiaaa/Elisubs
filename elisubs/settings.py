"""设置窗口：快捷键、记录保存位置、Notion 令牌和总页面。

保存时逐项检查，有问题就在窗口里标红，不保存；全部没问题才一次写进 config.json
（其他字段原样保留；原文件格式坏了会先另存一份）。
"""
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from . import hotkey, notion, paths, store

BG = "#202020"
FIELD = "#2c2c2c"
FG = "#F2F2F2"
SUB = "#B4B2A9"
ERR = "#F09595"
ACCENT = "#185FA5"
FONT = ("Microsoft YaHei UI", 10)


class Settings:
    def __init__(self, root, on_saved):
        self.root = root
        self.on_saved = on_saved  # on_saved(旧配置, 新配置)
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
        row = self._field(body, row, "hotkey_capture", "识别一次", cfg["hotkey_capture"])
        row = self._field(body, row, "hotkey_reselect", "换字幕区", cfg["hotkey_reselect"])
        row = self._section(body, row, "识别记录")
        current_dir = cfg["log_dir"].strip() or str(paths.LOGS)
        row = self._field(body, row, "log_dir", "保存位置", current_dir, button=("选择…", self._pick_dir))
        row = self._section(body, row, "Notion")
        row = self._field(body, row, "notion_token", "令牌", cfg["notion_token"], secret=True)
        row = self._field(body, row, "notion_parent_page", "总页面链接", cfg["notion_parent_page"])

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

    def close(self):
        if self.win is not None:
            self.win.destroy()
            self.win = None

    # ---------- 保存 ----------
    def _validate(self, v):
        for key, name in (("hotkey_capture", "识别一次"), ("hotkey_reselect", "换字幕区")):
            try:
                hotkey.parse(v[key])
            except ValueError as e:
                return f"{name}的快捷键不对：{e}（写法例子：alt+s、ctrl+shift+f2）"
        if hotkey.parse(v["hotkey_capture"]) == hotkey.parse(v["hotkey_reselect"]):
            return "两个快捷键不能一样"
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
        old = store.load_config()
        store.update_config(None, **{k: v[k].lower() if k.startswith("hotkey") else v[k] for k in v})
        self.close()
        self.on_saved(old, store.load_config())
