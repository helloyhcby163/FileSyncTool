"""通知管理器 - 跨平台通知支持

v7.4 修复：
- 通知失败时静默降级，不影响主功能
- 线程安全：通知在独立线程中发送，避免阻塞 UI
- 多级 fallback：plyer → 控制台输出 → 静默
"""

import threading
from pathlib import Path
import os

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


class NotificationManager:
    """通知管理器"""

    def __init__(self, app=None):
        """
        初始化通知管理器

        Args:
            app: 主应用实例（可选，用于点击通知时激活窗口）
        """
        self.app = app
        self.enabled = True

        if not PLYER_AVAILABLE:
            print("⚠️  plyer 未安装，通知功能不可用。安装命令：pip install plyer")

    def set_app(self, app):
        """设置应用引用，用于点击通知时激活窗口"""
        self.app = app

    def send_notification(self, title, message, clickable=True):
        """
        发送系统通知（线程安全，失败时静默降级）

        通知在独立线程中发送，避免阻塞 UI 线程。
        如果 plyer 不可用或通知发送失败，静默降级为控制台输出，
        不影响主功能。

        Args:
            title: 通知标题
            message: 通知内容
            clickable: 是否可点击（保留参数，暂未使用）
        """
        if not self.enabled:
            return

        # 在独立线程中发送通知，避免阻塞
        notify_thread = threading.Thread(
            target=self._send_notification_threaded,
            args=(title, message),
            daemon=True
        )
        notify_thread.start()

    def _send_notification_threaded(self, title, message):
        """
        在线程中实际发送通知（带多级 fallback）

        fallback 链：plyer 通知 → 控制台输出 → 静默
        """
        if not PLYER_AVAILABLE:
            # fallback：plyer 不可用，输出到控制台
            print(f"📢 [通知] {title}: {message}")
            return

        try:
            notification.notify(
                title=title,
                message=message,
                timeout=10,
                app_name="文件同步工具"
            )
        except Exception as e:
            # fallback：通知发送失败，静默降级为控制台输出
            # 不影响主功能
            print(f"📢 [通知-fallback] {title}: {message}")
            print(f"   (系统通知发送失败: {e})")

    def send_sync_complete(self, task_name, file_count, has_errors=False):
        """发送同步完成通知"""
        if has_errors:
            title = f"⚠️ 同步完成（有错误）"
            message = f"任务「{task_name}」完成，但存在错误"
        else:
            title = f"✅ 同步完成"
            message = f"任务「{task_name}」已完成，共 {file_count} 个文件"
        self.send_notification(title, message)

    def send_sync_interrupted(self, task_name):
        """发送同步被打断通知"""
        self.send_notification(
            "⏸️ 同步已中断",
            f"任务「{task_name}」已保存为打断任务"
        )
