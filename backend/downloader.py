# -*- coding: utf-8 -*-
"""纯 Python 多线程分块下载器（v7.7.1）。

彻底废弃外部 aria2c 与 FastGithub，仅使用标准库，跨平台可用：
- ThreadPoolExecutor + HTTP Range 多线程分块下载；
- 文件较小 / 服务器不支持 Range / 大小未知时自动降级为单线程流式下载；
- 三层线路降级：GitHub 官方源 -> Gitee 源 -> 公共镜像前缀（ghproxy 等）；
- 通过 on_status 回调向 UI 报告当前线路，供进度条显示。

download(url, target_dir, progress_callback=None, on_status=None,
         strategy=None, timeout=30, threads=8) -> Path

on_status(dict) 字段：
    phase       running / done / error
    source      github / gitee / mirror（当前线路类型）
    url         实际下载 URL
    mirror      镜像前缀（source=mirror 时非空，否则空串）
    threads     并发线程数
    speed_kbps  当前速度 KB/s
    percent     0-100（总大小未知时为 -1）
    received    已接收字节数
    total       总字节数（未知为 -1）
    error       错误信息（仅 phase=error）

安全说明：本模块不调用任何外部程序，也不接受任何 shell 命令。
"""

import math
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urlparse, urlunparse

try:
    from . import accelerator
except ImportError:  # 以脚本方式直接运行本模块时
    import accelerator

DEFAULT_THREADS = 8
MIN_CHUNK_SIZE = 1024 * 1024      # 小于 1MB 不分块
READ_BLOCK = 64 * 1024            # 单次读取块大小
USER_AGENT = "FileSyncTool-Downloader"

# Gitee 仓库（与 .github/workflows/release.yml 中的同步目标保持一致）
GITEE_OWNER = "hello-yhc"
GITEE_REPO = "FileSyncTool"

SOURCE_GITHUB = "github"
SOURCE_GITEE = "gitee"
SOURCE_MIRROR = "mirror"


def _filename_from_url(url):
    name = Path(unquote(urlparse(url).path)).name
    return name or "download.bin"


def _gitee_url(url):
    """把 GitHub Release 下载链接映射为 Gitee 同名 Release 链接。

    仅处理 https://github.com/{owner}/{repo}/releases/download/{tag}/{asset}
    这类链接；其他链接返回空串，表示没有 Gitee 对应源。
    """
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() != "github.com":
        return ""
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 6 or parts[2] != "releases" or parts[3] != "download":
        return ""
    tail = "/".join(parts[2:])  # releases/download/{tag}/{asset...}
    return urlunparse(
        ("https", "gitee.com", f"/{GITEE_OWNER}/{GITEE_REPO}/{tail}", "", "", "")
    )


def _candidates(url, strategy=None):
    """按策略返回候选线路列表 [(source, url, mirror_prefix), ...]。

    auto   : GitHub 官方 -> Gitee -> 公共镜像
    always : 公共镜像 -> GitHub 官方 -> Gitee（优先走加速线路）
    never  : 仅 GitHub 官方
    """
    strategy = strategy or accelerator.get_strategy()

    if not accelerator.is_github_url(url):
        return [(SOURCE_GITHUB, url, "")]

    official = (SOURCE_GITHUB, url, "")
    gitee = _gitee_url(url)
    gitee_item = (SOURCE_GITEE, gitee, "https://gitee.com/") if gitee else None
    mirrors = [
        (SOURCE_MIRROR, prefix + url, prefix)
        for prefix in accelerator.MIRROR_PREFIXES
    ]

    if strategy == accelerator.STRATEGY_NEVER:
        return [official]
    if strategy == accelerator.STRATEGY_ALWAYS:
        items = mirrors + [official]
        if gitee_item:
            items.append(gitee_item)
        return items

    items = [official]
    if gitee_item:
        items.append(gitee_item)
    items.extend(mirrors)
    return items


def _probe(url, timeout):
    """HEAD 探测总大小与是否支持 Range，返回 (total, accepts_ranges)。

    探测失败返回 (-1, False)，由实际下载阶段决定后续行为。
    """
    try:
        req = urllib.request.Request(
            url, method="HEAD", headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length") or -1)
            accepts = (resp.headers.get("Accept-Ranges") or "").lower() == "bytes"
            return total, accepts
    except (urllib.error.URLError, OSError, ValueError):
        return -1, False


def _remove_partial(dest):
    try:
        Path(dest).unlink()
    except OSError:
        pass


class _Progress:
    """下载进度与状态聚合：线程安全累加、限频回调。"""

    def __init__(self, total, on_progress, on_status):
        self.total = total
        self.received = 0
        self.on_progress = on_progress
        self.on_status = on_status
        self.source = SOURCE_GITHUB
        self.url = ""
        self.mirror = ""
        self.threads = 1
        self._speed = 0.0
        self._lock = threading.Lock()
        self._last_emit = 0.0
        self._last_time = time.monotonic()
        self._last_bytes = 0

    def set_candidate(self, source, url, mirror, threads, total):
        with self._lock:
            self.source = source
            self.url = url
            self.mirror = mirror
            self.threads = threads
            self.total = total
            self.received = 0
            now = time.monotonic()
            self._last_time = now
            self._last_bytes = 0
            self._last_emit = 0.0
            self._speed = 0.0

    def set_total(self, total):
        with self._lock:
            if total > 0:
                self.total = total

    def add(self, count):
        now = time.monotonic()
        emit = False
        with self._lock:
            self.received += count
            received = self.received
            dt = now - self._last_time
            if dt >= 0.5:
                self._speed = (received - self._last_bytes) / dt / 1024.0
                self._last_time = now
                self._last_bytes = received
                if now - self._last_emit >= 0.5:
                    self._last_emit = now
                    emit = True

        if self.on_progress:
            try:
                self.on_progress(received, self.total)
            except Exception:  # noqa: BLE001
                pass
        if emit:
            self.emit("running")

    def emit(self, phase, error=""):
        if not self.on_status:
            return
        with self._lock:
            received = self.received
            total = self.total
            percent = (received * 100 // total) if total > 0 else -1
            payload = {
                "phase": phase,
                "source": self.source,
                "url": self.url,
                "mirror": self.mirror,
                "threads": self.threads,
                "speed_kbps": round(self._speed, 1),
                "percent": percent,
                "received": received,
                "total": total,
                "error": error,
            }
        try:
            self.on_status(payload)
        except Exception:  # noqa: BLE001
            pass


def _download_stream(url, dest, progress, timeout):
    """单线程流式下载（服务器不支持 Range 或文件较小时使用）。"""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp, \
            open(dest, "wb") as fh:
        length = int(resp.headers.get("Content-Length") or -1)
        if length > 0:
            progress.set_total(length)
        while True:
            block = resp.read(READ_BLOCK)
            if not block:
                break
            fh.write(block)
            progress.add(len(block))


def _download_ranges(url, dest, total, workers, progress, timeout):
    """ThreadPoolExecutor + HTTP Range 多线程分块下载。"""
    chunk_size = max(MIN_CHUNK_SIZE, math.ceil(total / workers))
    ranges = []
    start = 0
    while start < total:
        end = min(start + chunk_size - 1, total - 1)
        ranges.append((start, end))
        start = end + 1

    progress.set_candidate(
        progress.source, progress.url, progress.mirror, len(ranges), total
    )

    # 预分配文件，各线程按偏移写入，互不覆盖
    with open(dest, "wb") as fh:
        fh.truncate(total)

    abort_event = threading.Event()

    def fetch(start_byte, end_byte):
        if abort_event.is_set():
            return
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Range": f"bytes={start_byte}-{end_byte}",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 206:
                raise RuntimeError("服务器不支持分段下载")
            remaining = end_byte - start_byte + 1
            with open(dest, "r+b") as fh:
                fh.seek(start_byte)
                while remaining > 0:
                    if abort_event.is_set():
                        return
                    block = resp.read(min(READ_BLOCK, remaining))
                    if not block:
                        raise RuntimeError("连接中断，分块未下载完整")
                    fh.write(block)
                    remaining -= len(block)
                    progress.add(len(block))

    with ThreadPoolExecutor(max_workers=len(ranges)) as pool:
        futures = [pool.submit(fetch, s, e) for s, e in ranges]
        try:
            for future in as_completed(futures):
                future.result()
        except Exception:
            abort_event.set()
            for future in futures:
                future.cancel()
            raise

    if Path(dest).stat().st_size != total:
        raise RuntimeError("下载文件大小与预期不一致")


def download(url, target_dir, progress_callback=None, on_status=None,
             strategy=None, timeout=30, threads=DEFAULT_THREADS):
    """下载 url 到 target_dir，返回下载后的文件 Path。

    progress_callback(received, total)：字节进度（与 requests 风格一致）。
    on_status(dict)：线路/线程/速度状态回调，见模块 docstring。
    失败抛 RuntimeError。
    """
    if not url:
        raise RuntimeError("下载地址为空")

    target = Path(target_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    dest = (target / _filename_from_url(url)).resolve()

    progress = _Progress(-1, progress_callback, on_status)
    candidates = _candidates(url, strategy)
    errors = []

    for source, candidate_url, mirror in candidates:
        progress.set_candidate(source, candidate_url, mirror, 1, -1)
        progress.emit("running")
        try:
            total, accepts_ranges = _probe(candidate_url, timeout)
            if total > 0:
                progress.set_total(total)

            workers = 1
            if total >= MIN_CHUNK_SIZE * 2 and accepts_ranges:
                workers = max(1, min(threads, int(math.ceil(total / MIN_CHUNK_SIZE))))

            progress.set_candidate(source, candidate_url, mirror, workers, total)

            if workers > 1:
                try:
                    _download_ranges(
                        candidate_url, dest, total, workers, progress, timeout
                    )
                except Exception:  # noqa: BLE001
                    # 分块失败（镜像可能不支持 Range）：同线路降级单线程
                    _remove_partial(dest)
                    progress.set_candidate(source, candidate_url, mirror, 1, total)
                    _download_stream(candidate_url, dest, progress, timeout)
            else:
                _download_stream(candidate_url, dest, progress, timeout)

            progress.emit("done")
            return dest
        except Exception as exc:  # noqa: BLE001
            _remove_partial(dest)
            errors.append(f"{source}: {exc}")

    progress.emit("error", error="；".join(errors))
    raise RuntimeError("下载失败：" + "；".join(errors))
