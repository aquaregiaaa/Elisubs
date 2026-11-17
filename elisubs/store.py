"""config.json（Kr 填的）和 state.json（程序记的）读写。"""
import json
import os
import threading
import time

from . import paths

CONFIG_DEFAULTS = {
    "notion_token": "",
    "notion_parent_page": "",
    "hotkey_capture": "alt+s",
    "hotkey_reselect": "alt+d",
    "log_dir": "",             # 识别记录（md）存哪；空 = 程序旁边的 data/logs
}

STATE_DEFAULTS = {
    "region": None,            # 字幕框 [left, top, right, bottom]，屏幕绝对像素
    "notion_enabled": None,    # None = 还没手动设过，按「配置填好了没有」决定
    "target": "auto",          # "auto" 最新建的子页面 / "parent" 总页面 / 某个页面 id
    "paused": False,
    "log_last": None,          # [日期, 视频标题]，决定 md 里要不要再写小标题
    "bar_hidden": False,       # 悬浮条藏起来了没有
    "bar_pos": None,           # 悬浮条位置 [x, y]；None = 主屏右下角
    "lang_mode": "both",       # 双语字幕留哪种："both" 都留 / "zh" 只留中文 / "foreign" 只留外文
}

_lock = threading.Lock()


def _write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


config_error = None  # config.json 读不出来时的原因（给界面提示用）；读得出来就是 None


def _read_config():
    """读 config.json。格式错了返回 None 并记下原因——不能悄悄当成空配置，令牌会像没填一样。"""
    global config_error
    try:
        data = json.loads(paths.CONFIG.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("最外层应该是 { }")
    except json.JSONDecodeError as e:
        config_error = f"第 {e.lineno} 行第 {e.colno} 个字符附近格式不对"
        return None
    except (OSError, ValueError) as e:
        config_error = str(e)
        return None
    config_error = None
    return data


def load_config():
    if not paths.CONFIG.exists():
        _write_json(paths.CONFIG, CONFIG_DEFAULTS)
    data = _read_config()
    return {**CONFIG_DEFAULTS, **(data or {})}


def update_config(key, value=None, **more):
    """改一项或几项，其余（包括用户手填的令牌）原样保留。
    原文件格式坏了的话先另存一份 config.broken-时间.json，再写新的，手填的内容不会丢。"""
    changes = {key: value} if key is not None else {}
    changes.update(more)
    with _lock:
        data = _read_config() if paths.CONFIG.exists() else None
        if data is None:
            if paths.CONFIG.exists():
                backup = paths.CONFIG.with_name(f"config.broken-{time.strftime('%Y%m%d-%H%M%S')}.json")
                backup.write_bytes(paths.CONFIG.read_bytes())
            data = dict(CONFIG_DEFAULTS)
        data.update(changes)
        _write_json(paths.CONFIG, data)
    _read_config()  # 刷新 config_error


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
