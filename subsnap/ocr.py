"""识别：RapidOCR 默认模型（PP-OCRv6），一个模型同时认中文、英文、法语重音。

2026-11-17 实测（8 句带重音的法语）：v6 全对 5 句，专门的 latin_PP-OCRv5 只全对 1 句，
所以不按语言切模型。模型 ocr2epub 那边已经下载在 rapidocr/models 里。
"""
import logging
import threading

log = logging.getLogger("subsnap")


class Ocr:
    def __init__(self):
        self._ready = threading.Event()
        self._lock = threading.Lock()  # 单次识别和录制可能同时调用，引擎一次只跑一个
        self._engine = None
        self._error = None
        threading.Thread(target=self._load, name="ocr-load", daemon=True).start()

    def _load(self):
        try:
            from rapidocr import RapidOCR
            from PIL import Image

            # RapidOCR 每建一个子模型都会把自己的日志级别重设成 INFO，用过滤器才压得住
            logging.getLogger("RapidOCR").addFilter(lambda r: r.levelno >= logging.ERROR)
            # 检测参数：默认 limit_type=min/736 会把 140 像素高的字幕截图放大 5 倍再找字，
            # 反而整行漏检（2026-11-17 实测 58 行漏 7 行，每张 1.06 秒）。改成只在最长边超过
            # 1280 时缩小、从不放大：58 行全检出，33 张全对 32 张，每张 0.16 秒。
            self._engine = RapidOCR(params={"Det.limit_type": "max", "Det.limit_side_len": 1280})
            self._engine(Image.new("RGB", (64, 32), "white"))  # 预热，第一次真识别就不慢了
        except Exception as e:  # noqa: BLE001
            self._error = e
            log.exception("OCR 引擎加载失败")
        finally:
            self._ready.set()

    def read(self, img):
        """返回 [(四个角点, 文字, 置信度), ...]。"""
        self._ready.wait()
        if self._error:
            raise RuntimeError(f"OCR 引擎没加载起来：{self._error}")
        with self._lock:
            r = self._engine(img.convert("RGB"))
        if r.boxes is None or r.txts is None:
            return []
        return [(b.tolist(), t, float(s)) for b, t, s in zip(r.boxes, r.txts, r.scores)]
