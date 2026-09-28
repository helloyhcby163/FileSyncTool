"""
文件同步工具 v7.0 - 文件夹单独配置页面
用于为每个子文件夹单独配置同步策略
"""

import os
import customtkinter as ctk
from backend.language_manager import get_font
from typing import Optional, Callable, Dict, List


class FolderConfigPage(ctk.CTkFrame):
    """文件夹单独配置页面：为每个子文件夹设置独立的同步策略"""
    
    # 策略列表
    STRATEGIES = [
        ("conservative", "strategy_conservative", "保守模式"),
        ("newest_wins", "strategy_newest_wins", "时间优先"),
        ("source_wins", "strategy_source_wins", "源目录优先"),
        ("target_wins", "strategy_target_wins", "目标目录优先"),
        ("skip", "strategy_skip", "不同步")
    ]
    
    def __init__(self, master, app, task_config: Dict = None,
                 on_prev_step: Optional[Callable] = None,
                 on_next_step: Optional[Callable] = None,
                 on_cancel: Optional[Callable] = None):
        """
        初始化文件夹配置页面
        
        Args:
            master: 父组件
            app: 主应用实例
            task_config: 任务配置字典
            on_prev_step: 上一步回调函数
            on_next_step: 下一步回调函数
            on_cancel: 取消回调函数
        """
        super().__init__(master)
        
        self.app = app
        self.language_manager = app.language_manager
        self.config_manager = app.config_manager
        self.task_config = task_config or {}
        
        self.on_prev_step = on_prev_step
        self.on_next_step = on_next_step
        self.on_cancel = on_cancel
        
        # 当前配置状态
        self.source_dir = self.task_config.get("source", "")
        self.target_dir = self.task_config.get("target", "")
        self.default_strategy = self.task_config.get("default_strategy", "conservative")
        self.folder_strategies = self.task_config.get("folder_strategies", {})
        self.folder_filters = dict(self.task_config.get("folder_filters", {}))
        self.root_strategy = self.task_config.get("root_strategy", self.default_strategy)
        self.root_included = self.task_config.get("root_included", False)
        self.selected_folders = self.task_config.get("folders", [])
        
        # 子文件夹列表
        self.subfolders: List[str] = []
        self.selected_indices: List[int] = []
        
        # 界面组件
        self.folder_checkboxes: Dict[str, ctk.CTkCheckBox] = {}
        self.strategy_buttons: Dict[str, ctk.CTkButton] = {}
        
        # 创建界面
        self._create_widgets()
        
        # 加载子文件夹
        self._load_subfolders()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 配置网格权重
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # ========== 顶部标题区域 ==========
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text=self.language_manager.get_text("folder_config", "文件夹配置"),
            font=get_font(size=18, weight="bold")
        )
        self.title_label.pack(padx=10, pady=10)
        
        # ========== 中间主内容区域 ==========
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=2)
        self.content_frame.grid_columnconfigure(1, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
        
        # 左列：文件夹列表
        self._create_folder_list_section()
        
        # 右列：策略按钮
        self._create_strategy_buttons_section()
        
        # ========== 提示信息区域 ==========
        self.tip_frame = ctk.CTkFrame(self)
        self.tip_frame.grid(row=2, column=0, padx=10, pady=(0, 5), sticky="ew")
        
        self.tip_label = ctk.CTkLabel(
            self.tip_frame,
            text=self.language_manager.get_text("select_folder_hint", "选中一个或多个文件夹，然后点击右侧按钮应用策略"),
            font=get_font(size=12),
            text_color="gray",
            wraplength=600
        )
        self.tip_label.pack(padx=10, pady=8)
        
        # ========== 底部按钮区域 ==========
        self.bottom_frame = ctk.CTkFrame(self)
        self.bottom_frame.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.bottom_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # 上一步按钮
        self.prev_step_btn = ctk.CTkButton(
            self.bottom_frame,
            text=self.language_manager.get_text("prev_step", "上一步"),
            height=45,
            font=get_font(size=15, weight="bold"),
            command=self._on_prev_step_click,
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            border_color=("gray70", "gray30")
        )
        self.prev_step_btn.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")
        
        # 下一步按钮（根据是否为编辑模式显示不同文字）
        is_edit_mode = "id" in self.task_config or "task_id" in self.task_config
        next_btn_text = self.language_manager.get_text("save_config", "保存配置") if is_edit_mode else self.language_manager.get_text("next_step", "下一步")
        
        self.next_step_btn = ctk.CTkButton(
            self.bottom_frame,
            text=next_btn_text,
            height=45,
            font=get_font(size=15, weight="bold"),
            command=self._on_next_step_click,
            fg_color="#3B8ED0",
            hover_color="#36719F"
        )
        self.next_step_btn.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        
        # 跳过按钮
        self.skip_btn = ctk.CTkButton(
            self.bottom_frame,
            text=self.language_manager.get_text("skip_config", "跳过配置"),
            height=45,
            font=get_font(size=15, weight="bold"),
            command=self._on_skip_click,
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            border_color=("gray70", "gray30")
        )
        self.skip_btn.grid(row=0, column=2, padx=5, pady=10, sticky="ew")
        
        # 取消按钮
        self.cancel_btn = ctk.CTkButton(
            self.bottom_frame,
            text=self.language_manager.get_text("cancel", "取消"),
            height=45,
            font=get_font(size=15, weight="bold"),
            command=self._on_cancel_click,
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            border_color=("gray70", "gray30")
        )
        self.cancel_btn.grid(row=0, column=3, padx=(5, 10), pady=10, sticky="ew")
    
    def _create_folder_list_section(self):
        """创建文件夹列表区域"""
        # 左侧容器
        self.left_frame = ctk.CTkFrame(self.content_frame)
        self.left_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(1, weight=1)
        
        # 根目录文件配置按钮
        self.root_config_frame = ctk.CTkFrame(self.left_frame)
        self.root_config_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.root_config_frame.grid_columnconfigure(1, weight=1)
        
        self.root_checkbox = ctk.CTkCheckBox(
            self.root_config_frame,
            text=self.language_manager.get_text("root_directory_files", "根目录文件"),
            font=get_font(size=14, weight="bold"),
            onvalue=True,
            offvalue=False,
            command=self._on_root_checkbox_change
        )
        self.root_checkbox.grid(row=0, column=0, padx=10, pady=8, sticky="w")
        if self.root_included:
            self.root_checkbox.select()
        
        # 根目录策略显示
        self.root_strategy_label = ctk.CTkLabel(
            self.root_config_frame,
            text=self._get_strategy_display_name(self.root_strategy),
            font=get_font(size=12),
            text_color=("gray50", "gray70")
        )
        self.root_strategy_label.grid(row=0, column=1, padx=10, pady=8, sticky="e")
        
        # 根目录策略按钮
        self.root_strategy_btn = ctk.CTkButton(
            self.root_config_frame,
            text=self.language_manager.get_text("config", "配置"),
            width=60,
            height=30,
            font=get_font(size=12),
            command=self._show_root_strategy_menu
        )
        self.root_strategy_btn.grid(row=0, column=2, padx=5, pady=8)
        
        # 子文件夹列表（可滚动）
        self.folder_scrollable = ctk.CTkScrollableFrame(
            self.left_frame,
            label_text=self.language_manager.get_text("folders_to_sync", "要同步的文件夹")
        )
        self.folder_scrollable.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.folder_scrollable.grid_columnconfigure(0, weight=1)
        
        # 全选/取消全选按钮
        self.select_all_frame = ctk.CTkFrame(self.left_frame)
        self.select_all_frame.grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        self.select_all_frame.grid_columnconfigure((0, 1), weight=1)
        
        self.select_all_btn = ctk.CTkButton(
            self.select_all_frame,
            text=self.language_manager.get_text("select_all", "全选"),
            height=30,
            font=get_font(size=12),
            command=self._select_all_folders
        )
        self.select_all_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        self.deselect_all_btn = ctk.CTkButton(
            self.select_all_frame,
            text=self.language_manager.get_text("deselect_all", "取消全选"),
            height=30,
            font=get_font(size=12),
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            border_color=("gray70", "gray30"),
            command=self._deselect_all_folders
        )
        self.deselect_all_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
    def _create_strategy_buttons_section(self):
        """创建策略按钮区域"""
        # 右侧容器（可滚动：策略按钮 + 筛选策略区域内容较多，超出窗口高度时可滚动查看）
        self.right_frame = ctk.CTkScrollableFrame(self.content_frame)
        self.right_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.right_frame.grid_columnconfigure(0, weight=1)
        
        # 策略标题
        self.strategy_title_label = ctk.CTkLabel(
            self.right_frame,
            text=self.language_manager.get_text("apply_strategy", "应用策略"),
            font=get_font(size=16, weight="bold")
        )
        self.strategy_title_label.pack(padx=10, pady=(15, 10))
        
        # 策略提示
        self.strategy_hint_label = ctk.CTkLabel(
            self.right_frame,
            text=self.language_manager.get_text("strategy_hint", "选中文件夹后点击下方按钮"),
            font=get_font(size=12),
            text_color="gray"
        )
        self.strategy_hint_label.pack(padx=10, pady=(0, 15))
        
        # 策略按钮容器
        self.strategy_buttons_frame = ctk.CTkFrame(self.right_frame)
        self.strategy_buttons_frame.pack(padx=10, pady=10, fill="x")
        
        # 创建5个策略按钮
        for i, (strategy_key, text_key, default_text) in enumerate(self.STRATEGIES):
            btn = ctk.CTkButton(
                self.strategy_buttons_frame,
                text=self.language_manager.get_text(text_key, default_text),
                height=38,
                font=get_font(size=13),
                command=lambda s=strategy_key: self._apply_strategy_to_selected(s),
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray85", "gray25"),
                border_width=2,
                border_color=("#3B8ED0", "#1F6AA5")
            )
            btn.pack(padx=5, pady=5, fill="x")
            self.strategy_buttons[strategy_key] = btn
        
        # 当前选中数量显示
        self.selection_info_frame = ctk.CTkFrame(self.right_frame)
        self.selection_info_frame.pack(padx=10, pady=8, fill="x")
        
        self.selection_count_label = ctk.CTkLabel(
            self.selection_info_frame,
            text=self.language_manager.get_text("selected_count", "已选中：0 个文件夹"),
            font=get_font(size=13)
        )
        self.selection_count_label.pack(padx=10, pady=6)
        
        # ========== v7.5: 筛选策略配置区域（每个文件夹独立配置）==========
        self.filter_section_frame = ctk.CTkFrame(self.right_frame)
        self.filter_section_frame.pack(padx=10, pady=(0, 15), fill="x")
        
        self.filter_section_title = ctk.CTkLabel(
            self.filter_section_frame,
            text=self.language_manager.get_text("filter_settings", "筛选策略"),
            font=get_font(size=14, weight="bold")
        )
        self.filter_section_title.pack(padx=10, pady=(10, 2), anchor="w")
        
        self.filter_section_hint = ctk.CTkLabel(
            self.filter_section_frame,
            text=self.language_manager.get_text(
                "folder_filter_hint",
                "为选中的文件夹配置筛选（扩展名/日期），未配置的文件夹同步全部文件"
            ),
            font=get_font(size=11),
            text_color="gray",
            wraplength=220,
            justify="left"
        )
        self.filter_section_hint.pack(padx=10, pady=(0, 8), anchor="w")
        
        self.filter_config_btn = ctk.CTkButton(
            self.filter_section_frame,
            text=self.language_manager.get_text("config_filter", "配置筛选"),
            height=35,
            font=get_font(size=13),
            command=self._apply_filter_to_selected,
            border_width=2,
            border_color=("#3B8ED0", "#1F6AA5"),
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25")
        )
        self.filter_config_btn.pack(padx=5, pady=4, fill="x")
        
        self.filter_clear_btn = ctk.CTkButton(
            self.filter_section_frame,
            text=self.language_manager.get_text("clear_filter", "清除筛选"),
            height=35,
            font=get_font(size=13),
            command=self._clear_filter_from_selected,
            border_width=2,
            border_color=("gray70", "gray30"),
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25")
        )
        self.filter_clear_btn.pack(padx=5, pady=(4, 10), fill="x")
    
    def _load_subfolders(self):
        """加载源目录的子文件夹列表"""
        # 清除现有内容
        for checkbox in self.folder_checkboxes.values():
            checkbox.destroy()
        self.folder_checkboxes.clear()
        self.selected_indices.clear()
        
        if not self.source_dir or not os.path.isdir(self.source_dir):
            self._show_empty_message()
            return
        
        # 获取子文件夹列表
        try:
            entries = os.listdir(self.source_dir)
            self.subfolders = [
                entry for entry in entries
                if os.path.isdir(os.path.join(self.source_dir, entry))
            ]
            self.subfolders.sort()  # 按名称排序
        except Exception as e:
            self._show_error_message(str(e))
            return
        
        if not self.subfolders:
            self._show_empty_message()
            return
        
        # 创建文件夹复选框列表
        for i, folder_name in enumerate(self.subfolders):
            # 获取该文件夹的策略
            folder_strategy = self.folder_strategies.get(folder_name, self.default_strategy)
            
            # 创建行框架
            row_frame = ctk.CTkFrame(self.folder_scrollable)
            row_frame.grid(row=i, column=0, padx=5, pady=3, sticky="ew")
            row_frame.grid_columnconfigure(1, weight=1)
            
            # 序号标签
            index_label = ctk.CTkLabel(
                row_frame,
                text=f"{i + 1}",
                font=get_font(size=13),
                width=30
            )
            index_label.grid(row=0, column=0, padx=(5, 5), pady=5)
            
            # 复选框
            checkbox = ctk.CTkCheckBox(
                row_frame,
                text=folder_name,
                font=get_font(size=13),
                onvalue=i,
                offvalue=-1,
                command=lambda idx=i: self._on_folder_select(idx)
            )
            checkbox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            
            # 策略显示标签
            strategy_label = ctk.CTkLabel(
                row_frame,
                text=self._get_strategy_display_name(folder_strategy),
                font=get_font(size=11),
                text_color=("gray50", "gray70")
            )
            strategy_label.grid(row=0, column=2, padx=5, pady=5, sticky="e")
            
            # v7.5: 筛选策略显示标签（未配置则不显示）
            filter_summary = self._get_filter_summary(folder_name)
            if filter_summary:
                filter_label = ctk.CTkLabel(
                    row_frame,
                    text=filter_summary,
                    font=get_font(size=11),
                    text_color=("#1F6AA5", "#3B8ED0")
                )
                filter_label.grid(row=0, column=3, padx=(0, 5), pady=5, sticky="e")
            
            self.folder_checkboxes[folder_name] = checkbox
    
    def _get_filter_summary(self, folder_name: str) -> str:
        """
        获取文件夹筛选策略的摘要显示文本
        
        Args:
            folder_name: 文件夹名
            
        Returns:
            摘要文本，未配置筛选时返回空字符串
        """
        cfg = self.folder_filters.get(folder_name)
        if not isinstance(cfg, dict):
            return ""
        
        parts = []
        if cfg.get("date_filter_enabled"):
            parts.append(self.language_manager.get_text("filter_summary_date", "日期"))
        if cfg.get("extension_filter_enabled"):
            parts.append(self.language_manager.get_text("filter_summary_ext", "扩展名"))
        
        if not parts:
            return ""
        return self.language_manager.get_text("filter_configured", "筛选") + ": " + "+".join(parts)
    
    def _show_empty_message(self):
        """显示空列表消息"""
        empty_label = ctk.CTkLabel(
            self.folder_scrollable,
            text=self.language_manager.get_text("no_folders", "无文件夹"),
            font=get_font(size=14),
            text_color="gray"
        )
        empty_label.grid(row=0, column=0, padx=10, pady=20)
    
    def _show_error_message(self, message: str):
        """显示错误消息"""
        error_label = ctk.CTkLabel(
            self.folder_scrollable,
            text=self.language_manager.format_text("error_with_message", message=message),
            font=get_font(size=14),
            text_color="red"
        )
        error_label.grid(row=0, column=0, padx=10, pady=20)
    
    def _get_strategy_display_name(self, strategy: str) -> str:
        """
        获取策略的显示名称
        
        Args:
            strategy: 策略键名
            
        Returns:
            策略显示名称
        """
        for key, text_key, default_text in self.STRATEGIES:
            if key == strategy:
                return self.language_manager.get_text(text_key, default_text)
        return strategy
    
    def _on_folder_select(self, index: int):
        """
        文件夹选择事件
        
        Args:
            index: 文件夹索引
        """
        checkbox = self.folder_checkboxes.get(self.subfolders[index])
        if checkbox and checkbox.get() != -1:
            if index not in self.selected_indices:
                self.selected_indices.append(index)
        else:
            if index in self.selected_indices:
                self.selected_indices.remove(index)
        
        # 更新选中数量显示
        self._update_selection_count()
    
    def _on_root_checkbox_change(self):
        """根目录复选框变化事件"""
        self.root_included = self.root_checkbox.get()
        
        # 更新提示信息
        if self.root_included:
            tip_text = self.language_manager.get_text(
                "root_included_hint", 
                "根目录文件已包含，策略：{strategy}"
            ).replace("{strategy}", self._get_strategy_display_name(self.root_strategy))
        else:
            tip_text = self.language_manager.get_text(
                "root_excluded_hint", 
                "根目录文件已排除"
            )
        self.tip_label.configure(text=tip_text)
    
    def _show_root_strategy_menu(self):
        """显示根目录策略选择菜单"""
        # 创建策略选择对话框
        dialog = StrategySelectDialog(
            self,
            self.language_manager,
            self.root_strategy,
            title=self.language_manager.get_text("root_strategy_config", "根目录策略配置")
        )
        
        # 等待用户选择
        if dialog.result:
            self.root_strategy = dialog.result
            self.root_strategy_label.configure(
                text=self._get_strategy_display_name(self.root_strategy)
            )
            self._on_root_checkbox_change()
    
    def _select_all_folders(self):
        """全选所有文件夹"""
        for folder_name, checkbox in self.folder_checkboxes.items():
            checkbox.select()
        
        self.selected_indices = list(range(len(self.subfolders)))
        self._update_selection_count()
    
    def _deselect_all_folders(self):
        """取消全选"""
        for folder_name, checkbox in self.folder_checkboxes.items():
            checkbox.deselect()
        
        self.selected_indices.clear()
        self._update_selection_count()
    
    def _update_selection_count(self):
        """更新选中数量显示"""
        count = len(self.selected_indices)
        text = self.language_manager.get_text(
            "selected_count", 
            "已选中：{count} 个文件夹"
        ).replace("{count}", str(count))
        self.selection_count_label.configure(text=text)
    
    def _apply_strategy_to_selected(self, strategy: str):
        """
        将策略应用到选中的文件夹
        
        Args:
            strategy: 策略键名
        """
        # 获取当前选中的文件夹数量
        selected_count = len(self.selected_indices)
        
        if selected_count == 0:
            self.tip_label.configure(
                text=self.language_manager.get_text("no_selection_hint", "请先选中文件夹"),
                text_color="orange"
            )
            return
        
        # 应用策略
        for index in self.selected_indices:
            folder_name = self.subfolders[index]
            self.folder_strategies[folder_name] = strategy
        
        # 更新提示信息（在清空选中之前）
        strategy_name = self._get_strategy_display_name(strategy)
        tip_text = self.language_manager.get_text(
            "apply_strategy_hint",
            "已将「{strategy}」应用到 {count} 个文件夹"
        ).replace("{strategy}", strategy_name).replace("{count}", str(selected_count))
        self.tip_label.configure(text=tip_text, text_color=("green", "#2CC985"))
        
        # 更新显示并清空选中
        self.selected_indices.clear()
        self._load_subfolders()
        self._update_selection_count()
    
    def _apply_filter_to_selected(self):
        """为选中的文件夹配置筛选策略（v7.5: 每个文件夹独立配置）"""
        if not self.selected_indices:
            self.tip_label.configure(
                text=self.language_manager.get_text("no_selection_hint", "请先选中文件夹"),
                text_color="orange"
            )
            return
        
        # 以第一个选中文件夹的现有配置作为预填值
        first_folder = self.subfolders[self.selected_indices[0]]
        current_filter = self.folder_filters.get(first_folder)
        if not isinstance(current_filter, dict):
            current_filter = None
        
        dialog = FilterConfigDialog(
            self,
            self.language_manager,
            current_filter=current_filter,
            title=self.language_manager.get_text("config_filter", "配置筛选")
        )
        
        if dialog.result is None:
            return
        
        # 应用到所有选中的文件夹；空配置表示不启用筛选
        for index in self.selected_indices:
            folder_name = self.subfolders[index]
            if dialog.result:
                self.folder_filters[folder_name] = dict(dialog.result)
            else:
                self.folder_filters.pop(folder_name, None)
        
        tip_text = self.language_manager.get_text(
            "apply_filter_hint",
            "已为 {count} 个文件夹配置筛选策略"
        ).replace("{count}", str(len(self.selected_indices)))
        self.tip_label.configure(text=tip_text, text_color=("green", "#2CC985"))
        
        # 刷新列表显示并清空选中
        self.selected_indices.clear()
        self._load_subfolders()
        self._update_selection_count()
    
    def _clear_filter_from_selected(self):
        """清除选中文件夹的筛选策略（未配置的文件夹同步全部文件）"""
        if not self.selected_indices:
            self.tip_label.configure(
                text=self.language_manager.get_text("no_selection_hint", "请先选中文件夹"),
                text_color="orange"
            )
            return
        
        for index in self.selected_indices:
            folder_name = self.subfolders[index]
            self.folder_filters.pop(folder_name, None)
        
        tip_text = self.language_manager.get_text(
            "clear_filter_hint",
            "已清除 {count} 个文件夹的筛选策略"
        ).replace("{count}", str(len(self.selected_indices)))
        self.tip_label.configure(text=tip_text, text_color=("green", "#2CC985"))
        
        self.selected_indices.clear()
        self._load_subfolders()
        self._update_selection_count()
    
    def _on_prev_step_click(self):
        """上一步按钮点击事件"""
        if self.on_prev_step:
            self.on_prev_step()
    
    def _on_skip_click(self):
        """跳过配置按钮点击事件"""
        # 构建更新后的配置，使用默认策略
        updated_config = self.task_config.copy()
        updated_config["folder_strategies"] = {}  # 空字典，使用全局默认策略
        updated_config["folder_filters"] = {}  # 空字典，不启用筛选
        updated_config["root_strategy"] = self.default_strategy
        updated_config["root_included"] = True
        updated_config["folders"] = []
        
        if self.on_next_step:
            self.on_next_step(updated_config)
    
    def _on_next_step_click(self):
        """下一步按钮点击事件"""
        # 构建更新后的配置
        updated_config = self.task_config.copy()
        updated_config["folder_strategies"] = self.folder_strategies
        updated_config["folder_filters"] = self.folder_filters
        updated_config["root_strategy"] = self.root_strategy
        updated_config["root_included"] = self.root_included
        updated_config["folders"] = [
            self.subfolders[i] for i in range(len(self.subfolders))
            if self.subfolders[i] not in self.folder_strategies or 
            self.folder_strategies[self.subfolders[i]] != "skip"
        ]
        
        if self.on_next_step:
            self.on_next_step(updated_config)
    
    def _on_cancel_click(self):
        """取消按钮点击事件"""
        if self.on_cancel:
            self.on_cancel()
    
    def get_config(self) -> Dict:
        """
        获取当前配置
        
        Returns:
            配置字典
        """
        return {
            "folder_strategies": self.folder_strategies,
            "folder_filters": self.folder_filters,
            "root_strategy": self.root_strategy,
            "root_included": self.root_included,
            "folders": self.selected_folders
        }
    
    def refresh(self):
        """刷新页面"""
        self._load_subfolders()
    
    def update_language(self):
        """更新界面语言"""
        # 更新标题
        self.title_label.configure(
            text=self.language_manager.get_text("folder_config", "文件夹配置")
        )
        
        # 更新根目录区域
        self.root_checkbox.configure(
            text=self.language_manager.get_text("root_directory_files", "根目录文件")
        )
        self.root_strategy_label.configure(
            text=self._get_strategy_display_name(self.root_strategy)
        )
        self.root_strategy_btn.configure(
            text=self.language_manager.get_text("config", "配置")
        )
        
        # 更新文件夹列表标题
        self.folder_scrollable.configure(
            label_text=self.language_manager.get_text("folders_to_sync", "要同步的文件夹")
        )
        
        # 更新全选按钮
        self.select_all_btn.configure(
            text=self.language_manager.get_text("select_all", "全选")
        )
        self.deselect_all_btn.configure(
            text=self.language_manager.get_text("deselect_all", "取消全选")
        )
        
        # 更新策略区域
        self.strategy_title_label.configure(
            text=self.language_manager.get_text("apply_strategy", "应用策略")
        )
        self.strategy_hint_label.configure(
            text=self.language_manager.get_text("strategy_hint", "选中文件夹后点击下方按钮")
        )
        
        for strategy_key, text_key, default_text in self.STRATEGIES:
            self.strategy_buttons[strategy_key].configure(
                text=self.language_manager.get_text(text_key, default_text)
            )
        
        # 更新筛选策略区域
        self.filter_section_title.configure(
            text=self.language_manager.get_text("filter_settings", "筛选策略")
        )
        self.filter_section_hint.configure(
            text=self.language_manager.get_text(
                "folder_filter_hint",
                "为选中的文件夹配置筛选（扩展名/日期），未配置的文件夹同步全部文件"
            )
        )
        self.filter_config_btn.configure(
            text=self.language_manager.get_text("config_filter", "配置筛选")
        )
        self.filter_clear_btn.configure(
            text=self.language_manager.get_text("clear_filter", "清除筛选")
        )
        
        # 更新提示信息
        self.tip_label.configure(
            text=self.language_manager.get_text("select_folder_hint", "选中一个或多个文件夹，然后点击右侧按钮应用策略")
        )
        
        # 更新底部按钮
        self.prev_step_btn.configure(
            text=self.language_manager.get_text("prev_step", "上一步")
        )
        
        is_edit_mode = "id" in self.task_config or "task_id" in self.task_config
        next_btn_text = self.language_manager.get_text("save_config", "保存配置") if is_edit_mode else self.language_manager.get_text("next_step", "下一步")
        self.next_step_btn.configure(text=next_btn_text)
        
        self.cancel_btn.configure(
            text=self.language_manager.get_text("cancel", "取消")
        )
        
        # 刷新文件夹列表显示
        self._load_subfolders()


class StrategySelectDialog(ctk.CTkToplevel):
    """策略选择对话框"""
    
    STRATEGIES = [
        ("conservative", "strategy_conservative", "保守模式"),
        ("newest_wins", "strategy_newest_wins", "时间优先"),
        ("source_wins", "strategy_source_wins", "源目录优先"),
        ("target_wins", "strategy_target_wins", "目标目录优先"),
        ("skip", "strategy_skip", "不同步")
    ]
    
    def __init__(self, master, language_manager, current_strategy: str, title: str = "策略选择"):
        """
        初始化策略选择对话框
        
        Args:
            master: 父组件
            language_manager: 语言管理器
            current_strategy: 当前策略
            title: 对话框标题
        """
        super().__init__(master)
        
        self.language_manager = language_manager
        self.current_strategy = current_strategy
        self.result = None
        
        # 设置窗口属性
        self.title(title)
        self.geometry("300x350")
        self.resizable(False, False)
        
        # 模态对话框
        self.transient(master)
        self.grab_set()
        
        # 创建界面
        self._create_widgets()
        
        # 等待窗口关闭
        self.wait_window()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 标题
        title_label = ctk.CTkLabel(
            self,
            text=self.language_manager.get_text("select_strategy", "选择策略"),
            font=get_font(size=16, weight="bold")
        )
        title_label.pack(padx=20, pady=(20, 15))
        
        # 策略按钮
        for strategy_key, text_key, default_text in self.STRATEGIES:
            is_selected = strategy_key == self.current_strategy
            
            btn = ctk.CTkButton(
                self,
                text=self.language_manager.get_text(text_key, default_text),
                height=40,
                font=get_font(size=14),
                command=lambda s=strategy_key: self._select_strategy(s),
                fg_color=("#3B8ED0", "#1F6AA5") if is_selected else "transparent",
                text_color="white" if is_selected else ("black", "white"),
                hover_color=("#36719F", "#144870") if is_selected else ("gray85", "gray25"),
                border_width=0 if is_selected else 2,
                border_color=("#3B8ED0", "#1F6AA5")
            )
            btn.pack(padx=20, pady=8, fill="x")
        
        # 取消按钮
        cancel_btn = ctk.CTkButton(
            self,
            text=self.language_manager.get_text("cancel", "取消"),
            height=35,
            font=get_font(size=13),
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            border_color=("gray70", "gray30"),
            command=self._cancel
        )
        cancel_btn.pack(padx=20, pady=(15, 20), fill="x")
    
    def _select_strategy(self, strategy: str):
        """选择策略"""
        self.result = strategy
        self.destroy()
    
    def _cancel(self):
        """取消选择"""
        self.result = None
        self.destroy()


class FilterConfigDialog(ctk.CTkToplevel):
    """筛选策略配置对话框（v7.5: 扩展名过滤 + 日期过滤，任务级配置，按文件夹独立生效）"""
    
    def __init__(self, master, language_manager, current_filter: Dict = None, title: str = "配置筛选"):
        """
        初始化筛选策略配置对话框
        
        Args:
            master: 父组件
            language_manager: 语言管理器
            current_filter: 现有筛选配置（用于预填），None 表示新配置
            title: 对话框标题
        """
        super().__init__(master)
        
        self.language_manager = language_manager
        self.current_filter = current_filter or {}
        self.result = None
        
        # 设置窗口属性
        self.title(title)
        self.geometry("420x520")
        self.resizable(False, False)
        
        # 模态对话框
        self.transient(master)
        self.grab_set()
        
        # 创建界面
        self._create_widgets()
        
        # 等待窗口关闭
        self.wait_window()
    
    def _create_widgets(self):
        """创建界面组件"""
        current = self.current_filter
        
        # 标题
        title_label = ctk.CTkLabel(
            self,
            text=self.language_manager.get_text("filter_settings", "筛选策略"),
            font=get_font(size=16, weight="bold")
        )
        title_label.pack(padx=20, pady=(15, 2))
        
        hint_label = ctk.CTkLabel(
            self,
            text=self.language_manager.get_text(
                "filter_dialog_hint",
                "日期过滤与扩展名过滤为 AND 关系，仅同步同时满足条件的文件"
            ),
            font=get_font(size=11),
            text_color="gray",
            wraplength=380
        )
        hint_label.pack(padx=20, pady=(0, 10))
        
        # ========== 日期过滤 ==========
        self.date_frame = ctk.CTkFrame(self)
        self.date_frame.pack(padx=15, pady=5, fill="x")
        
        self.date_switch = ctk.CTkSwitch(
            self.date_frame,
            text=self.language_manager.get_text("enable_date_filter", "启用日期过滤"),
            switch_width=50,
            switch_height=24,
            font=get_font(size=13)
        )
        if current.get("date_filter_enabled"):
            self.date_switch.select()
        self.date_switch.pack(padx=10, pady=(10, 5), anchor="w")
        
        date_range_frame = ctk.CTkFrame(self.date_frame, fg_color="transparent")
        date_range_frame.pack(padx=10, pady=(0, 10), fill="x")
        date_range_frame.grid_columnconfigure(1, weight=1)
        date_range_frame.grid_columnconfigure(3, weight=1)
        
        ctk.CTkLabel(
            date_range_frame,
            text=self.language_manager.get_text("date_filter_start", "开始日期") + ":",
            font=get_font(size=12)
        ).grid(row=0, column=0, padx=5, pady=3, sticky="w")
        
        self.date_start_entry = ctk.CTkEntry(
            date_range_frame,
            placeholder_text="YYYY-MM-DD",
            font=get_font(size=12)
        )
        if current.get("date_filter_start"):
            self.date_start_entry.insert(0, current["date_filter_start"])
        self.date_start_entry.grid(row=0, column=1, padx=5, pady=3, sticky="ew")
        
        ctk.CTkLabel(
            date_range_frame,
            text=self.language_manager.get_text("date_filter_end", "结束日期") + ":",
            font=get_font(size=12)
        ).grid(row=0, column=2, padx=5, pady=3, sticky="w")
        
        self.date_end_entry = ctk.CTkEntry(
            date_range_frame,
            placeholder_text="YYYY-MM-DD",
            font=get_font(size=12)
        )
        if current.get("date_filter_end"):
            self.date_end_entry.insert(0, current["date_filter_end"])
        self.date_end_entry.grid(row=0, column=3, padx=5, pady=3, sticky="ew")
        
        # ========== 扩展名过滤 ==========
        self.ext_frame = ctk.CTkFrame(self)
        self.ext_frame.pack(padx=15, pady=8, fill="x")
        
        self.ext_switch = ctk.CTkSwitch(
            self.ext_frame,
            text=self.language_manager.get_text("enable_extension_filter", "启用扩展名过滤"),
            switch_width=50,
            switch_height=24,
            font=get_font(size=13)
        )
        if current.get("extension_filter_enabled"):
            self.ext_switch.select()
        self.ext_switch.pack(padx=10, pady=(10, 5), anchor="w")
        
        ext_mode_frame = ctk.CTkFrame(self.ext_frame, fg_color="transparent")
        ext_mode_frame.pack(padx=10, pady=(0, 5), fill="x")
        
        ctk.CTkLabel(
            ext_mode_frame,
            text=self.language_manager.get_text("extension_filter_mode", "过滤模式") + ":",
            font=get_font(size=12)
        ).pack(side="left", padx=5)
        
        self.ext_mode_combo = ctk.CTkOptionMenu(
            ext_mode_frame,
            values=[
                self.language_manager.get_text("include_mode", "仅包含（白名单）"),
                self.language_manager.get_text("exclude_mode", "排除（黑名单）")
            ],
            font=get_font(size=12)
        )
        if current.get("extension_filter_mode") == "exclude":
            self.ext_mode_combo.set(self.language_manager.get_text("exclude_mode", "排除（黑名单）"))
        else:
            self.ext_mode_combo.set(self.language_manager.get_text("include_mode", "仅包含（白名单）"))
        self.ext_mode_combo.pack(side="left", padx=5)
        
        ctk.CTkLabel(
            self.ext_frame,
            text=self.language_manager.get_text(
                "extension_filter_list",
                "扩展名列表（用逗号分隔，如 .jpg,.png,.pdf）"
            ) + ":",
            font=get_font(size=12)
        ).pack(padx=10, pady=(5, 2), anchor="w")
        
        self.ext_list_entry = ctk.CTkEntry(
            self.ext_frame,
            placeholder_text=".jpg,.png,.pdf",
            font=get_font(size=12)
        )
        if current.get("extension_filter_list"):
            self.ext_list_entry.insert(0, ",".join(current["extension_filter_list"]))
        self.ext_list_entry.pack(padx=10, pady=(0, 10), fill="x")
        
        # 错误提示（默认隐藏）
        self.error_label = ctk.CTkLabel(
            self,
            text="",
            font=get_font(size=11),
            text_color="#E65100"
        )
        
        # ========== 底部按钮 ==========
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=15, pady=(10, 15), fill="x")
        btn_frame.grid_columnconfigure((0, 1), weight=1)
        
        confirm_btn = ctk.CTkButton(
            btn_frame,
            text=self.language_manager.get_text("confirm", "确定"),
            height=35,
            font=get_font(size=13),
            command=self._on_confirm
        )
        confirm_btn.grid(row=0, column=0, padx=5, sticky="ew")
        
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text=self.language_manager.get_text("cancel", "取消"),
            height=35,
            font=get_font(size=13),
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            border_color=("gray70", "gray30"),
            command=self._on_cancel
        )
        cancel_btn.grid(row=0, column=1, padx=5, sticky="ew")
    
    def _parse_ext_list(self, text: str) -> list:
        """解析扩展名列表字符串为规范化列表（小写、带点）"""
        result = []
        for item in text.split(","):
            item = item.strip().lower()
            if not item:
                continue
            if not item.startswith("."):
                item = "." + item
            if item not in result:
                result.append(item)
        return result
    
    def _on_confirm(self):
        """确定：校验并返回筛选配置"""
        import re
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        
        date_enabled = bool(self.date_switch.get())
        date_start = self.date_start_entry.get().strip()
        date_end = self.date_end_entry.get().strip()
        
        ext_enabled = bool(self.ext_switch.get())
        ext_list = self._parse_ext_list(self.ext_list_entry.get())
        mode = self.ext_mode_combo.get()
        exclude_text = self.language_manager.get_text("exclude_mode", "排除（黑名单）")
        ext_mode = "exclude" if mode == exclude_text else "include"
        
        # 校验日期格式
        if date_enabled:
            if (date_start and not date_pattern.match(date_start)) or \
               (date_end and not date_pattern.match(date_end)):
                self.error_label.configure(
                    text=self.language_manager.get_text("date_format_error", "日期格式错误，应为 YYYY-MM-DD")
                )
                self.error_label.pack(padx=20, pady=(5, 0))
                return
            if not date_start and not date_end:
                self.error_label.configure(
                    text=self.language_manager.get_text("date_range_empty", "启用日期过滤时请至少填写一个日期")
                )
                self.error_label.pack(padx=20, pady=(5, 0))
                return
        
        # 校验扩展名列表
        if ext_enabled and not ext_list:
            self.error_label.configure(
                text=self.language_manager.get_text("ext_list_empty", "启用扩展名过滤时请填写扩展名列表")
            )
            self.error_label.pack(padx=20, pady=(5, 0))
            return
        
        # 未启用任何过滤视为取消配置
        if not date_enabled and not ext_enabled:
            self.result = {}
            self.destroy()
            return
        
        self.result = {
            "date_filter_enabled": date_enabled,
            "date_filter_start": date_start if date_enabled else "",
            "date_filter_end": date_end if date_enabled else "",
            "extension_filter_enabled": ext_enabled,
            "extension_filter_mode": ext_mode,
            "extension_filter_list": ext_list if ext_enabled else []
        }
        self.destroy()
    
    def _on_cancel(self):
        """取消配置"""
        self.result = None
        self.destroy()