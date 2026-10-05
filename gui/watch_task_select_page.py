"""
文件同步工具 v7.6 - 监听任务选择页

从工具包进入，支持搜索 + 多选任务，统一配置空闲时间后启动后台监听。
"""

import customtkinter as ctk
from backend.language_manager import get_font
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import FileSyncApp


class WatchTaskSelectPage(ctk.CTkFrame):
    """监听任务选择页：多选任务 + 统一空闲时间启动监听"""

    def __init__(self, master, app: "FileSyncApp"):
        super().__init__(master)
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._selected_names: set = set()
        self._task_checkboxes = {}

        self._create_header()
        self._create_content()
        self._create_bottom()

    # ===================== 布局 =====================

    def _create_header(self):
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.header_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.header_frame,
            text=self.app.get_text("watch_select_tasks", "选择要监听的任务"),
            font=get_font(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=15, pady=12, sticky="w")

        self.search_entry = ctk.CTkEntry(
            self.header_frame,
            placeholder_text=self.app.get_text("search_placeholder", "搜索任务名..."),
            height=38,
            font=get_font(size=13),
        )
        self.search_entry.grid(row=0, column=1, padx=15, pady=12, sticky="ew")
        self.search_entry.bind("<KeyRelease>", lambda e: self._render_tasks())

    def _create_content(self):
        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)

        self.empty_label = ctk.CTkLabel(
            self.list_frame,
            text=self.app.get_text("no_tasks", "暂无任务"),
            font=get_font(size=14),
            text_color="gray",
        )
        self.empty_label.grid(row=0, column=0, padx=20, pady=40)

        self._render_tasks()

    def _create_bottom(self):
        self.bottom_frame = ctk.CTkFrame(self)
        self.bottom_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.bottom_frame.grid_columnconfigure((0, 1), weight=1)

        self.start_btn = ctk.CTkButton(
            self.bottom_frame,
            text=self.app.get_text("start_watch_selected", "开始监听"),
            height=45,
            font=get_font(size=15, weight="bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            command=self._on_start_watch,
            state="disabled",
        )
        self.start_btn.grid(row=0, column=0, padx=8, pady=10, sticky="ew")

        self.back_btn = ctk.CTkButton(
            self.bottom_frame,
            text=self.app.get_text("back_to_toolkit", "返回工具包"),
            height=45,
            font=get_font(size=15, weight="bold"),
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            border_color=("gray70", "gray30"),
            command=lambda: self.app.show_page("toolkit"),
        )
        self.back_btn.grid(row=0, column=1, padx=8, pady=10, sticky="ew")

    # ===================== 任务列表渲染 =====================

    def _render_tasks(self):
        keyword = self.search_entry.get().strip().lower() if hasattr(self, "search_entry") else ""

        for cb in self._task_checkboxes.values():
            try:
                cb.destroy()
            except Exception:
                pass
        self._task_checkboxes.clear()

        tasks = self.app.task_manager.get_all_tasks()
        if keyword:
            tasks = [t for t in tasks if keyword in (t.get("name") or "").lower()]

        if not tasks:
            self.empty_label.grid(row=0, column=0, padx=20, pady=40)
            self._update_start_btn()
            return

        self.empty_label.grid_forget()
        for i, task in enumerate(tasks):
            name = task.get("name", "")
            var = ctk.BooleanVar(value=name in self._selected_names)
            cb = ctk.CTkCheckBox(
                self.list_frame,
                text=name,
                font=get_font(size=14),
                variable=var,
                command=lambda n=name, v=var: self._on_toggle(n, v),
            )
            cb.grid(row=i, column=0, padx=20, pady=6, sticky="w")
            self._task_checkboxes[name] = cb

        self._update_start_btn()

    def _on_toggle(self, name: str, var: ctk.BooleanVar):
        if var.get():
            self._selected_names.add(name)
        else:
            self._selected_names.discard(name)
        self._update_start_btn()

    def _update_start_btn(self):
        if hasattr(self, "start_btn"):
            self.start_btn.configure(
                state="normal" if self._selected_names else "disabled"
            )

    # ===================== 启动监听 =====================

    def _on_start_watch(self):
        if not self._selected_names:
            return
        self._show_idle_dialog(sorted(self._selected_names))

    def _show_idle_dialog(self, task_names: list):
        """弹出空闲时间输入对话框，确认后启动监听"""
        from backend import watch_process

        dialog = ctk.CTkToplevel(self)
        dialog.title(self.app.get_text("set_idle_seconds", "设置空闲时间"))
        dialog.geometry("400x220")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=self.app.get_text("watch_idle_seconds", "空闲秒数"),
            font=get_font(size=14, weight="bold"),
        ).pack(padx=15, pady=(20, 8))

        hint = ctk.CTkLabel(
            dialog,
            text=self.app.get_text(
                "watch_idle_range_hint",
                "源目录连续空闲该秒数后自动同步（范围 3-300，默认 10）"
            ),
            font=get_font(size=12),
            text_color="gray",
            wraplength=360,
            justify="center",
        )
        hint.pack(padx=15, pady=(0, 8))

        idle_var = ctk.StringVar(value="10")
        idle_entry = ctk.CTkEntry(
            dialog, textvariable=idle_var, width=120, height=38,
            font=get_font(size=14), justify="center"
        )
        idle_entry.pack(pady=8)
        idle_entry.focus_set()

        msg_label = ctk.CTkLabel(dialog, text="", font=get_font(size=12), text_color="red")
        msg_label.pack(pady=(4, 8))

        def on_confirm():
            try:
                idle = int(idle_var.get().strip())
            except ValueError:
                msg_label.configure(text=self.app.get_text("watch_idle_invalid", "空闲秒数必须是 3-300 之间的整数"))
                return
            if not (3 <= idle <= 300):
                msg_label.configure(text=self.app.get_text("watch_idle_invalid", "空闲秒数必须是 3-300 之间的整数"))
                return

            config_dir = self.app.config_manager.get_config_dir()
            results = []
            for name in task_names:
                r = watch_process.start_watcher(config_dir, name, idle)
                results.append(f"• {name}: {r['message']}")
            dialog.destroy()
            self._show_result_dialog(results)
            self._selected_names.clear()
            self._render_tasks()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=8)
        ctk.CTkButton(
            btn_frame, text=self.app.get_text("confirm", "确定"), width=100, height=36,
            fg_color="#3B8ED0", command=on_confirm
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            btn_frame, text=self.app.get_text("cancel", "取消"), width=100, height=36,
            fg_color="transparent", text_color=("black", "white"),
            border_width=2, border_color=("gray70", "gray30"),
            command=dialog.destroy,
        ).pack(side="left", padx=8)

        idle_entry.bind("<Return>", lambda e: on_confirm())
        dialog.wait_window()

    def _show_result_dialog(self, results: list):
        dialog = ctk.CTkToplevel(self)
        dialog.title(self.app.get_text("watch_result", "监听启动结果"))
        dialog.geometry("460x320")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text=self.app.get_text("watch_result", "监听启动结果"),
            font=get_font(size=16, weight="bold")
        ).pack(pady=(15, 8))

        text = ctk.CTkTextbox(dialog, height=180, font=get_font(size=13))
        text.pack(fill="both", expand=True, padx=15, pady=8)
        text.insert("1.0", "\n".join(results))
        text.configure(state="disabled")

        ctk.CTkButton(
            dialog, text=self.app.get_text("close", "关闭"), width=100, height=36,
            command=dialog.destroy
        ).pack(pady=10)
        dialog.wait_window()

    def refresh(self):
        self._selected_names.clear()
        self._render_tasks()
