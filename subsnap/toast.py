"""屏幕右上角的小提示，几秒后自己消失，不抢焦点。

放右上角而不是右下角：字幕在画面底部，提示框盖在字幕上的话，
紧接着按下一次 Alt+S 会把提示框也截进去。
"""
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk

from . import paths, winutil

PIC = paths.ASSETS / "toast.png"  # 只在「已复制」时显示

BG = "#202020"
FG = "#F2F2F2"
SUB = "#B4B2A9"
KIND = {"ok": "#5DCAA5", "warn": "#EF9F27", "err": "#F09595"}
FONT = ("Microsoft YaHei UI", 10)
OFF = (-32000, -32000)


class Toast:
    def __init__(self, root):
        self.root = root
        w = self.win = tk.Toplevel(root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.attributes("-alpha", 0.96)
        w.configure(bg=BG)
        w.geometry(f"+{OFF[0]}+{OFF[1]}")
        outer = tk.Frame(w, bg=BG, padx=12, pady=10)
        outer.pack()
        self.pic = None
        self.pic_label = tk.Label(outer, bg=BG, bd=0)
        if PIC.exists():
            side = int(root.winfo_fpixels("1i") * 0.85)  # 约 0.85 英寸见方，高分屏上自动放大
            self.pic = ImageTk.PhotoImage(Image.open(PIC).resize((side, side), Image.LANCZOS))
            self.pic_label.configure(image=self.pic)
        self.text = frame = tk.Frame(outer, bg=BG)
        frame.pack(side="left", anchor="n")
        self.head = tk.Label(frame, bg=BG, fg=KIND["ok"], font=FONT, anchor="w", justify="left")
        self.head.pack(fill="x")
        self.body = tk.Label(frame, bg=BG, fg=FG, font=FONT, anchor="w", justify="left")
        self.body.pack(fill="x", pady=(4, 0))
        w.update_idletasks()
        winutil.make_noactivate(w)
        winutil.exclude_from_capture(w)  # 提示框盖在字幕上也不会被截进去
        self._job = None
        self.wrap = int(root.winfo_fpixels("1i") * 3.5)  # 约 3.5 英寸宽后折行

    def show(self, head, body="", kind="ok", near=None, ms=2200):
        """near：在哪个显示器上显示，给一个屏幕坐标点（一般是字幕框中心）。"""
        lines = body.splitlines()
        if len(lines) > 4:
            body = "\n".join(lines[:4]) + "\n…"
        self.head.configure(text=("✓ " if kind == "ok" else "! ") + head, fg=KIND[kind])
        self.body.configure(text=body, wraplength=self.wrap, fg=FG if kind == "ok" else SUB)
        if body:
            self.body.pack(fill="x", pady=(4, 0))
        else:
            self.body.pack_forget()
        if self.pic and kind == "ok":
            self.pic_label.pack(side="left", anchor="center", padx=(0, 12), before=self.text)
        else:
            self.pic_label.pack_forget()
        self.win.update_idletasks()
        if near is None:
            vx, vy, vw, vh = 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            near = (vx + vw // 2, vy + vh // 2)
        _, top, right, _ = winutil.work_area_at(*near)
        x = right - self.win.winfo_reqwidth() - 16
        y = top + 16
        self.win.geometry(f"+{x}+{y}")
        if self._job:
            self.root.after_cancel(self._job)
        self._job = self.root.after(ms, self.hide)

    def hide(self):
        self._job = None
        self.win.geometry(f"+{OFF[0]}+{OFF[1]}")
