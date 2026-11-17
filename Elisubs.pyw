"""双击启动（pythonw / 打包后的 Elisubs.exe，没有黑窗口）。

自检：Elisubs --selftest 图片路径
  用包里的模型识别这张图，结果写进 data/selftest.txt 后退出（不开界面）。
  用来确认打包完整、模型能加载；朋友那边识别不了时也可以让她跑一下。
"""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))


def selftest(img_path):
    import time
    import traceback

    from PIL import Image

    from elisubs import paths
    out = paths.DATA / "selftest.txt"
    try:
        from elisubs.lines import merge
        from elisubs.ocr import Ocr
        t = time.time()
        text = merge(Ocr().read(Image.open(img_path)))
        out.write_text(f"OK {time.time() - t:.1f}s\n{text}\n", encoding="utf-8")
    except Exception:  # noqa: BLE001
        out.write_text("FAIL\n" + traceback.format_exc(), encoding="utf-8")


if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
    selftest(sys.argv[2])
else:
    from elisubs.app import main
    main()
