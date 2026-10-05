"""
文件同步工具 v7.0 - 创建任务页面
用于创建新的同步任务，配置源目录、目标目录、同步模式等
"""

import customtkinter as ctk
from backend.language_manager import get_font
from tkinter import filedialog
from typing import Optional, Callable, Dict


class CreateTaskPage(ctk.CTkFrame):
    """创建任务页面：配置新任务的各项参数"""
    
    def __init__(self, master, language_manager, config_manager, task_manager=None,
                 on_next_step: Optional[Callable] = None,
                 on_cancel: Optional[Callable] = None,
                 on_folder_config: Optional[Callable] = None,
                 on_save: Optional[Callable] = None,
                 task_id: Optional[str] = None,
                 edit_mode: bool = False):
        """
        初始化创建任务页面
        
        Args:
            master: 父组件
            language_manager: 语言管理器
            config_manager: 配置管理器
            task_manager: 任务管理器
            on_next_step: 下一步回调函数
            on_cancel: 取消回调函数
            on_folder_config: 单独配置文件夹回调函数
            on_save: 保存回调函数（用于编辑模式）
            task_id: 任务ID（用于编辑模式）
            edit_mode: 是否为编辑模式
        """
        super().__init__(master)
        
        self.language_manager = language_manager
        self.config_manager = config_manager
        self.task_manager = task_manager
        self.on_next_step = on_next_step
        self.on_cancel = on_cancel
        self.on_folder_config = on_folder_config
        self.on_save = on_save
        self.task_id = task_id
        self.edit_mode = edit_mode
        
        # 当前配置状态
        self.source_dir = ""
        self.target_dir = ""
        self.sync_direction = "both"  # both, source_to_target, target_to_source
        self.use_multithreading_scan = False  # 是否使用多线程扫描
        self.use_multithreading_copy = False  # 是否使用多线程复制
        self.run_mode = "safe"  # fast, safe
        self.default_strategy = "conservative"  # conservative, newest_wins, source_wins, target_wins
        # v7.6: 同步成功后执行的命令（可选，留空不执行）
        self.post_sync_command = ""
        
        # 创建界面
        self._create_widgets()
        
        # 如果是编辑模式，加载任务数据
        if self.edit_mode and self.task_id and self.task_manager:
            self._load_task_data()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 配置网格权重
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # 主内容区域（可滚动）
        self.content_frame = ctk.CTkScrollableFrame(self)
        self.content_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.content_frame.grid_columnconfigure(1, weight=1)
        
        # ========== 源目录区域 ==========
        self._create_directory_section(
            row=0,
            label_key="source_directory",
            default_text="源目录",
            entry_var_name="source_entry",
            browse_command=self._browse_source
        )
        
        # ========== 目标目录区域 ==========
        self._create_directory_section(
            row=1,
            label_key="target_directory",
            default_text="目标目录",
            entry_var_name="target_entry",
            browse_command=self._browse_target
        )
        
        # ========== 同步模式区域 ==========
        self.sync_mode_frame = ctk.CTkFrame(self.content_frame)
        self.sync_mode_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=10, sticky="ew")
        self.sync_mode_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # 同步模式标签
        self.sync_mode_label = ctk.CTkLabel(
            self.sync_mode_frame,
            text=self.language_manager.get_text("sync_mode", "同步模式"),
            font=get_font(size=14, weight="bold")
        )
        self.sync_mode_label.grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 5), sticky="w")
        
        # 同步模式按钮组
        self.sync_both_btn = ctk.CTkButton(
            self.sync_mode_frame,
            text=self.language_manager.get_text("sync_both", "双向同步"),
            height=35,
            font=get_font(size=13),
            command=lambda: self._set_sync_direction("both"),
            fg_color=("#3B8ED0", "#1F6AA5"),
            hover_color=("#36719F", "#144870")
        )
        self.sync_both_btn.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        self.sync_source_btn = ctk.CTkButton(
            self.sync_mode_frame,
            text=self.language_manager.get_text("sync_source_to_target", "源→目标"),
            height=35,
            font=get_font(size=13),
            command=lambda: self._set_sync_direction("source_to_target"),
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            border_color=("#3B8ED0", "#1F6AA5")
        )
        self.sync_source_btn.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        
        self.sync_target_btn = ctk.CTkButton(
            self.sync_mode_frame,
            text=self.language_manager.get_text("sync_target_to_source", "目标→源"),
            height=35,
            font=get_font(size=13),
            command=lambda: self._set_sync_direction("target_to_source"),
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            border_color=("#3B8ED0", "#1F6AA5")
        )
        self.sync_target_btn.grid(row=1, column=2, padx=10, pady=10, sticky="ew")
        
        # ========== 运行模式区域 ==========
        self.run_mode_frame = ctk.CTkFrame(self.content_frame)
        self.run_mode_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=10, sticky="ew")
        self.run_mode_frame.grid_columnconfigure((0, 1), weight=1)
        
        # 运行模式标签
        self.run_mode_label = ctk.CTkLabel(
            self.run_mode_frame,
            text=self.language_manager.get_text("run_mode", "运行模式"),
            font=get_font(size=14, weight="bold")
        )
        self.run_mode_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w")
        
        # 运行模式切换按钮
        self.fast_mode_btn = ctk.CTkButton(
            self.run_mode_frame,
            text=self.language_manager.get_text("fast_mode", "快速模式"),
            height=35,
            font=get_font(size=13),
            command=lambda: self._set_run_mode("fast"),
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            border_color=("#3B8ED0", "#1F6AA5")
        )
        self.fast_mode_btn.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        self.safe_mode_btn = ctk.CTkButton(
            self.run_mode_frame,
            text=self.language_manager.get_text("safe_mode", "安全模式"),
            height=35,
            font=get_font(size=13),
            command=lambda: self._set_run_mode("safe"),
            fg_color=("#3B8ED0", "#1F6AA5"),
            hover_color=("#36719F", "#144870")
        )
        self.safe_mode_btn.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        
        # 运行模式提示信息
        self.run_mode_hint = ctk.CTkLabel(
            self.run_mode_frame,
            text=self.language_manager.get_text("run_mode_hint", "快速模式：速度快但风险较高；安全模式：建立快照更安全"),
            font=get_font(size=12),
            text_color="gray",
            wraplength=500
        )
        self.run_mode_hint.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="w")
        
        # ========== 多线程扫描区域 ==========
        self.scan_thread_frame = ctk.CTkFrame(self.content_frame)
        self.scan_thread_frame.grid(row=4, column=0, columnspan=2, padx=5, pady=10, sticky="ew")
        self.scan_thread_frame.grid_columnconfigure((0, 1), weight=1)
        
        # 多线程扫描标签
        self.scan_thread_label = ctk.CTkLabel(
            self.scan_thread_frame,
            text=self.language_manager.get_text("scan_thread_mode", "多线程扫描"),
            font=get_font(size=14, weight="bold")
        )
        self.scan_thread_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w")
        
        # 多线程扫描切换按钮
        self.scan_multi_thread_btn = ctk.CTkButton(
            self.scan_thread_frame,
            text=self.language_manager.get_text("multi_thread", "开启"),
            height=35,
            font=get_font(size=13),
            command=lambda: self._set_scan_thread_mode(True),
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            border_color=("#3B8ED0", "#1F6AA5")
        )
        self.scan_multi_thread_btn.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        self.scan_single_thread_btn = ctk.CTkButton(
            self.scan_thread_frame,
            text=self.language_manager.get_text("single_thread", "关闭"),
            height=35,
            font=get_font(size=13),
            command=lambda: self._set_scan_thread_mode(False),
            fg_color=("#3B8ED0", "#1F6AA5"),
            hover_color=("#36719F", "#144870")
        )
        self.scan_single_thread_btn.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        
        # ========== 多线程复制区域 ==========
        self.copy_thread_frame = ctk.CTkFrame(self.content_frame)
        self.copy_thread_frame.grid(row=5, column=0, columnspan=2, padx=5, pady=10, sticky="ew")
        self.copy_thread_frame.grid_columnconfigure((0, 1), weight=1)
        
        # 多线程复制标签
        self.copy_thread_label = ctk.CTkLabel(
            self.copy_thread_frame,
            text=self.language_manager.get_text("copy_thread_mode", "多线程同步"),
            font=get_font(size=14, weight="bold")
        )
        self.copy_thread_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w")
        
        # 多线程复制切换按钮
        self.copy_multi_thread_btn = ctk.CTkButton(
            self.copy_thread_frame,
            text=self.language_manager.get_text("multi_thread", "开启"),
            height=35,
            font=get_font(size=13),
            command=lambda: self._set_copy_thread_mode(True),
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            border_color=("#3B8ED0", "#1F6AA5")
        )
        self.copy_multi_thread_btn.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        self.copy_single_thread_btn = ctk.CTkButton(
            self.copy_thread_frame,
            text=self.language_manager.get_text("single_thread", "关闭"),
            height=35,
            font=get_font(size=14),
            command=lambda: self._set_copy_thread_mode(False),
            fg_color=("#3B8ED0", "#1F6AA5"),
            hover_color=("#36719F", "#144870")
        )
        self.copy_single_thread_btn.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        
        # ========== 全局策略区域 ==========
        self.strategy_frame = ctk.CTkFrame(self.content_frame)
        self.strategy_frame.grid(row=6, column=0, columnspan=2, padx=5, pady=10, sticky="ew")
        self.strategy_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # 全局策略标签
        self.strategy_label = ctk.CTkLabel(
            self.strategy_frame,
            text=self.language_manager.get_text("global_strategy", "全局策略"),
            font=get_font(size=14, weight="bold")
        )
        self.strategy_label.grid(row=0, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="w")
        
        # 四种策略切换按钮
        self.strategy_buttons = {}
        
        strategies = [
            ("conservative", "strategy_conservative", "保守模式"),
            ("newest_wins", "strategy_newest_wins", "时间优先"),
            ("source_wins", "strategy_source_wins", "源目录优先"),
            ("target_wins", "strategy_target_wins", "目标目录优先")
        ]
        
        for i, (strategy_key, text_key, default_text) in enumerate(strategies):
            btn = ctk.CTkButton(
                self.strategy_frame,
                text=self.language_manager.get_text(text_key, default_text),
                height=35,
                font=get_font(size=12),
                command=lambda s=strategy_key: self._set_strategy(s),
                fg_color=("#3B8ED0", "#1F6AA5") if strategy_key == "conservative" else "transparent",
                text_color="white" if strategy_key == "conservative" else ("black", "white"),
                hover_color=("#36719F", "#144870") if strategy_key == "conservative" else ("gray85", "gray25"),
                border_width=0 if strategy_key == "conservative" else 2,
                border_color=("#3B8ED0", "#1F6AA5")
            )
            btn.grid(row=1, column=i, padx=5, pady=10, sticky="ew")
            self.strategy_buttons[strategy_key] = btn
        
        # ========== 单独配置文件夹按钮 ==========
        self.folder_config_btn = ctk.CTkButton(
            self.content_frame,
            text=self.language_manager.get_text("folder_individual_config", "单独配置文件夹"),
            height=40,
            font=get_font(size=14),
            command=self._on_folder_config_click,
            fg_color="#2CC985",
            hover_color="#229E6A"
        )
        # v7.6: 修复与「全局策略」(row=6) 的行重叠，单独配置按钮移至 row=7
        self.folder_config_btn.grid(row=7, column=0, columnspan=2, padx=10, pady=15, sticky="ew")

        # ========== v7.6: 同步后执行命令（可选） ==========
        self._create_post_sync_command_section()

        # ========== 底部按钮区域 ==========
        self.bottom_frame = ctk.CTkFrame(self)
        self.bottom_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.bottom_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # 主操作按钮（根据模式显示不同文字）
        if self.edit_mode:
            self.main_btn = ctk.CTkButton(
                self.bottom_frame,
                text=self.language_manager.get_text("save_changes", "保存修改"),
                height=45,
                font=get_font(size=15, weight="bold"),
                command=self._on_save_click,
                fg_color="#2CC985",
                hover_color="#229E6A"
            )
        else:
            self.main_btn = ctk.CTkButton(
                self.bottom_frame,
                text=self.language_manager.get_text("next_step", "下一步"),
                height=45,
                font=get_font(size=15, weight="bold"),
                command=self._on_next_step_click,
                fg_color="#3B8ED0",
                hover_color="#36719F"
            )
        self.main_btn.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")
        
        # 跳过配置按钮（仅在非编辑模式下显示）
        if not self.edit_mode:
            self.skip_btn = ctk.CTkButton(
                self.bottom_frame,
                text=self.language_manager.get_text("skip_config", "跳过配置"),
                height=45,
                font=get_font(size=15, weight="bold"),
                command=self._on_skip_config_click,
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray85", "gray25"),
                border_width=2,
                border_color=("gray70", "gray30")
            )
            self.skip_btn.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        
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
        # 根据是否有跳过按钮，调整取消按钮的位置
        if self.edit_mode:
            self.cancel_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        else:
            self.cancel_btn.grid(row=0, column=2, padx=(5, 10), pady=10, sticky="ew")
    
    def _create_directory_section(self, row: int, label_key: str, default_text: str,
                                   entry_var_name: str, browse_command: Callable):
        """
        创建目录选择区域
        
        Args:
            row: 行号
            label_key: 翻译键
            default_text: 默认文本
            entry_var_name: 输入框变量名
            browse_command: 浏览按钮回调
        """
        # 标签
        label = ctk.CTkLabel(
            self.content_frame,
            text=self.language_manager.get_text(label_key, default_text),
            font=get_font(size=14, weight="bold")
        )
        label.grid(row=row, column=0, padx=(10, 5), pady=10, sticky="w")
        
        # 输入框
        entry = ctk.CTkEntry(
            self.content_frame,
            placeholder_text=self.language_manager.get_text("select_directory", "选择目录"),
            height=35
        )
        entry.grid(row=row, column=1, padx=5, pady=10, sticky="ew")
        
        # 浏览按钮
        browse_btn = ctk.CTkButton(
            self.content_frame,
            text=self.language_manager.get_text("browse", "浏览"),
            width=80,
            height=35,
            command=browse_command
        )
        browse_btn.grid(row=row, column=2, padx=(5, 10), pady=10)
        
        # 保存引用
        setattr(self, f"{entry_var_name}", entry)
        setattr(self, f"{entry_var_name}_label", label)
        setattr(self, f"{entry_var_name}_browse_btn", browse_btn)
    
    def _browse_source(self):
        """浏览源目录"""
        initial_dir = self.source_dir if self.source_dir else None
        path = filedialog.askdirectory(
            title=self.language_manager.get_text("source_directory", "选择源目录"),
            initialdir=initial_dir
        )
        if path:
            self.source_dir = path
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, path)
            # 添加到最近路径
            self.config_manager.add_recent_path(path)
    
    def _browse_target(self):
        """浏览目标目录"""
        initial_dir = self.target_dir if self.target_dir else None
        path = filedialog.askdirectory(
            title=self.language_manager.get_text("target_directory", "选择目标目录"),
            initialdir=initial_dir
        )
        if path:
            self.target_dir = path
            self.target_entry.delete(0, "end")
            self.target_entry.insert(0, path)
            # 添加到最近路径
            self.config_manager.add_recent_path(path)
    
    def _set_sync_direction(self, direction: str):
        """
        设置同步方向
        
        Args:
            direction: 同步方向 (both, source_to_target, target_to_source)
        """
        self.sync_direction = direction
        
        # 更新按钮样式
        buttons = {
            "both": self.sync_both_btn,
            "source_to_target": self.sync_source_btn,
            "target_to_source": self.sync_target_btn
        }
        
        for key, btn in buttons.items():
            if key == direction:
                btn.configure(
                    fg_color=("#3B8ED0", "#1F6AA5"),
                    text_color="white",
                    hover_color=("#36719F", "#144870"),
                    border_width=0
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=("black", "white"),
                    hover_color=("gray85", "gray25"),
                    border_width=2,
                    border_color=("#3B8ED0", "#1F6AA5")
                )
    
    def _set_scan_thread_mode(self, use_multithreading: bool):
        """
        设置扫描线程模式
        
        Args:
            use_multithreading: 是否使用多线程扫描
        """
        self.use_multithreading_scan = use_multithreading
        
        # 更新按钮样式
        if use_multithreading:
            self.scan_multi_thread_btn.configure(
                fg_color=("#3B8ED0", "#1F6AA5"),
                text_color="white",
                hover_color=("#36719F", "#144870"),
                border_width=0
            )
            self.scan_single_thread_btn.configure(
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray85", "gray25"),
                border_width=2,
                border_color=("#3B8ED0", "#1F6AA5")
            )
        else:
            self.scan_single_thread_btn.configure(
                fg_color=("#3B8ED0", "#1F6AA5"),
                text_color="white",
                hover_color=("#36719F", "#144870"),
                border_width=0
            )
            self.scan_multi_thread_btn.configure(
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray85", "gray25"),
                border_width=2,
                border_color=("#3B8ED0", "#1F6AA5")
            )
    
    def _set_copy_thread_mode(self, use_multithreading: bool):
        """
        设置复制线程模式
        
        Args:
            use_multithreading: 是否使用多线程复制
        """
        self.use_multithreading_copy = use_multithreading
        
        # 更新按钮样式
        if use_multithreading:
            self.copy_multi_thread_btn.configure(
                fg_color=("#3B8ED0", "#1F6AA5"),
                text_color="white",
                hover_color=("#36719F", "#144870"),
                border_width=0
            )
            self.copy_single_thread_btn.configure(
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray85", "gray25"),
                border_width=2,
                border_color=("#3B8ED0", "#1F6AA5")
            )
        else:
            self.copy_single_thread_btn.configure(
                fg_color=("#3B8ED0", "#1F6AA5"),
                text_color="white",
                hover_color=("#36719F", "#144870"),
                border_width=0
            )
            self.copy_multi_thread_btn.configure(
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray85", "gray25"),
                border_width=2,
                border_color=("#3B8ED0", "#1F6AA5")
            )
    
    def _set_run_mode(self, mode: str):
        """
        设置运行模式
        
        Args:
            mode: 运行模式 (fast, safe)
        """
        self.run_mode = mode
        
        # 更新按钮样式
        if mode == "fast":
            self.fast_mode_btn.configure(
                fg_color=("#3B8ED0", "#1F6AA5"),
                text_color="white",
                hover_color=("#36719F", "#144870"),
                border_width=0
            )
            self.safe_mode_btn.configure(
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray85", "gray25"),
                border_width=2,
                border_color=("#3B8ED0", "#1F6AA5")
            )
        else:
            self.safe_mode_btn.configure(
                fg_color=("#3B8ED0", "#1F6AA5"),
                text_color="white",
                hover_color=("#36719F", "#144870"),
                border_width=0
            )
            self.fast_mode_btn.configure(
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("gray85", "gray25"),
                border_width=2,
                border_color=("#3B8ED0", "#1F6AA5")
            )
    
    def _set_strategy(self, strategy: str):
        """
        设置全局策略
        
        Args:
            strategy: 策略类型 (conservative, newest_wins, source_wins, target_wins)
        """
        self.default_strategy = strategy
        
        # 更新按钮样式
        for key, btn in self.strategy_buttons.items():
            if key == strategy:
                btn.configure(
                    fg_color=("#3B8ED0", "#1F6AA5"),
                    text_color="white",
                    hover_color=("#36719F", "#144870"),
                    border_width=0
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=("black", "white"),
                    hover_color=("gray85", "gray25"),
                    border_width=2,
                    border_color=("#3B8ED0", "#1F6AA5")
                )
    
    def _create_post_sync_command_section(self):
        """v7.6：同步成功后执行命令区域（每任务一条，可选填，留空不执行）"""
        self.post_sync_frame = ctk.CTkFrame(self.content_frame)
        # v7.6: 单独配置按钮已占用 row=7，同步后命令区移至 row=8
        self.post_sync_frame.grid(row=8, column=0, columnspan=2, padx=5, pady=10, sticky="ew")
        self.post_sync_frame.grid_columnconfigure(0, weight=1)

        self.post_sync_label = ctk.CTkLabel(
            self.post_sync_frame,
            text=self.language_manager.get_text(
                "post_sync_command", "同步后执行命令（可选）"
            ),
            font=get_font(size=14, weight="bold")
        )
        self.post_sync_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.post_sync_entry = ctk.CTkEntry(
            self.post_sync_frame,
            font=get_font(size=13),
            height=35,
            placeholder_text=self.language_manager.get_text(
                "post_sync_command_placeholder",
                "同步成功后运行的脚本或命令，留空则不执行"
            )
        )
        self.post_sync_entry.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        if self.post_sync_command:
            self.post_sync_entry.insert(0, self.post_sync_command)

        self.post_sync_hint = ctk.CTkLabel(
            self.post_sync_frame,
            text=self.language_manager.get_text(
                "post_sync_command_security_hint",
                "⚠️ 请确认命令来源可信，不要运行来源不明的命令"
            ),
            font=get_font(size=12),
            text_color="#D97706",
            anchor="w"
        )
        self.post_sync_hint.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="w")

    def _read_post_sync_command(self) -> str:
        """从输入框读取同步后命令"""
        if hasattr(self, "post_sync_entry"):
            return self.post_sync_entry.get().strip()
        return self.post_sync_command

    def _on_folder_config_click(self):
        """单独配置文件夹按钮点击事件"""
        # 验证源目录和目标目录
        self.source_dir = self.source_entry.get().strip()
        self.target_dir = self.target_entry.get().strip()
        
        if not self.source_dir:
            self._show_error(
                self.language_manager.get_text("source_required", "请选择源目录")
            )
            return
        
        if not self.target_dir:
            self._show_error(
                self.language_manager.get_text("target_required", "请选择目标目录")
            )
            return
        
        if self.source_dir == self.target_dir:
            self._show_error(
                self.language_manager.get_text("same_directory_error", "源目录和目标目录不能相同")
            )
            return
        
        # 构建当前配置
        current_config = self.get_task_config()
        
        # 调用回调，跳转到文件夹配置页面
        if self.on_folder_config:
            self.on_folder_config(current_config)
    
    def _on_save_click(self):
        """保存修改按钮点击事件（编辑模式）"""
        # 验证输入
        self.source_dir = self.source_entry.get().strip()
        self.target_dir = self.target_entry.get().strip()
        
        if not self.source_dir:
            self._show_error(
                self.language_manager.get_text("source_dir_empty", "请选择源目录")
            )
            return
        
        if not self.target_dir:
            self._show_error(
                self.language_manager.get_text("target_dir_empty", "请选择目标目录")
            )
            return
        
        if self.source_dir == self.target_dir:
            self._show_error(
                self.language_manager.get_text("same_directory_error", "源目录和目标目录不能相同")
            )
            return
        
        # 构建更新后的配置
        task_config = self.get_task_config()
        
        # 更新任务
        if self.task_manager and self.task_id:
            self.task_manager.update_task(self.task_id, task_config)
        
        # 返回任务管理页面
        if self.on_save:
            self.on_save()
        elif self.on_cancel:
            self.on_cancel()
    
    def _on_next_step_click(self):
        """下一步按钮点击事件"""
        # 验证输入
        self.source_dir = self.source_entry.get().strip()
        self.target_dir = self.target_entry.get().strip()
        
        if not self.source_dir:
            self._show_error(
                self.language_manager.get_text("source_required", "请选择源目录")
            )
            return
        
        if not self.target_dir:
            self._show_error(
                self.language_manager.get_text("target_required", "请选择目标目录")
            )
            return
        
        if self.source_dir == self.target_dir:
            self._show_error(
                self.language_manager.get_text("same_directory_error", "源目录和目标目录不能相同")
            )
            return
        
        # 构建任务配置
        task_config = {
            "source": self.source_dir,
            "target": self.target_dir,
            "sync_direction": self.sync_direction,
            "use_multithreading_scan": self.use_multithreading_scan,
            "use_multithreading_copy": self.use_multithreading_copy,
            "mode": self.run_mode,
            "default_strategy": self.default_strategy,
            "folders": [],
            "folder_strategies": {},
            "root_included": False,
            "root_strategy": self.default_strategy,
            "post_sync_command": self._read_post_sync_command()
        }

        if self.on_next_step:
            self.on_next_step(task_config)
    
    def _on_skip_config_click(self):
        """跳过配置按钮点击事件，直接进入同步确认页面"""
        # 验证输入
        self.source_dir = self.source_entry.get().strip()
        self.target_dir = self.target_entry.get().strip()
        
        if not self.source_dir:
            self._show_error(
                self.language_manager.get_text("source_required", "请选择源目录")
            )
            return
        
        if not self.target_dir:
            self._show_error(
                self.language_manager.get_text("target_required", "请选择目标目录")
            )
            return
        
        if self.source_dir == self.target_dir:
            self._show_error(
                self.language_manager.get_text("same_directory_error", "源目录和目标目录不能相同")
            )
            return
        
        # 构建任务配置（使用默认策略，跳过文件夹配置）
        task_config = {
            "source": self.source_dir,
            "target": self.target_dir,
            "sync_direction": self.sync_direction,
            "use_multithreading_scan": self.use_multithreading_scan,
            "use_multithreading_copy": self.use_multithreading_copy,
            "mode": self.run_mode,
            "default_strategy": self.default_strategy,
            "folders": [],
            "folder_strategies": {},  # 空字典，使用全局默认策略
            "root_included": True,
            "root_strategy": self.default_strategy,
            "post_sync_command": self._read_post_sync_command()
        }
        
        # 直接跳转到同步确认页面
        if self.app:
            self.app.show_page("sync_confirm", task_config=task_config)
    
    def _on_cancel_click(self):
        """取消按钮点击事件"""
        if self.on_cancel:
            self.on_cancel()
    
    def _show_error(self, message: str):
        """
        显示错误提示
        
        Args:
            message: 错误消息
        """
        # 使用临时提示框显示错误
        error_dialog = ctk.CTkInputDialog(
            text=message,
            title=self.language_manager.get_text("error", "错误")
        )
    
    def get_task_config(self) -> Dict:
        """
        获取当前任务配置
        
        Returns:
            任务配置字典
        """
        return {
            "source": self.source_dir,
            "target": self.target_dir,
            "sync_direction": self.sync_direction,
            "use_multithreading_scan": self.use_multithreading_scan,
            "use_multithreading_copy": self.use_multithreading_copy,
            "mode": self.run_mode,
            "default_strategy": self.default_strategy,
            "post_sync_command": self._read_post_sync_command()
        }
    
    def _load_task_data(self):
        """加载任务数据到表单（兼容旧任务格式）"""
        task = self.task_manager.get_task_by_id(self.task_id)
        if not task:
            return
        
        # 加载基本配置
        self.source_dir = task.get("source", "")
        self.target_dir = task.get("target", "")
        self.sync_direction = task.get("sync_direction", "both")
        
        # 兼容旧任务格式
        use_multithreading = task.get("use_multithreading", False)
        self.use_multithreading_scan = task.get("use_multithreading_scan", use_multithreading)
        self.use_multithreading_copy = task.get("use_multithreading_copy", False)
        
        self.run_mode = task.get("mode", task.get("run_mode", "safe"))
        self.default_strategy = task.get("default_strategy", "conservative")
        self.post_sync_command = task.get("post_sync_command", "") or ""
        
        # 更新UI显示
        if hasattr(self, 'source_entry'):
            self.source_entry.delete(0, 'end')
            self.source_entry.insert(0, self.source_dir)
        
        if hasattr(self, 'target_entry'):
            self.target_entry.delete(0, 'end')
            self.target_entry.insert(0, self.target_dir)

        # v7.6: 同步后命令
        if hasattr(self, 'post_sync_entry'):
            self.post_sync_entry.delete(0, 'end')
            self.post_sync_entry.insert(0, self.post_sync_command)
        
        # 更新按钮状态
        if hasattr(self, '_set_sync_direction'):
            self._set_sync_direction(self.sync_direction)
        
        if hasattr(self, '_set_scan_thread_mode'):
            self._set_scan_thread_mode(self.use_multithreading_scan)
        
        if hasattr(self, '_set_copy_thread_mode'):
            self._set_copy_thread_mode(self.use_multithreading_copy)
        
        if hasattr(self, '_set_run_mode'):
            self._set_run_mode(self.run_mode)
        
        if hasattr(self, '_set_strategy'):
            self._set_strategy(self.default_strategy)
    
    def reset(self):
        """重置页面状态"""
        self.source_dir = ""
        self.target_dir = ""
        self.sync_direction = "both"
        self.use_multithreading = False
        self.run_mode = "safe"
        self.default_strategy = "conservative"
        self.post_sync_command = ""

        # 清空输入框
        self.source_entry.delete(0, "end")
        self.target_entry.delete(0, "end")
        if hasattr(self, 'post_sync_entry'):
            self.post_sync_entry.delete(0, "end")
        
        # 重置按钮样式
        self._set_sync_direction("both")
        self._set_thread_mode(False)
        self._set_run_mode("safe")
        self._set_strategy("conservative")
    
    def update_language(self):
        """更新界面语言"""
        # 更新目录区域
        self.source_entry_label.configure(
            text=self.language_manager.get_text("source_directory", "源目录")
        )
        self.source_entry.configure(
            placeholder_text=self.language_manager.get_text("select_directory", "选择目录")
        )
        self.source_entry_browse_btn.configure(
            text=self.language_manager.get_text("browse", "浏览")
        )
        
        self.target_entry_label.configure(
            text=self.language_manager.get_text("target_directory", "目标目录")
        )
        self.target_entry.configure(
            placeholder_text=self.language_manager.get_text("select_directory", "选择目录")
        )
        self.target_entry_browse_btn.configure(
            text=self.language_manager.get_text("browse", "浏览")
        )
        
        # 更新同步模式
        self.sync_mode_label.configure(
            text=self.language_manager.get_text("sync_mode", "同步模式")
        )
        self.sync_both_btn.configure(
            text=self.language_manager.get_text("sync_both", "双向同步")
        )
        self.sync_source_btn.configure(
            text=self.language_manager.get_text("sync_source_to_target", "源→目标")
        )
        self.sync_target_btn.configure(
            text=self.language_manager.get_text("sync_target_to_source", "目标→源")
        )
        
        # 更新线程模式
        self.scan_thread_label.configure(
            text=self.language_manager.get_text("scan_thread_mode", "多线程扫描")
        )
        self.scan_multi_thread_btn.configure(
            text=self.language_manager.get_text("multi_thread", "开启")
        )
        self.scan_single_thread_btn.configure(
            text=self.language_manager.get_text("single_thread", "关闭")
        )
        self.copy_thread_label.configure(
            text=self.language_manager.get_text("copy_thread_mode", "多线程同步")
        )
        self.copy_multi_thread_btn.configure(
            text=self.language_manager.get_text("multi_thread", "开启")
        )
        self.copy_single_thread_btn.configure(
            text=self.language_manager.get_text("single_thread", "关闭")
        )
        
        # 更新运行模式
        self.run_mode_label.configure(
            text=self.language_manager.get_text("run_mode", "运行模式")
        )
        self.fast_mode_btn.configure(
            text=self.language_manager.get_text("fast_mode", "快速模式")
        )
        self.safe_mode_btn.configure(
            text=self.language_manager.get_text("safe_mode", "安全模式")
        )
        self.run_mode_hint.configure(
            text=self.language_manager.get_text("run_mode_hint", "快速模式：速度快但风险较高；安全模式：建立快照更安全")
        )

        # v7.6: 同步后执行命令
        if hasattr(self, 'post_sync_label'):
            self.post_sync_label.configure(
                text=self.language_manager.get_text(
                    "post_sync_command", "同步后执行命令（可选）"
                )
            )
            self.post_sync_entry.configure(
                placeholder_text=self.language_manager.get_text(
                    "post_sync_command_placeholder",
                    "同步成功后运行的脚本或命令，留空则不执行"
                )
            )
            self.post_sync_hint.configure(
                text=self.language_manager.get_text(
                    "post_sync_command_security_hint",
                    "⚠️ 请确认命令来源可信，不要运行来源不明的命令"
                )
            )
        
        # 更新全局策略
        self.strategy_label.configure(
            text=self.language_manager.get_text("global_strategy", "全局策略")
        )
        
        strategies = [
            ("conservative", "strategy_conservative", "保守模式"),
            ("newest_wins", "strategy_newest_wins", "时间优先"),
            ("source_wins", "strategy_source_wins", "源目录优先"),
            ("target_wins", "strategy_target_wins", "目标目录优先")
        ]
        
        for strategy_key, text_key, default_text in strategies:
            self.strategy_buttons[strategy_key].configure(
                text=self.language_manager.get_text(text_key, default_text)
            )
        
        # 更新文件夹配置按钮
        self.folder_config_btn.configure(
            text=self.language_manager.get_text("folder_individual_config", "单独配置文件夹")
        )
        
        # 更新底部按钮
        self.next_step_btn.configure(
            text=self.language_manager.get_text("next_step", "下一步")
        )
        self.cancel_btn.configure(
            text=self.language_manager.get_text("cancel", "取消")
        )
    
    def set_on_folder_config(self, callback: Callable):
        """
        设置单独配置文件夹的回调
        
        Args:
            callback: 回调函数
        """
        self.folder_config_btn.configure(command=callback)