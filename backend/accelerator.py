# -*- coding: utf-8 -*-
"""下载加速：GitHub 镜像 URL 重写。

策略：
- GitHub 域名（github.com / raw.githubusercontent.com / objects.githubusercontent.com
  / gist.github.com）按顺序尝试镜像前缀，首个可连通（HTTP 探测通过）的镜像生效；
- 全部镜像不可达时回退原始 URL（"auto" 策略）；
- "always" 策略下即使探测全部失败也强制使用第一个镜像；
- "never" 策略不重写。

只做 URL 改写与连通性探测，不做实际下载（下载见 downloader.py）。
"""

import urllib.error
import urllib.request
from urllib.parse import urlparse

# GitHub 镜像前缀（按优先级排序）
MIRROR_PREFIXES = [
    "https://ghproxy.net/",
    "https://gh-proxy.com/",
    "https://ghproxy.homeboyc.cn/",
]

# 需要走镜像的 GitHub 域名
_GITHUB_HOSTS = (
    "github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com",
    "gist.github.com",
    "codeload.github.com",
)

STRATEGY_AUTO = "auto"      # 自动：镜像可达则加速，不可达回退原始 URL
STRATEGY_ALWAYS = "always"  # 始终开启：强制镜像（探测失败也用第一个）
STRATEGY_NEVER = "never"    # 始终关闭：原始 URL

# 当前策略（模块级，由 GUI 设置页写入；默认自动）
_strategy = STRATEGY_AUTO

# 已探测结果缓存：原始 URL -> 重写后 URL（避免每次下载重复探测）
_rewrite_cache = {}


def set_strategy(strategy):
    """设置加速策略：auto / always / never。"""
    global _strategy
    if strategy in (STRATEGY_AUTO, STRATEGY_ALWAYS, STRATEGY_NEVER):
        _strategy = strategy


def get_strategy():
    return _strategy


def is_github_url(url):
    """判断 URL 是否指向 GitHub 域名。"""
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return any(host == h or host.endswith("." + h) for h in _GITHUB_HOSTS)


def _probe(url, timeout=4):
    """HEAD 探测 URL 是否可达（允许 GET 兜底，部分镜像不支持 HEAD）。"""
    req = urllib.request.Request(url, method="HEAD",
                                 headers={"User-Agent": "EcoSeed"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400
    except urllib.error.HTTPError as exc:
        # 405 等说明服务在线但不支持 HEAD，认为可达
        return exc.code in (405, 403)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def rewrite_url(url, strategy=None, probe=True):
    """把 GitHub URL 重写为镜像 URL，返回 (最终URL, 使用的镜像前缀或空串)。

    strategy: None 用当前全局策略；probe=False 跳过连通性探测（直接取第一个镜像）。
    """
    strategy = strategy or _strategy
    if not url or strategy == STRATEGY_NEVER or not is_github_url(url):
        return url, ""

    if url in _rewrite_cache:
        cached = _rewrite_cache[url]
        return cached, _mirror_of(cached)

    chosen = ""
    if not probe:
        chosen = MIRROR_PREFIXES[0]
    else:
        for prefix in MIRROR_PREFIXES:
            if _probe(prefix + url):
                chosen = prefix
                break
        if not chosen and strategy == STRATEGY_ALWAYS:
            chosen = MIRROR_PREFIXES[0]

    final = (chosen + url) if chosen else url
    _rewrite_cache[url] = final
    return final, chosen


def _mirror_of(rewritten_url):
    for prefix in MIRROR_PREFIXES:
        if rewritten_url.startswith(prefix):
            return prefix
    return ""


def clear_cache():
    _rewrite_cache.clear()
