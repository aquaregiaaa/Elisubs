"""伊丽莎白举牌图标。
- 悬浮条、托盘、exe 图标（icon.png / icon_paused.png / icon.ico）：牌子上写 SUBS!
- 「已复制」提示框里的大图（toast.png）：牌子上写 COPIED

源图 assets/elizabeth_src.png（240×240，Kr 2026-11-17 给的）。
做法：放大到 1024 → 牌子内部（四角往里收一点，保住黑边）整块刷成牌子底色 →
先在一个「拉平的牌子」矩形里排字，再用透视变换贴回倾斜的牌子上，字就顺着牌子的四条边走。
暂停状态的图标是同一张图去色变淡。

  python make_icon.py            按 CHOICE 生成正式图标
  python make_icon.py variants   生成所有候选 + 对比图 assets/variants/
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent / "assets"
SRC = ROOT / "elizabeth_src.png"
FONTS = Path(r"C:\Windows\Fonts")
TEXT = "COPIED"      # 提示框 toast.png
ICON_TEXT = "SUBS!"  # 悬浮条 / 托盘 / exe 图标（Kr 2026-11-18）
ICON_TRACK = 0.05    # SUBS! 的字间距（按字号的比例；Kr 选的 A 档）
INK = (17, 17, 17, 255)
BIG = 1024
K = BIG / 240

# 牌子四个角（源图 240 像素坐标，左上、右上、右下、左下）
SIGN = [(121, 50), (236, 71), (235, 160), (118, 146)]
SIGN_COLOR = (239, 240, 241, 255)
INSET = 3.2  # 往里收几个源图像素，避开黑边

# 候选：名字 → (字体文件, 可变字体的样式名, 上下是否撑满)
VARIANTS = {
    "arial_black": ("ariblk.ttf", None, False),
    "segoe_black": ("seguibl.ttf", None, False),
    "segoe_bold": ("segoeuib.ttf", None, False),
    "impact": ("impact.ttf", None, False),
    "bahnschrift_bold": ("bahnschrift.ttf", "Bold", False),
    "bahnschrift_condensed": ("bahnschrift.ttf", "Bold Condensed", False),
    "franklin_heavy": ("FRAHV.TTF", None, False),
    "century_gothic": ("GOTHICB.TTF", None, False),
    "arial_rounded": ("ARLRDBD.TTF", None, False),
    "verdana_bold": ("verdanab.ttf", None, False),
    "arial_black_stretch": ("ariblk.ttf", None, True),
    "bahnschrift_stretch": ("bahnschrift.ttf", "Bold", True),
}
CHOICE = "arial_black_stretch"  # Kr 2026-11-17 选的 11 号

PAD_X = 0.05   # 左右留白占牌子宽度的比例（「顶格」）
PAD_Y = 0.10   # 撑满模式下上下留白


def _inset(poly, d):
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    out = []
    for x, y in poly:
        vx, vy = cx - x, cy - y
        n = math.hypot(vx, vy)
        out.append((x + vx / n * d * 1.4, y + vy / n * d))
    return out


def _perspective_coeffs(dst, src):
    """PIL 的 PERSPECTIVE 要的是「输出点 → 输入点」的 8 个系数。"""
    a, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b += [u, v]
    return np.linalg.solve(np.array(a, float), np.array(b, float)).tolist()


def _glyph(font_file, variation, text, track=0.0):
    """白字黑底的灰度图，裁到字的边缘。track = 字母之间额外加的空（按字号的比例）。"""
    size = 400
    font = ImageFont.truetype(str(FONTS / font_file), size)
    if variation:
        font.set_variation_by_name(variation)
    w = int(font.getlength(text) + track * size * len(text)) + 200
    glyph = Image.new("L", (w, size * 2), 0)
    d = ImageDraw.Draw(glyph)
    if track:
        x = 50
        for ch in text:
            d.text((x, 50), ch, font=font, fill=255)
            x += font.getlength(ch) + track * size
    else:
        d.text((50, 50), text, font=font, fill=255)
    return glyph.crop(glyph.getbbox())


def _text_card(font_file, variation, stretch, w, h, text=TEXT, track=0.0):
    """在 w×h 的平面矩形里排好字（透明底）。
    COPIED 左右顶格（PAD_X）；别的字用和 COPIED 一样的横竖缩放比例（同字号），居中，不硬撑满。"""
    ref = _glyph(font_file, variation, TEXT)
    tw = w * (1 - 2 * PAD_X)
    if stretch:
        th = h * (1 - 2 * PAD_Y)
    else:
        th = ref.height * tw / ref.width
        th = min(th, h * (1 - 2 * PAD_Y))
    glyph = _glyph(font_file, variation, text, track)
    kx, ky = tw / ref.width, th / ref.height
    glyph = glyph.resize((round(glyph.width * kx), round(glyph.height * ky)), Image.LANCZOS)
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ink = Image.new("RGBA", glyph.size, INK)
    card.paste(ink, ((w - glyph.width) // 2, (h - glyph.height) // 2), glyph)
    return card


def build(font_file, variation=None, stretch=False, text=TEXT, track=0.0):
    im = Image.open(SRC).convert("RGBA").resize((BIG, BIG), Image.LANCZOS)
    inner = [(x * K, y * K) for x, y in _inset(SIGN, INSET)]
    ImageDraw.Draw(im).polygon(inner, fill=SIGN_COLOR)

    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = inner
    w = round((math.hypot(x1 - x0, y1 - y0) + math.hypot(x2 - x3, y2 - y3)) / 2)
    h = round((math.hypot(x3 - x0, y3 - y0) + math.hypot(x2 - x1, y2 - y1)) / 2)
    card = _text_card(font_file, variation, stretch, w, h, text, track)
    coeffs = _perspective_coeffs(inner, [(0, 0), (w, 0), (w, h), (0, h)])
    warped = card.transform((BIG, BIG), Image.PERSPECTIVE, coeffs, Image.BICUBIC)
    im.alpha_composite(warped)
    return im


def paused(im):
    gray = ImageOps.grayscale(im.convert("RGB"))
    gray = ImageEnhance.Brightness(gray.convert("RGBA")).enhance(1.15)
    gray.putalpha(im.getchannel("A").point(lambda a: a * 0.75))
    return gray


def save_icon(toast, icon):
    toast.resize((512, 512), Image.LANCZOS).save(ROOT / "toast.png")  # 提示框里用的大图（COPIED）
    small = icon.resize((256, 256), Image.LANCZOS)
    small.save(ROOT / "icon.png")
    paused(small).save(ROOT / "icon_paused.png")
    small.save(ROOT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])


def variants():
    out_dir = ROOT / "variants"
    out_dir.mkdir(exist_ok=True)
    tiles = []
    for name, (f, var, stretch) in VARIANTS.items():
        im = build(f, var, stretch).resize((512, 512), Image.LANCZOS)
        im.save(out_dir / f"{name}.png")
        tiles.append((name, im))
    # 对比图：每格是放大的牌子 + 托盘实际大小
    cols, cw, ch = 4, 360, 400
    sheet = Image.new("RGB", (cols * cw, math.ceil(len(tiles) / cols) * ch), (250, 250, 250))
    d = ImageDraw.Draw(sheet)
    label = ImageFont.truetype("msyh.ttc", 20)
    for i, (name, im) in enumerate(tiles):
        x, y = (i % cols) * cw, (i // cols) * ch
        d.text((x + 14, y + 10), f"{i + 1}. {name}", font=label, fill=(40, 40, 40))
        crop = im.crop((215, 75, 512, 365)).resize((330, 322), Image.LANCZOS)
        sheet.paste(crop, (x + 14, y + 40), crop)
        strip = Image.new("RGB", (330, 30), (31, 31, 31))
        sx = 8
        for s in (16, 24, 32):
            ic = im.resize((s, s), Image.LANCZOS)
            strip.paste(ic, (sx, 15 - s // 2), ic)
            sx += s + 14
        sheet.paste(strip, (x + 14, y + 364))
    sheet.save(out_dir / "_compare.png")
    print("ok", out_dir)


def main():
    if sys.argv[1:] == ["variants"]:
        variants()
        return
    f, var, stretch = VARIANTS[CHOICE]
    save_icon(build(f, var, stretch), build(f, var, stretch, ICON_TEXT, ICON_TRACK))
    print("ok", CHOICE)


if __name__ == "__main__":
    main()
