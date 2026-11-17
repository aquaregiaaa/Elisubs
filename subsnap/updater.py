"""检查更新：问 GitHub 最新 Release 的版本号，比当前版本新就提示。

只发一个不带任何个人信息的请求（api.github.com/repos/<仓库>/releases/latest）。
"""
import json
import re
import urllib.request

from . import REPO, __version__

API = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGE = f"https://github.com/{REPO}/releases/latest"


def _ver(s):
    return tuple(int(x) for x in re.findall(r"\d+", s)[:3])


def latest():
    """返回 (最新版本号, 是否比当前新)。网络问题会抛异常。"""
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"subsnap/{__version__}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        tag = json.loads(r.read().decode("utf-8"))["tag_name"]
    return tag.lstrip("v"), _ver(tag) > _ver(__version__)
