# -*- coding: utf-8 -*-
"""异常退出检测：启动时创建运行锁，正常退出时删除。

若启动时发现锁文件且其中记录的进程已不存在，则判定上次为异常退出。
仅使用标准库，任何失败都静默降级，不影响主程序启动。
"""

import json
import os
from datetime import datetime
from pathlib import Path

LOCK_FILENAME = "running.lock"
_STILL_ACTIVE = 259

_lock_file = None


def _pid_alive(pid):
    """判断进程是否仍存活（失败时视为不存活）。"""
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return code.value == _STILL_ACTIVE
                return False
            finally:
                kernel32.CloseHandle(handle)
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def acquire(config_dir):
    """创建运行锁；返回 True 表示检测到上次异常退出。

    若锁中的进程仍存活（另一个实例正在运行），不覆盖锁并返回 False。
    """
    global _lock_file
    path = Path(config_dir) / LOCK_FILENAME
    crashed = False
    try:
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            pid = int(data.get("pid", 0) or 0)
            if pid and pid != os.getpid() and _pid_alive(pid):
                return False
            crashed = True

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"pid": os.getpid(), "started_at": datetime.now().isoformat(timespec="seconds")},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        _lock_file = path
    except Exception as exc:  # noqa: BLE001
        print(f"创建运行锁失败: {exc}")
    return crashed


def release():
    """正常退出时删除运行锁。"""
    global _lock_file
    try:
        if _lock_file is not None and _lock_file.is_file():
            _lock_file.unlink()
    except Exception as exc:  # noqa: BLE001
        print(f"删除运行锁失败: {exc}")
    finally:
        _lock_file = None
