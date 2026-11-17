"""写进 Notion。

- 只用标准库 urllib，不额外装 notion-client。
- 每条识别结果先落到 data/pending.jsonl，写成功才删；断网、密钥错、页面没连集成
  都会弹提示，条目留着，每分钟重试一次，程序重启也不丢。
- 目标页面在发送时才确定（"auto" = 总页面下最新建的子页面）。
"""
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from . import paths, store

log = logging.getLogger("subsnap")

API = os.environ.get("SUBSNAP_NOTION_API", "https://api.notion.com/v1")
VERSION = "2022-06-28"
RETRY_SECONDS = 60


class NotionError(Exception):
    def __init__(self, status, message):
        super().__init__(f"{status} {message}")
        self.status = status
        self.message = message

    def human(self):
        if self.status == 0:
            return "连不上 Notion（网络问题）"
        if self.status == 401:
            return "Notion 密钥不对，检查配置文件里的 notion_token"
        if self.status in (403, 404):
            return "Notion 找不到页面：总页面链接不对，或者还没把集成连到总页面上"
        if self.status == 429:
            return "Notion 限流了，稍后自动重试"
        if self.status >= 500:
            return f"Notion 那边出错了（{self.status}），稍后自动重试"
        return f"Notion 返回错误 {self.status}：{self.message}"


def page_id(link):
    """总页面链接或 id → 32 位 id。id 总在链接最后一段的末尾。"""
    s = (link or "").strip()
    if "/" in s or "?" in s or "#" in s:
        s = urlsplit(s if "://" in s else "https://" + s).path.rstrip("/").split("/")[-1]
    m = re.search(r"([0-9a-f]{32})$", s.replace("-", "").lower())
    if not m:
        raise NotionError(404, "认不出总页面链接")
    return m.group(1)


class Client:
    def __init__(self, token):
        self.token = token.strip()

    def _req(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(API + path, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8")).get("message", "")
            except Exception:  # noqa: BLE001
                msg = e.reason
            raise NotionError(e.code, msg) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise NotionError(0, str(e)) from None

    def child_pages(self, parent):
        """总页面下的直属子页面，最新建的排前面：[(id, 标题, 创建时间)]。"""
        out, cursor = [], None
        while True:
            q = "?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
            r = self._req("GET", f"/blocks/{parent}/children{q}")
            for b in r.get("results", []):
                if b.get("type") == "child_page":
                    out.append((b["id"].replace("-", ""), b["child_page"].get("title", ""),
                                b.get("created_time", "")))
            if not r.get("has_more"):
                break
            cursor = r.get("next_cursor")
        out.sort(key=lambda p: p[2], reverse=True)
        return out

    def page_title(self, pid):
        r = self._req("GET", f"/pages/{pid}")
        for prop in r.get("properties", {}).values():
            if prop.get("type") == "title":
                return "".join(t.get("plain_text", "") for t in prop["title"])
        return ""

    def append(self, pid, blocks):
        self._req("PATCH", f"/blocks/{pid}/children", {"children": blocks})


def _rich(text):
    # Notion 单段文字上限 2000 字，切开
    return [{"type": "text", "text": {"content": text[i:i + 2000]}} for i in range(0, len(text), 2000)]


def blocks_for(text):
    # 只写字幕本身，不写视频标题（Kr 2026-11-17 定的；标题只留在本地 md 里）
    return [{"type": "paragraph", "paragraph": {"rich_text": _rich(text)}}]


class Sync(threading.Thread):
    """后台发送队列。notify(kind, 标题, 正文) 由 App 提供，会被转到界面线程。"""

    def __init__(self, state, notify):
        super().__init__(name="notion", daemon=True)
        self.state = state
        self.notify = notify
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = False
        self.items = self._load()
        self.failing = None       # 上一次失败的提示文字；同一种失败只提示一次
        self.pages = []           # 子页面列表，给托盘菜单用
        self.parent_title = ""
        self.auto_target = None   # auto 模式下当前会写到的页面 (id, 标题)
        self.on_pages = None      # 页面列表刷新后的回调（托盘刷新菜单）
        self._refresh = threading.Event()

    # ---- 持久化 ----
    def _load(self):
        items = []
        if paths.PENDING.exists():
            for line in paths.PENDING.read_text(encoding="utf-8").splitlines():
                try:
                    items.append(json.loads(line))
                except ValueError:
                    log.warning("pending.jsonl 有坏行，跳过：%r", line)
        return items

    def _save(self):
        tmp = paths.PENDING.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in self.items),
                       encoding="utf-8")
        os.replace(tmp, paths.PENDING)

    # ---- 对外 ----
    def submit(self, text, title):
        with self._lock:
            self.items.append({"text": text, "title": title, "target": self.state["target"],
                               "ts": time.strftime("%Y-%m-%d %H:%M:%S")})
            self._save()
        self._wake.set()

    def refresh_pages(self):
        self._refresh.set()
        self._wake.set()

    def stop(self):
        self._stop = True
        self._wake.set()

    @property
    def pending(self):
        return len(self.items)

    # ---- 后台 ----
    def run(self):
        self._refresh.set()
        last_list = 0
        while not self._stop:
            cfg = store.load_config()
            if store.notion_configured(cfg):
                client = Client(cfg["notion_token"])
                if self._refresh.is_set() or time.time() - last_list > 120:
                    self._refresh.clear()
                    last_list = time.time()
                    self._list(client, cfg)
                if self.items and self.state.notion_on:
                    self._flush(client, cfg)
            self._wake.wait(RETRY_SECONDS if self.items else 120)
            self._wake.clear()

    def _list(self, client, cfg):
        try:
            parent = page_id(cfg["notion_parent_page"])
            self.parent_title = client.page_title(parent)
            self.pages = client.child_pages(parent)
            self.auto_target = self.pages[0][:2] if self.pages else (parent, self.parent_title)
        except NotionError as e:
            log.warning("刷新 Notion 页面列表失败：%s", e)
            return
        if self.on_pages:
            self.on_pages()

    def _resolve(self, client, cfg, target):
        parent = page_id(cfg["notion_parent_page"])
        if target == "parent":
            return parent
        if target == "auto":
            pages = client.child_pages(parent)
            self.pages = pages
            return pages[0][0] if pages else parent
        return target

    def _flush(self, client, cfg):
        sent = 0
        try:
            while self.items:
                item = self.items[0]
                pid = self._resolve(client, cfg, item.get("target", "auto"))
                client.append(pid, blocks_for(item["text"]))
                with self._lock:
                    self.items.pop(0)
                    self._save()
                sent += 1
        except NotionError as e:
            log.warning("写 Notion 失败：%s（还剩 %d 条）", e, len(self.items))
            msg = e.human()
            if msg != self.failing:
                self.failing = msg
                self.notify("err", "Notion 没写进去，已排队重试", msg)
            return
        if self.failing:
            self.failing = None
            self.notify("ok", f"Notion 已补写 {sent} 条", "")
