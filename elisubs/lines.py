"""把识别出的一个个文字框拼回字幕行。

规则：
1. 上下位置重叠的框算同一行，按从左到右拼（RapidOCR 常把一行中文切成两段）。
2. 相邻两行是同一种文字（都是中文，或都是西文）就并成一行，这样双语字幕
   出来正好是「中文一行、外文一行」，长句折行也会接回去。
3. 以破折号开头的行（两个人对话）不并。
"""
import re

_CJK = re.compile(r"[　-〿぀-ヿ㐀-鿿豈-﫿＀-￯]")
_HAN = re.compile(r"[㐀-鿿豈-﫿]")
_DASH = re.compile(r"^\s*[-–—]")

MIN_SCORE = 0.5  # 低于这个置信度的多半是背景里的杂纹


def _is_cjk_line(s):
    """有两个以上汉字就算中文行（日文行也含汉字，所以中日双语分不开）。"""
    return len(_HAN.findall(s)) >= 2


LANG_MODES = ("both", "zh", "foreign")  # 悬浮条语言按钮依次切换


def filter_lang(text, mode):
    """按语言留行：both 都留 / zh 只留中文行 / foreign 只留外文行。"""
    if mode == "both" or not text:
        return text
    keep = [ln for ln in text.splitlines() if _is_cjk_line(ln) == (mode == "zh")]
    return "\n".join(keep)


def paragraph(sentences):
    """录制结束时把多句拼成一段：中文行连成一段、外文行连成一段（句间空格），两段之间空一行。"""
    zh, fg = [], []
    for s in sentences:
        for ln in s.splitlines():
            ln = ln.strip()
            if ln:
                (zh if _is_cjk_line(ln) else fg).append(ln)
    return "\n\n".join(p for p in (" ".join(zh), " ".join(fg)) if p)


def _join(a, b):
    if not a:
        return b
    if not b:
        return a
    if _CJK.match(a[-1]) or _CJK.match(b[0]):
        return a + b
    return a.rstrip() + " " + b.lstrip()


def merge(items, min_score=MIN_SCORE):
    boxes = []
    for pts, text, score in items:
        text = (text or "").strip()
        if not text or score < min_score:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        boxes.append((min(xs), min(ys), max(xs), max(ys), text))
    if not boxes:
        return ""

    # 1. 按竖直位置分行
    boxes.sort(key=lambda b: (b[1] + b[3]) / 2)
    rows = []
    for b in boxes:
        if rows:
            top, bottom = rows[-1]["top"], rows[-1]["bottom"]
            overlap = min(bottom, b[3]) - max(top, b[1])
            if overlap >= 0.5 * min(bottom - top, b[3] - b[1]):
                rows[-1]["boxes"].append(b)
                rows[-1]["top"], rows[-1]["bottom"] = min(top, b[1]), max(bottom, b[3])
                continue
        rows.append({"top": b[1], "bottom": b[3], "boxes": [b]})

    texts = []
    for r in rows:
        line = ""
        for b in sorted(r["boxes"], key=lambda b: b[0]):
            line = _join(line, b[4])
        texts.append(line)

    # 2. 同种文字的相邻行并起来
    out = []
    for t in texts:
        if out and _is_cjk_line(out[-1]) == _is_cjk_line(t) and not _DASH.match(t):
            out[-1] = _join(out[-1], t)
        else:
            out.append(t)
    return "\n".join(out)
