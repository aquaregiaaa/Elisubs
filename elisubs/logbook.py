"""当天记录：<记录文件夹>/2026-11-17.md。换了视频才写一次小标题。

记录文件夹默认是 data/logs，config.json 的 log_dir 可以改（托盘「更改记录保存位置…」）。
改的位置用不了（被删、U 盘拔了、没权限）时这一次退回默认位置，并把原因告诉调用方。

去重：同一个视频（同一个小标题下）已经记过的字幕不再记，也不再发 Notion。
用相似度而不是完全相等来比——同一句字幕截两次，OCR 偶尔会差一两个字。
"""
import difflib
import os
import re
from datetime import datetime
from pathlib import Path

from . import paths, store

SIMILAR = 0.9  # 去掉空白后相似度 ≥ 0.9 算同一句


def logs_dir():
    """返回 (实际用的文件夹, 问题说明或 None)。"""
    custom = store.load_config().get("log_dir", "").strip()
    if not custom:
        return paths.LOGS, None
    p = Path(os.path.expandvars(custom))
    try:
        p.mkdir(parents=True, exist_ok=True)
        if os.access(p, os.W_OK):
            return p, None
        problem = "没有写入权限"
    except OSError as e:
        problem = e.strerror or str(e)
    return paths.LOGS, f"{custom}（{problem}）"


def today_file():
    return logs_dir()[0] / f"{datetime.now():%Y-%m-%d}.md"


def _norm(s):
    return re.sub(r"\s+", "", s)


def _same(a, b):
    a, b = _norm(a), _norm(b)
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= SIMILAR


def parse(text):
    """md → (日期标题行, [(视频标题, [条目, ...]), ...])。没有小标题的条目归在标题 "" 下。"""
    head, sections = "", []
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        # 小标题可能和下一条挤在同一个段落里（手动编辑过的文件）
        while lines and (lines[0].startswith("# ") or lines[0].startswith("## ")):
            if lines[0].startswith("## "):
                sections.append((lines[0][3:].strip(), []))
            else:
                head = lines[0]
            lines = lines[1:]
        if lines:
            if not sections:
                sections.append(("", []))
            sections[-1][1].append("\n".join(lines))
    return head, sections


def render(head, sections):
    parts = [head + "\n\n"] if head else []
    for title, entries in sections:
        if title:
            parts.append(f"## {title}\n\n")
        parts.extend(e + "\n\n" for e in entries)
    return "".join(parts)


def is_dup(text, title):
    f = today_file()
    if not f.exists():
        return False
    _, sections = parse(f.read_text(encoding="utf-8"))
    pool = [e for t, es in sections if t == (title or "") for e in es]
    if not title and sections:  # 拿不到窗口标题时，只和最后一段比
        pool = sections[-1][1]
    return any(_same(text, e) for e in pool)


def add(state, text, title):
    day = f"{datetime.now():%Y-%m-%d}"
    f = today_file()
    parts = []
    new_file = not f.exists()
    if new_file:
        parts.append(f"# {day}\n\n")
    if title and (new_file or state["log_last"] != [day, title]):
        parts.append(f"## {title}\n\n")
        state.set("log_last", [day, title])
    parts.append(text.strip() + "\n\n")
    with f.open("a", encoding="utf-8") as fh:
        fh.write("".join(parts))


def dedup_file(path):
    """清理已有文件：同一视频下重复的条目只留第一次。返回删掉几条。"""
    head, sections = parse(path.read_text(encoding="utf-8"))
    seen, out, removed = {}, [], 0
    for title, entries in sections:
        kept = []
        pool = seen.setdefault(title, [])
        for e in entries:
            if any(_same(e, p) for p in pool):
                removed += 1
            else:
                kept.append(e)
                pool.append(e)
        if kept or not title:
            out.append((title, kept))
    if removed:
        path.write_text(render(head, out), encoding="utf-8")
    return removed
