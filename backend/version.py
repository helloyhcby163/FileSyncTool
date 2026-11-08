# -*- coding: utf-8 -*-
"""应用版本与 GitHub Releases 地址（与配置 schema 版本无关）。"""

import re

APP_VERSION = "7.8.0"
GITHUB_REPO = "helloyhcby163/FileSyncTool"
RELEASES_LATEST_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"

_VERSION_RE = re.compile(r"\d+")
# 标题末尾的版本号（如 " v7.6" / "v7.8.0"），用于纠正不含占位符的旧译文
_TITLE_VERSION_RE = re.compile(r"\s*v?\d+(?:\.\d+)*\s*$", re.IGNORECASE)


def format_app_title(text):
    """把界面标题文案中的 {version} 占位符替换为当前 APP_VERSION。

    兼容不含占位符的旧译文：去掉末尾的旧版本号后追加当前版本，
    保证外挂翻译目录里的历史文案也显示为最新版本；异常时退回原样文本。
    """
    raw = str(text or "").strip()
    if "{version}" in raw:
        try:
            return raw.format(version=APP_VERSION)
        except (KeyError, IndexError, ValueError):
            pass
    base = _TITLE_VERSION_RE.sub("", raw).strip()
    if not base:
        return raw
    return f"{base} v{APP_VERSION}"


def parse_version(value):
    """把 "v7.8.0" / "7.8" 解析为整数元组，无法解析的片段忽略。"""
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
