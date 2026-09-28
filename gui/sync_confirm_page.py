"""
文件同步工具 v7.3 - 同步确认页面
显示同步预估信息、任务配置摘要和策略配置，供用户确认后开始同步
支持快速模式警告对话框
"""

import os
import customtkinter as ctk
from backend.language_manager import get_font
from typing import Optional, Callable, Dict, List


class FastModeWarningDialog(ctk.CTkToplevel):
    """快速模式警告对话框"""
    
    def __init__(self, master, on_continue_fast=None, on_switch_safe=None):
        super().__init__(master)

        # master 为 SyncConfirmPage，持有 language_manager
        self._get_text = master.language_manager.get_text

        self.title(self._get_text("fast_mode_warning_title", "快速模式警告"))
        self.geometry("500x380")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.on_continue_fast = on_continue_fast
        self.on_switch_safe = on_switch_safe

        self._create_widgets()

    def _create_widgets(self):
        """创建对话框组件"""
        # 警告图标和标题
        self.warning_frame = ctk.CTkFrame(self, fg_color="#FFF3E0")
        self.warning_frame.pack(fill="x", padx=20, pady=(20, 10))

        self.warning_label = ctk.CTkLabel(
            self.warning_frame,
            text="⚠️ " + self._get_text("fast_mode_warning_title", "快速模式警告"),
            font=get_font(size=18, weight="bold"),
            text_color="#E65100"
        )
        self.warning_label.pack(padx=20, pady=15)

        # 警告内容
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.pack(fill="both", padx=20, pady=10)

        warnings = [
            self._get_text("fast_warning_1", "• 快速模式不会建立安全快照"),
            self._get_text("fast_warning_2", "• 同步过程中修改文件可能导致版本不一致或数据损坏"),
            self._get_text("fast_warning_3", "• 只要文件总量不超过 10TB，安全模式建立快照的额外时间通常只有几秒到几十秒"),
            self._get_text("fast_warning_4", "• 建议谨慎使用")
        ]
        
        for i, warning in enumerate(warnings):
            label = ctk.CTkLabel(
                self.content_frame,
                text=warning,
                font=get_font(size=13),
                text_color="gray70"
            )
            label.pack(anchor="w", padx=10, pady=(5 if i > 0 else 0, 5))
        
        # 按钮区域
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.pack(fill="x", padx=20, pady=(10, 20))
        self.button_frame.grid_columnconfigure((0, 1), weight=1)
        
        # 切换为安全模式按钮
        self.safe_mode_btn = ctk.CTkButton(
            self.button_frame,
            text=self._get_text("switch_to_safe_mode", "切换为安全模式"),
            height=45,
            font=get_font(size=14, weight="bold"),
            fg_color="#3B8ED0",
            hover_color="#36719F",
            command=self._on_switch_safe
        )
        self.safe_mode_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # 继续使用快速模式按钮
        self.fast_mode_btn = ctk.CTkButton(
            self.button_frame,
            text=self._get_text("continue_fast_mode", "继续使用快速模式"),
            height=45,
            font=get_font(size=14, weight="bold"),
            fg_color="#E65100",
            hover_color="#BF360C",
            command=self._on_continue_fast
        )
        self.fast_mode_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
    
    def _on_continue_fast(self):
        """继续使用快速模式"""
        if self.on_continue_fast:
            self.on_continue_fast()
        self.destroy()
    
    def _on_switch_safe(self):
        """切换为安全模式"""
        if self.on_switch_safe:
            self.on_switch_safe()
        self.destroy()


class SyncConfirmPage(ctk.CTkFrame):
    """同步确认页面：显示同步预估和配置摘要，供用户确认"""
    
    # 策略列表
    STRATEGIES = [
        ("conservative", "strategy_conservative", "保守模式"),
        ("newest_wins", "strategy_newest_wins", "时间优先"),
        ("source_wins", "strategy_source_wins", "源目录优先"),
        ("target_wins", "strategy_target_wins", "目标目录优先"),
        ("skip", "strategy_skip", "不同步")
    ]
    
    # 同步方向映射
    SYNC_DIRECTIONS = {
        "both": ("sync_both", "双向同步"),
        "source_to_target": ("sync_source_to_target", "源→目标"),
        "target_to_source": ("sync_target_to_source", "目标→源")
    }
    
    def __init__(self, master, app, task_config: Dict = None,
                 on_save_and_start: Optional[Callable] = None,
                 on_start_without_save: Optional[Callable] = None,
                 on_cancel: Optional[Callable] = None):
        """
        初始化同步确认页面
        
        Args:
            master: 父组件
            app: 主应用实例
            task_config: 任务配置字典
            on_save_and_start: 保存任务并开始同步回调
            on_start_without_save: 开始同步（不保存）回调
            on_cancel: 取消回调
        """
        super().__init__(master)
        
        self.app = app
        self.language_manager = app.language_manager
        self.config_manager = app.config_manager
        self.task_config = task_config or {}
        
        self.on_save_and_start = on_save_and_start
        self.on_start_without_save = on_start_without_save
        self.on_cancel = on_cancel
        
        # 同步预估数据（默认值）
        self.file_count = 0
        self.total_size = 0
        self.estimated_time = 0
        
        # 初始化同步删除设置
        if "sync_delete_enabled" not in self.task_config:
            settings = self.config_manager.get_settings()
            self.task_config["sync_delete_enabled"] = settings.get("sync_delete_default", False)
        
        # 创建界面
        self._create_widgets()
        
        # 计算预估数据
        self._calculate_estimate()
    
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
            text=self.language_manager.get_text("sync_confirm", "同步确认"),
            font=get_font(size=18, weight="bold")
        )
        self.title_label.pack(padx=10, pady=10)
        
        # ========== 中间主内容区域 ==========
        self.content_frame = ctk.CTkScrollableFrame(self)
        self.content_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        
        # 同步预估区域
        self._create_estimate_section()
        
        # 任务配置摘要区域
        self._create_task_summary_section()
        
        # 策略配置区域
        self._create_strategy_section()
        
        # 筛选策略区域
        self._create_filter_section()
        
        # 同步删除设置区域
        self._create_sync_delete_section()
        
        # ========== 底部按钮区域 ==========
        self.bottom_frame = ctk.CTkFrame(self)
        self.bottom_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.bottom_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # 保存任务并开始同步按钮
        self.save_and_start_btn = ctk.CTkButton(
            self.bottom_frame,
            text=self.language_manager.get_text("save_and_start", "保存任务并开始同步"),
            height=45,
            font=get_font(size=15, weight="bold"),
            command=self._on_save_and_start_click,
            fg_color="#2CC985",
            hover_color="#229E6A"
        )
        self.save_and_start_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # 开始同步（不保存）按钮
        self.start_without_save_btn = ctk.CTkButton(
            self.bottom_frame,
            text=self.language_manager.get_text("start_without_save", "开始同步（不保存）"),
            height=45,
            font=get_font(size=15, weight="bold"),
            command=self._on_start_without_save_click,
            fg_color="#3B8ED0",
            hover_color="#36719F"
        )
        self.start_without_save_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
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
        self.cancel_btn.grid(row=0, column=2, padx=10, pady=10, sticky="ew")
    
    def _create_estimate_section(self):
        """创建同步预估区域"""
        self.estimate_frame = ctk.CTkFrame(self.content_frame)
        self.estimate_frame.grid(row=0, column=0, padx=5, pady=10, sticky="ew")
        self.estimate_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # 区域标题
        self.estimate_title = ctk.CTkLabel(
            self.estimate_frame,
            text=self.language_manager.get_text("sync_estimate", "同步预估"),
            font=get_font(size=16, weight="bold")
        )
        self.estimate_title.grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 15), sticky="w")
        
        # 文件数量
        self.file_count_frame = ctk.CTkFrame(self.estimate_frame)
        self.file_count_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        self.file_count_label = ctk.CTkLabel(
            self.file_count_frame,
            text=self.language_manager.get_text("file_count", "文件数量"),
            font=get_font(size=13)
        )
        self.file_count_label.pack(padx=10, pady=(10, 5))
        
        self.file_count_value = ctk.CTkLabel(
            self.file_count_frame,
            text="0",
            font=get_font(size=24, weight="bold"),
            text_color=("#3B8ED0", "#1F6AA5")
        )
        self.file_count_value.pack(padx=10, pady=(0, 10))
        
        # 总大小
        self.total_size_frame = ctk.CTkFrame(self.estimate_frame)
        self.total_size_frame.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        
        self.total_size_label = ctk.CTkLabel(
            self.total_size_frame,
            text=self.language_manager.get_text("total_size", "总大小"),
            font=get_font(size=13)
        )
        self.total_size_label.pack(padx=10, pady=(10, 5))
        
        self.total_size_value = ctk.CTkLabel(
            self.total_size_frame,
            text="0 B",
            font=get_font(size=24, weight="bold"),
            text_color=("#2CC985", "#229E6A")
        )
        self.total_size_value.pack(padx=10, pady=(0, 10))
        
        # 预估时间
        self.estimated_time_frame = ctk.CTkFrame(self.estimate_frame)
        self.estimated_time_frame.grid(row=1, column=2, padx=10, pady=10, sticky="ew")
        
        self.estimated_time_label = ctk.CTkLabel(
            self.estimated_time_frame,
            text=self.language_manager.get_text("estimated_time", "预估时间"),
            font=get_font(size=13)
        )
        self.estimated_time_label.pack(padx=10, pady=(10, 5))
        
        self.estimated_time_value = ctk.CTkLabel(
            self.estimated_time_frame,
            text="--",
            font=get_font(size=24, weight="bold"),
            text_color=("gray50", "gray70")
        )
        self.estimated_time_value.pack(padx=10, pady=(0, 10))
    
    def _create_task_summary_section(self):
        """创建任务配置摘要区域"""
        self.summary_frame = ctk.CTkFrame(self.content_frame)
        self.summary_frame.grid(row=1, column=0, padx=5, pady=10, sticky="ew")
        self.summary_frame.grid_columnconfigure(1, weight=1)
        
        # 区域标题
        self.summary_title = ctk.CTkLabel(
            self.summary_frame,
            text=self.language_manager.get_text("task_config_summary", "任务配置摘要"),
            font=get_font(size=16, weight="bold")
        )
        self.summary_title.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 15), sticky="w")
        
        # 源目录
        self.source_dir_label = ctk.CTkLabel(
            self.summary_frame,
            text=self.language_manager.get_text("source_directory", "源目录") + ":",
            font=get_font(size=13, weight="bold")
        )
        self.source_dir_label.grid(row=1, column=0, padx=(10, 5), pady=8, sticky="w")
        
        self.source_dir_value = ctk.CTkLabel(
            self.summary_frame,
            text=self.task_config.get("source", "--"),
            font=get_font(size=13),
            text_color=("gray50", "gray70"),
            wraplength=400
        )
        self.source_dir_value.grid(row=1, column=1, padx=5, pady=8, sticky="w")
        
        # 目标目录
        self.target_dir_label = ctk.CTkLabel(
            self.summary_frame,
            text=self.language_manager.get_text("target_directory", "目标目录") + ":",
            font=get_font(size=13, weight="bold")
        )
        self.target_dir_label.grid(row=2, column=0, padx=(10, 5), pady=8, sticky="w")
        
        self.target_dir_value = ctk.CTkLabel(
            self.summary_frame,
            text=self.task_config.get("target", "--"),
            font=get_font(size=13),
            text_color=("gray50", "gray70"),
            wraplength=400
        )
        self.target_dir_value.grid(row=2, column=1, padx=5, pady=8, sticky="w")
        
        # 同步方向
        self.sync_direction_label = ctk.CTkLabel(
            self.summary_frame,
            text=self.language_manager.get_text("sync_mode", "同步模式") + ":",
            font=get_font(size=13, weight="bold")
        )
        self.sync_direction_label.grid(row=3, column=0, padx=(10, 5), pady=8, sticky="w")
        
        sync_direction = self.task_config.get("sync_direction", "both")
        direction_text = self._get_sync_direction_display(sync_direction)
        self.sync_direction_value = ctk.CTkLabel(
            self.summary_frame,
            text=direction_text,
            font=get_font(size=13),
            text_color=("gray50", "gray70")
        )
        self.sync_direction_value.grid(row=3, column=1, padx=5, pady=8, sticky="w")
        
        # 运行模式
        self.run_mode_label = ctk.CTkLabel(
            self.summary_frame,
            text=self.language_manager.get_text("run_mode", "运行模式") + ":",
            font=get_font(size=13, weight="bold")
        )
        self.run_mode_label.grid(row=4, column=0, padx=(10, 5), pady=8, sticky="w")
        
        run_mode = self.task_config.get("mode", self.task_config.get("run_mode", "safe"))
        run_mode_text = self.language_manager.get_text(
            "fast_mode" if run_mode == "fast" else "safe_mode",
            "快速模式" if run_mode == "fast" else "安全模式"
        )
        self.run_mode_value = ctk.CTkLabel(
            self.summary_frame,
            text=run_mode_text,
            font=get_font(size=13),
            text_color=("gray50", "gray70")
        )
        self.run_mode_value.grid(row=4, column=1, padx=5, pady=8, sticky="w")
        
        # 多线程扫描
        self.scan_thread_label = ctk.CTkLabel(
            self.summary_frame,
            text=self.language_manager.get_text("scan_thread_mode", "多线程扫描") + ":",
            font=get_font(size=13, weight="bold")
        )
        self.scan_thread_label.grid(row=5, column=0, padx=(10, 5), pady=8, sticky="w")
        
        use_multithreading_scan = self.task_config.get("use_multithreading_scan", True)
        scan_thread_text = self.language_manager.get_text(
            "multi_thread" if use_multithreading_scan else "single_thread",
            "开启" if use_multithreading_scan else "关闭"
        )
        self.scan_thread_value = ctk.CTkLabel(
            self.summary_frame,
            text=scan_thread_text,
            font=get_font(size=13),
            text_color=("gray50", "gray70")
        )
        self.scan_thread_value.grid(row=5, column=1, padx=5, pady=8, sticky="w")
        
        # 多线程复制
        self.copy_thread_label = ctk.CTkLabel(
            self.summary_frame,
            text=self.language_manager.get_text("copy_thread_mode", "多线程同步") + ":",
            font=get_font(size=13, weight="bold")
        )
        self.copy_thread_label.grid(row=6, column=0, padx=(10, 5), pady=8, sticky="w")
        
        use_multithreading_copy = self.task_config.get("use_multithreading_copy", False)
        copy_thread_text = self.language_manager.get_text(
            "multi_thread" if use_multithreading_copy else "single_thread",
            "开启" if use_multithreading_copy else "关闭"
        )
        self.copy_thread_value = ctk.CTkLabel(
            self.summary_frame,
            text=copy_thread_text,
            font=get_font(size=13),
            text_color=("gray50", "gray70")
        )
        self.copy_thread_value.grid(row=6, column=1, padx=5, pady=8, sticky="w")
    
    def _create_strategy_section(self):
        """创建策略配置区域"""
        self.strategy_frame = ctk.CTkFrame(self.content_frame)
        self.strategy_frame.grid(row=2, column=0, padx=5, pady=10, sticky="ew")
        self.strategy_frame.grid_columnconfigure(0, weight=1)
        
        # 区域标题
        self.strategy_title = ctk.CTkLabel(
            self.strategy_frame,
            text=self.language_manager.get_text("strategy_config", "策略配置"),
            font=get_font(size=16, weight="bold")
        )
        self.strategy_title.grid(row=0, column=0, padx=10, pady=(10, 15), sticky="w")
        
        # 全局策略
        self.global_strategy_frame = ctk.CTkFrame(self.strategy_frame)
        self.global_strategy_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.global_strategy_frame.grid_columnconfigure(1, weight=1)
        
        self.global_strategy_label = ctk.CTkLabel(
            self.global_strategy_frame,
            text=self.language_manager.get_text("global_strategy", "全局策略") + ":",
            font=get_font(size=13, weight="bold")
        )
        self.global_strategy_label.grid(row=0, column=0, padx=(10, 5), pady=8, sticky="w")
        
        default_strategy = self.task_config.get("default_strategy", "conservative")
        strategy_text = self._get_strategy_display_name(default_strategy)
        self.global_strategy_value = ctk.CTkLabel(
            self.global_strategy_frame,
            text=strategy_text,
            font=get_font(size=13),
            text_color=("#3B8ED0", "#1F6AA5")
        )
        self.global_strategy_value.grid(row=0, column=1, padx=5, pady=8, sticky="w")
        
        # 根目录策略
        root_included = self.task_config.get("root_included", False)
        root_strategy = self.task_config.get("root_strategy", default_strategy)
        
        self.root_strategy_frame = ctk.CTkFrame(self.strategy_frame)
        self.root_strategy_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.root_strategy_frame.grid_columnconfigure(1, weight=1)
        
        self.root_strategy_label = ctk.CTkLabel(
            self.root_strategy_frame,
            text=self.language_manager.get_text("root_directory_files", "根目录文件") + ":",
            font=get_font(size=13, weight="bold")
        )
        self.root_strategy_label.grid(row=0, column=0, padx=(10, 5), pady=8, sticky="w")
        
        if root_included:
            root_text = self._get_strategy_display_name(root_strategy)
            self.root_strategy_value = ctk.CTkLabel(
                self.root_strategy_frame,
                text=root_text,
                font=get_font(size=13),
                text_color=("#2CC985", "#229E6A")
            )
        else:
            self.root_strategy_value = ctk.CTkLabel(
                self.root_strategy_frame,
                text=self.language_manager.get_text("excluded", "已排除"),
                font=get_font(size=13),
                text_color=("gray50", "gray70")
            )
        self.root_strategy_value.grid(row=0, column=1, padx=5, pady=8, sticky="w")
        
        # 文件夹策略列表 - 显示所有文件夹及其策略
        folder_strategies = self.task_config.get("folder_strategies", {})
        default_strategy = self.task_config.get("default_strategy", "conservative")
        
        # 获取所有子文件夹
        source_dir = self.task_config.get("source", "")
        all_folders = []
        if source_dir and os.path.isdir(source_dir):
            try:
                entries = os.listdir(source_dir)
                all_folders = [entry for entry in entries if os.path.isdir(os.path.join(source_dir, entry))]
                all_folders.sort()
            except:
                pass
        
        self.folder_strategy_title = ctk.CTkLabel(
            self.strategy_frame,
            text=self.language_manager.get_text("folder_strategies", "文件夹策略") + ":",
            font=get_font(size=13, weight="bold")
        )
        self.folder_strategy_title.grid(row=3, column=0, padx=(10, 5), pady=(10, 5), sticky="w")
        
        # 创建文件夹策略列表容器
        self.folder_list_frame = ctk.CTkScrollableFrame(self.strategy_frame)
        self.folder_list_frame.grid(row=4, column=0, padx=10, pady=5, sticky="nsew")
        self.folder_list_frame.grid_columnconfigure(1, weight=1)
        
        if all_folders:
            for i, folder_name in enumerate(all_folders):
                # 获取该文件夹的策略（单独配置或默认）
                strategy = folder_strategies.get(folder_name, default_strategy)
                
                # 创建行框架
                row_frame = ctk.CTkFrame(self.folder_list_frame)
                row_frame.grid(row=i, column=0, padx=5, pady=3, sticky="ew")
                row_frame.grid_columnconfigure(1, weight=1)
                
                # 文件夹名
                folder_label = ctk.CTkLabel(
                    row_frame,
                    text=f"  {folder_name}",
                    font=get_font(size=12)
                )
                folder_label.grid(row=0, column=0, padx=(10, 5), pady=5, sticky="w")
                
                # 策略
                strategy_text = self._get_strategy_display_name(strategy)
                strategy_color = ("gray50", "gray70") if strategy == "skip" else ("black", "white")
                
                # 如果使用默认策略，添加标记
                if strategy == default_strategy and folder_name not in folder_strategies:
                    strategy_text += " (默认)"
                
                strategy_label = ctk.CTkLabel(
                    row_frame,
                    text=strategy_text,
                    font=get_font(size=12),
                    text_color=strategy_color
                )
                strategy_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        else:
            self.no_folder_strategy_label = ctk.CTkLabel(
                self.folder_list_frame,
                text=self.language_manager.get_text("no_folders", "无文件夹"),
                font=get_font(size=12),
                text_color=("gray50", "gray70")
            )
            self.no_folder_strategy_label.grid(row=0, column=0, padx=10, pady=20, sticky="w")
    
    def _create_filter_section(self):
        """创建筛选策略展示区域"""
        self.filter_frame = ctk.CTkFrame(self.content_frame)
        self.filter_frame.grid(row=3, column=0, padx=5, pady=10, sticky="ew")
        self.filter_frame.grid_columnconfigure(0, weight=1)
        
        # 区域标题
        self.filter_title = ctk.CTkLabel(
            self.filter_frame,
            text=self.language_manager.get_text("filter_strategy", "筛选策略"),
            font=get_font(size=16, weight="bold")
        )
        self.filter_title.grid(row=0, column=0, padx=10, pady=(10, 15), sticky="w")
        
        # 获取任务的筛选策略配置
        folder_filters = self.task_config.get("folder_filters", {}) or {}
        
        # 过滤掉空配置（未启用任何过滤）
        active_filters = {}
        for folder_name, cfg in folder_filters.items():
            if isinstance(cfg, dict) and (cfg.get("date_filter_enabled") or cfg.get("extension_filter_enabled")):
                active_filters[folder_name] = cfg
        
        if not active_filters:
            # 未启用筛选
            self.filter_not_enabled_label = ctk.CTkLabel(
                self.filter_frame,
                text=self.language_manager.get_text("filter_not_enabled", "未启用筛选"),
                font=get_font(size=13),
                text_color=("gray50", "gray70")
            )
            self.filter_not_enabled_label.grid(row=1, column=0, padx=10, pady=(0, 15), sticky="w")
        else:
            # 列出每个有筛选策略的文件夹
            row = 1
            for folder_name, cfg in active_filters.items():
                # 文件夹名称
                folder_label = ctk.CTkLabel(
                    self.filter_frame,
                    text=f"  {folder_name}",
                    font=get_font(size=13, weight="bold")
                )
                folder_label.grid(row=row, column=0, padx=(10, 5), pady=(8, 2), sticky="w")
                row += 1
                
                # 构建筛选详情文本
                detail_parts = []
                
                # 日期过滤
                if cfg.get("date_filter_enabled"):
                    date_start = cfg.get("date_filter_start", "")
                    date_end = cfg.get("date_filter_end", "")
                    date_text = self.language_manager.get_text("filter_summary_date", "日期")
                    if date_start and date_end:
                        date_text += f": {date_start} ~ {date_end}"
                    elif date_start:
                        date_text += f": >= {date_start}"
                    elif date_end:
                        date_text += f": <= {date_end}"
                    detail_parts.append(date_text)
                
                # 扩展名过滤
                if cfg.get("extension_filter_enabled"):
                    ext_mode = cfg.get("extension_filter_mode", "include")
                    ext_list = cfg.get("extension_filter_list", [])
                    mode_text = self.language_manager.get_text("include_mode" if ext_mode == "include" else "exclude_mode",
                                                                "仅包含" if ext_mode == "include" else "排除")
                    ext_str = ", ".join(ext_list) if isinstance(ext_list, list) else str(ext_list)
                    detail_parts.append(f"{mode_text}: {ext_str}")
                
                if detail_parts:
                    detail_label = ctk.CTkLabel(
                        self.filter_frame,
                        text="    " + "  |  ".join(detail_parts),
                        font=get_font(size=12),
                        text_color=("gray50", "gray70")
                    )
                    detail_label.grid(row=row, column=0, padx=(10, 5), pady=(0, 8), sticky="w")
                    row += 1
    
    def _create_sync_delete_section(self):
        """创建同步删除设置区域"""
        self.sync_delete_frame = ctk.CTkFrame(self.content_frame)
        self.sync_delete_frame.grid(row=4, column=0, padx=5, pady=10, sticky="ew")
        self.sync_delete_frame.grid_columnconfigure(0, weight=1)
        
        # 区域标题
        self.sync_delete_title = ctk.CTkLabel(
            self.sync_delete_frame,
            text=self.language_manager.get_text("sync_delete", "同步删除"),
            font=get_font(size=16, weight="bold")
        )
        self.sync_delete_title.grid(row=0, column=0, padx=10, pady=(10, 15), sticky="w")
        
        # 获取默认设置
        settings = self.config_manager.get_settings()
        sync_delete_default = settings.get("sync_delete_default", False)
        
        # 同步删除复选框
        self.sync_delete_var = ctk.BooleanVar(value=sync_delete_default)
        self.sync_delete_checkbox = ctk.CTkCheckBox(
            self.sync_delete_frame,
            text=self.language_manager.get_text(
                "sync_delete_checkbox",
                "同步删除：检测并删除上次存在但本次消失的文件"
            ),
            variable=self.sync_delete_var,
            command=self._on_sync_delete_checkbox_change,
            font=get_font(size=13)
        )
        self.sync_delete_checkbox.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")
        
        # 警告信息（默认隐藏）
        self.sync_delete_warning_frame = ctk.CTkFrame(
            self.sync_delete_frame,
            fg_color="#FFF3E0"
        )
        self.sync_delete_warning_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        self.sync_delete_warning_label = ctk.CTkLabel(
            self.sync_delete_warning_frame,
            text=self.language_manager.get_text(
                "sync_delete_warning",
                "⚠️ 警告：\n\n• 此功能会删除文件，请确认您确实不想要这些文件\n• 删除的文件会移入最近删除，可在最近删除中恢复\n• 建议仅在确认无误后使用"
            ),
            font=get_font(size=12),
            text_color="#E65100",
            justify="left"
        )
        self.sync_delete_warning_label.pack(padx=10, pady=10)
        
        # 根据默认状态显示/隐藏警告
        if sync_delete_default:
            self.sync_delete_warning_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        else:
            self.sync_delete_warning_frame.grid_forget()
    
    def _on_sync_delete_checkbox_change(self):
        """同步删除复选框变化事件"""
        is_checked = self.sync_delete_var.get()
        
        if is_checked:
            self.sync_delete_warning_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        else:
            self.sync_delete_warning_frame.grid_forget()
        
        # 将同步删除设置添加到任务配置
        self.task_config["sync_delete_enabled"] = is_checked
    
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
    
    def _get_sync_direction_display(self, direction: str) -> str:
        """
        获取同步方向的显示名称
        
        Args:
            direction: 同步方向键名
            
        Returns:
            同步方向显示名称
        """
        if direction in self.SYNC_DIRECTIONS:
            text_key, default_text = self.SYNC_DIRECTIONS[direction]
            return self.language_manager.get_text(text_key, default_text)
        return direction
    
    def _calculate_estimate(self):
        """
        计算同步预估数据
        
        v7.5: 改用 SyncEngine.preview_sync() 获取预估数据，
        确保预估与引擎实际同步行为一致（包括按文件夹的筛选策略、策略跳过等）。
        """
        source_dir = self.task_config.get("source", "")
        target_dir = self.task_config.get("target", "")
        sync_direction = self.task_config.get("sync_direction", "both")
        mode = self.task_config.get("mode", self.task_config.get("run_mode", "safe"))
        folder_strategies = self.task_config.get("folder_strategies", {})
        default_strategy = self.task_config.get("default_strategy", "conservative")
        root_included = self.task_config.get("root_included", False)
        root_strategy = self.task_config.get("root_strategy", "conservative")
        # v7.5: 筛选策略为任务级配置（按文件夹独立，未配置的文件夹不启用筛选）
        folder_filters = self.task_config.get("folder_filters", {})
        
        if not source_dir or not os.path.isdir(source_dir):
            self._update_estimate_display()
            return
        
        try:
            # 使用与实际同步相同的引擎进行预估，确保一致
            from backend.sync_engine import FileSyncEngine as _SyncEngine
            preview_engine = _SyncEngine(
                mode=mode,
                default_strategy=default_strategy,
                folder_strategies=folder_strategies,
                root_included=root_included,
                root_strategy=root_strategy,
                folder_filters=folder_filters
            )
            preview = preview_engine.preview_sync(
                source_dir=source_dir,
                target_dir=target_dir,
                direction=sync_direction
            )
            
            self.file_count = preview.total_files
            self.total_size = preview.total_size
            self.estimated_time = preview.estimated_time
        except Exception as e:
            print(f"计算预估失败: {e}")
            self.file_count = 0
            self.total_size = 0
            self.estimated_time = 0
        
        # 更新显示
        self._update_estimate_display()
    
    def _update_estimate_display(self):
        """更新预估数据显示"""
        # 更新文件数量
        self.file_count_value.configure(text=str(self.file_count))
        
        # 更新总大小（转换为合适的单位）
        size_text = self._format_size(self.total_size)
        self.total_size_value.configure(text=size_text)
        
        # 更新预估时间
        time_text = self._format_time(self.estimated_time)
        self.estimated_time_value.configure(text=time_text)
    
    def _format_size(self, size: int) -> str:
        """
        格式化文件大小
        
        Args:
            size: 文件大小（字节）
            
        Returns:
            格式化后的大小字符串
        """
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.2f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.2f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"
    
    def _format_time(self, seconds: float) -> str:
        """
        格式化时间
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化后的时间字符串
        """
        if seconds < 1:
            return "< 1秒"
        elif seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}分{secs}秒"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}时{minutes}分"
    
    def _on_save_and_start_click(self):
        """保存任务并开始同步按钮点击事件"""
        run_mode = self.task_config.get("mode", self.task_config.get("run_mode", "safe"))
        
        if run_mode == "fast":
            FastModeWarningDialog(
                self,
                on_continue_fast=lambda: self._execute_save_and_start(),
                on_switch_safe=lambda: self._switch_to_safe_and_save_and_start()
            )
        else:
            self._execute_save_and_start()
    
    def _execute_save_and_start(self):
        """执行保存并开始同步"""
        if self.on_save_and_start:
            self.on_save_and_start(self.task_config)
    
    def _switch_to_safe_and_save_and_start(self):
        """切换为安全模式并保存开始同步"""
        self.task_config["mode"] = "safe"
        if self.on_save_and_start:
            self.on_save_and_start(self.task_config)
    
    def _on_start_without_save_click(self):
        """开始同步（不保存）按钮点击事件"""
        run_mode = self.task_config.get("mode", self.task_config.get("run_mode", "safe"))
        
        if run_mode == "fast":
            FastModeWarningDialog(
                self,
                on_continue_fast=lambda: self._execute_start_without_save(),
                on_switch_safe=lambda: self._switch_to_safe_and_start_without_save()
            )
        else:
            self._execute_start_without_save()
    
    def _execute_start_without_save(self):
        """执行开始同步（不保存）"""
        if self.on_start_without_save:
            self.on_start_without_save(self.task_config)
    
    def _switch_to_safe_and_start_without_save(self):
        """切换为安全模式并开始同步（不保存）"""
        self.task_config["mode"] = "safe"
        if self.on_start_without_save:
            self.on_start_without_save(self.task_config)
    
    def _on_cancel_click(self):
        """取消按钮点击事件"""
        if self.on_cancel:
            self.on_cancel()
    
    def get_task_config(self) -> Dict:
        """
        获取当前任务配置
        
        Returns:
            任务配置字典
        """
        return self.task_config
    
    def refresh(self):
        """刷新页面"""
        self._calculate_estimate()
    
    def update_language(self):
        """更新界面语言"""
        # 更新标题
        self.title_label.configure(
            text=self.language_manager.get_text("sync_confirm", "同步确认")
        )
        
        # 更新预估区域
        self.estimate_title.configure(
            text=self.language_manager.get_text("sync_estimate", "同步预估")
        )
        self.file_count_label.configure(
            text=self.language_manager.get_text("file_count", "文件数量")
        )
        self.total_size_label.configure(
            text=self.language_manager.get_text("total_size", "总大小")
        )
        self.estimated_time_label.configure(
            text=self.language_manager.get_text("estimated_time", "预估时间")
        )
        
        # 更新摘要区域
        self.summary_title.configure(
            text=self.language_manager.get_text("task_config_summary", "任务配置摘要")
        )
        self.source_dir_label.configure(
            text=self.language_manager.get_text("source_directory", "源目录") + ":"
        )
        self.target_dir_label.configure(
            text=self.language_manager.get_text("target_directory", "目标目录") + ":"
        )
        self.sync_direction_label.configure(
            text=self.language_manager.get_text("sync_mode", "同步模式") + ":"
        )
        self.run_mode_label.configure(
            text=self.language_manager.get_text("run_mode", "运行模式") + ":"
        )
        self.scan_thread_label.configure(
            text=self.language_manager.get_text("scan_thread_mode", "多线程扫描") + ":"
        )
        self.copy_thread_label.configure(
            text=self.language_manager.get_text("copy_thread_mode", "多线程同步") + ":"
        )
        
        # 更新同步方向显示
        sync_direction = self.task_config.get("sync_direction", "both")
        self.sync_direction_value.configure(text=self._get_sync_direction_display(sync_direction))
        
        # 更新运行模式显示
        run_mode = self.task_config.get("mode", self.task_config.get("run_mode", "safe"))
        run_mode_text = self.language_manager.get_text(
            "fast_mode" if run_mode == "fast" else "safe_mode",
            "快速模式" if run_mode == "fast" else "安全模式"
        )
        self.run_mode_value.configure(text=run_mode_text)
        
        # 更新多线程扫描显示
        use_multithreading_scan = self.task_config.get("use_multithreading_scan", False)
        scan_thread_text = self.language_manager.get_text(
            "multi_thread" if use_multithreading_scan else "single_thread",
            "开启" if use_multithreading_scan else "关闭"
        )
        self.scan_thread_value.configure(text=scan_thread_text)
        
        # 更新多线程同步显示
        use_multithreading_copy = self.task_config.get("use_multithreading_copy", False)
        copy_thread_text = self.language_manager.get_text(
            "multi_thread" if use_multithreading_copy else "single_thread",
            "开启" if use_multithreading_copy else "关闭"
        )
        self.copy_thread_value.configure(text=copy_thread_text)
        
        # 更新策略区域
        self.strategy_title.configure(
            text=self.language_manager.get_text("strategy_config", "策略配置")
        )
        # 更新筛选策略区域标题
        if hasattr(self, 'filter_title'):
            self.filter_title.configure(
                text=self.language_manager.get_text("filter_strategy", "筛选策略")
            )
        self.global_strategy_label.configure(
            text=self.language_manager.get_text("global_strategy", "全局策略") + ":"
        )
        
        default_strategy = self.task_config.get("default_strategy", "conservative")
        self.global_strategy_value.configure(text=self._get_strategy_display_name(default_strategy))
        
        self.root_strategy_label.configure(
            text=self.language_manager.get_text("root_directory_files", "根目录文件") + ":"
        )
        
        root_included = self.task_config.get("root_included", False)
        root_strategy = self.task_config.get("root_strategy", default_strategy)
        if root_included:
            self.root_strategy_value.configure(text=self._get_strategy_display_name(root_strategy))
        else:
            self.root_strategy_value.configure(
                text=self.language_manager.get_text("excluded", "已排除")
            )
        
        # 更新底部按钮
        self.save_and_start_btn.configure(
            text=self.language_manager.get_text("save_and_start", "保存任务并开始同步")
        )
        self.start_without_save_btn.configure(
            text=self.language_manager.get_text("start_without_save", "开始同步（不保存）")
        )
        self.cancel_btn.configure(
            text=self.language_manager.get_text("cancel", "取消")
        )
        
        # 刷新预估显示
        self._update_estimate_display()