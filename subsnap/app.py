"""主程序：把热键、悬浮条、框选、识别、录制、剪贴板、记录、Notion、托盘串起来。

线程分工：
- 主线程跑 tkinter（框选层、提示框、悬浮条、设置窗口），其他线程要动界面一律 app.post(函数)。
- 热键线程、托盘线程、Notion 发送线程、录制线程、检查更新线程、每次单次识别一个临时线程。
"""
import json
import logging
import os
import queue
import sys
import threading
import time
import tkinter as tk

from . import __version__, autostart, capture, logbook, notion, paths, store, updater, winutil
from .bar import Bar
from .hotkey import Hotkeys
from .lines import LANG_MODES, filter_lang, merge, paragraph
from .logbook import _same
from .ocr import Ocr
from .settings import Settings
from .toast import Toast
from .tray import Tray
from .watch import IDLE_STOP, Watcher

log = logging.getLogger("subsnap")
LANG_NAMES = {"both": "双语", "zh": "中文", "foreign": "外文"}


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
        self.rec = []                 # 这次录制收到的句子（已按语言筛过）
        self._log_problem = None
        self.update_available = None  # 有新版时是版本号

        self.toast = Toast(self.root)
        self.selector = capture.Selector(self.root)
        self.ocr = Ocr()
        self.sync = notion.Sync(self.state, lambda k, h, b: self.post(lambda: self.toast.show(h, b, k)))
        self.watcher = Watcher(self.ocr, lambda: self.state["region"],
                               on_text=lambda t: self.post(lambda: self._watch_text(t)),
                               on_stop=lambda r: self.post(lambda: self._watch_stopped(r)),
                               get_exclude=self._exclude)
        self.hot = self._make_hotkeys(self.cfg)
        self.settings = Settings(self.root, self._settings_saved)
        self.tray = Tray(self)
        self.bar = Bar(self.root, self.state,
                       on_capture=lambda: self.trigger(reselect=False),
                       on_region=lambda: self.trigger(reselect=True),
                       on_record=self.toggle_watch,
                       on_lang=self.cycle_lang)

    # ---------- 启动 / 退出 ----------
    def run(self):
        self.sync.start()
        self.hot.start()
        self.tray.start()
        self.hot.ready.wait(3)
        if store.config_error:
            self.toast.show("config.json 读不出来，暂用默认设置", store.config_error + "\n托盘 → 设置… 可以重新填", "err", ms=8000)
        elif self.hot.failed:
            self.toast.show("快捷键被别的程序占用了", "、".join(self.hot.failed) + "\n托盘 → 设置… 换一个", "err", ms=6000)
        self._recover_recording()
        threading.Thread(target=self._check_update, args=(False,), name="update", daemon=True).start()
        self.root.after(30, self._pump)
        self.root.mainloop()

    def quit(self):
        if self.watcher.running:
            self.watcher.stop()  # 录到的句子在 recording.jsonl 里，下次启动补存
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

    def _make_hotkeys(self, cfg):
        return Hotkeys({"capture": cfg["hotkey_capture"], "reselect": cfg["hotkey_reselect"]},
                       lambda name: self.post(lambda: self.trigger(reselect=name == "reselect")),
                       paused=self.state["paused"])

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

    def _done(self, raw, title, near):
        self.busy = False
        if not raw:
            self.toast.show("没认出文字", "框里没有字幕？可以换一个字幕区", "warn", near, ms=3000)
            return
        mode = self.state["lang_mode"]
        text = filter_lang(raw, mode)
        if not text:
            self.toast.show(f"这句没有{LANG_NAMES[mode]}", "悬浮条上的语言按钮可以切回双语", "warn", near, ms=3000)
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
    def save_entry(self, text, title, near=None, dedup=True):
        """写当天 md、发 Notion。dedup=True 时先去重，重复的返回 False。"""
        if dedup:
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
        _, problem = logbook.logs_dir()
        if problem and problem != self._log_problem:  # 同一个问题只提示一次，录制时不刷屏
            log.warning("记录保存位置用不了：%s", problem)
            self.toast.show("记录保存位置用不了，先存到了默认位置", problem, "err", near, ms=6000)
        self._log_problem = problem
        if self.state.notion_on and store.notion_configured():
            self.sync.submit(text, title)
        return True

    # ---------- 语言 ----------
    def cycle_lang(self):
        cur = self.state["lang_mode"]
        nxt = LANG_MODES[(LANG_MODES.index(cur) + 1) % len(LANG_MODES)] if cur in LANG_MODES else "both"
        self.state.set("lang_mode", nxt)
        self.bar.set_lang(nxt)
        self.tray.refresh()

    def set_lang(self, mode):
        self.state.set("lang_mode", mode)
        self.bar.set_lang(mode)
        self.tray.refresh()

    # ---------- 录制 ----------
    # 录制时每句先暂存（内存 + data/recording.jsonl），停止时拼成一段：
    # 放进剪贴板，当天 md 和 Notion 也只写这一段。程序中途崩了，下次启动从 recording.jsonl 补存。
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
        self.rec = []
        self._rec_write({"title": self.watch_title}, fresh=True)
        self.watcher.start()
        self.bar.set_recording(True, 0)
        self.tray.refresh()

    def _rec_write(self, obj, fresh=False):
        try:
            with paths.RECORDING.open("w" if fresh else "a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        except OSError:
            log.exception("写录制暂存文件失败")  # 只影响崩溃后补存，不打断录制

    def _watch_text(self, raw):
        text = filter_lang(raw, self.state["lang_mode"])
        if not text or any(_same(text, s) for s in self.rec):
            return
        self.rec.append(text)
        self._rec_write({"text": text})
        if self.watcher.running:
            self.bar.set_recording(True, len(self.rec))

    def _watch_stopped(self, reason):
        self.bar.set_recording(False)
        self.tray.refresh()
        n = len(self.rec)
        head = {"error": "录制出错，已停止", "idle": f"{IDLE_STOP // 60} 分钟没有新字幕，已停止录制",
                "region": "还没有字幕区，录制停止"}.get(reason, "录制结束")
        kind = "err" if reason == "error" else "warn" if reason == "region" else "ok"
        if not n:
            self._rec_clear()
            self.toast.show(head, "没有录到字幕", kind, ms=4000)
            return
        text = paragraph(self.rec)
        copied = True
        try:
            winutil.set_clipboard(text)
        except Exception:  # noqa: BLE001
            log.exception("写剪贴板失败")
            copied = False
        self.save_entry(text, self.watch_title, dedup=False)
        self._rec_clear()
        self.rec = []
        body = (f"已复制 {n} 句" if copied else f"存了 {n} 句（剪贴板被占用，没复制上，可以去当天记录里找）")
        if reason == "error":
            body += "\n详情在 data/subsnap.log"
        self.toast.show(head, body, "err" if (reason == "error" or not copied) else "ok", ms=5000)

    def _rec_clear(self):
        try:
            paths.RECORDING.unlink(missing_ok=True)
        except OSError:
            log.exception("删录制暂存文件失败")

    def _recover_recording(self):
        """上次录制没正常结束（崩溃、关机）：把暂存的句子补存进 md 和 Notion（不碰剪贴板）。"""
        if not paths.RECORDING.exists():
            return
        title, sentences, bad = "", [], 0
        try:
            for line in paths.RECORDING.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    bad += 1
                    continue
                title = obj.get("title", title)
                if obj.get("text"):
                    sentences.append(obj["text"])
        except (OSError, UnicodeDecodeError):
            log.exception("读录制暂存文件失败")
            bad += 1
        if sentences:
            self.save_entry(paragraph(sentences), title, dedup=False)
        if bad:  # 有读不出来的行：原文件另存，不删，免得丢内容
            keep = paths.RECORDING.with_name(f"recording.broken-{time.strftime('%Y%m%d-%H%M%S')}.jsonl")
            try:
                os.replace(paths.RECORDING, keep)
            except OSError:
                log.exception("另存录制暂存文件失败")
            self.toast.show("上次录制没正常结束，有部分内容读不出来",
                            f"补存了 {len(sentences)} 句；原始文件另存在 {keep.name}", "err", ms=8000)
            return
        if sentences:
            self.toast.show("上次录制没正常结束", f"已把录到的 {len(sentences)} 句补存进当天记录", "warn", ms=6000)
        self._rec_clear()

    # ---------- 设置 / 更新 ----------
    def open_settings(self):
        self.settings.open()

    def _settings_saved(self, old, new):
        if (old["hotkey_capture"], old["hotkey_reselect"]) != (new["hotkey_capture"], new["hotkey_reselect"]):
            self.hot.stop()
            self.hot = self._make_hotkeys(new)
            self.hot.start()
            self.hot.ready.wait(3)
            if self.hot.failed:
                self.toast.show("快捷键被别的程序占用了", "、".join(self.hot.failed) + "\n换一个再试", "err", ms=6000)
                return
        self.cfg = new
        self._log_problem = None
        self.sync.refresh_pages()  # Notion 开关默认跟着「配好了没有」走，配好就自动开
        self.tray.refresh()
        self.toast.show("设置已保存", "", "ok")

    def _check_update(self, manual):
        try:
            ver, newer = updater.latest()
        except Exception as e:  # noqa: BLE001
            log.warning("检查更新失败：%s", e)
            if manual:
                self.post(lambda: self.toast.show("没连上 GitHub，检查更新失败", "稍后再试", "err", ms=4000))
            return
        if newer:
            self.update_available = ver
            self.post(lambda: (self.tray.refresh(), self.toast.show(
                f"有新版本 {ver}", "托盘 → 下载新版本", "ok", ms=6000)))
        elif manual:
            self.post(lambda: self.toast.show(f"已经是最新版本（{__version__}）", "", "ok"))

    def check_update(self):
        if self.update_available:
            os.startfile(updater.PAGE)
            return
        threading.Thread(target=self._check_update, args=(True,), name="update", daemon=True).start()

    # ---------- 托盘菜单 ----------
    def toggle_notion(self):
        if not self.state.notion_on and not store.notion_configured():
            self.toast.show("先在设置里填 Notion 令牌和总页面链接", "", "warn", ms=4000)
            self.open_settings()
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
        self.toast.show("快捷键已暂停" if p else "快捷键已恢复", "", "warn" if p else "ok")

    def open_today(self):
        f = logbook.today_file()
        os.startfile(f if f.exists() else logbook.logs_dir()[0])

    def open_logs(self):
        os.startfile(logbook.logs_dir()[0])

    def change_log_dir(self):
        """选文件夹 → 写进 config.json 的 log_dir。选回默认的 data/logs 就是恢复默认。"""
        from tkinter import filedialog
        current = logbook.logs_dir()[0]
        holder = tk.Toplevel(self.root)  # 让选文件夹窗口浮在最上面（视频全屏时也看得到）
        holder.overrideredirect(True)
        holder.attributes("-topmost", True)
        holder.geometry("1x1+0+0")
        try:
            chosen = filedialog.askdirectory(parent=holder, initialdir=str(current),
                                             title="识别记录保存到哪个文件夹", mustexist=False)
        finally:
            holder.destroy()
        if not chosen:
            return
        path = os.path.normpath(chosen)
        is_default = os.path.normcase(path) == os.path.normcase(str(paths.LOGS))
        store.update_config("log_dir", "" if is_default else path)
        _, problem = logbook.logs_dir()
        if problem:
            self.toast.show("这个文件夹用不了", problem, "err", ms=5000)
            store.update_config("log_dir", "")
            return
        self._log_problem = None
        self.toast.show("记录保存位置已改", ("默认位置：" if is_default else "") + path + "\n以前的记录留在原处", "ok", ms=4000)

    def open_config(self):
        store.load_config()  # 没有就先生成
        os.startfile(paths.CONFIG)


def main():
    winutil.set_dpi_aware()
    if sys.stdout is None or sys.stderr is None:  # pythonw / exe 下没有控制台
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
    log.info("启动 %s（数据在 %s）", __version__, paths.DATA)
    App().run()
    log.info("退出")
