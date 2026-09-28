"""
文件同步工具 v7.0 - 运行中的任务页面
显示正在进行的任务列表
"""

import customtkinter as ctk
from backend.language_manager import get_font
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .app import FileSyncApp


class RunningTasksPage(ctk.CTkFrame):
    """运行中的任务页面：显示正在进行的任务列表"""
    
    def __init__(self, master, app: "FileSyncApp"):
        """
        初始化运行中的任务页面
        
        Args:
            master: 父容器
            app: 主窗口实例
        """
        super().__init__(master)
        
        self.app = app
        
        # 选中的任务
        self.selected_task: Optional[Dict[str, Any]] = None
        self.selected_task_id: Optional[str] = None
        
        # 任务项列表
        self.task_items: List[ctk.CTkFrame] = []
        
        # 设置布局
        self._setup_layout()
        
        # 加载数据
        self._load_data()
        
        # 启动自动刷新
        self._start_auto_refresh()
    
    def _setup_layout(self):
        """设置布局"""
        # 配置网格权重
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # ========== 顶部：标题区域 ==========
        self._create_header()
        
        # ========== 中间：任务列表区域 ==========
        self._create_task_list()
        
        # ========== 底部：按钮区域 ==========
        self._create_button_panel()
    
    def _create_header(self):
        """创建顶部标题区域"""
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)
        
        # 标题
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text=self.app.get_text("running_tasks"),
            font=get_font(size=20, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=15, sticky="w")
        
        # 任务数量标签
        self.count_label = ctk.CTkLabel(
            self.header_frame,
            text="",
            font=get_font(size=14),
            text_color="gray"
        )
        self.count_label.grid(row=0, column=1, padx=20, pady=15, sticky="e")
    
    def _create_task_list(self):
        """创建任务列表区域"""
        self.list_frame = ctk.CTkFrame(self)
        self.list_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(0, weight=1)
        
        # 可滚动任务列表
        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.list_frame,
            label_text=self.app.get_text("running_tasks_list")
        )
        self.scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        
        # 空状态提示
        self.empty_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=self.app.get_text("no_running_tasks", "当前没有正在进行的任务"),
            font=get_font(size=14),
            text_color="gray"
        )
        self.empty_label.grid(row=0, column=0, padx=20, pady=40)
    
    def _create_button_panel(self):
        """创建底部按钮区域"""
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=2, column=0, padx=20, pady=20, sticky="ew")
        self.button_frame.grid_columnconfigure((0, 1), weight=1)
        
        # 查看详情按钮
        self.btn_view_details = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("view_details"),
            height=45,
            font=get_font(size=14),
            command=self._on_view_details_click,
            state="disabled"
        )
        self.btn_view_details.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # 返回首页按钮
        self.btn_return_home = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("return_home"),
            height=45,
            font=get_font(size=14),
            command=self._on_return_home_click
        )
        self.btn_return_home.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
    
    def _load_data(self):
        """加载数据"""
        self._load_running_tasks()
    
    def _load_running_tasks(self):
        """加载运行中的任务列表"""
        # 清空现有列表
        for item in self.task_items:
            item.destroy()
        self.task_items.clear()
        
        # 获取运行中的任务
        running_tasks = self.app.get_running_tasks()
        
        # 更新任务数量
        count_text = f"{len(running_tasks)} {self.app.get_text('task_name', '个任务')}"
        self.count_label.configure(text=count_text)
        
        if not running_tasks:
            # 显示空状态
            self.empty_label.grid(row=0, column=0, padx=20, pady=40)
            self.btn_view_details.configure(state="disabled")
            return
        
        # 隐藏空状态提示
        self.empty_label.grid_forget()
        
        # 创建任务项
        for i, task in enumerate(running_tasks):
            self._create_task_item(task, i)
    
    def _create_task_item(self, task: Dict[str, Any], index: int):
        """
        创建任务项
        
        Args:
            task: 任务信息
            index: 任务索引
        """
        # 任务项容器
        item_frame = ctk.CTkFrame(self.scrollable_frame)
        item_frame.grid(row=index + 1, column=0, padx=5, pady=5, sticky="ew")
        item_frame.grid_columnconfigure(1, weight=1)
        
        # 任务状态指示器
        status_indicator = ctk.CTkLabel(
            item_frame,
            text="●",
            font=get_font(size=16),
            text_color=("green", "#2CC985")
        )
        status_indicator.grid(row=0, column=0, padx=(15, 5), pady=15)
        
        # 任务名称
        task_name = task.get("name", "未命名任务")
        name_label = ctk.CTkLabel(
            item_frame,
            text=task_name,
            font=get_font(size=14, weight="bold"),
            anchor="w"
        )
        name_label.grid(row=0, column=1, padx=10, pady=15, sticky="w")
        
        # 剩余时间
        remaining_time = task.get("remaining_time", 0)
        remaining_text = self._format_remaining_time(remaining_time)
        remaining_label = ctk.CTkLabel(
            item_frame,
            text=f"{self.app.get_text('remaining')}: {remaining_text}",
            font=get_font(size=12),
            text_color="gray",
            anchor="e"
        )
        remaining_label.grid(row=0, column=2, padx=15, pady=15, sticky="e")
        
        # 绑定点击事件
        def on_click(event, t=task):
            self._select_task(t)
        
        item_frame.bind("<Button-1>", on_click)
        name_label.bind("<Button-1>", on_click)
        remaining_label.bind("<Button-1>", on_click)
        status_indicator.bind("<Button-1>", on_click)
        
        # 存储任务信息
        item_frame.task_info = task
        item_frame.task_id = task.get("id", "")
        
        # 添加到列表
        self.task_items.append(item_frame)
    
    def _format_remaining_time(self, seconds: float) -> str:
        """
        格式化剩余时间
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化的时间字符串
        """
        if seconds <= 0:
            return "--:--"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def _select_task(self, task: Dict[str, Any]):
        """
        选择任务
        
        Args:
            task: 任务信息
        """
        # 更新选中状态
        self.selected_task = task
        self.selected_task_id = task.get("id", "")
        
        # 更新视觉反馈
        for item in self.task_items:
            if hasattr(item, 'task_id') and item.task_id == self.selected_task_id:
                item.configure(border_width=2, border_color=("blue", "#3B8ED0"))
            else:
                item.configure(border_width=0)
        
        # 启用查看详情按钮
        self.btn_view_details.configure(state="normal")
    
    def _on_view_details_click(self):
        """查看详情按钮点击事件"""
        if self.selected_task is None:
            return
        
        # 跳转到同步进度页面
        self.app.show_page("sync_progress", task_info=self.selected_task)
    
    def _on_return_home_click(self):
        """返回首页按钮点击事件"""
        self.app.show_page("home")
    
    def _start_auto_refresh(self):
        """启动自动刷新"""
        self._auto_refresh()
    
    def _auto_refresh(self):
        """自动刷新任务列表"""
        # 刷新任务列表
        self._load_running_tasks()
        
        # 每 2 秒刷新一次
        self.after(2000, self._auto_refresh)
    
    def refresh(self):
        """刷新页面"""
        # 刷新任务列表
        self._load_running_tasks()
        
        # 更新所有文本
        self._update_texts()
    
    def _update_texts(self):
        """更新所有文本"""
        self.title_label.configure(text=self.app.get_text("running_tasks"))
        self.scrollable_frame.configure(
            label_text=self.app.get_text("running_tasks_list")
        )
        self.btn_view_details.configure(text=self.app.get_text("view_details"))
        self.btn_return_home.configure(text=self.app.get_text("return_home"))
        
        # 更新任务数量
        running_tasks = self.app.get_running_tasks()
        count_text = f"{len(running_tasks)} {self.app.get_text('task_name', '个任务')}"
        self.count_label.configure(text=count_text)
        
        # 更新空状态提示
        self.empty_label.configure(
            text=self.app.get_text("no_running_tasks", "当前没有正在进行的任务")
        )