"""悬浮条：像输入法状态栏那样常驻，三个图标按钮。

  [伊丽莎白] [鼠标=识别一次] [取景框=换字幕区] [● 录制 / REC n] [⋮⋮]

- 伊丽莎白和右边点点都是拖动把手，位置记在 state.json。
- 点按钮不抢焦点（视频播放器的键盘焦点不丢）。
- 系统截图能截到悬浮条；本工具自己识别时会把悬浮条那块涂黑，所以压在字幕框上也不会被识别进去。
- 图标用 PIL 在 4 倍尺寸上画再缩小，高分屏上也清楚。
"""
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageTk

from . import paths, winutil

BG = "#202020"
HOVER = "#383838"
BORDER = "#3a3a3a"
FG = (232, 232, 232, 255)
RED = (226, 75, 74, 255)
BEAK = (252, 198, 89, 255)  # 伊丽莎白嘴的黄色（从 elizabeth_src.png 取色）：鼠标图标、取景框里的字幕条
GRIP = (110, 110, 110, 255)
SS = 4  # 超采样倍数
MASCOT = paths.ASSETS / "icon.png"


def _canvas(size):
    s = size * SS
    return Image.new("RGBA", (s, s), (0, 0, 0, 0)), s


def _done(im, size):
    return im.resize((size, size), Image.LANCZOS)


GLYPH = 0.54  # 三个按钮图标统一的外框边长（占按钮的比例），= 红色实心圆的直径


def icon_cursor(size):
    im, s = _canvas(size)
    # 原始箭头（0–1 坐标），按高度缩到 GLYPH 再居中
    pts = [(0.30, 0.14), (0.30, 0.80), (0.45, 0.665), (0.555, 0.895), (0.655, 0.85),
           (0.55, 0.625), (0.735, 0.625)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    k = GLYPH / (max(ys) - min(ys))
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    ImageDraw.Draw(im).polygon([((0.5 + (x - cx) * k) * s, (0.5 + (y - cy) * k) * s) for x, y in pts], fill=BEAK)
    return _done(im, size)


def icon_region(size):
    im, s = _canvas(size)
    d = ImageDraw.Draw(im)
    a, b = s * (0.5 - GLYPH / 2), s * (0.5 + GLYPH / 2)  # 框的边界
    L = s * GLYPH * 0.3                                    # 角的长度
    w = s * 0.07
    a, b = a + w / 2, b - w / 2                            # 线宽算在外框以内
    for (x, y, dx, dy) in ((a, a, 1, 1), (b, a, -1, 1), (b, b, -1, -1), (a, b, 1, -1)):
        d.line([(x + dx * L, y), (x, y), (x, y + dy * L)], fill=FG, width=round(w), joint="curve")
    # 框里两条字幕
    r = s * 0.035
    d.rounded_rectangle((s * 0.37, s * 0.475, s * 0.63, s * 0.475 + 2 * r), radius=r, fill=FG)
    d.rounded_rectangle((s * 0.415, s * 0.565, s * 0.585, s * 0.565 + 2 * r), radius=r, fill=BEAK)
    return _done(im, size)


def icon_record(size):
    im, s = _canvas(size)
    r = s * GLYPH / 2
    ImageDraw.Draw(im).ellipse((s / 2 - r, s / 2 - r, s / 2 + r, s / 2 + r), fill=RED)
    return _done(im, size)


def icon_grip(w, h):
    im = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = SS * max(1, w // 8)
    for cx in (0.35, 0.65):
        for cy in (0.3, 0.5, 0.7):
            x, y = cx * w * SS, cy * h * SS
            d.ellipse((x - r, y - r, x + r, y + r), fill=GRIP)
    return im.resize((w, h), Image.LANCZOS)


def label_rec(size, count):
    """录制中：红点 + REC + 已存几句。"""
    text = "REC" + (f" {count}" if count else "")
    font = ImageFont.truetype("arialbd.ttf", round(size * 0.42 * SS))
    l, t, r, b = font.getbbox(text)
    dot = size * 0.2 * SS
    gap = size * 0.14 * SS
    w = int(dot + gap + (r - l) + size * 0.3 * SS)
    h = size * SS
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0 = size * 0.15 * SS
    d.ellipse((x0, h / 2 - dot / 2, x0 + dot, h / 2 + dot / 2), fill=RED)
    d.text((x0 + dot + gap - l, h / 2 - (t + b) / 2), text, font=font, fill=RED)
    return im.resize((round(w / SS), size), Image.LANCZOS)


class Bar:
    def __init__(self, root, state, on_capture, on_region, on_record):
        self.root = root
        self.state = state
        self.scale = root.winfo_fpixels("1i") / 96
        self.btn = round(30 * self.scale)
        self.recording = False
        self.count = 0
        self._imgs = {}

        w = self.win = tk.Toplevel(root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=BORDER)
        inner = tk.Frame(w, bg=BG, padx=round(3 * self.scale), pady=round(3 * self.scale))
        inner.pack(padx=1, pady=1)

        # 从左到右：伊丽莎白（也能拖）、三个按钮、拖动点点
        handles = []
        if MASCOT.exists():
            size = self.btn + 2 * round(3 * self.scale)  # 和按钮（含内边距）一样高
            pic = ImageTk.PhotoImage(Image.open(MASCOT).convert("RGBA").resize((size, size), Image.LANCZOS))
            self.mascot = self._label(inner, pic, cursor="fleur")
            self.mascot.pack(side="left")
            handles.append(self.mascot)
        self.b_cap = self._button(inner, "cap", ImageTk.PhotoImage(icon_cursor(self.btn)), on_capture)
        self.b_reg = self._button(inner, "reg", ImageTk.PhotoImage(icon_region(self.btn)), on_region)
        self.b_rec = self._button(inner, "rec", ImageTk.PhotoImage(icon_record(self.btn)), on_record)
        self._rec_idle = self._imgs["rec"]
        self.grip = self._label(inner, ImageTk.PhotoImage(icon_grip(round(self.btn * 0.45), self.btn)), cursor="fleur")
        self.grip.pack(side="left", padx=(round(2 * self.scale), 0))
        handles.append(self.grip)

        for h in handles:
            h.bind("<ButtonPress-1>", self._drag_start)
            h.bind("<B1-Motion>", self._drag)
            h.bind("<ButtonRelease-1>", self._drag_end)

        # 系统截图里要能看到悬浮条（Kr 2026-11-17 要的），所以不设截图隐身；
        # 自己识别时改为把悬浮条所在的位置涂黑（见 capture.mask），rect 给录制线程读
        self.rect = None
        w.bind("<Configure>", lambda e: self._update_rect())
        w.update_idletasks()
        winutil.make_noactivate(w)
        winutil.round_corners(w)
        self._place()
        self.set_visible(not state["bar_hidden"])

    def _update_rect(self):
        w = self.win
        if w.winfo_viewable():
            x, y = w.winfo_rootx(), w.winfo_rooty()
            self.rect = (x, y, x + w.winfo_width(), y + w.winfo_height())
        else:
            self.rect = None

    # ---------- 组件 ----------
    def _label(self, parent, img, cursor=""):
        lbl = tk.Label(parent, image=img, bg=BG, bd=0, cursor=cursor)
        lbl.image = img
        return lbl

    def _button(self, parent, key, img, action):
        self._imgs[key] = img
        pad = round(3 * self.scale)
        b = tk.Label(parent, image=img, bg=BG, bd=0, padx=pad, pady=pad, cursor="hand2")
        b.pack(side="left", padx=(round(2 * self.scale), 0))
        b.bind("<Enter>", lambda e: b.configure(bg=HOVER))
        b.bind("<Leave>", lambda e: b.configure(bg=BG))
        b.bind("<ButtonRelease-1>", lambda e: action() if 0 <= e.x < b.winfo_width() and 0 <= e.y < b.winfo_height() else None)
        return b

    # ---------- 位置 ----------
    def _default_pos(self):
        _, _, right, bottom = winutil.work_area_at(0, 0)  # 主屏右下角，任务栏上方
        self.win.update_idletasks()
        m = round(12 * self.scale)
        return right - self.win.winfo_reqwidth() - m, bottom - self.win.winfo_reqheight() - m

    def _place(self):
        pos = self.state["bar_pos"]
        if not pos or not winutil.on_some_monitor(pos[0] + 5, pos[1] + 5):
            pos = self._default_pos()  # 第一次，或者那块显示器拔掉了
        self.win.geometry(f"+{pos[0]}+{pos[1]}")

    def _drag_start(self, e):
        self._off = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def _drag(self, e):
        self.win.geometry(f"+{e.x_root - self._off[0]}+{e.y_root - self._off[1]}")

    def _drag_end(self, e):
        self.state.set("bar_pos", [self.win.winfo_x(), self.win.winfo_y()])

    # ---------- 状态 ----------
    def set_visible(self, visible):
        if visible:
            self.win.deiconify()
            self.win.attributes("-topmost", True)
        else:
            self.win.withdraw()
        self.win.update_idletasks()
        self._update_rect()

    def set_recording(self, on, count=0):
        self.recording, self.count = on, count
        right = self.win.winfo_x() + self.win.winfo_width()  # 变宽变窄时右边缘不动（悬浮条一般贴在右下角）
        if on:
            img = ImageTk.PhotoImage(label_rec(self.btn, count))
            self._imgs["rec_on"] = img
            self.b_rec.configure(image=img)
        else:
            self.b_rec.configure(image=self._rec_idle)
        self.win.update_idletasks()
        if self.win.winfo_viewable():
            self.win.geometry(f"+{right - self.win.winfo_reqwidth()}+{self.win.winfo_y()}")
