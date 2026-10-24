# -*- coding: utf-8 -*-
"""多线程下载器：优先 aria2，降级 Python 单线程，可选 FastGithub 补充加速。

download(url, target_dir, progress_callback=None, on_status=None, strategy=None)
    1. GitHub URL 先经 accelerator.rewrite_url 镜像重写（策略 auto/always）；
    2. 存在 tools/aria2c.exe 则用其 16 线程下载（-x 16 -s 16）；
       不存在则降级 urllib 单线程；
    3. 下载期间监测速度，GitHub 资源持续低速（< _SLOW_KBPS）且
       tools/fastgithub.exe 存在时启动它补充加速（每进程只启动一次）；
    4. "never" 策略下不做任何加速：原始 URL + 单线程。

on_status(dict) 回调字段：
    phase       running / done / error
    mirror      生效的镜像前缀（无则空串）
    threads     并发线程数（aria2=16，单线程=1）
    fastgithub  是否已启动 FastGithub
    speed_kbps  当前速度 KB/s
    percent     0-100（总大小未知时为 -1）
    url         实际下载 URL
"""

import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse, unquote

try:
    from . import accelerator
except ImportError:  # 以脚本方式直接运行本模块时
    import accelerator

_ARIA2_THREADS = 16
_SLOW_KBPS = 256            # 低于此速度视为"低速"
_SLOW_WINDOW_SEC = 6        # 持续低速时长阈值
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"

# FastGithub 每进程最多启动一次
_fastgithub_started = False


def _aria2_exe():
    exe = _TOOLS_DIR / "aria2" / "aria2c.exe"
    return exe if exe.is_file() else None


def _fastgithub_exe():
    exe = _TOOLS_DIR / "fastgithub" / "FastGithub.UI.exe"
    return exe if exe.is_file() else None


def _filename_from_url(url):
    name = Path(unquote(urlparse(url).path)).name
    return name or "download.bin"


def _remote_size(url, timeout=6):
    """HEAD 获取 Content-Length，失败返回 -1。"""
    req = urllib.request.Request(url, method="HEAD",
                                 headers={"User-Agent": "EcoSeed"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.headers.get("Content-Length") or -1)
    except (urllib.error.URLError, OSError, ValueError):
        return -1


def _maybe_start_fastgithub(url, on_status):
    """GitHub 资源低速时启动 FastGithub 补充加速（幂等，每进程一次）。"""
    global _fastgithub_started
    if _fastgithub_started or not accelerator.is_github_url(url):
        return False
    exe = _fastgithub_exe()
    if not exe:
        return False
    try:
        subprocess.Popen([str(exe)], creationflags=_NO_WINDOW,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _fastgithub_started = True
        return True
    except OSError:
        return False


class _Status:
    """下载状态聚合：速度采样、低速判定、对外回调。"""

    def __init__(self, url, mirror, threads, total, on_status):
        self.url = url
        self.mirror = mirror
        self.threads = threads
        self.total = total
        self.on_status = on_status
        self.fastgithub = False
        self._start = time.monotonic()
        self._last_time = self._start
        self._last_bytes = 0
        self._slow_since = None

    def tick(self, received):
        now = time.monotonic()
        dt = now - self._last_time
        if dt < 0.5:
            return
        speed = (received - self._last_bytes) / dt / 1024.0
        self._last_time = now
        self._last_bytes = received
        percent = (received * 100 // self.total) if self.total > 0 else -1
        # 持续低速且是 GitHub 资源 → 启动 FastGithub
        if speed < _SLOW_KBPS:
            if self._slow_since is None:
                self._slow_since = now
            elif not self.fastgithub and now - self._slow_since >= _SLOW_WINDOW_SEC:
                self.fastgithub = _maybe_start_fastgithub(self.url, self.on_status)
        else:
            self._slow_since = None
        self.emit("running", received, speed, percent)

    def emit(self, phase, received=0, speed=0.0, percent=-1, error=""):
        if not self.on_status:
            return
        try:
            self.on_status({
                "phase": phase,
                "url": self.url,
                "mirror": self.mirror,
                "threads": self.threads,
                "fastgithub": self.fastgithub,
                "speed_kbps": round(speed, 1),
                "percent": percent,
                "received": received,
                "total": self.total,
                "error": error,
            })
        except Exception:  # noqa: BLE001
            pass


def download(url, target_dir, progress_callback=None, on_status=None,
             strategy=None, timeout=30):
    """下载 url 到 target_dir，返回下载后的文件 Path。

    progress_callback(received, total)：与 requests 风格一致的进度回调。
    on_status(dict)：加速状态回调（镜像/线程数/FastGithub/速度），见模块 docstring。
    失败抛 RuntimeError。
    """
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    dest = target / _filename_from_url(url)

    strategy = strategy or accelerator.get_strategy()
    if strategy == accelerator.STRATEGY_NEVER:
        final_url, mirror, use_aria2 = url, "", False
    else:
        final_url, mirror = accelerator.rewrite_url(url, strategy=strategy)
        use_aria2 = _aria2_exe() is not None

    threads = _ARIA2_THREADS if use_aria2 else 1
    total = _remote_size(final_url)
    status = _Status(url, mirror, threads, total, on_status)

    def on_progress(received, _total=total):
        if progress_callback:
            try:
                progress_callback(received, _total)
            except Exception:  # noqa: BLE001
                pass
        status.tick(received)

    try:
        if use_aria2:
            _download_aria2(final_url, dest, on_progress)
        else:
            _download_urllib(final_url, dest, on_progress, timeout)
    except Exception as exc:  # noqa: BLE001
        # aria2 失败时降级单线程再试一次（镜像可能不支持分段）
        if use_aria2:
            status.threads = 1
            try:
                _download_urllib(final_url, dest, on_progress, timeout)
            except Exception as exc2:  # noqa: BLE001
                status.emit("error", error=str(exc2))
                raise RuntimeError(f"下载失败: {exc2}") from exc2
        else:
            status.emit("error", error=str(exc))
            raise RuntimeError(f"下载失败: {exc}") from exc

    status.emit("done", received=dest.stat().st_size,
                percent=100)
    return dest


def _download_urllib(url, dest, on_progress, timeout):
    """单线程下载（urllib），64KB 分块。"""
    req = urllib.request.Request(url, headers={"User-Agent": "EcoSeed"})
    received = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp, \
            open(dest, "wb") as fh:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            fh.write(chunk)
            received += len(chunk)
            on_progress(received)


def _download_aria2(url, dest, on_progress):
    """调用 tools/aria2c.exe 16 线程下载，轮询文件大小回报进度。"""
    exe = _aria2_exe()
    cmd = [
        str(exe),
        "-x", str(_ARIA2_THREADS), "-s", str(_ARIA2_THREADS),
        "--console-log-level=warn", "--summary-interval=0",
        "--allow-overwrite=true",
        "-d", str(dest.parent), "-o", dest.name,
        url,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, creationflags=_NO_WINDOW)
    try:
        while proc.poll() is None:
            if dest.is_file():
                on_progress(dest.stat().st_size)
            time.sleep(0.5)
    finally:
        if proc.poll() is None:
            proc.kill()
    if proc.returncode != 0:
        raise RuntimeError(f"aria2 退出码 {proc.returncode}")
    if dest.is_file():
        on_progress(dest.stat().st_size)
