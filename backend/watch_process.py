
"""
文件同步工具 v7.6 - 后台监听子进程管理

GUI（工具包页面）通过本模块以独立进程启动 ``main.py --watch``：
- 子进程脱离 GUI 运行，关闭 GUI 后监听继续；
- PID 与启动参数记录在用户配置目录的 watchers.json 中，
  重新打开 GUI 后可读取运行状态并停止监听；
- 发现进程已退出时自动清理对应状态记录。

跨平台：
- Windows：DETACHED_PROCESS + 新进程组启动，taskkill /T /F 停止
- macOS/Linux：start_new_session 启动，向进程组发送 SIGTERM 停止
"""

import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .platform_utils import is_windows

STATE_FILENAME = "watchers.json"
LOG_DIRNAME = "watch_logs"
# 监听子进程同步进度状态文件，供 GUI「正在进行的任务」页轮询显示
WATCH_SYNC_STATUS_FILENAME = "watch_sync_status.json"


def _state_file(config_dir) -> Path:
    return Path(config_dir) / STATE_FILENAME


def _log_dir(config_dir) -> Path:
    return Path(config_dir) / LOG_DIRNAME


def _safe_name(name: str) -> str:
    """把任务名转成安全的文件名片段"""
    cleaned = re.sub(r'[\\/:*?"<>|\s]+', "_", name).strip("_")
    return cleaned[:60] or "task"


def is_process_alive(pid: int) -> bool:
    """判断指定 PID 的进程是否仍在运行（跨平台，不依赖 psutil）"""
    if pid <= 0:
        return False
    if is_windows():
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return exit_code.value == STILL_ACTIVE
                return False
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False
    return True


def _load_state(config_dir) -> Dict:
    """读取监听进程状态；损坏时视为空"""
    path = _state_file(config_dir)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(config_dir, state: Dict):
    """写入监听进程状态"""
    path = _state_file(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _prune_dead(state: Dict) -> Dict:
    """移除已经退出的监听记录"""
    alive = {}
    for name, info in state.items():
        pid = int(info.get("pid", 0))
        if is_process_alive(pid):
            alive[name] = info
    return alive


def list_watchers(config_dir) -> Dict:
    """
    返回当前仍在运行的监听：{任务名: {pid, idle, started_at, logfile}}。

    会顺带清理已退出进程的残留记录。
    """
    state = _prune_dead(_load_state(config_dir))
    if state != _load_state(config_dir):
        try:
            _save_state(config_dir, state)
        except Exception:
            pass
    return state


def _build_command(task_name: str, idle_seconds: int) -> List[str]:
    """构造监听子进程命令行"""
    if getattr(sys, "frozen", False):
        # 打包后：可执行文件自身支持 --watch
        return [
            sys.executable,
            "--watch", task_name,
            "--idle", str(idle_seconds),
            "--silent",
        ]
    # 开发阶段：当前解释器运行 main.py
    root = Path(__file__).resolve().parent.parent
    return [
        sys.executable,
        str(root / "main.py"),
        "--watch", task_name,
        "--idle", str(idle_seconds),
        "--silent",
    ]


def start_watcher(config_dir, task_name: str, idle_seconds: int) -> Dict:
    """
    启动一个后台监听进程。

    Returns:
        {"success": bool, "message": str, "pid": Optional[int]}
    """
    idle_seconds = int(idle_seconds)
    if not (3 <= idle_seconds <= 300):
        return {"success": False, "message": "空闲秒数必须在 3-300 之间", "pid": None}

    state = list_watchers(config_dir)
    if task_name in state:
        return {
            "success": False,
            "message": f"任务「{task_name}」已在监听中（PID {state[task_name].get('pid')}）",
            "pid": None,
        }

    log_dir = _log_dir(config_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"watch_{_safe_name(task_name)}.log"

    command = _build_command(task_name, idle_seconds)

    # 开发环境下以程序根目录为工作目录
    cwd = str(Path(__file__).resolve().parent.parent)

    try:
        log_file = open(log_path, "ab")
        # 继承当前环境并禁用子进程输出缓冲，保证监听日志实时写入文件
        child_env = dict(os.environ)
        child_env["PYTHONUNBUFFERED"] = "1"
        popen_kwargs = {
            "stdout": log_file,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
            "cwd": cwd,
            "close_fds": True,
            "env": child_env,
        }
        if is_windows():
            # 脱离当前控制台 + 独立进程组，关闭 GUI 不受影响
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            popen_kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        process = subprocess.Popen(command, **popen_kwargs)
        # Popen 已复制句柄给子进程，父进程侧及时关闭，避免长时间占用日志文件
        log_file.close()
    except Exception as e:
        try:
            log_file.close()
        except Exception:
            pass
        return {"success": False, "message": f"启动监听失败：{e}", "pid": None}

    state[task_name] = {
        "pid": process.pid,
        "idle": idle_seconds,
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "logfile": str(log_path),
    }
    try:
        _save_state(config_dir, state)
    except Exception as e:
        return {
            "success": True,
            "message": f"监听已启动（PID {process.pid}），但状态保存失败：{e}",
            "pid": process.pid,
        }

    return {
        "success": True,
        "message": f"已开始后台监听「{task_name}」（PID {process.pid}），关闭本窗口后仍会继续运行",
        "pid": process.pid,
    }


def stop_watcher(config_dir, task_name: str) -> Dict:
    """
    停止指定任务的后台监听进程。

    Returns:
        {"success": bool, "message": str}
    """
    state = _load_state(config_dir)
    info = state.get(task_name)
    if not info:
        # 状态里没有：顺手清理一次死记录
        cleaned = _prune_dead(state)
        if cleaned != state:
            _save_state(config_dir, cleaned)
        return {"success": False, "message": f"任务「{task_name}」当前未在监听"}

    pid = int(info.get("pid", 0))

    try:
        if is_windows():
            # /T 同时结束由该进程启动的子进程
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
            )
        else:
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    except Exception as e:
        # 终止命令失败时，如果进程其实已退出则按成功清理
        if is_process_alive(pid):
            return {"success": False, "message": f"停止监听失败：{e}"}

    # 从状态文件移除（无论记录中的进程是否还活着）
    state.pop(task_name, None)
    _save_state(config_dir, state)
    return {"success": True, "message": f"已停止监听「{task_name}」"}


def stop_all_watchers(config_dir) -> int:
    """停止全部后台监听（返回成功停止的数量）"""
    count = 0
    for task_name in list(_load_state(config_dir).keys()):
        if stop_watcher(config_dir, task_name)["success"]:
            count += 1
    return count


# ===================== 监听触发同步的进度状态（跨进程） =====================

def _watch_sync_status_file(config_dir) -> Path:
    return Path(config_dir) / WATCH_SYNC_STATUS_FILENAME


def update_watch_sync_status(config_dir, task_name: str, status: Dict) -> None:
    """
    监听子进程写入当前同步进度，供 GUI「正在进行的任务」页显示。

    status: {current_file, current_phase, total_files, completed_files,
             percentage, elapsed_time, estimated_remaining, speed}
    """
    path = _watch_sync_status_file(config_dir)
    try:
        data = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
            except Exception:
                data = {}
        data[task_name] = dict(status)
        data[task_name]["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def clear_watch_sync_status(config_dir, task_name: str) -> None:
    """移除某任务的监听同步进度记录"""
    path = _watch_sync_status_file(config_dir)
    try:
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and task_name in data:
            data.pop(task_name, None)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def get_watch_sync_statuses(config_dir, max_age_seconds: float = 600.0) -> Dict[str, Dict]:
    """
    读取当前监听触发的同步进度。
    自动清理超过 max_age_seconds 未更新的陈旧记录（子进程异常退出时）。
    """
    path = _watch_sync_status_file(config_dir)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}

    cutoff = datetime.now().timestamp() - max_age_seconds
    result: Dict[str, Dict] = {}
    stale = []
    for name, info in data.items():
        if not isinstance(info, dict):
            stale.append(name)
            continue
        updated = info.get("updated_at", "")
        try:
            ts = datetime.strptime(updated, "%Y-%m-%d %H:%M:%S").timestamp()
            if ts < cutoff:
                stale.append(name)
                continue
        except Exception:
            stale.append(name)
            continue
        result[name] = info

    if stale:
        for name in stale:
            data.pop(name, None)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass
    return result


def clear_watch_sync_statuses(config_dir) -> bool:
    """
    v7.6: 清空监听同步进度状态文件。

    停止全部监听子进程后调用，避免被终止子进程留下的
    陈旧"进行中"记录被 GUI 误报为同步仍在运行。

    Returns:
        是否成功清理（文件不存在视为成功）
    """
    try:
        path = _watch_sync_status_file(config_dir)
        if path.exists():
            path.unlink()
        return True
    except Exception:
        return False
