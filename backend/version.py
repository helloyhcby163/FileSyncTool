# -*- coding: utf-8 -*-
"""应用版本与 GitHub Releases 地址（与配置 schema 版本无关）。"""

import re

APP_VERSION = "7.7"
GITHUB_REPO = "helloyhcby163/FileSyncTool"
RELEASES_LATEST_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"

_VERSION_RE = re.compile(r"\d+")


def parse_version(value):
    """把 "v7.7.1" / "7.7" 解析为整数元组，无法解析的片段忽略。"""
    parts = _VERSION_RE.findall(str(value or ""))
    return tuple(int(p) for p in parts)


def is_newer(latest, current=APP_VERSION):
    """latest 是否比 current 新（逐段比较，缺失段按 0）。"""
    a, b = parse_version(latest), parse_version(current)
    if not a:
        return False
    length = max(len(a), len(b))
    a += (0,) * (length - len(a))
    b += (0,) * (length - len(b))
    return a > b
