"""
文件同步工具 v7.6 - 工具包页面

收纳非同步功能：
1. 后台监听：以独立进程启动/停止 --watch，GUI 关闭后继续运行
2. 添加到系统菜单/桌面（跨平台，见 backend/system_menu.py）
3. 任务导入导出（v7.6 从设置页迁入）
4. 系统信息
5. 反馈入口（GitHub / Gitee）
"""

import os
import platform
import re
import shutil
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from pathlib import Path

import customtkinter as ctk

from backend.language_manager import get_font
from backend.platform_utils import get_log_file_path, get_resource_path
from backend import system_menu
from backend import watch_process

GITHUB_URL = "https://github.com/helloyhcby163/FileSyncTool"
GITEE_URL = "https://gitee.com/hello-yhc/FileSyncTool"

# 帮助文档图片最大显示宽度（px），超出等比缩放
HELP_IMAGE_MAX_WIDTH = 400
_HELP_IMAGE_LINE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
_HELP_INLINE = re.compile(r'\*\*(.+?)\*\*|`([^`]+)`')
_HELP_BULLET = re.compile(r'^\s*[-*]\s+(.*)$')
_HELP_ORDERED = re.compile(r'^\s*\d+\.\s+(.*)$')
_HELP_TABLE_SEP = re.compile(r'^\|?[\s:|-]+\|?$')


class ToolkitPage(ctk.CTkFrame):
    """工具包页面：非同步功能的统一入口"""

    def __init__(self, master, app):
        """
        Args:
            master: 父容器
            app: 主窗口实例
        """
        super().__init__(master)
        self.app = app

        # 后台监听状态轮询任务 id
        self._poll_job = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._create_header()
        self._create_content()
        self._create_bottom()

    # ===================== 页面骨架 =====================

    def _create_header(self):
        """顶部标题栏"""
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text=self.app.get_text("toolkit_page", "工具包"),
            font=get_font(size=18, weight="bold"),
        )
        self.title_label.pack(padx=10, pady=10)

    def _create_content(self):
        """中部可滚动内容区"""
        self.content_frame = ctk.CTkScrollableFrame(self)
        self.content_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)

        self._create_watcher_section()
        self._create_system_menu_section()
        self._create_import_export_section()
        self._create_system_info_section()
        self._create_post_sync_actions_section()
        self._create_feedback_section()

    def _create_bottom(self):
        """底部返回按钮"""
        self.bottom_frame = ctk.CTkFrame(self)
        self.bottom_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.bottom_frame.grid_columnconfigure(0, weight=1)
        self.back_btn = ctk.CTkButton(
            self.bottom_frame,
            text=self.app.get_text("return_home", "返回首页"),
            height=45,
            font=get_font(size=15, weight="bold"),
            command=lambda: self.app.show_page("home"),
        )
        self.back_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

    def _make_section(self, row: int, title_key: str, default_title: str) -> ctk.CTkFrame:
        """创建一个标准分区卡片"""
        frame = ctk.CTkFrame(self.content_frame)
        frame.grid(row=row, column=0, padx=5, pady=10, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        title = ctk.CTkLabel(
            frame,
            text=self.app.get_text(title_key, default_title),
            font=get_font(size=16, weight="bold"),
        )
        title.grid(row=0, column=0, padx=10, pady=(10, 8), sticky="w")
        return frame

    # ===================== 1. 后台监听 =====================

    def _create_watcher_section(self):
        """后台监听分区：监听任务 / 查看监听详情 两个入口 + 状态汇总"""
        frame = self._make_section(0, "background_watch", "后台监听")

        hint = ctk.CTkLabel(
            frame,
            text=self.app.get_text(
                "background_watch_hint",
                "以独立进程监听任务源目录，连续空闲指定秒数后自动同步；"
                "关闭本程序后监听仍会继续，可重新打开本页停止。"
            ),
            font=get_font(size=12),
            text_color="gray",
            justify="left",
            wraplength=700,
        )
        hint.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="w")

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        btn_row.grid_columnconfigure((0, 1), weight=1)

        self.watch_select_btn = ctk.CTkButton(
            btn_row,
            text=self.app.get_text("watch_select_tasks", "监听任务"),
            height=42,
            font=get_font(size=14),
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            command=self._on_watch_select_tasks,
        )
        self.watch_select_btn.grid(row=0, column=0, padx=5, sticky="ew")

        self.watch_detail_btn = ctk.CTkButton(
            btn_row,
            text=self.app.get_text("view_watch_details", "查看监听详情"),
            height=42,
            font=get_font(size=14),
            fg_color="#1F6AA5",
            hover_color="#154E7A",
            command=self._on_view_watch_details,
        )
        self.watch_detail_btn.grid(row=0, column=1, padx=5, sticky="ew")

        self.watch_status_label = ctk.CTkLabel(
            frame,
            text="",
            font=get_font(size=13),
            justify="left",
            anchor="w",
        )
        self.watch_status_label.grid(row=3, column=0, padx=10, pady=(8, 10), sticky="w")

    def _on_watch_select_tasks(self):
        """打开监听任务选择页（多选 + 统一空闲时间启动监听）"""
        self.app.show_page("watch_task_select")

    def _on_view_watch_details(self):
        """查看监听详情：显示当前监听的任务列表，可单独停止"""
        dialog = ctk.CTkToplevel(self)
        dialog.title(self.app.get_text("view_watch_details", "查看监听详情"))
        dialog.geometry("620x460")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        header = ctk.CTkFrame(dialog)
        header.pack(fill="x", padx=15, pady=(15, 8))
        ctk.CTkLabel(
            header, text=self.app.get_text("view_watch_details", "查看监听详情"),
            font=get_font(size=16, weight="bold")
        ).pack(side="left")
        ctk.CTkLabel(
            header, text=self.app.get_text("watch_detail_cols", "任务名 / 源目录 / 空闲秒数"),
            font=get_font(size=12), text_color="gray"
        ).pack(side="left", padx=12)

        list_frame = ctk.CTkScrollableFrame(dialog)
        list_frame.pack(fill="both", expand=True, padx=15, pady=8)
        list_frame.grid_columnconfigure(0, weight=1)

        status_label = ctk.CTkLabel(dialog, text="", font=get_font(size=12))
        status_label.pack(pady=(0, 8))

        def render():
            for w in list_frame.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass
            active = watch_process.list_watchers(self.app.config_manager.get_config_dir())
            if not active:
                ctk.CTkLabel(
                    list_frame, text=self.app.get_text("watch_status_idle", "未监听"),
                    font=get_font(size=14), text_color="gray"
                ).grid(row=0, column=0, padx=20, pady=30)
                status_label.configure(text="")
                return

            status_label.configure(
                text=self.app.get_text("watch_running_count", "当前共有 {n} 个任务正在监听").format(n=len(active)),
                text_color="#2E7D32"
            )
            for i, (name, info) in enumerate(active.items()):
                row = ctk.CTkFrame(list_frame)
                row.grid(row=i, column=0, padx=5, pady=6, sticky="ew")
                row.grid_columnconfigure(0, weight=1)

                task = self.app.task_manager.get_task_by_name(name) or {}
                source_dir = task.get("source", info.get("source", ""))

                text = (
                    f"● {name}\n"
                    f"  {self.app.get_text('info_source', '源目录')}: {source_dir or self.app.get_text('not_configured', '（未配置）')}\n"
                    f"  {self.app.get_text('watch_idle_seconds', '空闲秒数')}: {info.get('idle', 10)}   "
                    f"PID: {info.get('pid')}"
                )
                ctk.CTkLabel(
                    row, text=text, font=get_font(size=13), justify="left", anchor="w"
                ).grid(row=0, column=0, padx=10, pady=6, sticky="w")

                stop_btn = ctk.CTkButton(
                    row, text=self.app.get_text("stop_watch", "停止监听"),
                    width=90, height=32, font=get_font(size=12),
                    fg_color="#C62828", hover_color="#8E1B1B",
                    command=lambda n=name: stop_one(n),
                )
                stop_btn.grid(row=0, column=1, padx=10, pady=6)

        def stop_one(name):
            result = watch_process.stop_watcher(self.app.config_manager.get_config_dir(), name)
            status_label.configure(
                text=result["message"],
                text_color="#2E7D32" if result["success"] else "#C62828",
            )
            render()

        render()

        bottom = ctk.CTkFrame(dialog, fg_color="transparent")
        bottom.pack(pady=(0, 15))
        ctk.CTkButton(
            bottom, text=self.app.get_text("close", "关闭"), width=100, height=36,
            command=dialog.destroy
        ).pack()
        dialog.wait_window()

    def _refresh_watch_status(self):
        """刷新监听状态汇总显示"""
        active = watch_process.list_watchers(self.app.config_manager.get_config_dir())
        if not active:
            text = self.app.get_text("watch_status_idle", "未监听")
            self.watch_status_label.configure(text=text, text_color="gray")
        else:
            lines = [
                self.app.get_text(
                    "watch_status_running",
                    "正在监听：{name}（空闲 {idle} 秒，PID {pid}）",
                ).format(name=name, idle=info.get("idle", 10), pid=info.get("pid"))
                for name, info in active.items()
            ]
            self.watch_status_label.configure(text="\n".join(lines), text_color="#2E7D32")

    def _schedule_poll(self):
        """周期刷新监听状态（页面销毁后自动停止）"""
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
        self._poll_job = self.after(3000, self._poll_tick)

    def _poll_tick(self):
        """轮询一次并安排下一次"""
        try:
            if self.winfo_exists():
                self._refresh_watch_status()
                self._poll_job = self.after(3000, self._poll_tick)
        except Exception:
            self._poll_job = None

    # ===================== 2. 添加到系统菜单 =====================

    def _create_system_menu_section(self):
        """系统菜单/桌面快捷方式分区"""
        frame = self._make_section(1, "system_menu", "添加到系统菜单")

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="ew")
        btn_row.grid_columnconfigure((0, 1), weight=1)

        col = 0
        if system_menu.supports_start_menu():
            btn = ctk.CTkButton(
                btn_row,
                text=self.app.get_text("add_to_start_menu", "添加到开始菜单"),
                height=40,
                font=get_font(size=14),
                command=self._on_add_start_menu,
            )
            btn.grid(row=0, column=col, padx=5, sticky="ew")
            col += 1

        if system_menu.supports_desktop():
            btn = ctk.CTkButton(
                btn_row,
                text=self.app.get_text("add_to_desktop", "添加到桌面"),
                height=40,
                font=get_font(size=14),
                command=self._on_add_desktop,
            )
            btn.grid(row=0, column=col, padx=5, sticky="ew")
            col += 1

        self.system_menu_result = ctk.CTkLabel(
            frame,
            text="",
            font=get_font(size=12),
            justify="left",
            anchor="w",
            wraplength=700,
        )
        self.system_menu_result.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="w")

    def _show_menu_result(self, result: dict):
        """展示快捷方式创建结果"""
        color = "#2E7D32" if result["success"] else "#C62828"
        self.system_menu_result.configure(text=result["message"], text_color=color)

    def _on_add_start_menu(self):
        self._show_menu_result(system_menu.add_to_start_menu())

    def _on_add_desktop(self):
        self._show_menu_result(system_menu.add_to_desktop())

    # ===================== 3. 任务导入导出 =====================

    def _create_import_export_section(self):
        """任务导入导出分区（v7.6 从设置页迁入）"""
        frame = self._make_section(2, "task_import_export", "任务导入导出")

        hint = ctk.CTkLabel(
            frame,
            text=self.app.get_text(
                "task_import_export_hint",
                "将任务导出为 JSON 配置文件，可在另一台电脑导入恢复",
            ),
            font=get_font(size=12),
            text_color="gray",
            justify="left",
            wraplength=700,
        )
        hint.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="w")

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        btn_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row,
            text=self.app.get_text("export_all_tasks", "导出所有任务"),
            height=40,
            font=get_font(size=14),
            command=self._on_export_all_tasks,
        ).grid(row=0, column=0, padx=5, sticky="ew")

        ctk.CTkButton(
            btn_row,
            text=self.app.get_text("import_tasks", "导入任务"),
            height=40,
            font=get_font(size=14),
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            command=self._on_import_tasks,
        ).grid(row=0, column=1, padx=5, sticky="ew")

        ctk.CTkLabel(
            frame,
            text=self.app.get_text(
                "multi_export_hint",
                "提示：如需只导出部分任务，请到「任务配置」页多选后导出",
            ),
            font=get_font(size=12),
            text_color="gray",
            justify="left",
            wraplength=700,
        ).grid(row=3, column=0, padx=10, pady=(5, 10), sticky="w")

    def _on_export_all_tasks(self):
        """导出所有任务"""
        import tkinter as tk
        from tkinter import filedialog, messagebox

        root = tk.Toplevel(self)
        root.withdraw()
        file_path = filedialog.asksaveasfilename(
            parent=root,
            title=self.app.get_text("export_all_tasks", "导出所有任务"),
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        root.destroy()
        if not file_path:
            return
        success = self.app.task_manager.export_all_tasks(file_path)
        root = tk.Toplevel(self)
        root.withdraw()
        if success:
            messagebox.showinfo(
                self.app.get_text("export_all_tasks", "导出所有任务"),
                self.app.get_text("export_success", "任务导出成功"),
                parent=root,
            )
        else:
            messagebox.showerror(
                self.app.get_text("export_all_tasks", "导出所有任务"),
                self.app.get_text("export_failed", "任务导出失败"),
                parent=root,
            )
        root.destroy()

    def _on_import_tasks(self):
        """导入任务"""
        import tkinter as tk
        from tkinter import filedialog, messagebox

        root = tk.Toplevel(self)
        root.withdraw()
        file_path = filedialog.askopenfilename(
            parent=root,
            title=self.app.get_text("import_tasks", "导入任务"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        root.destroy()
        if not file_path:
            return
        result = self.app.task_manager.import_tasks(file_path)
        root = tk.Toplevel(self)
        root.withdraw()
        if result["success"]:
            messagebox.showinfo(
                self.app.get_text("import_tasks", "导入任务"),
                result["message"],
                parent=root,
            )
        else:
            messagebox.showerror(
                self.app.get_text("import_tasks", "导入任务"),
                result["message"],
                parent=root,
            )
        root.destroy()

    # ===================== 4. 系统信息 =====================

    def _create_system_info_section(self):
        """系统信息分区"""
        frame = self._make_section(3, "system_info", "系统信息")

        info_text = self._collect_system_info()
        self.system_info_textbox = ctk.CTkTextbox(
            frame,
            height=220,
            font=get_font(size=12),
            wrap="word",
        )
        self.system_info_textbox.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")
        self.system_info_textbox.insert("1.0", info_text)
        self.system_info_textbox.configure(state="disabled")

        ctk.CTkButton(
            frame,
            text=self.app.get_text("copy_system_info", "复制系统信息"),
            height=36,
            font=get_font(size=13),
            width=180,
            command=self._on_copy_system_info,
        ).grid(row=2, column=0, padx=10, pady=(0, 10), sticky="w")

    def _collect_system_info(self) -> str:
        """收集系统信息文本"""
        lines = [
            f"{self.app.get_text('app_title', '文件同步工具')}",
            f"{self.app.get_text('info_os', '操作系统')}: {platform.platform()}",
            f"{self.app.get_text('info_python', 'Python 版本')}: {platform.python_version()}",
            f"{self.app.get_text('info_cpu', 'CPU 核心')}: {os.cpu_count() or '未知'}",
        ]

        memory = self._get_memory_text()
        if memory:
            lines.append(
                f"{self.app.get_text('info_memory', '内存')}: {memory}"
            )

        try:
            config_dir = self.app.config_manager.get_config_dir()
            usage = shutil.disk_usage(config_dir)
            lines.append(
                f"{self.app.get_text('info_disk', '配置目录所在磁盘')}: "
                f"{self._format_size(usage.used)} / {self._format_size(usage.total)} "
                f"({self.app.get_text('info_available', '可用')} "
                f"{self._format_size(usage.free)})"
            )
        except Exception:
            pass

        lines.append(
            f"{self.app.get_text('info_config_dir', '配置目录')}: "
            f"{self.app.config_manager.get_config_dir()}"
        )
        lines.append(
            f"{self.app.get_text('info_log_path', '日志文件')}: {get_log_file_path()}"
        )
        return "\n".join(lines)

    @staticmethod
    def _format_size(num_bytes: int) -> str:
        size = float(num_bytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _get_memory_text(self) -> str:
        """跨平台获取物理内存总量（失败返回空字符串）"""
        try:
            if os.name == "nt":
                import ctypes

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                return (
                    f"{self._format_size(stat.ullTotalPhys)}（总量），"
                    f"{self._format_size(stat.ullAvailPhys)}（可用）"
                )
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    return f"{self._format_size(int(result.stdout.strip()))}（总量）"
                return ""
            # Linux
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return f"{self._format_size(pages * page_size)}（总量）"
        except Exception:
            return ""

    def _on_copy_system_info(self):
        """复制系统信息到剪贴板"""
        import tkinter.messagebox as messagebox

        try:
            text = self.system_info_textbox.get("1.0", "end").strip()
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo(
                self.app.get_text("system_info", "系统信息"),
                self.app.get_text("system_info_copied", "系统信息已复制到剪贴板"),
            )
        except Exception as e:
            messagebox.showerror(
                self.app.get_text("system_info", "系统信息"),
                f"{self.app.get_text('copy_failed', '复制失败')}: {e}",
            )

    # ===================== 5. 同步后操作（自动关机） =====================

    def _create_post_sync_actions_section(self):
        """同步后操作分区：全部成功后自动关机开关 + 延迟选择"""
        frame = self._make_section(4, "post_sync_actions", "同步后操作")

        settings = self.app.config_manager.get_settings()
        enabled = bool(settings.get("auto_shutdown_enabled", False))
        delay = int(settings.get("auto_shutdown_delay", 60) or 60)
        if delay not in (30, 60, 120):
            delay = 60

        self.shutdown_var = ctk.BooleanVar(value=enabled)

        self.shutdown_checkbox = ctk.CTkCheckBox(
            frame,
            text=self.app.get_text(
                "auto_shutdown_checkbox", "全部同步任务成功后自动关机"
            ),
            variable=self.shutdown_var,
            font=get_font(size=14),
            checkbox_width=22,
            checkbox_height=22,
            command=self._on_auto_shutdown_toggle,
        )
        self.shutdown_checkbox.grid(row=1, column=0, padx=10, pady=(2, 8), sticky="w")

        delay_row = ctk.CTkFrame(frame, fg_color="transparent")
        delay_row.grid(row=2, column=0, padx=10, pady=(0, 6), sticky="w")

        ctk.CTkLabel(
            delay_row,
            text=self.app.get_text("shutdown_delay_label", "关机延迟"),
            font=get_font(size=13),
        ).pack(side="left", padx=(0, 8))

        self.shutdown_delay_combo = ctk.CTkComboBox(
            delay_row,
            values=["30", "60", "120"],
            width=100,
            height=32,
            font=get_font(size=13),
            dropdown_font=get_font(size=13),
            state="readonly",
            command=self._on_shutdown_delay_change,
        )
        self.shutdown_delay_combo.set(str(delay))
        self.shutdown_delay_combo.pack(side="left")
        ctk.CTkLabel(
            delay_row,
            text=self.app.get_text("seconds_unit", "秒"),
            font=get_font(size=13),
        ).pack(side="left", padx=(6, 0))

        hint = ctk.CTkLabel(
            frame,
            text=self.app.get_text(
                "auto_shutdown_hint",
                "倒计时期间可在底部状态栏点击「取消关机」；"
                "如有任何任务失败，将保留任务状态并取消关机。",
            ),
            font=get_font(size=12),
            text_color="gray",
            justify="left",
            wraplength=700,
        )
        hint.grid(row=3, column=0, padx=10, pady=(2, 10), sticky="w")

        self._set_delay_combo_state(enabled)

    def _set_delay_combo_state(self, enabled: bool):
        """根据开关状态启用/禁用延迟下拉框"""
        try:
            self.shutdown_delay_combo.configure(state="readonly" if enabled else "disabled")
        except Exception:
            pass

    def _on_auto_shutdown_toggle(self):
        """自动关机开关变化：写入设置"""
        enabled = bool(self.shutdown_var.get())
        settings = self.app.config_manager.get_settings()
        settings["auto_shutdown_enabled"] = enabled
        self.app.config_manager.update_settings(settings)
        self._set_delay_combo_state(enabled)

    def _on_shutdown_delay_change(self, value: str):
        """关机延迟变化：校验并写入设置"""
        try:
            delay = int(str(value).strip())
        except (TypeError, ValueError):
            delay = 60
        if delay not in (30, 60, 120):
            delay = 60
            try:
                self.shutdown_delay_combo.set("60")
            except Exception:
                pass
        settings = self.app.config_manager.get_settings()
        settings["auto_shutdown_delay"] = delay
        self.app.config_manager.update_settings(settings)

    # ===================== 6. 反馈入口 =====================

    def _create_feedback_section(self):
        """反馈入口分区"""
        frame = self._make_section(5, "feedback", "反馈与问题")

        ctk.CTkLabel(
            frame,
            text=self.app.get_text(
                "feedback_hint",
                "遇到问题或有功能建议？欢迎在代码仓库提交 Issue：",
            ),
            font=get_font(size=12),
            text_color="gray",
            justify="left",
            wraplength=700,
        ).grid(row=1, column=0, padx=10, pady=(0, 8), sticky="w")

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        btn_row.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(
            btn_row,
            text="GitHub Issues",
            height=40,
            font=get_font(size=14),
            command=lambda: webbrowser.open(f"{GITHUB_URL}/issues"),
        ).grid(row=0, column=0, padx=5, sticky="ew")

        ctk.CTkButton(
            btn_row,
            text="Gitee Issues",
            height=40,
            font=get_font(size=14),
            command=lambda: webbrowser.open(f"{GITEE_URL}/issues"),
        ).grid(row=0, column=1, padx=5, sticky="ew")

        ctk.CTkButton(
            btn_row,
            text=self.app.get_text("help_document", "帮助文档"),
            height=40,
            font=get_font(size=14),
            fg_color="#6A1B9A",
            hover_color="#4A148C",
            command=self._on_open_help,
        ).grid(row=0, column=2, padx=5, sticky="ew")

    # ===================== 帮助文档 =====================

    def _on_open_help(self):
        """打开帮助文档窗口：tk.Text 渲染 HELP.md，支持图片、滚动、选中复制"""
        docs_dir = get_resource_path("docs")
        help_path = docs_dir / "HELP.md"
        try:
            content = help_path.read_text(encoding="utf-8")
        except Exception as e:
            content = (
                f"# {self.app.get_text('help_load_failed', '无法加载帮助文档')}\n\n{e}"
            )

        dialog = ctk.CTkToplevel(self)
        dialog.title(self.app.get_text("help_document", "帮助文档"))
        dialog.geometry("820x680")
        dialog.minsize(560, 420)
        dialog.transient(self.winfo_toplevel())

        dark = ctk.get_appearance_mode() == "Dark"
        bg_color = "#2b2b2b" if dark else "#f7f8fa"
        fg_color = "#dce4ee" if dark else "#1d1d1f"
        muted_color = "#9aa4b2" if dark else "#6b7280"
        accent_color = "#9575cd" if dark else "#6A1B9A"
        code_bg = "#3a3d42" if dark else "#e9ebef"

        container = ctk.CTkFrame(dialog, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        text = tk.Text(
            container,
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            background=bg_color,
            foreground=fg_color,
            insertbackground=fg_color,
            selectbackground="#7e57c2",
            selectforeground="#ffffff",
            padx=14,
            pady=12,
            cursor="arrow",
        )
        text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ctk.CTkScrollbar(container, command=text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        text.configure(yscrollcommand=scrollbar.set)

        # 字体：沿用当前语言推荐字体族（tk.Text 标签需原生 tkfont）
        family = get_font(size=13).cget("family")
        mono_family = "Consolas" if sys.platform == "win32" else "Menlo"

        def tk_f(size, weight="normal"):
            return tkfont.Font(family=family, size=size, weight=weight)

        text.tag_configure("h1", font=tk_f(20, "bold"), spacing1=6, spacing3=12)
        text.tag_configure("h2", font=tk_f(16, "bold"), foreground=accent_color,
                           spacing1=16, spacing3=8)
        text.tag_configure("h3", font=tk_f(14, "bold"), spacing1=12, spacing3=5)
        text.tag_configure("body", font=tk_f(13), spacing1=2, spacing3=6,
                           lmargin1=4, lmargin2=20)
        text.tag_configure("bullet", font=tk_f(13), spacing1=2, spacing3=5,
                           lmargin1=22, lmargin2=38)
        text.tag_configure("ordered", font=tk_f(13), spacing1=2, spacing3=5,
                           lmargin1=22, lmargin2=38)
        text.tag_configure("quote", font=tk_f(12), foreground=muted_color,
                           lmargin1=20, lmargin2=26, spacing1=2, spacing3=5)
        text.tag_configure("table", font=tk_f(12), spacing1=0, spacing3=2,
                           lmargin1=10, lmargin2=10)
        text.tag_configure("bold", font=tk_f(13, "bold"))
        text.tag_configure(
            "inline_code",
            font=tkfont.Font(family=mono_family, size=12),
            background=code_bg,
        )
        text.tag_configure("img_center", justify="center", spacing1=8, spacing3=8)
        text.tag_configure("img_placeholder", font=tk_f(12), foreground=muted_color)

        # PhotoImage 必须持有引用，否则被垃圾回收后图片不显示
        dialog.help_images = []

        def insert_inline(content, base_tag):
            """按行内 Markdown（**粗体**、`代码`）分段插入"""
            pos = 0
            for match in _HELP_INLINE.finditer(content):
                if match.start() > pos:
                    text.insert("end", content[pos:match.start()], base_tag)
                if match.group(1) is not None:
                    text.insert("end", match.group(1), (base_tag, "bold"))
                else:
                    text.insert("end", match.group(2), (base_tag, "inline_code"))
                pos = match.end()
            if pos < len(content):
                text.insert("end", content[pos:], base_tag)
            text.insert("end", "\n", base_tag)

        def insert_image(rel_path):
            name = Path(rel_path).name
            img_path = Path(rel_path)
            if not img_path.is_absolute():
                img_path = docs_dir / rel_path

            if not img_path.is_file():
                # 图片缺失：占位文字，不报错
                text.insert("end", f"[图片待补充: {name}]\n",
                            ("img_center", "img_placeholder"))
                return
            try:
                from PIL import Image, ImageTk

                image = Image.open(str(img_path))
                if image.width > HELP_IMAGE_MAX_WIDTH:
                    ratio = HELP_IMAGE_MAX_WIDTH / image.width
                    image = image.resize(
                        (HELP_IMAGE_MAX_WIDTH, max(1, int(image.height * ratio))),
                        Image.LANCZOS,
                    )
                photo = ImageTk.PhotoImage(image)
                dialog.help_images.append(photo)

                line_start = text.index("end-1c linestart")
                text.image_create("end", image=photo, padx=4, pady=6)
                text.insert("end", "\n")
                text.tag_add("img_center", line_start, "end-1c")
            except Exception:
                text.insert("end", f"[图片待补充: {name}]\n",
                            ("img_center", "img_placeholder"))

        # ===== 逐行渲染 Markdown 子集 =====
        in_blank = False
        for raw_line in content.splitlines():
            line = raw_line.strip()

            img_match = _HELP_IMAGE_LINE.fullmatch(line)
            if img_match:
                insert_image(img_match.group(2).strip())
                in_blank = False
                continue

            if not line:
                if not in_blank:
                    text.insert("end", "\n", "body")
                in_blank = True
                continue
            in_blank = False

            if line.startswith("### "):
                insert_inline(line[4:], "h3")
            elif line.startswith("## "):
                insert_inline(line[3:], "h2")
            elif line.startswith("# "):
                insert_inline(line[2:], "h1")
            elif line.startswith(">"):
                insert_inline(line.lstrip(">").strip(), "quote")
            elif line.startswith("|") and line.endswith("|"):
                # 表格分隔行（| --- |）直接跳过
                if _HELP_TABLE_SEP.fullmatch(line):
                    continue
                insert_inline(line, "table")
            else:
                bullet = _HELP_BULLET.match(raw_line)
                ordered = _HELP_ORDERED.match(raw_line)
                if bullet:
                    text.insert("end", "•  ", "bullet")
                    insert_inline(bullet.group(1), "bullet")
                elif ordered:
                    number = raw_line.strip().split(".", 1)[0] + "."
                    text.insert("end", f"{number} ", "ordered")
                    insert_inline(ordered.group(1), "ordered")
                else:
                    insert_inline(line, "body")

        # 只读（仍可选中与 Ctrl+C 复制）
        text.configure(state="disabled")

        # 鼠标滚轮（Windows/macOS 与 X11 分别绑定）
        text.bind(
            "<MouseWheel>",
            lambda e: text.yview_scroll(int(-e.delta / 120), "units"),
        )
        text.bind("<Button-4>", lambda e: text.yview_scroll(-1, "units"))
        text.bind("<Button-5>", lambda e: text.yview_scroll(1, "units"))
        text.bind(
            "<Enter>",
            lambda e: text.bind_all("<MouseWheel>", lambda ev: text.yview_scroll(
                int(-ev.delta / 120), "units")),
        )
        text.bind("<Leave>", lambda e: text.unbind_all("<MouseWheel>"))

        ctk.CTkButton(
            dialog,
            text=self.app.get_text("close", "关闭"),
            width=110,
            height=36,
            command=dialog.destroy,
        ).pack(pady=(0, 12))

        dialog.after(50, lambda: text.yview_moveto(0.0))

    # ===================== 页面刷新 =====================

    def refresh(self):
        """每次显示页面时刷新监听状态"""
        self._refresh_watch_status()
        self._schedule_poll()

    def on_page_destroy(self):
        """页面销毁时取消轮询任务"""
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None

    def update_language(self):
        """语言切换后刷新标题（页面通常会被整体重建，此方法保底）"""
        self.title_label.configure(text=self.app.get_text("toolkit_page", "工具包"))
        self.back_btn.configure(text=self.app.get_text("return_home", "返回首页"))
