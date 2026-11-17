"""主程序：把热键、悬浮条、框选、识别、录制、剪贴板、记录、Notion、托盘串起来。

线程分工：
- 主线程跑 tkinter（框选层、提示框、悬浮条），其他线程要动界面一律 app.post(函数)。
- 热键线程、托盘线程、Notion 发送线程、录制线程、每次单次识别一个临时线程。
"""
import logging
import os
import queue
import sys
import threading
import tkinter as tk

from . import autostart, capture, logbook, notion, paths, store, winutil
from .bar import Bar
from .hotkey import Hotkeys
from .lines import merge
from .ocr import Ocr
from .toast import Toast
from .tray import Tray
from .watch import IDLE_STOP, Watcher

log = logging.getLogger("subsnap")


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.report_callback_exception = self._tk_error
        self.cfg = store.load_config()
        self.state = store.State()
        self.uiq = queue.Queue()
        self.busy = False
        self.watch_title = ""
        self.watch_count = 0

        self.toast = Toast(self.root)
        self.selector = capture.Selector(self.root)
        self.ocr = Ocr()
        self.sync = notion.Sync(self.state, lambda k, h, b: self.post(lambda: self.toast.show(h, b, k)))
        self.watcher = Watcher(self.ocr, lambda: self.state["region"],
                               on_text=lambda t: self.post(lambda: self._watch_text(t)),
                               on_stop=lambda r: self.post(lambda: self._watch_stopped(r)),
                               get_exclude=self._exclude)
        self.hot = Hotkeys({"capture": self.cfg["hotkey_capture"], "reselect": self.cfg["hotkey_reselect"]},
                           lambda name: self.post(lambda: self.trigger(reselect=name == "reselect")),
                           paused=self.state["paused"])
        self.tray = Tray(self)
        self.bar = Bar(self.root, self.state,
                       on_capture=lambda: self.trigger(reselect=False),
                       on_region=lambda: self.trigger(reselect=True),
                       on_record=self.toggle_watch)

    # ---------- 启动 / 退出 ----------
    def run(self):
        self.sync.start()
        self.hot.start()
        self.tray.start()
        self.hot.ready.wait(3)
        if self.hot.failed:
            self.toast.show("热键被别的程序占用了", "、".join(self.hot.failed) + "\n改 config.json 里的热键后重启", "err", ms=6000)
        self.root.after(30, self._pump)
        self.root.mainloop()

    def quit(self):
        self.watcher.stop()
        self.hot.stop()
        self.sync.stop()
        self.tray.stop()
        self.root.after(50, self.root.destroy)

    def post(self, fn):
        self.uiq.put(fn)

    def _pump(self):
        try:
            while True:
                fn = self.uiq.get_nowait()
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    log.exception("界面任务出错")
                    self.busy = False
                    self.toast.show("出错了", "详情在 data/subsnap.log", "err", ms=4000)
        except queue.Empty:
            pass
        self.root.after(30, self._pump)

    def _tk_error(self, *args):
        log.error("tk 出错", exc_info=args)

    def _exclude(self):
        """识别时要涂黑的区域：悬浮条（系统截图里看得见，自己识别时要挡掉）。录制线程也会调用，只读缓存值。"""
        bar = getattr(self, "bar", None)
        return [bar.rect] if bar and bar.rect else []

    # ---------- 框选 ----------
    def _select(self, hwnd, then, on_cancel=None):
        """弹框选层；选好后记住字幕框，再调用 then(region, 整屏截图, 截图原点)。"""
        shot, origin = capture.grab_all()

        def done(r):
            winutil.activate(hwnd)  # 把焦点还给播放器
            if not r:
                if on_cancel:
                    on_cancel()
                return
            self.state.set("region", r)
            then(r, shot, origin)

        self.selector.select(shot, origin, done)

    # ---------- 单次识别 ----------
    def trigger(self, reselect=False):
        if self.busy or self.selector.active:
            return
        self.busy = True
        hwnd = winutil.foreground()
        title = winutil.clean_title(winutil.window_title(hwnd))
        region = self.state["region"]

        if reselect or not region:
            def then(r, shot, origin):
                # 换完框马上识别一次（录制中也一样；录制随后会跟上新框，同一句靠去重不会存两遍）
                vx, vy = origin
                img = shot.crop((r[0] - vx, r[1] - vy, r[2] - vx, r[3] - vy))
                self._recognize(capture.mask(img, r[:2], self._exclude()), title, r)

            self._select(hwnd, then, on_cancel=lambda: setattr(self, "busy", False))
        else:
            self._recognize(capture.grab_region(region, self._exclude()), title, region)

    def _recognize(self, img, title, region):
        near = ((region[0] + region[2]) // 2, (region[1] + region[3]) // 2)

        def work():
            try:
                text = merge(self.ocr.read(img))
                self.post(lambda: self._done(text, title, near))
            except Exception as e:  # noqa: BLE001
                log.exception("识别失败")
                msg = str(e)
                self.post(lambda: self._fail("识别失败", msg, near))

        threading.Thread(target=work, name="ocr", daemon=True).start()

    def _fail(self, head, body, near):
        self.busy = False
        self.toast.show(head, body, "err", near, ms=4000)

    def _done(self, text, title, near):
        self.busy = False
        if not text:
            self.toast.show("没认出文字", "框里没有字幕？可以换一个字幕区", "warn", near, ms=3000)
            return
        try:
            winutil.set_clipboard(text)  # 重复的也照样放进剪贴板，可能就是想再粘一次
        except Exception as e:  # noqa: BLE001
            log.exception("写剪贴板失败")
            self.toast.show("没能放进剪贴板", str(e), "err", near, ms=4000)
            self.save_entry(text, title, near)
            return
        saved = self.save_entry(text, title, near)
        self.toast.show("已复制" if saved else "已复制（这句记过了，不再记录）", text, "ok", near)

    # ---------- 保存（单次和录制共用） ----------
    def save_entry(self, text, title, near=None):
        """去重后写当天 md、发 Notion。返回是否真的存了（重复的返回 False）。"""
        try:
            if logbook.is_dup(text, title):
                return False
        except Exception:  # noqa: BLE001
            log.exception("去重检查失败，按不重复处理")
        try:
            logbook.add(self.state, text, title)
        except Exception:  # noqa: BLE001
            log.exception("写当天记录失败")
            self.toast.show("当天记录没写进去", "详情在 data/subsnap.log", "err", near, ms=4000)
        if self.state.notion_on and store.notion_configured():
            self.sync.submit(text, title)
        return True

    # ---------- 录制 ----------
    def toggle_watch(self):
        if self.watcher.running:
            self.watcher.stop()
            return
        if self.selector.active:
            return
        hwnd = winutil.foreground()  # 悬浮条不抢焦点，所以这里还是视频窗口
        self.watch_title = winutil.clean_title(winutil.window_title(hwnd))
        if self.state["region"]:
            self._start_watch()
        else:
            self._select(hwnd, lambda r, shot, origin: self._start_watch())

    def _start_watch(self):
        self.watch_count = 0
        self.watcher.start()
        self.bar.set_recording(True, 0)
        self.tray.refresh()

    def _watch_text(self, text):
        if self.save_entry(text, self.watch_title):
            self.watch_count += 1
            if self.watcher.running:
                self.bar.set_recording(True, self.watch_count)

    def _watch_stopped(self, reason):
        self.bar.set_recording(False)
        self.tray.refresh()
        body = f"这次存了 {self.watch_count} 句"
        if reason == "error":
            self.toast.show("录制出错，已停止", body + "\n详情在 data/subsnap.log", "err", ms=5000)
        elif reason == "idle":
            self.toast.show(f"{IDLE_STOP // 60} 分钟没有新字幕，已停止录制", body, "ok", ms=5000)
        elif reason == "region":
            self.toast.show("还没有字幕区，录制停止", "", "warn", ms=4000)
        else:
            self.toast.show("录制结束", body, "ok", ms=3000)

    # ---------- 托盘菜单 ----------
    def toggle_notion(self):
        if not self.state.notion_on and not store.notion_configured():
            self.toast.show("先填 Notion 配置", "在打开的 config.json 里填 notion_token 和 notion_parent_page", "warn", ms=5000)
            self.open_config()
            return
        self.state.set("notion_enabled", not self.state.notion_on)
        if self.state.notion_on:
            self.sync.refresh_pages()
        self.tray.refresh()

    def toggle_bar(self):
        hidden = not self.state["bar_hidden"]
        self.state.set("bar_hidden", hidden)
        self.bar.set_visible(not hidden)
        self.tray.refresh()

    def toggle_autostart(self):
        on = not autostart.enabled()
        try:
            autostart.set_enabled(on)
        except OSError as e:
            log.exception("设置开机自启失败")
            self.toast.show("开机自启没设置成功", str(e), "err", ms=4000)
            return
        self.tray.refresh()
        self.toast.show("已设为开机自启" if on else "已取消开机自启", "", "ok")

    def set_target(self, t):
        self.state.set("target", t)
        self.tray.refresh()

    def toggle_pause(self):
        p = not self.state["paused"]
        self.state.set("paused", p)
        self.hot.set_paused(p)
        self.tray.refresh()
        self.toast.show("热键已暂停" if p else "热键已恢复", "", "warn" if p else "ok")

    def open_today(self):
        f = logbook.today_file()
        os.startfile(f if f.exists() else paths.LOGS)

    def open_logs(self):
        os.startfile(paths.LOGS)

    def open_config(self):
        store.load_config()  # 没有就先生成
        os.startfile(paths.CONFIG)


def main():
    winutil.set_dpi_aware()
    if sys.stdout is None or sys.stderr is None:  # pythonw 下没有控制台
        sys.stdout = sys.stderr = open(paths.APPLOG, "a", encoding="utf-8", buffering=1)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(paths.APPLOG, encoding="utf-8")],
    )
    # 互斥锁名带上数据目录：同一份数据只能开一个；测试实例（另一个数据目录）可以和正式版同时跑
    import hashlib
    tag = hashlib.md5(str(paths.DATA.resolve()).lower().encode()).hexdigest()[:8]
    if not winutil.single_instance(f"Local\\subsnap_{tag}"):
        log.info("已经有一个在运行，退出")
        return
    log.info("启动")
    App().run()
    log.info("退出")
