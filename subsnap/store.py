"""config.json（Kr 填的）和 state.json（程序记的）读写。"""
import json
import os
import threading

from . import paths

CONFIG_DEFAULTS = {
    "notion_token": "",
    "notion_parent_page": "",
    "hotkey_capture": "alt+s",
    "hotkey_reselect": "alt+d",
}

STATE_DEFAULTS = {
    "region": None,            # 字幕框 [left, top, right, bottom]，屏幕绝对像素
    "notion_enabled": None,    # None = 还没手动设过，按「配置填好了没有」决定
    "target": "auto",          # "auto" 最新建的子页面 / "parent" 总页面 / 某个页面 id
    "paused": False,
    "log_last": None,          # [日期, 视频标题]，决定 md 里要不要再写小标题
    "bar_hidden": False,       # 悬浮条藏起来了没有
    "bar_pos": None,           # 悬浮条位置 [x, y]；None = 主屏右下角
}

_lock = threading.Lock()


def _write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_config():
    if not paths.CONFIG.exists():
        _write_json(paths.CONFIG, CONFIG_DEFAULTS)
    try:
        data = json.loads(paths.CONFIG.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        data = {}
    return {**CONFIG_DEFAULTS, **data}


def notion_configured(cfg=None):
    cfg = cfg or load_config()
    return bool(cfg["notion_token"].strip() and cfg["notion_parent_page"].strip())


class State:
    def __init__(self):
        try:
            data = json.loads(paths.STATE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        self._d = {**STATE_DEFAULTS, **data}

    def __getitem__(self, k):
        return self._d[k]

    def set(self, k, v):
        with _lock:
            self._d[k] = v
            _write_json(paths.STATE, self._d)

    @property
    def notion_on(self):
        v = self._d["notion_enabled"]
        return notion_configured() if v is None else v
