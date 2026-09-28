"""
文件同步工具 v7.0 - 最近删除页面
显示已删除的文件列表，支持打开所在目录、清空所有等操作
"""

import os
import platform
from pathlib import Path
import customtkinter as ctk
from backend.language_manager import get_font
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .app import FileSyncApp


class RecyclePage(ctk.CTkFrame):
    """最近删除页面：显示已删除的文件列表"""
    
    # 存储上限警告阈值（MB）
    WARNING_THRESHOLD_MB = 5120  # 5GB
    
    def __init__(self, master, app: "FileSyncApp"):
        """
        初始化最近删除页面
        
        Args:
            master: 父容器
            app: 主窗口实例
        """
        super().__init__(master)
        
        self.app = app
        
        # 选中的文件
        self.selected_file: Optional[Dict] = None
        self.selected_index: Optional[int] = None
        
        # 文件列表数据
        self.deleted_files: List[Dict] = []
        self.filtered_files: List[Dict] = []
        
        # 文件项组件列表
        self.file_items: List[ctk.CTkFrame] = []
        
        # 设置布局
        self._setup_layout()
        
        # 加载文件数据
        self._load_deleted_files()
    
    def _setup_layout(self):
        """设置布局"""
        # 配置网格权重
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # ========== 上方：搜索框区域 ==========
        self._create_search_panel()
        
        # ========== 中间：文件列表区域 ==========
        self._create_file_list_panel()
        
        # ========== 底部：按钮区域 ==========
        self._create_button_panel()
    
    def _create_search_panel(self):
        """创建搜索框区域"""
        self.search_frame = ctk.CTkFrame(self)
        self.search_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.search_frame.grid_columnconfigure(1, weight=1)
        
        # 标题
        self.title_label = ctk.CTkLabel(
            self.search_frame,
            text=self.app.get_text("recycle_page"),
            font=get_font(size=18, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=(10, 20), pady=10, sticky="w")
        
        # 搜索输入框
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(
            self.search_frame,
            placeholder_text=self.app.get_text("search"),
            textvariable=self.search_var,
            width=250,
            height=35
        )
        self.search_entry.grid(row=0, column=1, padx=5, pady=10, sticky="e")
        self.search_entry.bind("<KeyRelease>", self._on_search_change)
        
        # 清除搜索按钮
        self.clear_search_btn = ctk.CTkButton(
            self.search_frame,
            text="×",
            width=35,
            height=35,
            font=get_font(size=16),
            command=self._clear_search
        )
        self.clear_search_btn.grid(row=0, column=2, padx=(5, 10), pady=10)
    
    def _create_file_list_panel(self):
        """创建文件列表区域"""
        self.list_frame = ctk.CTkFrame(self)
        self.list_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(1, weight=1)
        
        # 存储上限警告区域
        self.warning_frame = ctk.CTkFrame(self.list_frame)
        self.warning_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        self.warning_label = ctk.CTkLabel(
            self.warning_frame,
            text="",
            font=get_font(size=12),
            text_color="orange"
        )
        self.warning_label.pack(padx=10, pady=5)
        
        # 文件列表（使用 ScrollableFrame）
        self.file_scrollable = ctk.CTkScrollableFrame(
            self.list_frame,
            label_text=self.app.get_text("deleted_files_list")
        )
        self.file_scrollable.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.file_scrollable.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        
        # 空列表提示
        self.empty_label = ctk.CTkLabel(
            self.file_scrollable,
            text=self.app.get_text("no_deleted_files", "暂无已删除的文件"),
            font=get_font(size=14),
            text_color="gray"
        )
        
        # 存储大小信息
        self.size_info_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        self.size_info_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        self.size_label = ctk.CTkLabel(
            self.size_info_frame,
            text="",
            font=get_font(size=12),
            text_color="gray"
        )
        self.size_label.pack(side="left")
    
    def _create_button_panel(self):
        """创建底部按钮区域"""
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.button_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # 打开所在目录按钮
        self.open_dir_btn = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("open_directory"),
            height=40,
            font=get_font(size=14),
            command=self._on_open_directory_click,
            state="disabled"
        )
        self.open_dir_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # 清空所有按钮
        self.clear_all_btn = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("clear_all"),
            height=40,
            font=get_font(size=14),
            fg_color="red",
            hover_color="darkred",
            command=self._on_clear_all_click
        )
        self.clear_all_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        # 返回首页按钮
        self.return_home_btn = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("return_home"),
            height=40,
            font=get_font(size=14),
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            command=self._on_return_home_click
        )
        self.return_home_btn.grid(row=0, column=2, padx=10, pady=10, sticky="ew")
    
    def _load_deleted_files(self):
        """加载已删除文件列表"""
        self.deleted_files = self.app.recycle_manager.get_all_deleted_files()
        self.filtered_files = self.deleted_files.copy()
        
        # 更新存储大小信息
        self._update_size_info()
        
        # 更新警告显示
        self._update_warning()
        
        # 更新文件列表
        self._update_file_list()
    
    def _update_size_info(self):
        """更新存储大小信息"""
        current_size_mb = self.app.recycle_manager.get_current_size_mb()
        limit_mb = self.app.recycle_manager.get_limit_mb()
        
        # 格式化大小显示
        current_size_str = self._format_size(current_size_mb * 1024 * 1024)
        limit_size_str = self._format_size(limit_mb * 1024 * 1024)
        
        self.size_label.configure(
            text=self.app.get_text(
                "storage_usage",
                current=current_size_str,
                limit=limit_size_str
            )
        )
    
    def _update_warning(self):
        """更新存储上限警告"""
        if self.app.recycle_manager.is_over_limit():
            limit_mb = self.app.recycle_manager.get_limit_mb()
            limit_gb = limit_mb / 1024
            warning_text = self.app.get_text("recycle_limit_warning").replace("{limit}", str(limit_gb))
            self.warning_label.configure(text=warning_text)
            self.warning_frame.configure(fg_color=("orange", "darkorange"))
        else:
            self.warning_label.configure(text="")
            self.warning_frame.configure(fg_color="transparent")
    
    def _update_file_list(self):
        """更新文件列表显示"""
        # 清除现有文件项
        for item in self.file_items:
            item.destroy()
        self.file_items.clear()
        
        # 显示/隐藏空列表提示
        if not self.filtered_files:
            self.empty_label.grid(row=0, column=0, padx=10, pady=20)
            return
        else:
            self.empty_label.grid_forget()
        
        # 创建文件项
        for i, file_info in enumerate(self.filtered_files):
            self._create_file_item(i, file_info)
    
    def _create_file_item(self, index: int, file_info: Dict):
        """
        创建单个文件项
        
        Args:
            index: 文件索引
            file_info: 文件信息
        """
        # 文件项容器
        item_frame = ctk.CTkFrame(self.file_scrollable)
        item_frame.grid(row=index, column=0, padx=5, pady=3, sticky="ew")
        item_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        
        # 存储文件信息
        item_frame.file_info = file_info
        item_frame.file_index = index
        
        # 序号标签
        index_label = ctk.CTkLabel(
            item_frame,
            text=f"{index + 1}",
            font=get_font(size=12),
            width=30
        )
        index_label.grid(row=0, column=0, padx=(5, 2), pady=5)
        
        # 文件名
        original_path = file_info.get("original_path", "")
        file_name = Path(original_path).name if original_path else "未知文件"
        name_label = ctk.CTkLabel(
            item_frame,
            text=file_name,
            font=get_font(size=12),
            anchor="w"
        )
        name_label.grid(row=0, column=1, padx=2, pady=5, sticky="ew")
        
        # 删除日期
        deleted_at = file_info.get("deleted_at", "")
        if deleted_at:
            # 格式化日期显示（只显示日期部分）
            date_str = deleted_at.split("T")[0] if "T" in deleted_at else deleted_at
        else:
            date_str = "未知"
        date_label = ctk.CTkLabel(
            item_frame,
            text=date_str,
            font=get_font(size=12),
            anchor="center"
        )
        date_label.grid(row=0, column=2, padx=2, pady=5)
        
        # 文件大小
        file_size = file_info.get("size", 0)
        size_str = self._format_size(file_size)
        size_label = ctk.CTkLabel(
            item_frame,
            text=size_str,
            font=get_font(size=12),
            anchor="center"
        )
        size_label.grid(row=0, column=3, padx=2, pady=5)
        
        # 文件类型
        file_type = file_info.get("file_type", "")
        if file_type:
            type_str = file_type.lstrip(".")
        else:
            type_str = "未知"
        type_label = ctk.CTkLabel(
            item_frame,
            text=type_str,
            font=get_font(size=12),
            anchor="center"
        )
        type_label.grid(row=0, column=4, padx=(2, 5), pady=5)
        
        # 绑定点击事件
        def on_click(event, idx=index, f=file_info, frame=item_frame):
            self._on_file_click(event, idx, f, frame)
        
        item_frame.bind("<Button-1>", on_click)
        index_label.bind("<Button-1>", on_click)
        name_label.bind("<Button-1>", on_click)
        date_label.bind("<Button-1>", on_click)
        size_label.bind("<Button-1>", on_click)
        type_label.bind("<Button-1>", on_click)
        
        # 保存引用
        self.file_items.append(item_frame)
    
    def _format_size(self, size_bytes: int) -> str:
        """
        格式化文件大小
        
        Args:
            size_bytes: 文件大小（字节）
            
        Returns:
            格式化后的大小字符串
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def _on_file_click(self, event, index: int, file_info: Dict, frame: ctk.CTkFrame):
        """
        文件项点击事件
        
        Args:
            event: 点击事件
            index: 文件索引
            file_info: 文件信息
            frame: 文件项容器
        """
        # 更新选中状态
        self.selected_file = file_info
        self.selected_index = index
        
        # 更新视觉反馈
        self._update_selection_visual()
        
        # 更新按钮状态
        self._update_button_states()
    
    def _update_selection_visual(self):
        """更新选中状态的视觉反馈"""
        for item in self.file_items:
            index = item.file_index
            if index == self.selected_index:
                item.configure(border_width=2, border_color=("#3B8ED0", "#1F6AA5"))
            else:
                item.configure(border_width=0)
    
    def _update_button_states(self):
        """更新按钮状态"""
        has_selection = self.selected_file is not None
        
        # 打开所在目录按钮：有选中即可
        self.open_dir_btn.configure(state="normal" if has_selection else "disabled")
    
    def _on_search_change(self, event):
        """搜索框内容变化事件"""
        keyword = self.search_var.get().strip().lower()
        
        if keyword:
            self.filtered_files = [
                file_info for file_info in self.deleted_files
                if keyword in Path(file_info.get("original_path", "")).name.lower() or
                   keyword in file_info.get("deleted_at", "").lower() or
                   keyword in file_info.get("file_type", "").lower()
            ]
        else:
            self.filtered_files = self.deleted_files.copy()
        
        # 重置选中状态
        self.selected_file = None
        self.selected_index = None
        self._update_button_states()
        
        # 更新列表
        self._update_file_list()
    
    def _clear_search(self):
        """清除搜索"""
        self.search_var.set("")
        self._on_search_change(None)
    
    def _on_open_directory_click(self):
        """打开所在目录按钮点击事件"""
        if self.selected_file is None:
            return
        
        # 获取备份路径
        backup_path = self.selected_file.get("backup_path", "")
        
        if backup_path:
            directory = Path(backup_path).parent
            
            # 跨平台打开目录
            try:
                system = platform.system()
                
                if system == "Windows":
                    os.startfile(str(directory))
                elif system == "Darwin":  # macOS
                    os.system(f"open '{directory}'")
                else:  # Linux
                    os.system(f"xdg-open '{directory}'")
            except Exception as e:
                self._show_message(f"打开目录失败：{e}")
    
    def _on_clear_all_click(self):
        """清空所有按钮点击事件"""
        # 弹出确认对话框
        from .task_manage_page import ConfirmDialog
        
        dialog = ConfirmDialog(
            self,
            title=self.app.get_text("delete_confirm"),
            message=self.app.get_text("clear_all_confirm"),
            app=self.app
        )
        
        if dialog.get_result():
            # 清空所有已删除文件
            self.app.recycle_manager.clear_all_deleted_files()
            
            # 显示成功提示
            self._show_message("已清空所有删除的文件")
            
            # 清空选中状态
            self.selected_file = None
            self.selected_index = None
            
            # 刷新列表
            self._load_deleted_files()
    
    def _on_return_home_click(self):
        """返回首页按钮点击事件"""
        self.app.show_page("home")
    
    def _show_message(self, message: str):
        """
        显示消息
        
        Args:
            message: 消息内容
        """
        dialog = ctk.CTkInputDialog(
            text=message,
            title=self.app.get_text("info")
        )
    
    def refresh(self):
        """刷新页面"""
        # 刷新文件列表
        self._load_deleted_files()
        
        # 清空选中状态
        self.selected_file = None
        self.selected_index = None
        self._update_button_states()
        
        # 更新文本
        self._update_texts()
    
    def _update_texts(self):
        """更新所有文本"""
        # 更新标题
        self.title_label.configure(text=self.app.get_text("recycle_page"))
        
        # 更新搜索框
        self.search_entry.configure(placeholder_text=self.app.get_text("search"))
        
        # 更新文件列表标题
        self.file_scrollable.configure(label_text=self.app.get_text("deleted_files_list"))
        
        # 更新按钮文本
        self.open_dir_btn.configure(text=self.app.get_text("open_directory"))
        self.clear_all_btn.configure(text=self.app.get_text("clear_all"))
        self.return_home_btn.configure(text=self.app.get_text("return_home"))