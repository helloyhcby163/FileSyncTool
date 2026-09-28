"""
文件同步工具 v7.0 - 首页
显示主要功能入口和最近打断的任务
"""

import customtkinter as ctk
from backend.language_manager import get_font
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .app import FileSyncApp


class HomePage(ctk.CTkFrame):
    """首页类：显示主要功能入口和最近打断的任务"""
    
    def __init__(self, master, app: "FileSyncApp"):
        """
        初始化首页
        
        Args:
            master: 父容器
            app: 主窗口实例
        """
        super().__init__(master)
        
        self.app = app
        
        # 选中的打断任务
        self.selected_interrupted_task: Optional[Dict] = None
        
        # 提示信息索引
        self.tip_index = 0
        self.tips = [
            "tip_open_source",
            "tip_features",
            "tip_download",
            "tip_support"
        ]
        
        # 设置布局
        self._setup_layout()
        
        # 加载数据
        self._load_data()
    
    def _setup_layout(self):
        """设置布局"""
        # 配置网格权重
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=220)  # 左列固定宽度
        self.grid_columnconfigure(1, weight=1)  # 右列自适应
        
        # 创建左列（按钮区域）
        self._create_left_panel()
        
        # 创建右列
        self._create_right_panel()
    
    def _create_left_panel(self):
        """创建左列按钮区域"""
        # 左列容器
        self.left_panel = ctk.CTkFrame(self)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.left_panel.grid_rowconfigure(6, weight=1)  # 底部留空
        
        # 标题
        self.title_label = ctk.CTkLabel(
            self.left_panel,
            text=self.app.get_text("home_page"),
            font=get_font(size=20, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 30), sticky="w")
        
        # 文件同步按钮
        self.btn_file_sync = ctk.CTkButton(
            self.left_panel,
            text=self.app.get_text("btn_file_sync"),
            height=45,
            font=get_font(size=14),
            command=self._on_file_sync_click
        )
        self.btn_file_sync.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        
        # 正在进行的任务按钮
        self.btn_running_tasks = ctk.CTkButton(
            self.left_panel,
            text=self.app.get_text("btn_running_tasks"),
            height=45,
            font=get_font(size=14),
            command=self._on_running_tasks_click
        )
        self.btn_running_tasks.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        # 任务配置按钮
        self.btn_task_config = ctk.CTkButton(
            self.left_panel,
            text=self.app.get_text("btn_task_config"),
            height=45,
            font=get_font(size=14),
            command=self._on_task_config_click
        )
        self.btn_task_config.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        
        # 最近删除按钮
        self.btn_recycle = ctk.CTkButton(
            self.left_panel,
            text=self.app.get_text("btn_recycle"),
            height=45,
            font=get_font(size=14),
            command=self._on_recycle_click
        )
        self.btn_recycle.grid(row=4, column=0, padx=20, pady=5, sticky="ew")
        
        # v7.5.1: 语言选择下拉框（动态扫描 translations 目录，替代循环切换按钮）
        self._language_options = self.app.language_manager.get_language_options()
        self.language_var = ctk.StringVar(
            value=self._get_language_display(self.app.language_manager.get_language())
        )
        self.language_combobox = ctk.CTkComboBox(
            self.left_panel,
            values=[display for _, display, _ in self._language_options],
            variable=self.language_var,
            command=self._on_language_select,
            height=45,
            font=get_font(size=14),
            dropdown_font=get_font(size=14),
            state="readonly"
        )
        self.language_combobox.grid(row=5, column=0, padx=20, pady=5, sticky="ew")
        
        # 设置按钮
        self.btn_settings = ctk.CTkButton(
            self.left_panel,
            text=self.app.get_text("btn_settings", "设置"),
            height=45,
            font=get_font(size=14),
            command=self._on_settings_click
        )
        self.btn_settings.grid(row=6, column=0, padx=20, pady=5, sticky="ew")
        
        # 分隔线
        self.separator = ctk.CTkFrame(
            self.left_panel,
            height=2,
            fg_color="#4a4a4a"
        )
        self.separator.grid(row=7, column=0, padx=20, pady=15, sticky="ew")
        
        # 退出按钮
        self.btn_exit = ctk.CTkButton(
            self.left_panel,
            text=self.app.get_text("btn_exit", "退出"),
            height=45,
            font=get_font(size=14),
            fg_color="#d32f2f",
            hover_color="#b71c1c",
            command=self._on_exit_click
        )
        self.btn_exit.grid(row=8, column=0, padx=20, pady=5, sticky="ew")
    
    def _create_right_panel(self):
        """创建右列"""
        # 右列容器
        self.right_panel = ctk.CTkFrame(self)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.right_panel.grid_rowconfigure(0, weight=2)  # 上方区域（打断任务列表）
        self.right_panel.grid_rowconfigure(1, weight=1)  # 下方区域（提示信息）
        self.right_panel.grid_columnconfigure(0, weight=1)
        
        # 上方：最近打断的任务列表
        self._create_interrupted_tasks_panel()
        
        # 下方：提示信息区域
        self._create_tips_panel()
    
    def _create_interrupted_tasks_panel(self):
        """创建最近打断的任务列表面板"""
        # 上方容器
        self.interrupted_panel = ctk.CTkFrame(self.right_panel)
        self.interrupted_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.interrupted_panel.grid_rowconfigure(1, weight=1)
        self.interrupted_panel.grid_columnconfigure(0, weight=1)
        
        # 标题和搜索框容器
        self.header_frame = ctk.CTkFrame(self.interrupted_panel, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.header_frame.grid_columnconfigure(1, weight=1)
        
        # 标题
        self.interrupted_title = ctk.CTkLabel(
            self.header_frame,
            text=self.app.get_text("interrupted_tasks"),
            font=get_font(size=16, weight="bold")
        )
        self.interrupted_title.grid(row=0, column=0, padx=(0, 10), sticky="w")
        
        # 搜索框
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(
            self.header_frame,
            placeholder_text=self.app.get_text("search"),
            textvariable=self.search_var,
            width=200
        )
        self.search_entry.grid(row=0, column=1, sticky="e")
        self.search_entry.bind("<KeyRelease>", self._on_search_change)
        
        # 提示文本
        self.interrupted_hint = ctk.CTkLabel(
            self.interrupted_panel,
            text=self.app.get_text("interrupted_tasks_hint"),
            font=get_font(size=12),
            text_color="gray"
        )
        self.interrupted_hint.grid(row=0, column=0, padx=10, pady=(5, 5), sticky="w")
        
        # 任务列表（使用 ScrollableFrame）
        self.tasks_frame = ctk.CTkScrollableFrame(self.interrupted_panel)
        self.tasks_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # 底部按钮区域
        self.button_frame = ctk.CTkFrame(self.interrupted_panel, fg_color="transparent")
        self.button_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        self.button_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # 继续同步按钮
        self.btn_continue = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("continue_sync"),
            height=35,
            command=self._on_continue_click
        )
        self.btn_continue.grid(row=0, column=0, padx=5, sticky="ew")
        
        # 删除按钮
        self.btn_delete = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("delete"),
            height=35,
            fg_color="red",
            hover_color="darkred",
            command=self._on_delete_click
        )
        self.btn_delete.grid(row=0, column=1, padx=5, sticky="ew")
        
        # 查看按钮
        self.btn_view = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("view"),
            height=35,
            command=self._on_view_click
        )
        self.btn_view.grid(row=0, column=2, padx=5, sticky="ew")
    
    def _create_tips_panel(self):
        """创建提示信息面板"""
        # 下方容器
        self.tips_panel = ctk.CTkFrame(self.right_panel)
        self.tips_panel.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.tips_panel.grid_rowconfigure(0, weight=1)
        self.tips_panel.grid_columnconfigure(0, weight=1)
        
        # 提示信息标签
        self.tip_label = ctk.CTkLabel(
            self.tips_panel,
            text=self.app.get_text(self.tips[self.tip_index]),
            font=get_font(size=13),
            wraplength=500
        )
        self.tip_label.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        # 自动切换提示信息
        self._auto_switch_tip()
    
    def _auto_switch_tip(self):
        """自动切换提示信息"""
        self.tip_index = (self.tip_index + 1) % len(self.tips)
        self.tip_label.configure(text=self.app.get_text(self.tips[self.tip_index]))
        
        # 每 5 秒切换一次
        self.after(5000, self._auto_switch_tip)
    
    def _load_data(self):
        """加载数据"""
        # 加载打断的任务列表
        self._load_interrupted_tasks()
    
    def _load_interrupted_tasks(self):
        """加载打断的任务列表"""
        # 清空现有列表
        for widget in self.tasks_frame.winfo_children():
            widget.destroy()
        
        # 获取打断的任务
        interrupted_tasks = self.app.config_manager.get_interrupted_tasks()
        
        if not interrupted_tasks:
            # 显示空状态
            empty_label = ctk.CTkLabel(
                self.tasks_frame,
                text=self.app.get_text("no_interrupted_tasks", "暂无打断的任务"),
                font=get_font(size=12),
                text_color="gray"
            )
            empty_label.pack(pady=20)
            return
        
        # 创建任务项
        for task in interrupted_tasks:
            self._create_task_item(task)
    
    def _create_task_item(self, task: Dict[str, Any]):
        """
        创建任务项
        
        Args:
            task: 任务信息
        """
        # 任务项容器
        item_frame = ctk.CTkFrame(self.tasks_frame)
        item_frame.pack(fill="x", pady=5, padx=5)
        
        # 单选按钮（用于选择）
        task_id = task.get("id", "")
        
        # 任务名称
        task_name = task.get("name", "未命名任务")
        name_label = ctk.CTkLabel(
            item_frame,
            text=task_name,
            font=get_font(size=13, weight="bold"),
            anchor="w"
        )
        name_label.pack(side="left", padx=10, pady=10)
        
        # 任务信息
        source = task.get("source", "")
        target = task.get("target", "")
        info_text = f"{source} → {target}"
        info_label = ctk.CTkLabel(
            item_frame,
            text=info_text,
            font=get_font(size=11),
            text_color="gray",
            anchor="e"
        )
        info_label.pack(side="right", padx=10, pady=10)
        
        # 绑定点击事件
        def on_click(event, t=task):
            self._select_task(t)
        
        item_frame.bind("<Button-1>", on_click)
        name_label.bind("<Button-1>", on_click)
        info_label.bind("<Button-1>", on_click)
        
        # 存储任务信息
        item_frame.task_info = task
    
    def _select_task(self, task: Dict[str, Any]):
        """
        选择任务
        
        Args:
            task: 任务信息
        """
        # 更新选中状态
        self.selected_interrupted_task = task
        
        # 更新视觉反馈
        for widget in self.tasks_frame.winfo_children():
            if hasattr(widget, 'task_info'):
                if widget.task_info.get("id") == task.get("id"):
                    widget.configure(border_width=2, border_color="blue")
                else:
                    widget.configure(border_width=0)
    
    def _get_language_display(self, language_code: str) -> str:
        """根据语言代码获取下拉框中的显示名"""
        for code, display, _broken in self._language_options:
            if code == language_code:
                return display
        return self.app.language_manager.get_language_name(language_code)

    def _on_language_select(self, value: str):
        """语言下拉框选择事件：损坏文件标注“损坏”且不允许选择"""
        selected_code = None
        selected_broken = False
        for code, display, broken in self._language_options:
            if display == value:
                selected_code = code
                selected_broken = broken
                break

        current_language = self.app.language_manager.get_language()

        if selected_code is None:
            self.language_var.set(self._get_language_display(current_language))
            return

        if selected_broken:
            # 损坏的语言文件不允许选择：提示并复位为当前语言
            import tkinter as tk
            from tkinter import messagebox

            filename = f"{selected_code}.json"
            warning_template = self.app.get_text(
                "language_broken_warning",
                "语言文件 {filename} 已损坏，无法选择，请检查该文件。"
            )
            warning_text = warning_template.replace("{filename}", filename)

            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning(
                self.app.get_text("language_settings", "语言设置"),
                warning_text
            )
            root.destroy()

            self.language_var.set(self._get_language_display(current_language))
            return

        if selected_code == current_language:
            return

        # 切换语言（主窗口会销毁并重建全部页面，字体随语言 meta 一并刷新）
        self.app.change_language(selected_code)
    
    def _on_file_sync_click(self):
        """文件同步按钮点击事件"""
        self.app.show_page("sync")
    
    def _on_running_tasks_click(self):
        """正在进行的任务按钮点击事件"""
        self.app.show_page("running_tasks")
    
    def _on_task_config_click(self):
        """任务配置按钮点击事件"""
        self.app.show_page("task_manage")
    
    def _on_recycle_click(self):
        """最近删除按钮点击事件"""
        self.app.show_page("recycle")
    
    def _on_settings_click(self):
        """设置按钮点击事件"""
        self.app.show_page("settings")
    
    def _on_search_change(self, event):
        """搜索框内容变化事件"""
        keyword = self.search_var.get().strip().lower()
        
        # 过滤任务列表
        for widget in self.tasks_frame.winfo_children():
            if hasattr(widget, 'task_info'):
                task = widget.task_info
                task_name = task.get("name", "").lower()
                source = task.get("source", "").lower()
                target = task.get("target", "").lower()
                
                if keyword in task_name or keyword in source or keyword in target:
                    widget.pack(fill="x", pady=5, padx=5)
                else:
                    widget.pack_forget()
    
    def _on_continue_click(self):
        """继续同步按钮点击事件"""
        if self.selected_interrupted_task is None:
            self._show_message(self.app.get_text("select_hint"))
            return
        
        # 获取选中的打断任务
        selected = self.selected_interrupted_task
        
        # 获取任务配置
        task_config = selected.get("task_config", {})
        task_name = selected.get("name", "未命名任务")
        
        # 构建任务信息（兼容旧任务格式）
        use_multithreading = task_config.get("use_multithreading", False)
        task_info = {
            "name": task_name,
            "source": task_config.get("source", ""),
            "target": task_config.get("target", ""),
            "mode": task_config.get("run_mode", "safe"),
            "thread_mode": use_multithreading,
            "use_multithreading_scan": task_config.get("use_multithreading_scan", use_multithreading),
            "use_multithreading_copy": task_config.get("use_multithreading_copy", False),
            "strategy": task_config.get("default_strategy", "conservative"),
            "folder_strategies": task_config.get("folder_strategies", {}),
            "resume_from": selected.get("last_processed", ""),
            "completed_files": selected.get("completed_files", 0),
            "total_files": selected.get("total_files", 0)
        }
        
        # 跳转到同步页面开始同步
        self.app.start_sync_from_interrupted(task_info, selected.get("id"))
    
    def _on_delete_click(self):
        """删除按钮点击事件"""
        if self.selected_interrupted_task is None:
            self._show_message(self.app.get_text("select_hint"))
            return
        
        # TODO: 显示确认对话框并删除
        task_id = self.selected_interrupted_task.get("id", "")
        self.app.config_manager.remove_interrupted_task(task_id)
        self.selected_interrupted_task = None
        self._load_interrupted_tasks()
    
    def _on_view_click(self):
        """查看按钮点击事件"""
        if self.selected_interrupted_task is None:
            self._show_message(self.app.get_text("select_hint"))
            return
        
        # 获取选中的打断任务
        selected = self.selected_interrupted_task
        
        # 构建任务配置用于预览
        task_config = selected.get("task_config", {})
        task_config["name"] = selected.get("name", "未命名任务")
        task_config["source"] = selected.get("source", "")
        task_config["target"] = selected.get("target", "")
        
        # 跳转到同步确认页面查看详情
        self.app.show_page("sync_confirm", task_config=task_config)
    
    def _show_message(self, message: str):
        """
        显示消息
        
        Args:
            message: 消息内容
        """
        # 创建消息对话框
        dialog = ctk.CTkInputDialog(
            text=message,
            title=self.app.get_text("info")
        )
    
    def refresh(self):
        """完全刷新页面内容"""
        # 清除搜索状态
        self.search_var.set("")
        
        # 清除旧的任务显示并重新加载
        self._load_interrupted_tasks()
        
        # 重置选中状态
        self.selected_interrupted_task = None
        
        # 更新所有文本
        self._update_texts()
    
    def refresh_interrupted_tasks(self):
        """刷新打断的任务列表"""
        self._load_interrupted_tasks()
    
    def _update_texts(self):
        """更新所有文本"""
        # 更新标题
        self.title_label.configure(text=self.app.get_text("home_page"))
        
        # 更新按钮文本
        self.btn_file_sync.configure(text=self.app.get_text("btn_file_sync"))
        self.btn_running_tasks.configure(text=self.app.get_text("btn_running_tasks"))
        self.btn_task_config.configure(text=self.app.get_text("btn_task_config"))
        self.btn_recycle.configure(text=self.app.get_text("btn_recycle"))
        # 刷新语言下拉框（重新扫描语言文件与当前选中项）
        self._language_options = self.app.language_manager.get_language_options()
        self.language_combobox.configure(
            values=[display for _, display, _ in self._language_options]
        )
        self.language_var.set(
            self._get_language_display(self.app.language_manager.get_language())
        )
        self.btn_settings.configure(text=self.app.get_text("btn_settings", "设置"))
        
        # 更新打断任务区域
        self.interrupted_title.configure(text=self.app.get_text("interrupted_tasks"))
        self.interrupted_hint.configure(text=self.app.get_text("interrupted_tasks_hint"))
        self.search_entry.configure(placeholder_text=self.app.get_text("search"))
        
        # 更新底部按钮
        self.btn_continue.configure(text=self.app.get_text("continue_sync"))
        self.btn_delete.configure(text=self.app.get_text("delete"))
        self.btn_view.configure(text=self.app.get_text("view"))
        
        # 更新退出按钮
        self.btn_exit.configure(text=self.app.get_text("btn_exit", "退出"))
    
    def _on_exit_click(self):
        """退出按钮点击事件"""
        self.app.safe_exit()