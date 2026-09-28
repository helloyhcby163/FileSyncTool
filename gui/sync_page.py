"""
文件同步工具 v7.0 - 文件同步页面
显示任务列表，支持搜索、选择任务和创建新任务
"""

import customtkinter as ctk
from backend.language_manager import get_font
from typing import Optional, Callable, List, Dict


class SyncPage(ctk.CTkFrame):
    """文件同步页面：显示任务列表，支持搜索和选择"""
    
    def __init__(self, master, app, language_manager, task_manager, 
                 on_use_task: Optional[Callable] = None,
                 on_create_task: Optional[Callable] = None):
        """
        初始化文件同步页面
        
        Args:
            master: 父组件
            app: 应用程序实例
            language_manager: 语言管理器
            task_manager: 任务管理器
            on_use_task: 使用任务的回调函数
            on_create_task: 创建新任务的回调函数
        """
        super().__init__(master)
        
        self.app = app
        self.language_manager = language_manager
        self.task_manager = task_manager
        self.on_use_task = on_use_task
        self.on_create_task = on_create_task
        
        # 当前选中的任务
        self.selected_task = None
        self.selected_index = None
        
        # 任务列表数据
        self.tasks = []
        self.filtered_tasks = []
        
        # 创建界面
        self._create_widgets()
        
        # 加载任务
        self._load_tasks()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 配置网格权重
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # ========== 上方：搜索框区域 ==========
        self.search_frame = ctk.CTkFrame(self)
        self.search_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.search_frame.grid_columnconfigure(1, weight=1)
        
        # 搜索标签
        self.search_label = ctk.CTkLabel(
            self.search_frame,
            text=self.language_manager.get_text("search", "搜索"),
            font=get_font(size=14)
        )
        self.search_label.grid(row=0, column=0, padx=(10, 5), pady=10)
        
        # 搜索输入框
        self.search_entry = ctk.CTkEntry(
            self.search_frame,
            placeholder_text=self.language_manager.get_text("search_placeholder", "输入任务名搜索..."),
            height=35
        )
        self.search_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search)
        
        # 清除搜索按钮
        self.clear_search_btn = ctk.CTkButton(
            self.search_frame,
            text="×",
            width=35,
            height=35,
            command=self._clear_search
        )
        self.clear_search_btn.grid(row=0, column=2, padx=(5, 10), pady=10)
        
        # ========== 中间：任务列表区域 ==========
        self.list_frame = ctk.CTkFrame(self)
        self.list_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(0, weight=1)
        
        # 任务列表（使用 ScrollableFrame）
        self.task_scrollable = ctk.CTkScrollableFrame(
            self.list_frame,
            label_text=self.language_manager.get_text("task_list", "任务列表")
        )
        self.task_scrollable.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.task_scrollable.grid_columnconfigure(0, weight=1)
        
        # 任务按钮列表
        self.task_buttons = []
        
        # 空列表提示
        self.empty_label = ctk.CTkLabel(
            self.task_scrollable,
            text=self.language_manager.get_text("no_tasks", "暂无任务，请创建新任务"),
            font=get_font(size=14),
            text_color="gray"
        )
        
        # ========== 下方：按钮区域 ==========
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.button_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # 使用选中的任务按钮
        self.use_task_btn = ctk.CTkButton(
            self.button_frame,
            text=self.language_manager.get_text("use_selected_task", "使用选中的任务"),
            height=40,
            font=get_font(size=14, weight="bold"),
            command=self._on_use_task_click,
            state="disabled"
        )
        self.use_task_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # 创建新任务按钮
        self.create_task_btn = ctk.CTkButton(
            self.button_frame,
            text=self.language_manager.get_text("create_new_task", "创建新任务"),
            height=40,
            font=get_font(size=14, weight="bold"),
            command=self._on_create_task_click,
            fg_color="#2CC985",
            hover_color="#229E6A"
        )
        self.create_task_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        # 返回首页按钮
        self.back_home_btn = ctk.CTkButton(
            self.button_frame,
            text=self.language_manager.get_text("back_home", "返回首页"),
            height=40,
            font=get_font(size=14, weight="bold"),
            command=self._on_back_home_click,
            fg_color="#6B7280",
            hover_color="#4B5563"
        )
        self.back_home_btn.grid(row=0, column=2, padx=10, pady=10, sticky="ew")
        
        # ========== 提示信息区域 ==========
        self.tip_frame = ctk.CTkFrame(self)
        self.tip_frame.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        self.tip_label = ctk.CTkLabel(
            self.tip_frame,
            text=self.language_manager.get_text("no_task_selected", "请选中一个任务，或创建新任务"),
            font=get_font(size=12),
            text_color="gray",
            wraplength=400
        )
        self.tip_label.pack(padx=10, pady=10)
    
    def _load_tasks(self):
        """加载任务列表"""
        self.tasks = self.task_manager.get_all_tasks()
        self.filtered_tasks = self.tasks.copy()
        self._update_task_list()
    
    def _update_task_list(self):
        """更新任务列表显示"""
        # 清除现有按钮和框架
        for task_frame, task_btn in self.task_buttons:
            task_frame.destroy()
            task_btn.destroy()
        self.task_buttons.clear()
        
        # 显示/隐藏空列表提示
        if not self.filtered_tasks:
            self.empty_label.grid(row=0, column=0, padx=10, pady=10)
            return
        else:
            self.empty_label.grid_forget()
        
        # 创建任务按钮
        for i, task in enumerate(self.filtered_tasks):
            # 任务按钮框架
            task_frame = ctk.CTkFrame(self.task_scrollable)
            task_frame.grid(row=i, column=0, padx=5, pady=3, sticky="ew")
            task_frame.grid_columnconfigure(1, weight=1)
            
            # 序号标签
            index_label = ctk.CTkLabel(
                task_frame,
                text=f"{i + 1}",
                font=get_font(size=14, weight="bold"),
                width=40
            )
            index_label.grid(row=0, column=0, padx=(10, 5), pady=8)
            
            # 任务名称按钮
            task_btn = ctk.CTkButton(
                task_frame,
                text=task.get("name", "未命名任务"),
                height=35,
                font=get_font(size=14),
                anchor="w",
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray85", "gray25"),
                command=lambda t=task, idx=i: self._select_task(t, idx)
            )
            task_btn.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
            
            # 保存按钮引用
            self.task_buttons.append((task_frame, task_btn))
    
    def _select_task(self, task: Dict, index: int):
        """
        选中任务
        
        Args:
            task: 任务字典
            index: 任务索引
        """
        # 更新选中状态
        self.selected_task = task
        self.selected_index = index
        
        # 更新按钮样式
        for i, (frame, btn) in enumerate(self.task_buttons):
            if i == index:
                btn.configure(
                    fg_color=("#3B8ED0", "#1F6AA5"),
                    text_color="white"
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=("black", "white")
                )
        
        # 启用使用任务按钮
        self.use_task_btn.configure(state="normal")
        
        # 更新提示信息
        tip_text = self.language_manager.format_text(
            "selected_hint",
            task_name=task.get("name", "未命名任务")
        )
        self.tip_label.configure(text=tip_text, text_color=("green", "#2CC985"))
    
    def _on_search(self, event=None):
        """搜索任务"""
        keyword = self.search_entry.get().strip().lower()
        
        if keyword:
            self.filtered_tasks = [
                task for task in self.tasks
                if keyword in task.get("name", "").lower()
            ]
        else:
            self.filtered_tasks = self.tasks.copy()
        
        # 重置选中状态
        self.selected_task = None
        self.selected_index = None
        self.use_task_btn.configure(state="disabled")
        self.tip_label.configure(
            text=self.language_manager.get_text("no_task_selected", "请选中一个任务，或创建新任务"),
            text_color="gray"
        )
        
        # 更新列表
        self._update_task_list()
    
    def _clear_search(self):
        """清除搜索"""
        self.search_entry.delete(0, "end")
        self._on_search()
    
    def _on_use_task_click(self):
        """使用选中的任务按钮点击事件"""
        if self.selected_task and self.on_use_task:
            self.on_use_task(self.selected_task)
    
    def _on_create_task_click(self):
        """创建新任务按钮点击事件"""
        if self.on_create_task:
            self.on_create_task()
    
    def _on_back_home_click(self):
        """返回首页按钮点击事件"""
        self.app.show_page("home")
    
    def refresh(self):
        """刷新页面数据"""
        self._load_tasks()
        self._clear_search()
    
    def update_language(self):
        """更新界面语言"""
        self.search_label.configure(
            text=self.language_manager.get_text("search", "搜索")
        )
        self.search_entry.configure(
            placeholder_text=self.language_manager.get_text("search_placeholder", "输入任务名搜索...")
        )
        self.task_scrollable.configure(
            label_text=self.language_manager.get_text("task_list", "任务列表")
        )
        self.use_task_btn.configure(
            text=self.language_manager.get_text("use_selected_task", "使用选中的任务")
        )
        self.create_task_btn.configure(
            text=self.language_manager.get_text("create_new_task", "创建新任务")
        )
        
        if self.selected_task:
            tip_text = self.language_manager.format_text(
                "selected_hint",
                task_name=self.selected_task.get("name", "未命名任务")
            )
            self.tip_label.configure(text=tip_text)
        else:
            self.tip_label.configure(
                text=self.language_manager.get_text("no_task_selected", "请选中一个任务，或创建新任务")
            )
        
        # 刷新任务列表
        self._update_task_list()