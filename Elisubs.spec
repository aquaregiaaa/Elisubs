# PyInstaller 打包配置：python -m PyInstaller Elisubs.spec --noconfirm
# 产物在 dist/Elisubs/（文件夹版，双击 Elisubs.exe）。
import os
from pathlib import Path

import rapidocr
from PyInstaller.utils.hooks import collect_submodules

RAPID = Path(rapidocr.__file__).parent
MODELS = ["PP-OCRv6_det_small.onnx", "PP-OCRv6_rec_small.onnx", "ch_ppocr_mobile_v2.0_cls_mobile.onnx"]

datas = [
    ("assets/icon.png", "assets"),
    ("assets/icon_paused.png", "assets"),
    ("assets/toast.png", "assets"),
    ("assets/icon.ico", "assets"),
    (str(RAPID / "config.yaml"), "rapidocr"),
    (str(RAPID / "default_models.yaml"), "rapidocr"),
] + [(str(RAPID / "models" / m), "rapidocr/models") for m in MODELS]  # 只带默认那套小模型

hidden = [m for m in collect_submodules("rapidocr")
          if not any(e in m for e in ("tensorrt", "openvino", "paddle", "pytorch", "mnn"))]

a = Analysis(
    ["Elisubs.pyw"],
    pathex=[],
    datas=datas,
    hiddenimports=hidden + ["pystray._win32"],
    excludes=["scipy", "matplotlib", "pandas", "torch", "tensorflow", "IPython", "jupyter",
              "rapidocr.inference_engine.tensorrt", "rapidocr.inference_engine.openvino",
              "rapidocr.inference_engine.paddle", "rapidocr.inference_engine.pytorch",
              "rapidocr.inference_engine.mnn"],
    noarchive=False,
)
# OpenCV 自带的视频解码库（每个 25MB+），截图识别用不到
a.binaries = [b for b in a.binaries if "opencv_videoio_ffmpeg" not in b[0]]

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Elisubs", console=False,
          icon="assets/icon.ico", upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="Elisubs", upx=False)
