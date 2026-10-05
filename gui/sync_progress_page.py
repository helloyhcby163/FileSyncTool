"""
文件同步工具 v7.3 - 同步进度页面
显示同步进度、速度、剩余时间等信息，支持寿命保护暂停状态显示
"""

import customtkinter as ctk
from backend.language_manager import get_font
import time
from typing import Optional, Callable, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .app import FileSyncApp


class SyncProgressPage(ctk.CTkFrame):
    """同步进度页面：显示同步进度和统计信息"""
    
    def __init__(self, master, app: "FileSyncApp", task_info: Dict[str, Any] = None,
                 on_complete: Optional[Callable] = None,
                 on_cancel: Optional[Callable] = None,
                 on_save_interrupted: Optional[Callable] = None):
        """
        初始化同步进度页面
        
        Args:
            master: 父容器
            app: 主窗口实例
            task_info: 任务信息
            on_complete: 同步完成回调
            on_cancel: 取消任务回调
            on_save_interrupted: 保存为打断任务回调
        """
        super().__init__(master)
        
        self.app = app
        self.task_info = task_info or {}
        self.on_complete = on_complete
        self.on_cancel = on_cancel
        self.on_save_interrupted = on_save_interrupted
        
        # 进度数据（从 task_info 初始化）
        self.current_file = 0
        self.total_files = task_info.get("total_files", 0)
        self.elapsed_time = 0.0
        self.remaining_time = task_info.get("estimated_time", 0.0)
        self.read_speed = 0.0
        self.write_speed = 0.0
        self.percentage = 0.0
        
        # 同步引擎引用
        self.sync_engine = None

        # 启动前/同步中的错误明细（如源/目标目录不存在），None 表示无错误
        self._error_message = None

        # 进度刷新定时器
        self.refresh_timer = None
        
        # 设置布局
        self._setup_layout()
    
    def _setup_layout(self):
        """设置布局"""
        # 配置网格权重
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # ========== 顶部：任务名称 ==========
        self._create_header()
        
        # ========== 中间：进度信息 ==========
        self._create_progress_panel()
        
        # ========== 底部：按钮区域 ==========
        self._create_button_panel()
    
    def _create_header(self):
        """创建顶部标题区域"""
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)
        
        # 任务名称
        task_name = self.task_info.get("name", self.app.get_text("sync_progress"))
        self.task_name_label = ctk.CTkLabel(
            self.header_frame,
            text=f"{self.app.get_text('task_name')}: {task_name}",
            font=get_font(size=18, weight="bold")
        )
        self.task_name_label.grid(row=0, column=0, padx=20, pady=15, sticky="w")
        
        # 同步状态
        self.status_label = ctk.CTkLabel(
            self.header_frame,
            text=self.app.get_text("syncing"),
            font=get_font(size=14),
            text_color=("green", "#2CC985")
        )
        self.status_label.grid(row=0, column=1, padx=20, pady=15, sticky="e")

        # 错误明细（如未插 U 盘导致源/目标目录不存在），默认隐藏
        self.error_detail_label = ctk.CTkLabel(
            self.header_frame,
            text="",
            font=get_font(size=14),
            text_color="red",
            justify="left",
            anchor="w",
            wraplength=900,
        )
        # row=1, columnspan=2；无错误时不占位

    def show_error(self, message: str):
        """在进度页顶部以红色多行文本显示错误明细（含具体路径）"""
        self._error_message = message
        self.error_detail_label.configure(text=message)
        if self.error_detail_label.winfo_manager() == "":
            self.error_detail_label.grid(
                row=1, column=0, columnspan=2, padx=20, pady=(0, 12), sticky="w"
            )

    def clear_error(self):
        """清除错误明细"""
        self._error_message = None
        self.error_detail_label.configure(text="")
        self.error_detail_label.grid_forget()
    
    def _create_progress_panel(self):
        """创建进度信息面板"""
        self.progress_panel = ctk.CTkFrame(self)
        self.progress_panel.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.progress_panel.grid_columnconfigure(0, weight=1)
        self.progress_panel.grid_rowconfigure(0, weight=1)
        
        # 进度信息容器
        self.info_container = ctk.CTkFrame(self.progress_panel, fg_color="transparent")
        self.info_container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.info_container.grid_columnconfigure((0, 1), weight=1)
        
        # ========== 文件进度 ==========
        self.file_progress_frame = ctk.CTkFrame(self.info_container)
        self.file_progress_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        self.file_progress_frame.grid_columnconfigure(0, weight=1)
        
        # 文件进度标签
        self.file_progress_label = ctk.CTkLabel(
            self.file_progress_frame,
            text=self.app.get_text("syncing_file", current=0, total=0),
            font=get_font(size=16)
        )
        self.file_progress_label.grid(row=0, column=0, padx=20, pady=15, sticky="w")
        
        # ========== 预估剩余时间 ==========
        self.time_frame = ctk.CTkFrame(self.info_container)
        self.time_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.time_frame.grid_columnconfigure(1, weight=1)
        
        self.time_title_label = ctk.CTkLabel(
            self.time_frame,
            text=self.app.get_text("remaining_time"),
            font=get_font(size=14)
        )
        self.time_title_label.grid(row=0, column=0, padx=20, pady=15, sticky="w")
        
        self.time_value_label = ctk.CTkLabel(
            self.time_frame,
            text="--:--:--",
            font=get_font(size=14, weight="bold")
        )
        self.time_value_label.grid(row=0, column=1, padx=20, pady=15, sticky="e")
        
        # ========== 读取速度 ==========
        self.read_speed_frame = ctk.CTkFrame(self.info_container)
        self.read_speed_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        self.read_speed_frame.grid_columnconfigure(1, weight=1)
        
        self.read_speed_title_label = ctk.CTkLabel(
            self.read_speed_frame,
            text=self.app.get_text("read_speed"),
            font=get_font(size=14)
        )
        self.read_speed_title_label.grid(row=0, column=0, padx=20, pady=15, sticky="w")
        
        self.read_speed_value_label = ctk.CTkLabel(
            self.read_speed_frame,
            text="0.00 MB/s",
            font=get_font(size=14, weight="bold")
        )
        self.read_speed_value_label.grid(row=0, column=1, padx=20, pady=15, sticky="e")
        
        # ========== 写入速度 ==========
        self.write_speed_frame = ctk.CTkFrame(self.info_container)
        self.write_speed_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        self.write_speed_frame.grid_columnconfigure(1, weight=1)
        
        self.write_speed_title_label = ctk.CTkLabel(
            self.write_speed_frame,
            text=self.app.get_text("write_speed"),
            font=get_font(size=14)
        )
        self.write_speed_title_label.grid(row=0, column=0, padx=20, pady=15, sticky="w")
        
        self.write_speed_value_label = ctk.CTkLabel(
            self.write_speed_frame,
            text="0.00 MB/s",
            font=get_font(size=14, weight="bold")
        )
        self.write_speed_value_label.grid(row=0, column=1, padx=20, pady=15, sticky="e")
        
        # ========== 进度条 ==========
        self.progressbar_frame = ctk.CTkFrame(self.info_container)
        self.progressbar_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=20, sticky="ew")
        self.progressbar_frame.grid_columnconfigure(0, weight=1)
        
        # 进度百分比标签
        self.percentage_label = ctk.CTkLabel(
            self.progressbar_frame,
            text="0%",
            font=get_font(size=14)
        )
        self.percentage_label.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")
        
        # 进度条
        self.progress_bar = ctk.CTkProgressBar(
            self.progressbar_frame,
            height=20
        )
        self.progress_bar.grid(row=1, column=0, padx=20, pady=(5, 15), sticky="ew")
        self.progress_bar.set(0)
        
        # ========== 当前文件信息 ==========
        self.current_file_frame = ctk.CTkFrame(self.info_container)
        self.current_file_frame.grid(row=5, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        self.current_file_frame.grid_columnconfigure(0, weight=1)
        
        self.current_file_label = ctk.CTkLabel(
            self.current_file_frame,
            text="",
            font=get_font(size=12),
            text_color="gray",
            wraplength=600
        )
        self.current_file_label.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        
        # ========== 寿命保护状态 ==========
        self.life_protection_frame = ctk.CTkFrame(self.info_container)
        self.life_protection_frame.grid(row=6, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        self.life_protection_frame.grid_columnconfigure(0, weight=1)
        
        self.life_protection_label = ctk.CTkLabel(
            self.life_protection_frame,
            text="",
            font=get_font(size=12),
            text_color="orange",
            wraplength=600
        )
        self.life_protection_label.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        
        # ========== 筛选策略 ==========
        self._create_filter_section()
    
    def _start_life_protection_monitor(self):
        """启动寿命保护状态监控"""
        def check_status():
            if self.sync_engine and hasattr(self.sync_engine, 'get_life_protection_status'):
                status = self.sync_engine.get_life_protection_status()
                
                if status.get("active", False):
                    remaining = int(status.get("remaining_time", 0))
                    usb_level = status.get("usb_level", "")
                    pause_count = status.get("pause_count", 0)
                    
                    self.life_protection_label.configure(
                        text=self.app.get_text(
                            "life_protection_pausing_detail",
                            minutes=status.get('continuous_write_time', 0) // 60,
                            seconds=remaining
                        )
                    )
                    self.status_label.configure(
                        text=self.app.get_text("life_protection_paused", "寿命保护暂停"),
                        text_color="orange"
                    )
                else:
                    self.life_protection_label.configure(text="")
                    if self.current_file < self.total_files:
                        self.status_label.configure(
                            text=self.app.get_text("syncing"),
                            text_color=("green", "#2CC985")
                        )
            
            if self.sync_engine and not self.sync_engine.is_interrupted():
                self.life_protection_monitor = self.after(500, check_status)
        
        if hasattr(self, 'life_protection_monitor'):
            self.after_cancel(self.life_protection_monitor)
        
        check_status()
    
    def _create_filter_section(self):
        """创建筛选策略展示区域"""
        self.filter_frame = ctk.CTkFrame(self.info_container)
        self.filter_frame.grid(row=7, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        self.filter_frame.grid_columnconfigure(0, weight=1)
        
        # 区域标题
        self.filter_title_label = ctk.CTkLabel(
            self.filter_frame,
            text=self.app.get_text("filter_strategy", "筛选策略"),
            font=get_font(size=14, weight="bold")
        )
        self.filter_title_label.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")
        
        # 从任务配置中获取筛选策略
        task_config = self.task_info.get("config", {}) or {}
        folder_filters = task_config.get("folder_filters", {}) or {}
        
        # 过滤掉空配置
        active_filters = {}
        for folder_name, cfg in folder_filters.items():
            if isinstance(cfg, dict) and (cfg.get("date_filter_enabled") or cfg.get("extension_filter_enabled")):
                active_filters[folder_name] = cfg
        
        if not active_filters:
            self.filter_content_label = ctk.CTkLabel(
                self.filter_frame,
                text=self.app.get_text("filter_not_enabled", "未启用筛选"),
                font=get_font(size=12),
                text_color=("gray50", "gray70")
            )
            self.filter_content_label.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        else:
            lines = []
            for folder_name, cfg in active_filters.items():
                parts = [f"  {folder_name}:"]
                # 日期过滤
                if cfg.get("date_filter_enabled"):
                    date_start = cfg.get("date_filter_start", "")
                    date_end = cfg.get("date_filter_end", "")
                    date_text = self.app.get_text("filter_summary_date", "日期")
                    if date_start and date_end:
                        date_text += f" {date_start}~{date_end}"
                    elif date_start:
                        date_text += f" >={date_start}"
                    elif date_end:
                        date_text += f" <={date_end}"
                    parts.append(date_text)
                # 扩展名过滤
                if cfg.get("extension_filter_enabled"):
                    ext_mode = cfg.get("extension_filter_mode", "include")
                    ext_list = cfg.get("extension_filter_list", [])
                    mode_text = self.app.get_text("include_mode" if ext_mode == "include" else "exclude_mode",
                                                  "仅包含" if ext_mode == "include" else "排除")
                    ext_str = ", ".join(ext_list) if isinstance(ext_list, list) else str(ext_list)
                    parts.append(f"{mode_text} {ext_str}")
                lines.append("  ".join(parts))
            
            self.filter_content_label = ctk.CTkLabel(
                self.filter_frame,
                text="\n".join(lines),
                font=get_font(size=12),
                text_color=("gray50", "gray70"),
                justify="left",
                wraplength=600
            )
            self.filter_content_label.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
    
    def _create_button_panel(self):
        """创建底部按钮区域"""
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=2, column=0, padx=20, pady=20, sticky="ew")
        self.button_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # 返回首页按钮
        self.btn_return_home = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("return_home"),
            height=45,
            font=get_font(size=14),
            command=self._on_return_home_click
        )
        self.btn_return_home.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # 取消任务按钮
        self.btn_cancel = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("cancel_task"),
            height=45,
            font=get_font(size=14),
            fg_color="#D32F2F",
            hover_color="#B71C1C",
            command=self._on_cancel_click
        )
        self.btn_cancel.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        # 保存为打断任务并退出按钮
        self.btn_save_interrupted = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("save_interrupted"),
            height=45,
            font=get_font(size=14),
            fg_color="#FF9800",
            hover_color="#F57C00",
            command=self._on_save_interrupted_click
        )
        self.btn_save_interrupted.grid(row=0, column=2, padx=10, pady=10, sticky="ew")
    
    def set_sync_engine(self, sync_engine):
        """
        设置同步引擎引用
        
        Args:
            sync_engine: 同步引擎实例
        """
        self.sync_engine = sync_engine
        if self.sync_engine:
            self.sync_engine.set_progress_callback(self._on_progress_update)
            # v7.5: 若引擎已在运行（如从首页返回进度页），立即恢复状态
            if hasattr(self.sync_engine, '_current_progress') and self.sync_engine._current_progress:
                try:
                    self._on_progress_update(self.sync_engine._current_progress)
                except Exception:
                    pass
            self._start_life_protection_monitor()
    
    def on_page_destroy(self):
        """页面销毁前调用：取消定时器，避免访问已销毁的 Canvas 导致 TclError"""
        # 取消寿命保护监控定时器
        monitor = getattr(self, 'life_protection_monitor', None)
        if monitor is not None:
            try:
                self.after_cancel(monitor)
            except Exception:
                pass
            self.life_protection_monitor = None
        # 取消进度刷新定时器
        if getattr(self, 'refresh_timer', None) is not None:
            try:
                self.after_cancel(self.refresh_timer)
            except Exception:
                pass
            self.refresh_timer = None
    
    def _on_progress_update(self, progress):
        """
        进度更新回调
        
        Args:
            progress: SyncProgress 对象
        """
        # 更新数据
        self.current_file = progress.completed_files
        self.total_files = progress.total_files
        self.elapsed_time = progress.elapsed_time
        self.remaining_time = progress.estimated_remaining
        self.percentage = progress.percentage
        
        # 读取速度和写入速度使用相同的速度值
        self.read_speed = progress.speed
        self.write_speed = progress.speed
        
        # 更新 task_manager 中的任务进度
        task_id = self.task_info.get("id", "sync_task")
        try:
            self.app.task_manager.update_task_progress(
                task_id=task_id,
                progress=progress.percentage,
                current_file=progress.current_file,
                completed_files=progress.completed_files,
                total_files=progress.total_files
            )
        except Exception:
            pass
        
        # 更新界面（捕获 TclError：页面可能已销毁）
        try:
            self._update_display(progress)
        except Exception:
            pass
    
    def _update_display(self, progress):
        """
        更新界面显示
        
        Args:
            progress: SyncProgress 对象
        """
        # 处理错误状态
        if progress.current_phase == "error":
            # 更新文件进度显示错误信息
            self.file_progress_label.configure(
                text=self.app.get_text("sync_interrupted_error", "❌ 同步中断")
            )
            
            # 进度条变红
            self.progress_bar.configure(fg_color="red")
            self.progress_bar.set(0)
            self.percentage_label.configure(text="0%", text_color="red")
            
            # 更新当前文件显示错误信息
            if progress.current_file:
                self.current_file_label.configure(text=progress.current_file)
            
            # 更新速度显示为0
            self.read_speed_value_label.configure(text="0.00 MB/s")
            self.write_speed_value_label.configure(text="0.00 MB/s")
            
            # 按钮变为"返回首页"
            if hasattr(self, 'cancel_btn'):
                self.cancel_btn.configure(
                    text=self.app.get_text("return_home", "返回首页"),
                    command=self._on_return_home
                )
            
            # 发送系统通知
            try:
                from plyer import notification
                notification.notify(
                    title=self.app.get_text("app_title", "文件同步工具"),
                    message=progress.current_file if progress.current_file else self.app.get_text("sync_interrupted_short", "同步中断"),
                    app_name=self.app.get_text("app_title", "文件同步工具"),
                    timeout=10
                )
            except Exception:
                pass
            
            return
        
        # 处理寿命保护停歇状态
        if progress.current_phase == "paused":
            self.file_progress_label.configure(
                text=self.app.get_text(
                    "life_protection_pausing", "⏸️ 寿命保护：暂停写入中..."
                )
            )
            
            self.read_speed_value_label.configure(text="0.00 MB/s")
            self.write_speed_value_label.configure(text="0.00 MB/s")
            
            if progress.current_file:
                self.current_file_label.configure(text=progress.current_file)
            
            return
        
        # 更新文件进度
        file_text = self.app.get_text("syncing_file", 
                                       current=progress.completed_files,
                                       total=progress.total_files)
        self.file_progress_label.configure(text=file_text)
        
        # 更新剩余时间
        time_text = self._format_time(progress.estimated_remaining)
        self.time_value_label.configure(text=time_text)
        
        # 更新读取速度
        read_speed_text = self._format_speed(progress.speed)
        self.read_speed_value_label.configure(text=read_speed_text)
        
        # 更新写入速度
        write_speed_text = self._format_speed(progress.speed)
        self.write_speed_value_label.configure(text=write_speed_text)
        
        # 更新进度条
        self.progress_bar.set(progress.percentage / 100)
        self.percentage_label.configure(text=f"{progress.percentage:.1f}%")
        
        # 更新当前文件
        if progress.current_file:
            self.current_file_label.configure(text=progress.current_file)
    
    def _on_return_home(self):
        """返回首页按钮点击事件"""
        self.app.show_page("home")
    
    def _format_time(self, seconds: float) -> str:
        """
        格式化时间显示
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化的时间字符串
        """
        if seconds <= 0:
            return "--:--:--"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _format_speed(self, bytes_per_second: float) -> str:
        """
        格式化速度显示
        
        Args:
            bytes_per_second: 每秒字节数
            
        Returns:
            格式化的速度字符串
        """
        if bytes_per_second <= 0:
            return "0.00 MB/s"
        
        mb_per_second = bytes_per_second / (1024 * 1024)
        
        if mb_per_second >= 1024:
            gb_per_second = mb_per_second / 1024
            return f"{gb_per_second:.2f} GB/s"
        else:
            return f"{mb_per_second:.2f} MB/s"
    
    def _on_return_home_click(self):
        """返回首页按钮点击事件"""
        self.app.show_page("home")
    
    def _on_cancel_click(self):
        """取消任务按钮点击事件"""
        interrupted = False
        if self.sync_engine:
            try:
                self.sync_engine.interrupt()
                interrupted = True
            except Exception as e:
                print(f"中断同步失败: {e}")
                interrupted = False
        
        # v7.5: 中断反馈
        if interrupted:
            self.status_label.configure(
                text=self.app.get_text("sync_stopping", "正在停止同步..."),
                text_color="orange"
            )
        else:
            self.status_label.configure(
                text=self.app.get_text("sync_stop_failed", "停止同步失败，请稍后重试"),
                text_color="red"
            )
        
        if self.on_cancel:
            self.on_cancel()
        
        # 禁用取消按钮
        self.btn_cancel.configure(state="disabled")
    
    def _on_save_interrupted_click(self):
        """保存为打断任务并退出按钮点击事件"""
        if self.sync_engine:
            self.sync_engine.interrupt()
        
        # 收集当前进度信息
        progress_info = {
            "completed_files": self.current_file,
            "total_files": self.total_files,
            "percentage": self.percentage,
            "elapsed_time": self.elapsed_time,
            "remaining_time": self.remaining_time
        }
        
        # 调用回调，传递任务信息和进度
        if self.on_save_interrupted:
            self.on_save_interrupted(self.task_info, progress_info)
        
        # 禁用按钮防止重复点击
        self.btn_save_interrupted.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        
        # 返回首页
        self.app.show_page("home")
    
    def set_complete(self, success: bool = True):
        """
        设置同步完成状态
        
        Args:
            success: 是否成功完成
        """
        if success:
            self.status_label.configure(
                text=self.app.get_text("sync_completed"),
                text_color=("green", "#2CC985")
            )
            self.progress_bar.set(1.0)
            self.percentage_label.configure(text="100%")
        else:
            self.status_label.configure(
                text=self.app.get_text("sync_failed"),
                text_color="red"
            )
        
        # 禁用取消和保存按钮
        self.btn_cancel.configure(state="disabled")
        self.btn_save_interrupted.configure(state="disabled")
    
    def refresh(self):
        """刷新页面，从同步引擎恢复当前状态"""
        # 如果同步引擎正在运行，恢复进度状态
        if self.sync_engine and hasattr(self.sync_engine, '_current_progress') and self.sync_engine._current_progress:
            progress = self.sync_engine._current_progress
            
            # 更新进度数据
            self.current_file = progress.completed_files
            self.total_files = progress.total_files
            self.percentage = progress.percentage
            self.elapsed_time = progress.elapsed_time
            self.remaining_time = progress.estimated_remaining
            self.read_speed = progress.speed
            self.write_speed = progress.speed
            
            # 重新绑定进度回调
            if hasattr(self.sync_engine, 'set_progress_callback'):
                self.sync_engine.set_progress_callback(self._on_progress_update)
            
            # 更新显示
            try:
                self._update_display(progress)
            except Exception:
                pass
        
        # 重启寿命保护监控（页面重建后需要重新启动）
        if self.sync_engine and not self.sync_engine.is_interrupted():
            self._start_life_protection_monitor()
        
        # 更新所有文本
        self._update_texts()
    
    def _update_texts(self):
        """更新所有文本"""
        task_name = self.task_info.get("name", self.app.get_text("sync_progress"))
        self.task_name_label.configure(
            text=f"{self.app.get_text('task_name')}: {task_name}"
        )
        
        self.status_label.configure(text=self.app.get_text("syncing"))
        
        self.file_progress_label.configure(
            text=self.app.get_text("syncing_file", 
                                   current=self.current_file,
                                   total=self.total_files)
        )
        
        self.time_title_label.configure(text=self.app.get_text("remaining_time"))
        self.read_speed_title_label.configure(text=self.app.get_text("read_speed"))
        self.write_speed_title_label.configure(text=self.app.get_text("write_speed"))
        
        # 更新筛选策略区域标题
        if hasattr(self, 'filter_title_label'):
            self.filter_title_label.configure(
                text=self.app.get_text("filter_strategy", "筛选策略")
            )
        
        self.btn_return_home.configure(text=self.app.get_text("return_home"))
        self.btn_cancel.configure(text=self.app.get_text("cancel_task"))
        self.btn_save_interrupted.configure(text=self.app.get_text("save_interrupted"))