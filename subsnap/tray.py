"""托盘图标和右键菜单。菜单动作都转到界面线程去做。"""
import threading
from pathlib import Path

import pystray
from PIL import Image, ImageDraw, ImageFont
from pystray import Menu
from pystray import MenuItem as Item

from . import autostart, paths


ASSETS = paths.ASSETS


def _icon(paused, recording=False):
    """伊丽莎白举 COPIED 牌（make_icon.py 生成），录制中右下角加红点；文件缺了就退回画一个蓝色「字」。"""
    f = ASSETS / ("icon_paused.png" if paused else "icon.png")
    if f.exists():
        img = Image.open(f).convert("RGBA")
        if recording:
            s = img.width
            r = s * 0.2
            cx, cy = s - r - s * 0.02, s - r - s * 0.02
            ImageDraw.Draw(img).ellipse((cx - r, cy - r, cx + r, cy + r), fill=(226, 75, 74, 255),
                                        outline="white", width=max(2, int(s * 0.035)))
        return img
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, 62, 62), radius=12, fill=(136, 135, 128) if paused else (24, 95, 165))
    try:
        font = ImageFont.truetype("msyh.ttc", 42)
    except OSError:
        font = ImageFont.load_default()
    d.text((32, 31), "字", font=font, fill="white", anchor="mm")
    return img


def _short(s, n=28):
    s = s or "无标题"
    return s if len(s) <= n else s[: n - 1] + "…"


class Tray:
    def __init__(self, app):
        self.app = app
        st, sync = app.state, app.sync

        def do(fn):
            return lambda icon, item: app.post(fn)

        def set_target(t):
            return lambda icon, item: app.post(lambda: app.set_target(t))

        def is_target(t):
            return lambda item: st["target"] == t

        def auto_text(item):
            cur = sync.auto_target
            return "自动：最新建的子页面" + (f"（{_short(cur[1], 20)}）" if cur else "")

        def target_items():
            yield Item(auto_text, set_target("auto"), checked=is_target("auto"), radio=True)
            yield Item(lambda i: "总页面：" + _short(sync.parent_title or "（未连接）", 20),
                       set_target("parent"), checked=is_target("parent"), radio=True)
            if sync.pages:
                yield Menu.SEPARATOR
                for pid, title, _ in sync.pages[:25]:
                    yield Item(_short(title), set_target(pid), checked=is_target(pid), radio=True)
            yield Menu.SEPARATOR
            yield Item("刷新列表", lambda icon, item: sync.refresh_pages())

        def notion_text(item):
            n = sync.pending
            return "写入 Notion" + (f"（{n} 条待发）" if n else "")

        menu = Menu(
            Item("重新框选字幕区", do(lambda: app.trigger(reselect=True))),
            Item("录制字幕", do(app.toggle_watch), checked=lambda i: app.watcher.running),
            Item("隐藏悬浮窗", do(app.toggle_bar), checked=lambda i: st["bar_hidden"]),
            Menu.SEPARATOR,
            Item(notion_text, do(app.toggle_notion), checked=lambda i: st.notion_on),
            Item("目标页面", Menu(target_items)),
            Item("暂停热键", do(app.toggle_pause), checked=lambda i: st["paused"]),
            Item("开机自启", do(app.toggle_autostart), checked=lambda i: autostart.enabled()),
            Menu.SEPARATOR,
            Item("打开今天的记录", do(app.open_today)),
            Item("打开记录文件夹", do(app.open_logs)),
            Item("打开配置文件", do(app.open_config)),
            Menu.SEPARATOR,
            Item("退出", do(app.quit)),
        )
        self.icon = pystray.Icon("subsnap", _icon(st["paused"]), "字幕识别", menu)
        sync.on_pages = self.refresh

    def start(self):
        threading.Thread(target=self.icon.run, name="tray", daemon=True).start()

    def refresh(self):
        self.icon.icon = _icon(self.app.state["paused"], self.app.watcher.running)
        self.icon.update_menu()

    def stop(self):
        self.icon.stop()
