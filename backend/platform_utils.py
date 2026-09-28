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
