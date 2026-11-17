"""录制：盯着字幕框，字幕换了就自动识别保存。

每 0.3 秒截一次字幕框，但不是每次都识别（识别一次约 1 秒，太费电）：
1. 只提取「像字幕的笔画」：很亮（白字、黄字）而且旁边有深色（字幕的黑边或暗背景）的像素。
   这样后面的画面怎么动，这张笔画图基本不变。
2. 笔画图和上一帧差不多（字幕已经稳定，不是淡入淡出中间）→ 再和上次识别时的笔画图比，
   明显不一样才识别。
3. 识别出来的文字和上一句差不多就跳过（同一句字幕反复出现）。
"""
import logging
import threading
import time

import numpy as np
from PIL import ImageFilter

from . import capture
from .lines import merge
from .logbook import _same

log = logging.getLogger("subsnap")

INTERVAL = 0.3      # 秒
IDLE_STOP = 120     # 这么多秒没有新字幕就自动停（视频暂停、看完了）；Kr 定的 2 分钟
STABLE = 0.15       # 相邻两帧笔画图差异 ≤ 这个 = 字幕稳定了
SAME = 0.35         # 和上次识别的笔画图差异 ≤ 这个 = 还是同一句
MIN_INK = 0.002     # 笔画像素占比低于这个 = 框里没字幕
WORK_H = 120        # 笔画图缩到这个高度再比，省电


def text_mask(img):
    w, h = img.size
    if h > WORK_H:
        img = img.resize((max(1, round(w * WORK_H / h)), WORK_H))
    v = np.asarray(img.convert("HSV").getchannel(2))           # 最亮的颜色通道：白字黄字都高
    near_dark = np.asarray(img.convert("L").filter(ImageFilter.MinFilter(5)))
    return (v >= 190) & (near_dark <= 90)


def diff(a, b):
    if a.shape != b.shape:
        return 1.0
    union = np.count_nonzero(a | b)
    return 0.0 if union == 0 else np.count_nonzero(a ^ b) / union


class Detector:
    """喂一帧，返回这一帧要不要拿去识别。"""

    def __init__(self):
        self.prev = None
        self.last = None

    def feed(self, img):
        m = text_mask(img)
        stable = self.prev is not None and diff(m, self.prev) <= STABLE
        self.prev = m
        if not stable:
            return False
        if m.mean() < MIN_INK:
            self.last = None  # 字幕消失了，下一句出现时一定识别
            return False
        if self.last is not None and diff(m, self.last) <= SAME:
            return False
        self.last = m
        return True


class Watcher:
    def __init__(self, ocr, get_region, on_text, on_stop, get_exclude=lambda: ()):
        """on_text(文字)、on_stop(原因) 在录制线程里调用，调用方自己转到界面线程。
        原因：'user' 手动停 / 'idle' 太久没新字幕 / 'error' 出错 / 'region' 没有字幕框。"""
        self.ocr = ocr
        self.get_region = get_region
        self.get_exclude = get_exclude  # 要涂黑的屏幕区域（悬浮条）
        self.on_text = on_text
        self.on_stop = on_stop
        self._stop = None
        self._thread = None
        self._active = False  # 不用 thread.is_alive()：on_stop 回调时线程还活着，界面会以为还在录

    @property
    def running(self):
        return self._active

    def start(self):
        if self.running:
            return
        self._active = True
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(self._stop,), name="watch", daemon=True)
        self._thread.start()

    def stop(self):
        if self._stop:
            self._stop.set()

    def _run(self, stop):
        det, last_text, last_new, reason = Detector(), "", time.time(), "user"
        try:
            while not stop.is_set():
                t0 = time.time()
                region = self.get_region()  # 每次都读，录制中重新框选也能跟上
                if not region:
                    reason = "region"
                    break
                img = capture.grab_region(region, self.get_exclude())
                if det.feed(img):
                    text = merge(self.ocr.read(img))
                    if text and not _same(text, last_text):
                        last_text, last_new = text, time.time()
                        self.on_text(text)
                if time.time() - last_new > IDLE_STOP:
                    reason = "idle"
                    break
                stop.wait(max(0.0, INTERVAL - (time.time() - t0)))
        except Exception:  # noqa: BLE001
            log.exception("录制出错")
            reason = "error"
        self._active = False
        self.on_stop(reason)
