
"""
文件同步工具 v7.8.0 - 实时监控（watchdog 空闲触发）

监听任务源目录：文件发生任何变化后重置计时；连续 idle_seconds 秒
没有新变化时才触发一次同步，避免文件正在写入时被频繁触发。

上一次同步尚未结束时，新的触发请求会被跳过（不排队、不重叠）。
仅在 --watch 命令行常驻模式下使用，GUI 不内嵌监听循环。
"""

import os
import threading
import time
from typing import Callable, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 同步过程自身产生的临时/进度文件不触发同步
_IGNORE_SUFFIXES = (".sync.tmp",)
_IGNORE_NAMES = (".sync_progress.json",)


def _is_ignored(path: str, allow_hidden: bool = False) -> bool:
    """判断变化的文件是否应被忽略（同步临时文件、隐藏文件）

    v7.8.0 修复：任务开启 sync_hidden_files 时放行隐藏项，与同步逻辑保持一致。
    同步自身的临时/进度文件始终忽略。
    """
    name = os.path.basename(path)
    if not name:
        return True
    if name in _IGNORE_NAMES:
        return True
    if any(name.endswith(suffix) for suffix in _IGNORE_SUFFIXES):
        return True
    if name.startswith(".") and not allow_hidden:
        return True
    return False


class _IdleTriggerHandler(FileSystemEventHandler):
    """watchdog 事件处理：任何有效变化都重置空闲计时"""

    def __init__(self, notify: Callable[[str], None], allow_hidden: Callable[[], bool]):
        self._notify = notify
        # 每次事件实时求值，任务运行中修改 sync_hidden_files 也能立即生效
        self._allow_hidden = allow_hidden

    def on_created(self, event):
        self._handle(event)

    def on_modified(self, event):
        self._handle(event)

    def on_deleted(self, event):
        self._handle(event)

    def on_moved(self, event):
        self._handle(event)

    def _handle(self, event):
        path = getattr(event, "src_path", "")
        allow_hidden = self._allow_hidden()
        if event.is_directory:
            # 目录变化同样重置计时（如新建文件夹），隐藏目录按任务开关放行
            if allow_hidden or not os.path.basename(path).startswith("."):
                self._notify(path)
            return
        if not _is_ignored(path, allow_hidden):
            self._notify(path)


class WatchManager:
    """
    空闲触发式目录监听管理器。

    Args:
        watch_dir: 要监听的目录（任务源目录）
        idle_seconds: 空闲秒数，连续无变化达到该时长后触发（建议 3-300）
        on_trigger: 触发回调（在等待线程中调用，需自行保证线程安全）
        logger: 日志输出函数
    """

    # 心跳自检间隔（秒）：检查 observer 是否存活、监听目录是否仍可访问
    HEALTH_CHECK_INTERVAL = 10.0

    def __init__(
        self,
        watch_dir: str,
        idle_seconds: float = 10.0,
        on_trigger: Optional[Callable[[], None]] = None,
        logger: Callable[[str], None] = print,
        sync_hidden_files: bool = False,
    ):
        self.watch_dir = watch_dir
        # 与任务的 sync_hidden_files 保持一致：开启后隐藏文件变化同样触发同步
        self.sync_hidden_files = bool(sync_hidden_files)
        self.idle_seconds = max(1.0, float(idle_seconds))
        self._on_trigger = on_trigger
        self._log = logger

        self._observer: Optional[Observer] = None
        self._waiter: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()

        # 最近一次有效变化的时间戳；0 表示当前没有待触发的变化
        self._last_change = 0.0
        self._change_lock = threading.Lock()
        # 同步是否正在执行（防止重叠触发）
        self._sync_running = False

        # 监听健康状态："ok" / "error"（目录不可访问或 observer 已退出）
        self.status = "ok"
        self.last_error = ""
        self._last_health_check = 0.0

    def _notify_change(self, path: str = ""):
        """文件变化：重置空闲计时器"""
        with self._change_lock:
            self._last_change = time.monotonic()
        self._wake_event.set()

    def _wait_loop(self):
        """等待线程：检查“连续 N 秒无变化”的空闲条件"""
        while not self._stop_event.is_set():
            # 若已被 restart() 替换为新的 waiter 线程，旧线程立即退出
            if self._waiter is not threading.current_thread():
                return
            # v7.8.0：定时心跳自检（observer 存活 + 目录可访问）
            now = time.monotonic()
            if now - self._last_health_check >= self.HEALTH_CHECK_INTERVAL:
                self._last_health_check = now
                self._health_check()
            # 等待第一次变化或停止信号，避免空转
            self._wake_event.wait(timeout=1.0)
            if self._stop_event.is_set():
                return
            self._wake_event.clear()

            while not self._stop_event.is_set():
                if self._waiter is not threading.current_thread():
                    return
                with self._change_lock:
                    last_change = self._last_change
                if last_change == 0.0:
                    break  # 等待新的变化

                idle_for = time.monotonic() - last_change
                remaining = self.idle_seconds - idle_for
                if remaining <= 0:
                    # 达到空闲条件，触发同步
                    with self._change_lock:
                        self._last_change = 0.0
                    self._fire()
                    break
                # 剩余时间内被新变化唤醒则重新计时
                if self._wake_event.wait(timeout=min(remaining, 0.5)):
                    self._wake_event.clear()
                    continue

    def _health_check(self) -> bool:
        """心跳自检：observer 线程是否存活、监听目录是否仍可访问。

        Returns:
            True 表示健康；False 表示监听异常（已写入 status/last_error 并记录日志）
        """
        healthy = True
        reason = ""
        observer = self._observer
        if observer is None or not observer.is_alive():
            healthy = False
            reason = "监听线程已退出"
        if not os.path.isdir(self.watch_dir):
            healthy = False
            reason = "监听目录不可访问"

        previous = self.status
        if healthy:
            self.status = "ok"
            self.last_error = ""
            return True

        self.status = "error"
        self.last_error = reason
        # 只在状态由正常转为异常时记录一次，避免每 10 秒刷屏
        if previous != "error":
            self._log(f"监听异常（{reason}）：{self.watch_dir}")
        return False

    def _fire(self):
        """满足空闲条件后执行触发回调（上一次未结束则跳过）"""
        if self._sync_running:
            self._log("上一次同步仍在执行，跳过本次触发")
            return
        self._sync_running = True
        try:
            self._log(f"检测到文件变化且已空闲 {self.idle_seconds:g} 秒，开始同步")
            if self._on_trigger:
                self._on_trigger()
        except Exception as e:
            self._log(f"监听触发的同步失败: {e}")
        finally:
            self._sync_running = False
            self._log("监听已恢复，等待新的文件变化")

    def start(self) -> bool:
        """启动监听，目录不存在时返回 False"""
        if not os.path.isdir(self.watch_dir):
            self._log(f"监听目录不存在：{self.watch_dir}")
            return False

        self._stop_event.clear()
        self._wake_event.clear()
        self.status = "ok"
        self.last_error = ""
        self._last_health_check = time.monotonic()

        self._observer = Observer()
        self._observer.schedule(
            _IdleTriggerHandler(
                self._notify_change,
                lambda: self.sync_hidden_files,
            ),
            self.watch_dir,
            recursive=True,
        )
        self._observer.start()

        self._waiter = threading.Thread(target=self._wait_loop, daemon=True)
        self._waiter.start()

        self._log(
            f"开始监听 {self.watch_dir}（空闲 {self.idle_seconds:g} 秒后自动同步，Ctrl+C 退出）"
        )
        return True

    def stop(self):
        """停止监听"""
        self._stop_event.set()
        self._wake_event.set()
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
            self._observer = None
        if self._waiter is not None:
            # 若 stop() 由触发回调在 _waiter 线程内调用，不能 join 自己
            if self._waiter is not threading.current_thread():
                self._waiter.join(timeout=2)
            self._waiter = None
        self._log("监听已停止")

    def restart(self, new_watch_dir: Optional[str] = None) -> bool:
        """
        重新启动监听（用于源目录被修改的场景）。

        先停止现有 observer，再以新目录启动；new_watch_dir 为 None 时沿用原目录。
        """
        if new_watch_dir is not None:
            self.watch_dir = new_watch_dir
        self.stop()
        # 重置状态并重新启动
        self._stop_event.clear()
        self._wake_event.clear()
        return self.start()
