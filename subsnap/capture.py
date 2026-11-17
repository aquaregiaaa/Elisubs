"""截图和框选层。

框选：先截整个屏幕，盖一层变暗的截图，拖出来的框里恢复原亮度。
Esc / 右键 / 框太小 = 取消。
"""
import tkinter as tk

from PIL import ImageDraw, ImageEnhance, ImageGrab, ImageTk

from . import winutil

MIN_SIZE = 8


def grab_all():
    """整个虚拟屏幕截图 + 它左上角的绝对坐标。"""
    vx, vy, _, _ = winutil.virtual_screen()
    return ImageGrab.grab(all_screens=True), (vx, vy)


def mask(img, origin, rects):
    """把 rects（屏幕绝对坐标）落在图里的部分涂黑。用来挡掉压在字幕框上的悬浮条。"""
    ox, oy = origin
    d = None
    for r in rects:
        if not r:
            continue
        l, t = max(r[0] - ox, 0), max(r[1] - oy, 0)
        rr, b = min(r[2] - ox, img.width), min(r[3] - oy, img.height)
        if rr > l and b > t:
            if d is None:
                img = img.copy()
                d = ImageDraw.Draw(img)
            d.rectangle((l, t, rr - 1, b - 1), fill="black")
    return img


def grab_region(region, exclude=()):
    img = ImageGrab.grab(bbox=tuple(region), all_screens=True)
    return mask(img, region[:2], exclude)


class Selector:
    def __init__(self, root):
        self.root = root
        self.win = None

    @property
    def active(self):
        return self.win is not None

    def select(self, shot, origin, on_done):
        """on_done(region 或 None)，region 是屏幕绝对坐标 [l, t, r, b]。"""
        vx, vy = origin
        w, h = shot.size
        self._shot, self._origin, self._on_done = shot, origin, on_done
        self._start = None
        self._bright_img = None

        win = self.win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"{w}x{h}+{vx}+{vy}")
        win.configure(cursor="crosshair")

        self._dark = ImageTk.PhotoImage(ImageEnhance.Brightness(shot).enhance(0.45))
        c = self.canvas = tk.Canvas(win, width=w, height=h, highlightthickness=0, bd=0)
        c.pack()
        c.create_image(0, 0, anchor="nw", image=self._dark)
        self._bright = c.create_image(0, 0, anchor="nw")
        self._rect = c.create_rectangle(0, 0, 0, 0, outline="#85B7EB", width=2, state="hidden")

        c.bind("<ButtonPress-1>", self._press)
        c.bind("<B1-Motion>", self._drag)
        c.bind("<ButtonRelease-1>", self._release)
        c.bind("<ButtonPress-3>", lambda e: self._finish(None))
        win.bind("<Escape>", lambda e: self._finish(None))
        win.update_idletasks()
        win.deiconify()
        win.lift()
        win.focus_force()

    def _box(self, e):
        x0, y0 = self._start
        return min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y)

    def _press(self, e):
        self._start = (e.x, e.y)

    def _drag(self, e):
        if not self._start:
            return
        l, t, r, b = self._box(e)
        self.canvas.coords(self._rect, l, t, r, b)
        self.canvas.itemconfigure(self._rect, state="normal")
        if r - l > 2 and b - t > 2:
            self._bright_img = ImageTk.PhotoImage(self._shot.crop((l, t, r, b)))
            self.canvas.itemconfigure(self._bright, image=self._bright_img)
            self.canvas.coords(self._bright, l, t)
            self.canvas.tag_raise(self._rect)

    def _release(self, e):
        if not self._start:
            return
        l, t, r, b = self._box(e)
        if r - l < MIN_SIZE or b - t < MIN_SIZE:
            self._finish(None)
            return
        vx, vy = self._origin
        self._finish([l + vx, t + vy, r + vx, b + vy])

    def _finish(self, region):
        if self.win is not None:
            self.win.destroy()
            self.win = None
        self._dark = self._bright_img = None
        cb, self._on_done = self._on_done, None
        if cb:
            cb(region)
