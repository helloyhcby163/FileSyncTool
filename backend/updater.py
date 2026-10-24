# -*- coding: utf-8 -*-
"""更新下载与 Windows 自替换。

Windows 替换流程：
1. 下载新 exe 到临时目录；
2. 生成 update.bat（等待 2 秒 → move 重试 5 次、每次间隔 2 秒 → 成功则启动新程序；
   失败则写 update_failed.txt 并用 mshta 弹出系统级提示）；
3. 以 CREATE_NO_WINDOW | DETACHED_PROCESS 启动脚本，主程序随后退出。

非 frozen（开发环境）/ 非 Windows / 目录不可写时不做替换，仅提示手动处理。
"""

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .version import APP_VERSION, RELEASES_PAGE


class UpdateIntegrityError(RuntimeError):
    """更新包完整性校验失败（v7.7.1）。"""


class UpdateHashMissingError(UpdateIntegrityError):
    """官方未提供 SHA-256，出于安全考虑中止自动更新。"""


class UpdateHashMismatchError(UpdateIntegrityError):
    """下载文件的 SHA-256 与官方值不一致，可能被篡改。"""


def _sha256_of(path):
    """计算文件 SHA-256（分块读取，避免大文件占满内存）。"""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remove_safely(path):
    try:
        Path(path).unlink()
    except OSError:
        pass


def update_temp_dir():
    path = Path(tempfile.gettempdir()) / "FileSyncTool_update"
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_update(info, progress_cb=None, on_status=None, strategy=None):
    """下载更新文件并强制校验 SHA-256，返回校验通过的本地 Path。

    v7.7.1：
    - 官方未提供 SHA-256 → 删除下载文件并抛 UpdateHashMissingError；
    - 哈希不一致 → 删除下载文件并抛 UpdateHashMismatchError。
    """
    asset_url = (info or {}).get("asset_url") or ""
    if not asset_url:
        raise RuntimeError("该版本未提供可下载的 exe 文件")
    from .downloader import download
    path = download(
        asset_url,
        update_temp_dir(),
        progress_callback=progress_cb,
        on_status=on_status,
        strategy=strategy,
    )

    expected = str((info or {}).get("sha256") or "").strip().lower()
    if not expected:
        _remove_safely(path)
        raise UpdateHashMissingError(
            "⚠️ 安全警告：无法获取官方 SHA-256 哈希值，已中止自动更新。"
        )

    actual = _sha256_of(path)
    if actual != expected:
        _remove_safely(path)
        raise UpdateHashMismatchError(
            "⚠️ 安全警告：更新包哈希校验失败，可能已被篡改！"
        )

    return path


def can_replace(current_exe=None):
    """预检旧 exe 所在目录是否可写（不可写则不应启动替换脚本）。"""
    exe = Path(current_exe) if current_exe else Path(sys.executable)
    try:
        return exe.is_file() and os.access(str(exe.parent), os.W_OK)
    except OSError:
        return False


def write_windows_update_script(new_exe, current_exe=None):
    """生成 update.bat 并返回其路径。"""
    new_exe = Path(new_exe).resolve()
    exe = Path(current_exe).resolve() if current_exe else Path(sys.executable).resolve()
    bat_path = update_temp_dir() / "update.bat"

    lines = [
        "@echo off",
        "chcp 65001 >nul",
        f'set "NEW={new_exe}"',
        f'set "OLD={exe}"',
        'set "FAILFILE=%TEMP%\\FileSyncTool_update_failed.txt"',
        "set /a TRIES=0",
        "timeout /t 2 /nobreak >nul",
        "",
        ":retry",
        'move /y "%NEW%" "%OLD%" >nul 2>&1',
        "if not errorlevel 1 goto success",
        "set /a TRIES+=1",
        "if %TRIES% lss 5 (",
        "    timeout /t 2 /nobreak >nul",
        "    goto retry",
        ")",
        "goto failed",
        "",
        ":success",
        'start "" "%OLD%"',
        'del "%~f0"',
        "exit /b 0",
        "",
        ":failed",
        '> "%FAILFILE%" echo 更新失败，请手动替换。',
        '>> "%FAILFILE%" echo 新文件: %NEW%',
        '>> "%FAILFILE%" echo 旧文件: %OLD%',
        '>> "%FAILFILE%" echo 时间: %DATE% %TIME%',
        "mshta \"javascript:alert('更新失败，请手动替换。"
        "详细信息见临时目录中的 FileSyncTool_update_failed.txt。');close()\"",
        'del "%~f0"',
        "exit /b 1",
        "",
    ]
    bat_path.write_text("\r\n".join(lines), encoding="utf-8", newline="")
    return bat_path


def launch_update_script(bat_path):
    """以隐藏窗口方式启动替换脚本（脚本自身延迟等待主程序退出）。"""
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
    subprocess.Popen(
        ["cmd", "/c", str(bat_path)],
        cwd=str(Path(bat_path).parent),
        creationflags=flags,
        close_fds=True,
    )


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def release_page_url():
    return RELEASES_PAGE


def current_version():
    return APP_VERSION
