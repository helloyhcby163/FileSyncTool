"""文件同步工具 v7.8.0 - 系统资源守护

独立后台线程采样 CPU / 可用内存；同步主循环只调用轻量 `tick()` 读取缓存状态，
避免在扫描/复制线程中直接调用 psutil 拖慢性能。

当 CPU 占用 > 90% 或可用内存 < 500MB 时，`tick()` 返回 True，由调用方 sleep(0.5) 降速；
连续多次触发时，找出占用最高的非本程序进程，并通过 notification_manager 提示用户。
"""

import os
import threading
import time
from typing import Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False


class ResourceGuard:
    """同步资源守护（psutil 缺失时自动禁用，所有方法安全 no-op）"""

    def __init__(
        self,
        enabled: bool = True,
        cpu_threshold: float = 90.0,
        memory_threshold_mb: float = 500.0,
        sample_interval: float = 2.0,
        max_consecutive: int = 3,
        notify_cooldown: float = 60.0,
        notification_manager=None,
    ):
        self.enabled = bool(enabled) and PSUTIL_AVAILABLE
        self.cpu_threshold = float(cpu_threshold)
        self.memory_threshold_mb = float(memory_threshold_mb)
        self.sample_interval = max(0.5, float(sample_interval))
        self.max_consecutive = max(1, int(max_consecutive))
        self.notify_cooldown = max(1.0, float(notify_cooldown))
        self.notification_manager = notification_manager

        self._lock = threading.Lock()
        self._throttle_active = False
        self._consecutive = 0
        self._top_offender = ""
        self._last_notify = 0.0
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ===================== 生命周期 =====================

    def start(self):
        """启动后台监控线程"""
        if not self.enabled:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop, name="ResourceGuard", daemon=True
        )
        self._thread.start()

    def stop(self):
        """停止后台监控线程（同步结束/异常/中断时均调用）"""
        if self._thread is None:
            return
        self._stop_event.set()
        try:
            self._thread.join(timeout=2.0)
        except RuntimeError:
            pass
        self._thread = None
        with self._lock:
            self._throttle_active = False
            self._consecutive = 0

    # ===================== 主线程轻量钩子 =====================

    def tick(self) -> bool:
        """每处理 100 个文件调用一次；返回 True 表示应 sleep(0.5) 降速"""
        if not self.enabled:
            return False

        now = time.time()
        with self._lock:
            active = self._throttle_active
            offender = self._top_offender
            should_notify = (
                active
                and bool(offender)
                and (now - self._last_notify) >= self.notify_cooldown
            )
            if should_notify:
                self._last_notify = now

        if should_notify:
            self._notify_slowdown(offender)
        return active

    # ===================== 后台采样 =====================

    def _monitor_loop(self):
        """周期性采样 CPU 与可用内存，更新缓存状态"""
        try:
            psutil.cpu_percent(interval=None)  # 预热，首次采样才有意义
        except Exception:
            pass

        while not self._stop_event.is_set():
            cpu = 0.0
            available_mb = float("inf")
            try:
                cpu = float(psutil.cpu_percent(interval=None))
                available_mb = psutil.virtual_memory().available / (1024 * 1024)
            except Exception:
                cpu, available_mb = 0.0, float("inf")

            high = cpu >= self.cpu_threshold or available_mb < self.memory_threshold_mb

            with self._lock:
                if high:
                    self._throttle_active = True
                    self._consecutive += 1
                else:
                    self._throttle_active = False
                    self._consecutive = 0
                # v7.8.0 修复：在锁内取快照，避免锁外读取被 stop()/其他线程改写
                consecutive = self._consecutive

            if high and consecutive >= self.max_consecutive:
                offender = self._find_top_offender()
                with self._lock:
                    self._top_offender = offender

            self._stop_event.wait(self.sample_interval)

    def _find_top_offender(self) -> str:
        """找出占用最高的非本程序进程名（优先 CPU，其次内存）"""
        if not PSUTIL_AVAILABLE:
            return ""
        own_pid = os.getpid()
        best_name = ""
        best_score = -1.0
        try:
            for proc in psutil.process_iter(
                ["pid", "name", "cpu_percent", "memory_percent"]
            ):
                try:
                    info = proc.info
                    pid = int(info.get("pid") or 0)
                    if pid == own_pid:
                        continue
                    name = str(info.get("name") or "").strip()
                    if not name or name.lower() in ("system idle process", "idle"):
                        continue
                    score = float(info.get("cpu_percent") or 0.0) + float(
                        info.get("memory_percent") or 0.0
                    )
                    if score > best_score:
                        best_score = score
                        best_name = name
                except Exception:
                    continue
        except Exception:
            return ""
        return best_name

    def _notify_slowdown(self, process_name: str):
        """通过 notification_manager 提示用户（自动适配当前语言）"""
        manager = self.notification_manager
        if manager is None:
            return

        title = "同步已自动降速"
        message = f"由于 {process_name} 占用过高，同步已自动降速"

        app = getattr(manager, "app", None)
        get_text = getattr(app, "get_text", None)
        if callable(get_text):
            try:
                title = get_text("resource_guard_slowdown_title", title)
                template = get_text(
                    "resource_guard_slowdown_message",
                    "由于 {process} 占用过高，同步已自动降速",
                )
                message = template.format(process=process_name)
            except (KeyError, IndexError, ValueError, TypeError):
                pass

        try:
            manager.send_notification(title, message)
        except Exception:
            pass
