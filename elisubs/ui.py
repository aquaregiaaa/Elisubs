"""设置窗口用的控件：圆角卡片、输入框、键帽、开关、按钮。

主题色是伊丽莎白黄（悬浮条鼠标图标同一个黄）；黄底上用深色字。
圆角都是 PIL 4 倍超采样画好再缩小的图，边缘不毛；尺寸都乘 scale，高分屏上不变小。
"""
import tkinter as tk
import tkinter.font as tkfont

from PIL import Image, ImageDraw, ImageTk

BG = "#1B1B1B"
CARD = "#242424"
CARD_LINE = "#2F2F2F"
FIELD = "#2D2D2D"
FIELD_LINE = "#3A3A3A"
KEY = "#3A3A3A"
KEY_LINE = "#4A4A4A"
KEY_HOVER = "#474747"
FG = "#F2F2F2"
SUB = "#A8A69E"
DIM = "#6F6D67"
YELLOW = "#FCC659"
YELLOW_HOVER = "#FFD57E"
ON_YELLOW = "#1A1A1A"
ERR = "#F09595"
FONT = ("Microsoft YaHei UI", 10)
FONT_B = ("Microsoft YaHei UI", 10, "bold")
FONT_KEY = ("Segoe UI Semibold", 9)
SS = 4

_cache = {}


def rounded(w, h, r, fill, line=None):
    """w×h 的圆角矩形图（带 1 像素描边可选）。同样参数只画一次。"""
    key = (w, h, r, fill, line)
    if key not in _cache:
        im = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        ImageDraw.Draw(im).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), r * SS, fill=fill,
                                             outline=line, width=SS if line else 0)
        _cache[key] = ImageTk.PhotoImage(im.resize((w, h), Image.LANCZOS))
    return _cache[key]


class Scale:
    def __init__(self, root):
        self.k = root.winfo_fpixels("1i") / 96

    def __call__(self, v):
        return round(v * self.k)


class Card(tk.Frame):
    """圆角卡片：背景图跟着卡片大小重画；内容放 .body，四周让出几像素给圆角。标题前一条黄竖线。"""

    def __init__(self, parent, title, px):
        super().__init__(parent, bg=BG)
        self.px = px
        self._bg = tk.Label(self, bg=BG, bd=0)
        self._bg.place(x=0, y=0, relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=CARD, padx=px(12), pady=px(8))
        self.body.pack(padx=px(6), pady=px(6), fill="x")
        self.body.lift()
        head = tk.Frame(self.body, bg=CARD)
        head.pack(fill="x", pady=(0, px(8)))
        tk.Frame(head, bg=YELLOW, width=px(3), height=px(14)).pack(side="left", padx=(0, px(8)))
        tk.Label(head, text=title, bg=CARD, fg=FG, font=FONT_B).pack(side="left")
        self.bind("<Configure>", lambda e: self._bg.configure(image=rounded(e.width, e.height, self.px(10), CARD, CARD_LINE)))

    def row(self, label, label_w):
        """一行：左边固定宽度的标签，返回右边放控件的 Frame。"""
        r = tk.Frame(self.body, bg=CARD)
        r.pack(fill="x", pady=self.px(5))
        holder = tk.Frame(r, bg=CARD, width=label_w, height=self.px(32))
        holder.pack_propagate(False)
        holder.pack(side="left")
        tk.Label(holder, text=label, bg=CARD, fg=SUB, font=FONT, anchor="w").pack(side="left")
        return r


class Field(tk.Canvas):
    """圆角输入框。选中时边框变黄，出错时变红；secret=True 时右边有眼睛图标切换明文。"""

    def __init__(self, parent, var, width, px, secret=False):
        self.h = px(32)
        super().__init__(parent, width=width, height=self.h, bg=CARD, highlightthickness=0, bd=0)
        self.w, self.px = width, px
        self.focused = self.error = False
        self._bg = self.create_image(0, 0, anchor="nw")
        self.entry = tk.Entry(self, textvariable=var, bg=FIELD, fg=FG, insertbackground=YELLOW, relief="flat",
                              font=FONT, bd=0, highlightthickness=0, show="•" if secret else "")
        eye = px(26) if secret else 0
        self.create_window(px(10), self.h // 2, anchor="w", window=self.entry, width=width - px(20) - eye)
        if secret:
            self._eye = self.create_text(width - px(18), self.h // 2, text="👁", fill=SUB, font=("Segoe UI Emoji", 10))
            self.tag_bind(self._eye, "<Button-1>", lambda e: self._toggle_secret())
            self.tag_bind(self._eye, "<Enter>", lambda e: self.configure(cursor="hand2"))
            self.tag_bind(self._eye, "<Leave>", lambda e: self.configure(cursor=""))
        self.entry.bind("<FocusIn>", lambda e: self._set(focused=True))
        self.entry.bind("<FocusOut>", lambda e: self._set(focused=False))
        self.entry.bind("<Key>", lambda e: self.error and self._set(error=False), add="+")  # 一改就去掉红框
        self._paint()

    def _toggle_secret(self):
        shown = not self.entry.cget("show")
        self.entry.configure(show="•" if shown else "")
        self.itemconfigure(self._eye, fill=SUB if shown else FG)

    def _set(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        self._paint()

    def set_error(self, on):
        self._set(error=on)

    def _paint(self):
        line = ERR if self.error else (YELLOW if self.focused else FIELD_LINE)
        self.itemconfigure(self._bg, image=rounded(self.w, self.h, self.px(6), FIELD, line))


def key_names(spec):
    """'ctrl+shift+f2' → ['Ctrl', 'Shift', 'F2']。"""
    names = {"alt": "Alt", "ctrl": "Ctrl", "control": "Ctrl", "shift": "Shift", "win": "Win"}
    return [names.get(p, p.upper()) for p in spec.lower().replace(" ", "").split("+") if p]


class Keycaps(tk.Canvas):
    """快捷键显示成键帽 [Alt] + [S]，没有外框（Kr 2026-11-19 定的）。点一下进入录制：黄框里写「按下新的组合键…」。"""

    def __init__(self, parent, var, px, on_click):
        self.h = px(32)
        super().__init__(parent, height=self.h, bg=CARD, highlightthickness=0, bd=0, cursor="hand2")
        self.var, self.px = var, px
        self.recording = self.error = False
        self.hover = False
        self.bind("<Button-1>", lambda e: on_click())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        var.trace_add("write", lambda *a: self.paint())
        self.paint()

    def _set_hover(self, on):
        self.hover = on
        self.paint()

    def set_recording(self, on):
        self.recording = on
        self.paint()

    def set_error(self, on):
        self.error = on
        self.paint()

    def paint(self):
        px, h = self.px, self.h
        self.delete("all")
        f = tkfont.Font(font=FONT)
        if self.recording:
            text = "按下新的组合键…"
            w = f.measure(text) + px(24)
            self.create_image(0, 0, anchor="nw", image=rounded(w, h, px(6), FIELD, YELLOW))
            self.create_text(px(12), h // 2, anchor="w", text=text, fill=YELLOW, font=FONT)
            self.configure(width=w)
            return
        fk = tkfont.Font(font=FONT_KEY)
        kh = px(24)
        top = (h - kh) // 2
        fill = KEY_HOVER if self.hover else KEY
        line = ERR if self.error else KEY_LINE
        x = 0
        for i, k in enumerate(key_names(self.var.get())):
            if i:
                self.create_text(x + px(7), h // 2, text="+", fill=DIM, font=FONT_KEY)
                x += px(14)
            kw = max(px(30), fk.measure(k) + px(18))
            self.create_image(x, top, anchor="nw", image=rounded(kw, kh, px(5), fill, line))
            self.create_text(x + kw // 2, h // 2, text=k, fill=FG, font=FONT_KEY)
            x += kw
        self.configure(width=max(x, 1))


class Switch(tk.Canvas):
    """开关：开 = 黄底深色圆点，关 = 灰底浅色圆点。"""

    def __init__(self, parent, var, px):
        self.w, self.h = px(40), px(22)
        super().__init__(parent, width=self.w, height=self.h, bg=CARD, highlightthickness=0, bd=0, cursor="hand2")
        self.var, self.px = var, px
        self.bind("<Button-1>", lambda e: var.set(not var.get()))
        var.trace_add("write", lambda *a: self.paint())
        self.paint()

    def paint(self):
        px, on = self.px, self.var.get()
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=rounded(self.w, self.h, self.h // 2, YELLOW if on else KEY))
        k = self.h - px(6)
        x = self.w - k - px(3) if on else px(3)
        self.create_image(x, px(3), anchor="nw", image=rounded(k, k, k // 2, ON_YELLOW if on else "#BDBBB4"))


class Button(tk.Canvas):
    """圆角按钮。kind：primary 黄底深字 / secondary 灰底 / ghost 无底色（取消）。"""
    STYLES = {
        "primary": (YELLOW, YELLOW_HOVER, ON_YELLOW, None, FONT_B),
        "secondary": ("#333333", "#3D3D3D", FG, "#444444", FONT),
        "ghost": (None, "#2A2A2A", SUB, None, FONT),
    }

    def __init__(self, parent, text, command, px, kind="secondary", bg=CARD):
        self.h = px(32)
        super().__init__(parent, height=self.h, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.px, self.parent_bg, self.command = px, bg, command
        self.hover = False
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", lambda e: command() if 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height() else None)
        self.set(text, kind)

    def _set_hover(self, on):
        self.hover = on
        self._paint()

    def set(self, text, kind=None):
        self.text = text
        self.kind = kind or self.kind
        self._paint()

    def _paint(self):
        fill, hover, fg, line, font = self.STYLES[self.kind]
        w = tkfont.Font(font=font).measure(self.text) + self.px(32)
        self.configure(width=w)
        self.delete("all")
        bgfill = hover if self.hover else (fill or self.parent_bg)
        self.create_image(0, 0, anchor="nw", image=rounded(w, self.h, self.px(6), bgfill, line))
        self.create_text(w // 2, self.h // 2, text=self.text, fill=FG if (self.kind == "ghost" and self.hover) else fg, font=font)
