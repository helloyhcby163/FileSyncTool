"""
文件同步工具 v7.6 - 程序入口
基于 CustomTkinter 的图形界面版本
继承 v7.5 的所有功能，v7.6 新增：
- 命令行执行：--task "任务名" [--silent]
- 实时监控：--watch "任务名" [--idle 秒数]，空闲触发，Ctrl+C 退出
- 崩溃弹窗支持“查看详细信息”（在终端中打开日志）

历史版本：
- v7.4：全局异常捕获、打包资源路径、跨平台配置目录、系统语言检测
- v7.5：多语言架构重构
"""

import sys
import os
import signal
import traceback
import argparse
from datetime import datetime
from pathlib import Path

# 判断是否为 PyInstaller 打包环境
IS_FROZEN = getattr(sys, 'frozen', False)

if not IS_FROZEN:
    # 开发环境：确保程序所在目录为工作目录
    program_dir = Path(__file__).resolve().parent
    os.chdir(program_dir)

    # 尝试使用虚拟环境中的 Python
    def try_use_venv():
        """检查并使用虚拟环境中的 Python"""
        venv_python = program_dir / ".venv" / "Scripts" / "python.exe"

        # 如果当前 Python 不是虚拟环境中的，且虚拟环境存在，则重新启动
        if not str(sys.executable).startswith(str(program_dir / ".venv")):
            if venv_python.exists():
                print(f"检测到虚拟环境，正在使用 {venv_python} 重新启动...")
                subprocess.run([str(venv_python), str(program_dir / "main.py")] + sys.argv[1:], check=True)
                sys.exit(0)

    import subprocess
    # 检查虚拟环境
    try_use_venv()

    # 添加项目路径到 sys.path
    if str(program_dir) not in sys.path:
        sys.path.insert(0, str(program_dir))


# ========== 全局异常捕获 ==========

def _write_error_log(exc_type, exc_value, exc_tb):
    """将异常信息写入日志文件"""
    try:
        from backend.platform_utils import get_log_file_path

        log_path = get_log_file_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"[{timestamp}] 未捕获的异常\n")
            f.write(f"{'='*60}\n")
            f.write(tb_text)
            f.write(f"\n")

        return str(log_path)
    except Exception:
        return None


def _show_error_dialog(exc_type, exc_value, log_path):
    """
    自定义错误对话框：在普通错误信息之外提供“查看详细信息”按钮，
    点击后在系统终端中打开日志文件。
    """
    import tkinter as tk

    root = tk._default_root
    should_destroy = False
    if root is None:
        root = tk.Tk()
        root.withdraw()
        should_destroy = True

    dialog = tk.Toplevel(root)
    dialog.title("程序错误")
    dialog.resizable(False, False)
    dialog.transient(root)

    error_msg = (
        f"程序遇到未预期的错误：\n\n"
        f"错误类型：{exc_type.__name__}\n"
        f"错误信息：{str(exc_value)}\n\n"
    )
    if log_path:
        error_msg += f"错误日志已保存到：\n{log_path}\n\n"
    error_msg += "建议：\n• 重启程序\n• 如问题持续，请将日志文件发送给开发者"

    label = tk.Label(dialog, text=error_msg, justify="left", padx=20, pady=15)
    label.pack()

    button_frame = tk.Frame(dialog, padx=10, pady=10)
    button_frame.pack()

    def on_close():
        if should_destroy:
            try:
                root.destroy()
            except Exception:
                pass
        else:
            try:
                dialog.destroy()
            except Exception:
                pass

    def on_view_details():
        if not log_path:
            on_close()
            return
        try:
            from backend.platform_utils import open_log_in_terminal
            opened = open_log_in_terminal(log_path)
        except Exception:
            opened = False
        if not opened:
            try:
                from tkinter import messagebox
                messagebox.showinfo(
                    "错误日志",
                    f"无法自动打开终端，请手动查看日志文件：\n{log_path}",
                    parent=dialog,
                )
            except Exception:
                pass
        on_close()

    btn_details = tk.Button(button_frame, text="查看详细信息", width=16, command=on_view_details)
    btn_details.pack(side="left", padx=8)
    btn_ok = tk.Button(button_frame, text="关闭", width=10, command=on_close)
    btn_ok.pack(side="left", padx=8)

    dialog.protocol("WM_DELETE_WINDOW", on_close)

    try:
        dialog.grab_set()
        root.wait_window(dialog)
    except Exception:
        pass


def global_exception_handler(exc_type, exc_value, exc_tb):
    """
    全局异常处理器

    捕获所有未处理的异常，写入日志文件并弹出错误对话框。
    """
    # 不捕获 KeyboardInterrupt
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    # 写日志文件
    log_path = _write_error_log(exc_type, exc_value, exc_tb)

    # 打印到控制台
    print(f"\n{'='*60}")
    print(f"未捕获的异常: {exc_type.__name__}: {exc_value}")
    traceback.print_exception(exc_type, exc_value, exc_tb)
    if log_path:
        print(f"错误日志已保存到: {log_path}")

    # 尝试弹出 GUI 错误对话框（含“查看详细信息”）
    try:
        _show_error_dialog(exc_type, exc_value, log_path)
    except Exception:
        pass  # GUI 不可用时静默处理

    # 调用默认处理器
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def tk_callback_exception_handler(self, exc_type, exc_value, exc_tb):
    """
    Tkinter 回调异常处理器

    Tkinter 默认会将回调中的异常打印到控制台而不触发 sys.excepthook。
    通过重写 Tk.report_callback_exception 来捕获这些异常。

    v7.5: 对于因页面销毁导致的无害 TclError（如 "has been destroyed"、
    "invalid command name"），仅记录日志而不弹窗，避免干扰用户。
    """
    import tkinter as tk
    # 忽略因组件已销毁导致的无害 TclError（页面切换时常见）
    if issubclass(exc_type, tk.TclError):
        msg = str(exc_value).lower()
        harmless_keywords = (
            "has been destroyed",
            "invalid command name",
            "bad window path name",
            "can't invoke",
            "application has been destroyed",
        )
        if any(kw in msg for kw in harmless_keywords):
            # 仅写入日志，不弹窗
            _write_error_log(exc_type, exc_value, exc_tb)
            return
    global_exception_handler(exc_type, exc_value, exc_tb)


# 安装全局异常处理器
sys.excepthook = global_exception_handler


# 全局应用实例（用于信号处理）
global_app = None


def signal_handler(signum, frame):
    """
    信号处理器：捕获 SIGINT 和 SIGTERM

    Args:
        signum: 信号编号
        frame: 调用栈帧
    """
    global global_app

    signal_name = {
        signal.SIGINT: "SIGINT (Ctrl+C)",
        signal.SIGTERM: "SIGTERM",
        signal.SIGBREAK: "SIGBREAK"
    }.get(signum, f"信号 {signum}")

    print(f"\n⚠️ 收到 {signal_name}，正在保存状态...")

    if global_app:
        global_app.handle_force_close(signal_name)


def setup_signal_handlers():
    """设置信号处理器"""
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, signal_handler)
        print("✅ 信号处理器已注册")
    except Exception as e:
        print(f"⚠️ 信号处理器注册失败: {e}")


# ========== v7.6: 窗口图标 ==========

def set_window_icon(root) -> bool:
    """
    为主窗口设置 FileSyncTool.ico 图标。

    - Windows：iconbitmap（同时设为默认图标，后续 Toplevel 自动继承）
    - macOS/Linux：经 Pillow 读取 ico 后用 iconphoto
    - 打包环境通过 get_resource_path() 定位随包资源

    任何失败都静默跳过，不影响程序启动。

    Returns:
        是否设置成功
    """
    try:
        from backend.platform_utils import get_resource_path
        icon_path = get_resource_path("FileSyncTool.ico")
        if not icon_path.exists():
            return False

        if sys.platform == "win32":
            # default 只对之后创建的窗口生效，因此当前窗口需单独设置一次
            win_ok = False
            try:
                root.iconbitmap(str(icon_path))
                win_ok = True
            except Exception:
                pass
            try:
                # 后续 Toplevel（对话框等）自动继承
                root.iconbitmap(default=str(icon_path))
                win_ok = True
            except Exception:
                pass
            return win_ok

        # macOS / Linux：tk 不直接支持 ico，经 Pillow 转为 PhotoImage
        from PIL import Image, ImageTk
        image = Image.open(str(icon_path))
        photo = ImageTk.PhotoImage(image)
        root.iconphoto(True, photo)
        # 保留引用，防止 PhotoImage 被垃圾回收导致图标消失
        root._app_icon_photo = photo
        return True
    except Exception:
        return False


# ========== v7.6: 命令行模式（--task / --watch / --list-tasks） ==========

CLI_HELP_DESCRIPTION = """FileSyncTool v7.6 - 跨平台文件同步工具

用法：
  FileSyncTool                             启动图形界面
  FileSyncTool --help                      显示帮助
  FileSyncTool --list-tasks                列出所有任务
  FileSyncTool --task "任务名"              执行指定任务
  FileSyncTool --task "任务名" --silent      静默执行（无界面）
  FileSyncTool --watch "任务名"             后台监听指定任务
"""

CLI_HELP_EPILOG = """示例：
  FileSyncTool --task "备份照片" --silent
  FileSyncTool --watch "同步文档"

更多信息：https://github.com/helloyhcby163/FileSyncTool
"""


def list_all_tasks() -> int:
    """--list-tasks：列出全部已配置任务"""
    from backend.config_manager import ConfigManager
    from backend.task_manager import TaskManager

    config_manager = ConfigManager()
    task_manager = TaskManager(config_manager)
    tasks = task_manager.get_all_tasks()

    if not tasks:
        print("（暂无任务，可在图形界面中新建）")
        return 0

    print(f"共 {len(tasks)} 个任务：")
    for i, task in enumerate(tasks, 1):
        name = task.get("name", "未命名任务")
        source = task.get("source", "")
        target = task.get("target", "")
        print(f"  {i}. {name}")
        print(f"     源目录：{source}")
        print(f"     目标目录：{target}")
    return 0


def run_cli(args) -> int:
    """
    无界面命令行模式入口。

    Returns:
        进程退出码：0 成功，1 失败
    """
    from backend.config_manager import ConfigManager
    from backend.task_manager import TaskManager
    from backend.recycle_manager import RecycleManager
    from backend.cli_sync import run_task_once
    from backend.watch_manager import WatchManager

    config_manager = ConfigManager()
    task_manager = TaskManager(config_manager)
    recycle_manager = RecycleManager(config_manager)

    idle_seconds = args.idle
    if not (3 <= idle_seconds <= 300):
        print("❌ --idle 取值范围为 3-300 秒")
        return 1

    task_name = args.watch or args.task
    task = task_manager.get_task_by_name(task_name)
    if not task:
        print(f"❌ 未找到任务：{task_name}")
        return 1

    if args.watch:
        # ===== 常驻监听模式 =====
        import threading

        source_dir = task.get("source", "")
        if not source_dir or not os.path.isdir(source_dir):
            print(f"❌ 监听目录不存在：{source_dir or '（未配置源目录）'}，请检查 U 盘是否已插入")
            return 1

        exit_event = threading.Event()

        def trigger_sync():
            # 每次触发重新读取任务，确保用户在 GUI 中修改的配置（含快照）生效
            config_manager.reload_config()
            latest = task_manager.get_task_by_name(task_name)
            if latest is None:
                # 任务已被删除：自动停止监听
                print(f"⚠️ 任务「{task_name}」已被删除，自动停止监听")
                manager.stop()
                exit_event.set()
                return

            # 源目录被修改：重启 observer 监听新目录
            new_source = latest.get("source", "")
            if new_source and new_source != manager.watch_dir:
                if os.path.isdir(new_source):
                    print(f"🔄 源目录已变更，重新监听：{new_source}")
                    manager.restart(new_source)
                else:
                    print(f"⚠️ 任务源目录不存在：{new_source}，跳过本次同步")
                    return

            run_task_once(
                latest,
                config_manager,
                task_manager,
                recycle_manager=recycle_manager,
                silent=args.silent,
                watch_mode=True,
            )

        manager = WatchManager(
            source_dir,
            idle_seconds=idle_seconds,
            on_trigger=trigger_sync,
        )
        if not manager.start():
            return 1

        # 主线程等待 Ctrl+C 或任务被删除
        try:
            while not exit_event.is_set():
                if hasattr(signal, "pause"):
                    signal.pause()
                else:
                    if exit_event.wait(timeout=3600):
                        break
        except KeyboardInterrupt:
            print("\n⚠️ 收到 Ctrl+C，正在退出监听...")
        finally:
            manager.stop()
        return 0

    # ===== 单次执行模式 =====
    success = run_task_once(
        task,
        config_manager,
        task_manager,
        recycle_manager=recycle_manager,
        silent=args.silent,
    )
    return 0 if success else 1


def main():
    """程序主入口"""
    global global_app

    parser = argparse.ArgumentParser(
        prog="FileSyncTool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=CLI_HELP_DESCRIPTION,
        epilog=CLI_HELP_EPILOG,
    )
    parser.add_argument(
        "--list-tasks",
        action="store_true",
        help="列出所有已配置的任务后退出",
    )
    parser.add_argument(
        "--task",
        metavar="任务名",
        help="无界面执行一次指定名称的同步任务后退出",
    )
    parser.add_argument(
        "--watch",
        metavar="任务名",
        help="常驻模式：监听任务源目录，空闲后自动触发同步（Ctrl+C 退出）",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="静默模式：仅输出摘要、警告与错误（配合 --task/--watch 使用）",
    )
    parser.add_argument(
        "--idle",
        type=int,
        default=10,
        help="监听模式的空闲触发秒数，默认 10，范围 3-300",
    )
    args = parser.parse_args()

    # 命令行模式：不初始化 GUI
    if args.list_tasks:
        sys.exit(list_all_tasks())
    if args.task or args.watch:
        exit_code = run_cli(args)
        sys.exit(exit_code)

    # GUI 模式下才导入界面依赖，保持无界面模式轻量
    from gui.app import FileSyncApp

    try:
        # 1. 创建应用实例（内部先加载配置和语言，再初始化页面）
        #    语言加载在 _init_backend_modules 中完成，先于信号处理器注册
        global_app = FileSyncApp()

        # v7.6: 设置窗口图标（失败静默跳过）
        set_window_icon(global_app)

        # 2. 应用和语言加载完成后，再注册信号处理器
        #    确保 signal_handler 触发时语言系统已就绪
        setup_signal_handlers()

        # 3. 安装 Tkinter 回调异常处理器
        try:
            import tkinter as tk
            tk.Tk.report_callback_exception = tk_callback_exception_handler
        except Exception:
            pass

        # 4. 运行应用
        global_app.mainloop()

    except Exception as e:
        print(f"程序启动失败: {e}")
        traceback.print_exc()

        # 记录到崩溃日志并弹出带“查看详细信息”的对话框
        log_path = _write_error_log(type(e), e, e.__traceback__)
        try:
            _show_error_dialog(type(e), e, log_path)
        except Exception:
            pass

        sys.exit(1)


if __name__ == "__main__":
    main()
