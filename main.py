"""
文件同步工具 v7.3 - 程序入口
基于 CustomTkinter 的图形界面版本
继承 v7.2 的所有功能，新增性能优化：大文件分块复制、断点续传、批量预创建目录、块级寿命保护

v7.4 稳定性修复：
- 全局异常捕获（sys.excepthook + Tkinter callback）
- 打包环境资源路径处理（sys._MEIPASS）
- 跨平台配置目录
- 系统语言自动检测
- 启动顺序优化：语言加载先于信号处理器注册
"""

import sys
import os
import signal
import traceback
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
                subprocess.run([str(venv_python), str(program_dir / "main.py")], check=True)
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

    # 尝试弹出 GUI 错误对话框
    try:
        import tkinter as tk
        from tkinter import messagebox

        # 优先复用已有的 Tk root（应用正在运行时）
        # 避免在回调异常中创建第二个 root 导致冲突
        root = tk._default_root
        should_destroy = False
        if root is None:
            root = tk.Tk()
            root.withdraw()
            should_destroy = True

        error_msg = (
            f"程序遇到未预期的错误：\n\n"
            f"错误类型：{exc_type.__name__}\n"
            f"错误信息：{str(exc_value)}\n\n"
        )
        if log_path:
            error_msg += f"错误日志已保存到：\n{log_path}\n\n"
        error_msg += "建议：\n• 重启程序\n• 如问题持续，请将日志文件发送给开发者"

        messagebox.showerror("程序错误", error_msg)

        if should_destroy:
            root.destroy()
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


# 导入 GUI 应用
from gui.app import FileSyncApp

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


def main():
    """程序主入口"""
    global global_app

    try:
        # 1. 创建应用实例（内部先加载配置和语言，再初始化页面）
        #    语言加载在 _init_backend_modules 中完成，先于信号处理器注册
        global_app = FileSyncApp()

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

        # 尝试弹出错误对话框
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk._default_root
            should_destroy = False
            if root is None:
                root = tk.Tk()
                root.withdraw()
                should_destroy = True

            messagebox.showerror(
                "启动失败",
                f"程序启动失败：\n{str(e)}\n\n请检查环境配置或联系开发者。"
            )

            if should_destroy:
                root.destroy()
        except Exception:
            pass

        sys.exit(1)


if __name__ == "__main__":
    main()
