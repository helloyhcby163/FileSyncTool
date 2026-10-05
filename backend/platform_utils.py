"""
跨平台工具模块
提供平台检测和跨平台兼容函数
"""

import sys
import os
import locale
from pathlib import Path


def get_resource_path(relative_path: str) -> Path:
    """
    获取资源文件的绝对路径（兼容 PyInstaller 打包环境）

    打包后资源被解压到 sys._MEIPASS 临时目录；
    开发环境下资源位于程序根目录。

    Args:
        relative_path: 相对于程序根目录的资源路径

    Returns:
        资源文件的绝对 Path 对象
    """
    if getattr(sys, '_MEIPASS', False):
        return Path(sys._MEIPASS) / relative_path
    # 开发环境：platform_utils.py 位于 backend/ 下，根目录是其上一级
    return Path(__file__).resolve().parent.parent / relative_path


def get_app_root_dir() -> Path:
    """
    获取应用程序根目录（开发环境为源码目录，打包环境为可执行文件所在目录）

    Returns:
        应用程序根目录 Path
    """
    if getattr(sys, '_MEIPASS', False):
        # 打包环境：可执行文件所在目录
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).resolve().parent
        return Path(sys._MEIPASS)
    # 开发环境
    return Path(__file__).resolve().parent.parent


def get_log_file_path() -> Path:
    """
    获取日志文件路径（写入用户配置目录，确保打包后有写权限）

    Returns:
        日志文件 Path 对象
    """
    return get_default_config_dir() / "filesynctool.log"


def detect_system_language() -> str:
    """
    自动检测系统语言，返回语言代码候选（如 'zh', 'zh_tw', 'en', 'fr'）。

    本函数只负责检测：translations/ 目录下是否存在对应语言文件，
    由 LanguageManager 判断；不支持的语言由其回退到 'en'，
    'en' 不可用时再回退到 'zh'。检测失败时返回 'en'。

    中文子语言规则：台/港/澳及繁体标记归为 'zh_tw'，其余中文归为 'zh'；
    其他语言返回主语言代码（如 'en_US' -> 'en'、'fr_FR' -> 'fr'）。

    Returns:
        语言代码字符串
    """
    raw_locale = None
    try:
        raw_locale = locale.getdefaultlocale()[0]
    except Exception:
        raw_locale = None

    # getdefaultlocale 失败时（常见于部分 Linux/macOS 环境）回退到环境变量
    if not raw_locale:
        raw_locale = (
            os.environ.get("LC_ALL")
            or os.environ.get("LC_MESSAGES")
            or os.environ.get("LANG")
        )

    if not raw_locale:
        return "en"

    # 形如 "zh_TW.UTF-8" / "fr_FR.utf8" / "English_US"
    code = raw_locale.split(".")[0].strip().lower().replace("-", "_")
    if not code or code in ("c", "posix"):
        return "en"

    # 中文：繁体优先识别
    if code.startswith("zh"):
        traditional_tags = ("zh_tw", "zh_hk", "zh_mo", "zh_hant")
        if code in traditional_tags or code.endswith(("_tw", "_hk", "_mo", "_hant")):
            return "zh_tw"
        return "zh"

    # 其他语言取主语言代码
    return code.split("_")[0] or "en"


def get_platform() -> str:
    """获取当前平台"""
    return sys.platform


def is_windows() -> bool:
    """是否为 Windows 平台"""
    return sys.platform == "win32"


def is_macos() -> bool:
    """是否为 macOS 平台"""
    return sys.platform == "darwin"


def is_linux() -> bool:
    """是否为 Linux 平台"""
    return sys.platform.startswith("linux")


def is_posix() -> bool:
    """是否为 POSIX 平台（macOS/Linux）"""
    return sys.platform in ("darwin", "linux") or sys.platform.startswith("linux")


def get_drive_letter(path: str) -> str:
    """
    获取路径的盘符（仅 Windows）
    
    Args:
        path: 文件路径
        
    Returns:
        盘符（如 "C:"），非 Windows 返回空字符串
    """
    if is_windows():
        return os.path.splitdrive(os.path.abspath(path))[0]
    return ""


def get_mount_point(path: str) -> str:
    """
    获取路径的挂载点
    
    Args:
        path: 文件路径
        
    Returns:
        挂载点路径
    """
    path = os.path.abspath(path)
    
    if is_windows():
        return get_drive_letter(path) + "\\"
    
    try:
        import subprocess
        result = subprocess.run(
            ["df", "-P", path],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                return lines[1].split()[5]
    except Exception:
        pass
    
    return "/"


def is_removable_disk(path: str) -> bool:
    """
    检测路径是否在可移动磁盘上（跨平台）
    
    Args:
        path: 文件路径
        
    Returns:
        是否为可移动磁盘
    """
    if is_windows():
        return _is_removable_disk_windows(path)
    elif is_macos():
        return _is_removable_disk_macos(path)
    elif is_linux():
        return _is_removable_disk_linux(path)
    else:
        return False


def _is_removable_disk_windows(path: str) -> bool:
    """Windows 平台：使用 GetDriveTypeW 检测可移动磁盘"""
    try:
        import ctypes
        drive_letter = get_drive_letter(path)
        if not drive_letter:
            return False
        
        drive_path = drive_letter + "\\"
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_path)
        
        return drive_type == 2
    except Exception:
        return False


def _is_removable_disk_macos(path: str) -> bool:
    """macOS 平台：检测挂载点是否在 /Volumes/ 下"""
    try:
        mount_point = get_mount_point(path)
        return mount_point.startswith("/Volumes/")
    except Exception:
        return False


def _is_removable_disk_linux(path: str) -> bool:
    """Linux 平台：检测挂载点是否在 /media/ 或 /mnt/ 下"""
    try:
        mount_point = get_mount_point(path)
        return mount_point.startswith("/media/") or mount_point.startswith("/mnt/")
    except Exception:
        return False


def get_path_identifier(path: str) -> str:
    """
    获取路径的唯一标识符（用于跨平台路径转换）
    
    Args:
        path: 文件路径
        
    Returns:
        路径标识符（不含特殊字符）
    """
    original_path = Path(path)
    
    if is_windows():
        identifier = str(original_path).replace(":", "").replace("\\", "_").replace("/", "_")
    else:
        identifier = str(original_path).replace("/", "_")
    
    return identifier


def get_default_config_dir() -> Path:
    """
    获取默认配置目录（跨平台）
    
    Returns:
        配置目录路径
    """
    if is_windows():
        return Path(os.environ.get("APPDATA", str(Path.home() / ".config"))) / "FileSyncTool"
    elif is_macos():
        return Path.home() / "Library" / "Application Support" / "FileSyncTool"
    else:
        return Path.home() / ".config" / "FileSyncTool"


def get_default_recycle_dir() -> Path:
    """
    获取默认回收站目录（跨平台）
    
    Returns:
        回收站目录路径
    """
    return get_default_config_dir() / "recycle"


def get_default_data_dir() -> Path:
    """
    获取默认数据目录（跨平台）
    
    Returns:
        数据目录路径
    """
    return get_default_config_dir() / "data"


def get_target_root_path(path: str) -> str:
    """
    获取目标目录根路径（用于U盘脱落检测）
    
    Args:
        path: 文件路径
        
    Returns:
        根路径
    """
    if is_windows():
        return os.path.splitdrive(path)[0] + "\\"
    else:
        return get_mount_point(path)


def normalize_path(path: str) -> str:
    """
    规范化路径（跨平台）
    
    Args:
        path: 文件路径
        
    Returns:
        规范化后的路径
    """
    return str(Path(path).resolve())


def get_file_encoding() -> str:
    """
    获取默认文件编码
    
    Returns:
        编码名称
    """
    return "utf-8"


def get_newline_char() -> str:
    """
    获取换行符

    Returns:
        换行符
    """
    return "\n"


def open_log_in_terminal(log_path) -> bool:
    """
    在系统终端窗口中打开日志文件（供崩溃弹窗“查看详细信息”使用）。

    - Windows：新开 cmd 窗口，切换 UTF-8 代码页后 type 日志
    - macOS：通过 osascript 让 Terminal 执行 cat
    - Linux：依次尝试常见终端模拟器，tail 显示最后 300 行

    Args:
        log_path: 日志文件路径（str 或 Path）

    Returns:
        是否成功调起终端
    """
    import subprocess

    log_path = str(log_path)

    try:
        if is_windows():
            # start 的第一个引号参数是窗口标题；"" 用于转义路径中的引号
            command = (
                f'start "FileSyncTool" cmd /k '
                f'"chcp 65001 >nul & type ""{log_path}""" '
            )
            subprocess.Popen(command, shell=True)
            return True

        if is_macos():
            script = f'tell application "Terminal" to do script "cat {_sh_quote(log_path)}"'
            subprocess.Popen(["osascript", "-e", script])
            subprocess.Popen(["osascript", "-e", 'tell application "Terminal" to activate'])
            return True

        if is_linux():
            tail_cmd = f"tail -n 300 -f {_sh_quote(log_path)}"
            candidates = [
                ["x-terminal-emulator", "-e", tail_cmd],
                ["gnome-terminal", "--", "bash", "-c", tail_cmd],
                ["konsole", "-e", "bash", "-c", tail_cmd],
                ["xfce4-terminal", "-e", tail_cmd],
                ["xterm", "-e", "bash", "-c", tail_cmd],
            ]
            for cmd in candidates:
                try:
                    subprocess.Popen(cmd)
                    return True
                except FileNotFoundError:
                    continue
    except Exception:
        return False

    return False


def _sh_quote(text: str) -> str:
    """POSIX shell 单引号转义"""
    return "'" + str(text).replace("'", "'\\''") + "'"


# ===================== 电源管理（v7.6） =====================
#
# 阻止休眠的状态管理：
# - Windows 使用线程级 SetThreadExecutionState，状态保存在线程局部变量中，
#   线程/进程结束时系统自动恢复；
# - macOS/Linux 尽力使用 caffeinate 子进程，多个并发同步任务按引用计数共享。

import threading as _threading

_sleep_lock = _threading.Lock()
_sleep_tls = _threading.local()
_sleep_proc = None
_sleep_refs = 0

# POSIX 下延迟关机的分离进程句柄（GUI 退出后仍由系统接管）
_shutdown_proc = None


def prevent_sleep() -> bool:
    """
    同步期间阻止系统进入空闲休眠（不强制点亮显示器）。

    - Windows：SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)，
      线程级，线程结束时系统自动恢复；
    - macOS/Linux：尽力启动 caffeinate -i 子进程。
    不支持或失败时静默返回 False，调用方无需特殊处理。

    Returns:
        是否成功进入阻止状态（True 时必须在 finally 中调用 allow_sleep）
    """
    global _sleep_proc, _sleep_refs
    try:
        if is_windows():
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            result = ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED
            )
            if result:
                _sleep_tls.prevented = True
                return True
            return False

        # macOS/Linux：尝试 caffeinate（-i 阻止系统空闲休眠）
        with _sleep_lock:
            if _sleep_proc is None:
                import subprocess
                _sleep_proc = subprocess.Popen(
                    ["caffeinate", "-i"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            _sleep_refs += 1
            return True
    except Exception:
        return False


def allow_sleep():
    """
    恢复系统休眠策略，与 prevent_sleep() 配对。

    必须放在 finally 块中调用；Windows 清除当前线程的连续执行状态，
    macOS/Linux 在引用计数归零时结束 caffeinate 进程。
    """
    global _sleep_proc, _sleep_refs
    try:
        if is_windows():
            if getattr(_sleep_tls, "prevented", False):
                import ctypes
                ES_CONTINUOUS = 0x80000000
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                _sleep_tls.prevented = False
            return

        with _sleep_lock:
            if _sleep_proc is not None:
                _sleep_refs = max(0, _sleep_refs - 1)
                if _sleep_refs == 0:
                    try:
                        _sleep_proc.terminate()
                    except Exception:
                        pass
                    _sleep_proc = None
    except Exception:
        pass


def schedule_shutdown(delay_seconds: int) -> bool:
    """
    安排 delay_seconds 秒后自动关机。

    计时由操作系统（或分离进程）接管，调用方（含 GUI）退出后倒计时依然有效。
    Windows 优先；macOS/Linux 尽力而为；不支持或调用失败时静默返回 False。

    Args:
        delay_seconds: 延迟秒数（非负整数）

    Returns:
        是否已成功安排关机
    """
    global _shutdown_proc
    delay_seconds = max(0, int(delay_seconds))
    import subprocess

    try:
        if is_windows():
            # /f 强制关闭应用，避免倒计时结束时被无响应程序阻塞
            result = subprocess.run(
                ["shutdown", "/s", "/t", str(delay_seconds), "/f"],
                capture_output=True,
            )
            return result.returncode == 0

        if is_macos():
            # osascript 走系统标准关机流程；延迟阶段在分离进程中 sleep
            cmd = (
                f"sleep {delay_seconds}; "
                "osascript -e 'tell application \"System Events\" to shut down'"
            )
            _shutdown_proc = subprocess.Popen(
                ["/bin/sh", "-c", cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True

        if is_linux():
            # shutdown -h 通常需要 root/权限；无权限时静默失败
            cmd = f"sleep {delay_seconds}; shutdown -h now"
            _shutdown_proc = subprocess.Popen(
                ["/bin/sh", "-c", cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
    except Exception:
        return False
    return False


def cancel_scheduled_shutdown() -> bool:
    """
    取消由 schedule_shutdown() 安排的关机。

    Windows 调用 shutdown /a；macOS/Linux 结束延迟关机的分离进程。
    未安排、已过取消窗口或不支持时返回 False。
    """
    global _shutdown_proc
    import subprocess

    try:
        if is_windows():
            result = subprocess.run(
                ["shutdown", "/a"],
                capture_output=True,
            )
            return result.returncode == 0

        if _shutdown_proc is not None:
            import signal
            try:
                os.killpg(os.getpgid(_shutdown_proc.pid), signal.SIGTERM)
            except Exception:
                try:
                    _shutdown_proc.terminate()
                except Exception:
                    pass
            _shutdown_proc = None
            return True
    except Exception:
        return False
    return False


def open_directory_in_file_manager(dir_path) -> bool:
    """
    用系统默认文件管理器打开指定目录（跨平台）。

    - Windows：explorer <目录>
    - macOS：open <目录>
    - Linux：xdg-open <目录>
    """
    import subprocess

    dir_path = str(dir_path)
    try:
        if is_windows():
            subprocess.Popen(["explorer", dir_path])
            return True
        if is_macos():
            subprocess.Popen(["open", dir_path])
            return True
        if is_linux():
            subprocess.Popen(["xdg-open", dir_path])
            return True
    except Exception:
        return False
    return False
