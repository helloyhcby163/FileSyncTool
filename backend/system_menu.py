"""
文件同步工具 v7.6 - 系统菜单/桌面快捷方式

跨平台实现：
- Windows：使用 pywin32 的 COM 接口（WScript.Shell）创建 .lnk，
  支持开始菜单与桌面两个位置；COM 初始化/反初始化严格成对执行。
- macOS：使用 pyshortcuts（>=1.9.7）在桌面创建 .app 快捷方式；
  pyshortcuts 不可用或创建失败时不做自行兜底，由界面提示用户手动处理。
- Linux：生成 .desktop 文件，同时放到桌面与
  ~/.local/share/applications/，不依赖第三方库。

快捷方式目标：
- 打包后（sys.frozen == True）：指向 FileSyncTool 可执行文件
- 开发阶段（sys.frozen == False）：指向 .venv 中的解释器，
  参数为 main.py 的完整路径，工作目录为 main.py 所在目录

所有函数返回统一结构：
    {"success": bool, "message": str, "paths": List[str], "manual_required": bool}
"""

import os
import sys
from pathlib import Path
from typing import Dict, List

from .platform_utils import is_windows, is_macos, is_linux

APP_NAME = "FileSyncTool"
APP_DISPLAY_NAME = "文件同步工具"


def get_app_root_dir() -> Path:
    """获取程序根目录（开发环境为源码目录，打包环境为可执行文件所在目录）"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resolve_launch_target() -> Dict[str, str]:
    """
    解析快捷方式要启动的目标。

    Returns:
        {"target": 可执行/解释器绝对路径,
         "arguments": 命令行参数,
         "workdir": 工作目录,
         "error": 不可用时的原因（可用时为空字符串）}
    """
    root = get_app_root_dir()

    if getattr(sys, "frozen", False):
        # 打包后：直接指向可执行文件
        return {
            "target": str(Path(sys.executable).resolve()),
            "arguments": "",
            "workdir": str(root),
            "error": "",
        }

    # 开发阶段：使用 .venv 中的解释器启动 main.py
    main_py = root / "main.py"
    if is_windows():
        venv_python = root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = root / ".venv" / "bin" / "python"

    if not venv_python.exists():
        return {
            "target": str(venv_python),
            "arguments": str(main_py),
            "workdir": str(root),
            "error": f"未找到开发环境解释器：{venv_python}，请先创建 .venv 虚拟环境",
        }

    return {
        "target": str(venv_python.resolve()),
        "arguments": str(main_py.resolve()),
        "workdir": str(root),
        "error": "",
    }


def _ok(message: str, paths: List[str]) -> Dict:
    return {"success": True, "message": message, "paths": paths, "manual_required": False}


def _fail(message: str, manual_required: bool = False) -> Dict:
    return {
        "success": False,
        "message": message,
        "paths": [],
        "manual_required": manual_required,
    }


# ===================== Windows =====================

def _create_lnk_windows(lnk_path: Path) -> Dict:
    """通过 pywin32 COM 接口在指定位置创建 .lnk 快捷方式"""
    target_info = resolve_launch_target()
    if target_info["error"]:
        return _fail(target_info["error"])

    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return _fail(
            "缺少 pywin32 依赖，无法创建快捷方式（请运行 pip install pywin32），"
            "并将该问题反馈给开发者"
        )

    lnk_path.parent.mkdir(parents=True, exist_ok=True)

    com_initialized = False
    shell = None
    shortcut = None
    try:
        # CoInitialize/CoUninitialize 必须成对出现，用 try/finally 保证释放
        pythoncom.CoInitialize()
        com_initialized = True

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(lnk_path))
        shortcut.Targetpath = target_info["target"]
        shortcut.Arguments = target_info["arguments"]
        shortcut.WorkingDirectory = target_info["workdir"]
        shortcut.Description = APP_DISPLAY_NAME
        shortcut.IconLocation = target_info["target"]
        shortcut.save()
    except Exception as e:
        return _fail(f"创建快捷方式失败：{e}（请将该错误反馈给开发者）")
    finally:
        # 必须在 CoUninitialize 之前显式释放 COM 对象，
        # 否则对象延迟到解释器回收时才 Release，会触发 IUnknown 释放异常
        try:
            del shortcut
        except Exception:
            pass
        try:
            del shell
        except Exception:
            pass
        if com_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    return _ok(f"已创建快捷方式：{lnk_path}", [str(lnk_path)])


def _add_to_start_menu_windows() -> Dict:
    """Windows：添加到当前用户开始菜单"""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return _fail("无法获取 APPDATA 路径，请手动创建快捷方式")
    lnk_path = (
        Path(appdata)
        / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        / f"{APP_DISPLAY_NAME}.lnk"
    )
    return _create_lnk_windows(lnk_path)


def _add_to_desktop_windows() -> Dict:
    """Windows：在当前用户桌面创建快捷方式"""
    userprofile = os.environ.get("USERPROFILE", str(Path.home()))
    lnk_path = Path(userprofile) / "Desktop" / f"{APP_DISPLAY_NAME}.lnk"
    return _create_lnk_windows(lnk_path)


# ===================== Linux =====================

def _build_desktop_entry() -> str:
    """生成 .desktop 文件内容"""
    target_info = resolve_launch_target()
    exec_line = target_info["target"]
    if target_info["arguments"]:
        exec_line = f'{exec_line} "{target_info["arguments"]}"'

    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_DISPLAY_NAME}\n"
        f"Comment={APP_DISPLAY_NAME}\n"
        f"Exec={exec_line}\n"
        f"Path={target_info['workdir']}\n"
        "Terminal=false\n"
        "Categories=Utility;FileTools;\n"
    )


def _write_desktop_file(dest: Path, content: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)
    os.chmod(dest, 0o755)


def _add_to_desktop_linux() -> Dict:
    """Linux：在桌面与应用菜单各放一个 .desktop 文件"""
    target_info = resolve_launch_target()
    if target_info["error"]:
        return _fail(target_info["error"])

    content = _build_desktop_entry()
    desktop_dir = Path(os.environ.get("XDG_DESKTOP_DIR", str(Path.home() / "Desktop")))
    applications_dir = Path.home() / ".local" / "share" / "applications"

    created: List[str] = []
    errors: List[str] = []
    for dest in (
        desktop_dir / f"{APP_NAME}.desktop",
        applications_dir / f"{APP_NAME}.desktop",
    ):
        try:
            _write_desktop_file(dest, content)
            created.append(str(dest))
        except Exception as e:
            errors.append(f"{dest}: {e}")

    if not created:
        return _fail("创建 .desktop 文件失败：" + "；".join(errors))

    # 部分 GNOME 版本需要将桌面文件标记为可信，失败不影响应用菜单中的入口
    try:
        import subprocess
        subprocess.run(
            ["gio", "set", str(desktop_dir / f"{APP_NAME}.desktop"),
             "metadata::trusted", "true"],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass

    message = f"已创建快捷方式：{', '.join(created)}"
    if errors:
        message += "（部分位置失败：" + "；".join(errors) + "）"
    return _ok(message, created)


# ===================== macOS =====================

def _add_to_desktop_macos() -> Dict:
    """
    macOS：使用 pyshortcuts 在桌面创建 .app 快捷方式。

    按需求约定：pyshortcuts 不可用或创建异常时不自行兜底，
    提示用户手动处理并反馈给开发者。
    """
    target_info = resolve_launch_target()
    if target_info["error"]:
        return _fail(target_info["error"], manual_required=True)

    try:
        from pyshortcuts import make_shortcut
    except ImportError:
        return _fail(
            "缺少 pyshortcuts（>=1.9.7）依赖，无法在 macOS 自动创建快捷方式。"
            "请手动将程序拖入“应用程序”文件夹，并将该问题反馈给开发者。",
            manual_required=True,
        )

    try:
        if getattr(sys, "frozen", False):
            # 打包后：目标为可执行文件本身
            make_shortcut(
                target_info["target"],
                name=APP_NAME,
                description=APP_DISPLAY_NAME,
                terminal=False,
                folder=str(Path.home() / "Desktop"),
            )
        else:
            # 开发阶段：用 .venv 解释器运行 main.py
            make_shortcut(
                target_info["arguments"],
                name=APP_NAME,
                description=APP_DISPLAY_NAME,
                terminal=False,
                folder=str(Path.home() / "Desktop"),
                executable=target_info["target"],
            )
    except Exception as e:
        return _fail(
            f"pyshortcuts 创建快捷方式失败：{e}。请手动处理，并将该错误反馈给开发者。",
            manual_required=True,
        )

    # pyshortcuts 在桌面目录下生成 FileSyncTool.app
    app_path = Path.home() / "Desktop" / f"{APP_NAME}.app"
    return _ok(f"已创建快捷方式：{app_path}", [str(app_path)])


# ===================== 统一入口 =====================

def supports_start_menu() -> bool:
    """当前平台是否支持“添加到开始菜单”"""
    return is_windows()


def supports_desktop() -> bool:
    """当前平台是否支持“添加到桌面”"""
    return is_windows() or is_macos() or is_linux()


def add_to_start_menu() -> Dict:
    """添加到系统菜单（仅 Windows 支持开始菜单）"""
    if is_windows():
        return _add_to_start_menu_windows()
    return _fail("当前平台不支持添加到系统菜单", manual_required=True)


def add_to_desktop() -> Dict:
    """添加到桌面快捷方式"""
    if is_windows():
        return _add_to_desktop_windows()
    if is_macos():
        return _add_to_desktop_macos()
    if is_linux():
        return _add_to_desktop_linux()
    return _fail("当前平台不支持创建桌面快捷方式", manual_required=True)
