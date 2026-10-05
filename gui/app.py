"""
文件同步工具 v7.3 - 主窗口
基于 CustomTkinter 的主应用程序窗口
"""

import os
import threading
import customtkinter as ctk
from typing import Optional, Dict, Any

from backend.config_manager import ConfigManager
from backend.language_manager import (
    LanguageManager,
    get_font,
    ensure_user_translations_dir,
)
from backend.task_manager import TaskManager
from backend.recycle_manager import RecycleManager
from backend.sync_engine import FileSyncEngine as SyncEngine
from backend.notification_manager import NotificationManager
from backend.theme_manager import ThemeManager
from backend.platform_utils import get_default_config_dir


class FileSyncApp(ctk.CTk):
    """主窗口类：管理整个应用程序的主窗口"""
    
    # 窗口默认尺寸
    DEFAULT_WIDTH = 1200
    DEFAULT_HEIGHT = 800
    # v7.6: 增大最小尺寸，避免首页/创建任务页按钮被遮挡或截断
    MIN_WIDTH = 1000
    MIN_HEIGHT = 720
    
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        # 初始化状态栏引用（在加载语言前使用）
        self.status_bar = None
        
        # 1. 创建基础窗口（临时标题，语言加载后更新）
        self._setup_window()
        
        # 2. 创建状态栏（优先显示，给用户视觉反馈）
        self._create_status_bar()
        self.update_idletasks()
        
        # 3. 分阶段加载后端模块，每阶段更新状态栏
        self._init_backend_modules()
        
        # 4. 更新窗口标题为正确语言
        self.title(self.language_manager.get_text("app_title"))
        
        # 5. 初始化页面容器
        self._init_pages()
        
        # 6. 设置主题
        self._setup_theme()
        
        # 7. 绑定事件
        self._bind_events()
        
        # 8. 显示首页
        self.show_page("home")
        
        # 9. 状态栏显示就绪
        self._update_status("ready")
    
    def _check_recovery_on_start(self):
        """
        启动时检查未完成的任务和残留文件
        
        - 检查是否有进度文件，提示用户是否继续
        - 检查是否有残留的 .sync.tmp 文件，清理或恢复
        """
        import glob
        
        print("🔍 启动时恢复检查...")
        
        # 检查残留的临时文件
        temp_files = []
        for task in self.task_manager.get_all_tasks():
            target_dir = task.get("target", "")
            if target_dir and os.path.exists(target_dir):
                try:
                    tmp_pattern = os.path.join(target_dir, "**", "*.sync.tmp")
                    temp_files.extend(glob.glob(tmp_pattern, recursive=True))
                except Exception:
                    pass
        
        if temp_files:
            print(f"⚠️ 发现 {len(temp_files)} 个残留临时文件")
            for tmp_file in temp_files[:5]:
                print(f"  - {tmp_file}")
            if len(temp_files) > 5:
                print(f"  ... 还有 {len(temp_files) - 5} 个")
            
            # 询问用户是否清理
            self._show_recovery_dialog(temp_files)
        
        # 检查中断的任务
        interrupted_tasks = self.config_manager.get_interrupted_tasks()
        if interrupted_tasks:
            print(f"⚠️ 发现 {len(interrupted_tasks)} 个未完成的任务")
            for task in interrupted_tasks[:5]:
                print(f"  - {task.get('name', '未知任务')}")
            
            # 可以在这里添加恢复提示
            for task in interrupted_tasks:
                task['status'] = 'pending'
        
        print("✅ 恢复检查完成")
    
    def _show_recovery_dialog(self, temp_files):
        """
        显示恢复对话框
        
        Args:
            temp_files: 临时文件列表
        """
        import tkinter as tk
        from tkinter import messagebox
        
        root = tk.Tk()
        root.withdraw()
        
        msg = f"发现 {len(temp_files)} 个残留的同步临时文件（.sync.tmp），可能是上次同步被中断导致的。\n\n是否清理这些文件？"
        
        result = messagebox.askyesno(
            "残留文件清理",
            msg,
            default=messagebox.YES
        )
        
        if result:
            cleaned = 0
            for tmp_file in temp_files:
                try:
                    os.remove(tmp_file)
                    cleaned += 1
                except Exception as e:
                    print(f"❌ 删除失败: {tmp_file} - {e}")
            print(f"✅ 已清理 {cleaned} 个临时文件")
            messagebox.showinfo("清理完成", f"已清理 {cleaned} 个临时文件")
        
        root.destroy()
    
    def _init_backend_modules(self):
        """分阶段初始化后端模块，每阶段更新状态栏"""
        
        # 阶段 1：加载配置
        self._update_status("loading_config")
        self.config_manager = ConfigManager()
        
        # 阶段 2：加载语言
        self._update_status("loading_language")
        language = self.config_manager.get_language()
        # v7.6: 外挂翻译目录 —— 默认 get_default_config_dir()/translations，
        # 与「配置存储路径」相互独立；用户单独设置后持久化到 settings
        settings = self.config_manager.get_settings()
        user_translations_dir = settings.get("user_translations_dir") or (
            get_default_config_dir() / "translations"
        )
        # 首次启动/目录为空时初始化外挂目录（复制内置语言与翻译说明，不覆盖已有文件）
        user_translations_dir = ensure_user_translations_dir(user_translations_dir)
        self.language_manager = LanguageManager(
            language, user_translations_dir=str(user_translations_dir)
        )

        # 语言加载后，状态栏字体切换为当前语言 meta 推荐字体
        if getattr(self, "status_label", None) is not None:
            try:
                self.status_label.configure(font=self.language_manager.get_font(size=12))
            except Exception:
                pass
        
        # 阶段 3：加载其他模块
        self._update_status("loading_modules")
        
        # 任务管理器
        self.task_manager = TaskManager(self.config_manager)
        
        # 回收站管理器
        self.recycle_manager = RecycleManager(self.config_manager)
        
        # 同步引擎
        self.sync_engine = SyncEngine()
        
        # 通知管理器
        self.notification_manager = NotificationManager(self)
        
        # 主题管理器
        self.theme_manager = ThemeManager(self.config_manager)
        
        # 当前运行的任务列表
        self.running_tasks: list = []
        
        # 当前正在编辑的任务配置
        self.current_task_config: Dict[str, Any] = {}
        
        # 当前页面名称
        self.current_page: str = ""
        
        # 页面实例缓存
        self.pages: Dict[str, ctk.CTkFrame] = {}
        
        # v7.5: 当前正在运行的同步引擎（供进度页恢复状态）
        self.current_sync_engine = None

        # v7.6: 自动关机 —— 本批同步各任务的成败结果 {task_id: bool}
        self._sync_outcomes: Dict[str, bool] = {}
        # 本批中真正失败（非用户手动取消）的任务信息 {task_id: task_dict}
        self._sync_failures: Dict[str, Dict[str, Any]] = {}
        self._sync_outcomes_lock = threading.Lock()
        # 关机倒计时
        self._shutdown_remaining: int = 0
        self._shutdown_after_id: Optional[str] = None
        
        # 阶段 4：启动时检查未完成的任务和残留文件
        self._update_status("checking_recovery")
        self._check_recovery_on_start()
    
    def _setup_window(self):
        """设置窗口属性"""
        # 设置窗口标题（临时，语言加载后更新）
        self.title("文件同步工具")
        
        # 设置窗口大小
        self.geometry(f"{self.DEFAULT_WIDTH}x{self.DEFAULT_HEIGHT}")
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        
        # 设置窗口图标（如果有的话）
        # self.iconbitmap("icon.ico")
        
        # 设置窗口关闭行为
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # 设置窗口缩放（row 0 为内容区，row 1 为状态栏）
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)
    
    def _create_status_bar(self):
        """创建底部状态栏，用于显示启动进度和运行状态"""
        self.status_bar = ctk.CTkFrame(self, height=28)
        self.status_bar.grid(row=1, column=0, sticky="ew")
        self.status_bar.grid_columnconfigure(0, weight=1)
        
        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="...",
            # 语言管理器尚未加载，先使用内置默认字体，加载后重配为当前语言字体
            font=get_font(size=12),
            text_color="gray",
            anchor="w"
        )
        self.status_label.grid(row=0, column=0, padx=10, pady=4, sticky="ew")

        # v7.6: 自动关机倒计时区域（平时隐藏）
        self.shutdown_frame = ctk.CTkFrame(self.status_bar, fg_color="transparent")
        self.shutdown_frame.grid(row=0, column=1, padx=(0, 10), pady=2, sticky="e")
        self.shutdown_label = ctk.CTkLabel(
            self.shutdown_frame,
            text="",
            font=get_font(size=12, weight="bold"),
            text_color="#C62828",
        )
        self.shutdown_label.pack(side="left", padx=(0, 8))
        self.shutdown_cancel_btn = ctk.CTkButton(
            self.shutdown_frame,
            text="取消关机",
            width=90,
            height=24,
            font=get_font(size=12),
            fg_color="#C62828",
            hover_color="#8E1B1B",
            command=self._cancel_shutdown_countdown,
        )
        self.shutdown_cancel_btn.pack(side="left")
        self.shutdown_frame.grid_remove()
    
    def _update_status(self, stage: str):
        """
        更新状态栏文本
        
        Args:
            stage: 启动阶段标识
                   "loading_config" - 正在加载配置
                   "loading_language" - 正在加载语言
                   "loading_modules" - 正在加载模块
                   "checking_recovery" - 正在检查信号
                   "ready" - 就绪
        """
        # 状态文本映射（支持中英文，语言加载前使用中文默认值）
        status_texts = {
            "loading_config": "正在加载配置..." if not hasattr(self, 'language_manager') else self.language_manager.get_text("status_loading_config", "正在加载配置..."),
            "loading_language": "正在加载语言..." if not hasattr(self, 'language_manager') else self.language_manager.get_text("status_loading_language", "正在加载语言..."),
            "loading_modules": "正在加载模块..." if not hasattr(self, 'language_manager') else self.language_manager.get_text("status_loading_modules", "正在加载模块..."),
            "checking_recovery": "正在检查信号..." if not hasattr(self, 'language_manager') else self.language_manager.get_text("status_checking_recovery", "正在检查信号..."),
            "ready": "就绪" if not hasattr(self, 'language_manager') else self.language_manager.get_text("status_ready", "就绪"),
        }
        
        text = status_texts.get(stage, stage)
        
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.configure(text=text)
            self.update_idletasks()
    
    def _setup_theme(self):
        """设置主题"""
        # 获取有效的主题（考虑用户偏好和系统主题）
        effective_theme = self.theme_manager.get_effective_theme()
        
        # 设置颜色主题
        ctk.set_appearance_mode(effective_theme)
        
        # 设置默认颜色主题
        ctk.set_default_color_theme("blue")
    
    def switch_theme(self, theme: str):
        """
        切换主题
        
        Args:
            theme: 主题类型 ("system", "light", "dark")
        """
        self.theme_manager.set_user_theme(theme)
        effective_theme = self.theme_manager.get_effective_theme()
        ctk.set_appearance_mode(effective_theme)
        
        # 刷新所有页面
        if self.current_page and self.current_page in self.pages:
            page = self.pages[self.current_page]
            if hasattr(page, 'refresh'):
                page.refresh()
            if hasattr(page, 'update_language'):
                page.update_language()
    
    def _init_pages(self):
        """初始化页面容器"""
        # 创建主容器
        self.main_container = ctk.CTkFrame(self)
        self.main_container.grid(row=0, column=0, sticky="nsew")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
    
    def _bind_events(self):
        """绑定事件"""
        # 绑定窗口大小变化事件
        self.bind("<Configure>", self._on_resize)
        
        # 绑定快捷键
        self.bind("<Control-q>", lambda e: self._on_closing())
        self.bind("<Escape>", lambda e: self.show_page("home"))
    
    def _on_resize(self, event):
        """窗口大小变化事件处理"""
        # 可以在这里处理窗口缩放时的布局调整
        pass
    
    def _on_closing(self):
        """窗口关闭事件处理"""
        # 检查是否有正在运行的任务
        if self.task_manager.get_running_tasks():
            self.handle_force_close("WM_CLOSE")
        
        # 保存配置
        self.config_manager.save_config()
        
        # 关闭窗口
        self.destroy()
    
    def handle_force_close(self, reason: str = "unknown"):
        """
        处理强制关闭事件（信号或窗口关闭）
        
        Args:
            reason: 关闭原因
        """
        print(f"⚠️ 强制关闭处理: {reason}")
        
        # 停止所有正在运行的同步任务
        if hasattr(self, 'sync_engine') and self.sync_engine:
            try:
                self.sync_engine.interrupt()
                print("✅ 同步引擎已中断")
            except Exception as e:
                print(f"❌ 中断同步引擎失败: {e}")
        
        # v7.5: 中断当前正在运行的同步引擎
        current_engine = getattr(self, 'current_sync_engine', None)
        if current_engine:
            try:
                current_engine.interrupt()
                print("✅ 当前同步引擎已中断")
            except Exception as e:
                print(f"❌ 中断当前同步引擎失败: {e}")
        
        # 保存当前进度
        if hasattr(self, 'current_sync_page') and self.current_sync_page:
            try:
                self.current_sync_page.save_progress()
                print("✅ 当前进度已保存")
            except Exception as e:
                print(f"❌ 保存进度失败: {e}")
        
        # 保存配置
        self.config_manager.save_config()
        print("✅ 配置已保存")
    
    def safe_exit(self):
        """
        安全退出流程
        
        步骤：
        1. 检查是否有正在运行的任务
        2. 如果有，弹出确认对话框
        3. 停止同步引擎
        4. 保存为打断任务
        5. 清理临时文件和进度文件
        6. 保存配置
        7. 关闭窗口
        """
        import tkinter as tk
        from tkinter import messagebox
        
        print("🔍 安全退出：检查运行中的任务...")
        
        # 步骤1：检查是否有正在运行的任务
        running_tasks = self.task_manager.get_running_tasks()
        
        if running_tasks:
            # 步骤2：弹出确认对话框
            task_names = [t.get('name', '未知任务') for t in running_tasks]
            task_name_str = "、".join(task_names)
            
            msg = f"检测到同步任务「{task_name_str}」正在运行，退出前将自动保存为打断任务。是否继续退出？"
            
            result = messagebox.askyesno(
                "确认退出",
                msg,
                icon=messagebox.WARNING,
                default=messagebox.NO
            )
            
            if not result:
                print("❌ 用户取消退出")
                return
            
            # 步骤3：停止同步引擎
            print("⏹️ 正在停止同步引擎...")
            if hasattr(self, 'sync_engine') and self.sync_engine:
                try:
                    self.sync_engine.interrupt()
                    print("✅ 同步引擎已中断")
                except Exception as e:
                    print(f"❌ 中断同步引擎失败: {e}")
            
            # 等待引擎完全停止
            import time
            timeout = 5
            start_time = time.time()
            while time.time() - start_time < timeout:
                if not self.task_manager.get_running_tasks():
                    break
                time.sleep(0.5)
            
            # 步骤4：保存为打断任务
            print("💾 正在保存为打断任务...")
            for task in running_tasks:
                try:
                    task_info = {
                        "id": task.get("id", ""),
                        "name": task.get("name", "未知任务"),
                        "source": task.get("source", ""),
                        "target": task.get("target", ""),
                        "status": "interrupted",
                        "interrupted_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    self.config_manager.add_interrupted_task(task_info)
                    print(f"✅ 已保存打断任务: {task.get('name')}")
                except Exception as e:
                    print(f"❌ 保存打断任务失败: {e}")
        
        # 步骤5：清理残留文件
        print("🧹 正在清理残留文件...")
        self._cleanup_temp_files()
        
        # 步骤6：保存配置
        print("💾 正在保存配置...")
        self.config_manager.save_config()
        print("✅ 配置已保存")
        
        # 步骤7：关闭窗口
        print("🚪 正在退出...")
        self.destroy()
    
    def _cleanup_temp_files(self):
        """
        清理残留的临时文件和进度文件
        
        - .sync.tmp 文件
        - .sync_progress.json 文件
        """
        import glob
        
        cleaned_count = 0
        
        # 清理所有任务目标目录中的临时文件
        for task in self.task_manager.get_all_tasks():
            target_dir = task.get("target", "")
            if target_dir and os.path.exists(target_dir):
                try:
                    # 清理 .sync.tmp 文件
                    tmp_pattern = os.path.join(target_dir, "**", "*.sync.tmp")
                    for tmp_file in glob.glob(tmp_pattern, recursive=True):
                        try:
                            os.remove(tmp_file)
                            cleaned_count += 1
                            print(f"  ✅ 已删除临时文件: {tmp_file}")
                        except Exception as e:
                            print(f"  ❌ 删除失败: {tmp_file} - {e}")
                    
                    # 清理进度文件
                    progress_pattern = os.path.join(target_dir, ".sync_progress.json")
                    for progress_file in glob.glob(progress_pattern):
                        try:
                            os.remove(progress_file)
                            cleaned_count += 1
                            print(f"  ✅ 已删除进度文件: {progress_file}")
                        except Exception as e:
                            print(f"  ❌ 删除失败: {progress_file} - {e}")
                except Exception:
                    pass
        
        if cleaned_count > 0:
            print(f"✅ 共清理 {cleaned_count} 个残留文件")
        else:
            print("✅ 没有残留文件需要清理")
    
    def show_page(self, page_name: str, **kwargs):
        """
        显示指定页面
        
        Args:
            page_name: 页面名称 (home, sync, create_task, folder_config, 
                       sync_confirm, sync_progress, running_tasks, 
                       task_manage, recycle)
            **kwargs: 传递给页面的额外参数
        """
        # 隐藏当前页面
        if self.current_page and self.current_page in self.pages:
            self.pages[self.current_page].grid_forget()
        
        # 获取或创建页面
        page = self._get_or_create_page(page_name, **kwargs)
        
        # 显示页面
        page.grid(row=0, column=0, sticky="nsew")
        
        # 更新当前页面名称
        self.current_page = page_name
        
        # 如果页面有 refresh 方法，调用它
        if hasattr(page, 'refresh'):
            page.refresh()
    
    def _get_or_create_page(self, page_name: str, **kwargs) -> ctk.CTkFrame:
        """
        获取或创建页面实例
        
        Args:
            page_name: 页面名称
            **kwargs: 传递给页面的额外参数
            
        Returns:
            页面实例
        """
        # 某些页面需要每次重新创建（如同步确认页、同步进度页、文件夹配置页、创建任务页）
        recreate_pages = ["sync_confirm", "sync_progress", "folder_config", "create_task"]
        
        if page_name in recreate_pages or page_name not in self.pages:
            # 在创建新页面前，先销毁旧页面（若存在），避免 CustomTkinter 访问已销毁 Canvas
            old_page = self.pages.get(page_name)
            if old_page is not None:
                try:
                    # 通知页面即将销毁（用于取消定时器等）
                    if hasattr(old_page, 'on_page_destroy'):
                        old_page.on_page_destroy()
                    old_page.destroy()
                except Exception:
                    pass
            page = self._create_page(page_name, **kwargs)
            self.pages[page_name] = page
            
            # v7.5: 若重新创建的是同步进度页且有正在运行的引擎，重新绑定以恢复状态
            if page_name == "sync_progress" and getattr(self, 'current_sync_engine', None) is not None:
                try:
                    page.set_sync_engine(self.current_sync_engine)
                except Exception:
                    pass
        else:
            page = self.pages[page_name]
        
        return page
    
    def _create_page(self, page_name: str, **kwargs) -> ctk.CTkFrame:
        """
        创建页面实例
        
        Args:
            page_name: 页面名称
            **kwargs: 传递给页面的额外参数
            
        Returns:
            页面实例
        """
        # 延迟导入以避免循环依赖
        if page_name == "home":
            from .home_page import HomePage
            return HomePage(self.main_container, self)
        
        elif page_name == "sync":
            from .sync_page import SyncPage
            return SyncPage(
                self.main_container,
                self,
                self.language_manager,
                self.task_manager,
                on_use_task=self._on_use_task,
                on_create_task=self._on_create_task
            )
        
        elif page_name == "create_task":
            from .create_task_page import CreateTaskPage
            return CreateTaskPage(
                self.main_container,
                self.language_manager,
                self.config_manager,
                task_manager=self.task_manager,
                on_next_step=self._on_create_task_next,
                on_cancel=self._on_create_task_cancel,
                on_folder_config=self._on_folder_config_from_create_task,
                on_save=self._on_save_task_edit,
                task_id=kwargs.get("task_id"),
                edit_mode=kwargs.get("edit_mode", False)
            )
        
        elif page_name == "folder_config":
            from .folder_config_page import FolderConfigPage
            return FolderConfigPage(
                self.main_container,
                self,
                task_config=kwargs.get("task_config"),
                on_prev_step=self._on_folder_config_prev,
                on_next_step=self._on_folder_config_next,
                on_cancel=self._on_folder_config_cancel
            )
        
        elif page_name == "sync_confirm":
            from .sync_confirm_page import SyncConfirmPage
            return SyncConfirmPage(
                self.main_container,
                self,
                task_config=kwargs.get("task_config"),
                on_save_and_start=self._on_save_and_start_sync,
                on_start_without_save=self._on_start_sync_without_save,
                on_cancel=self._on_sync_confirm_cancel
            )
        
        elif page_name == "sync_progress":
            from .sync_progress_page import SyncProgressPage
            return SyncProgressPage(
                self.main_container,
                self,
                task_info=kwargs.get("task_info"),
                on_complete=self._on_sync_complete,
                on_cancel=self._on_sync_cancel,
                on_save_interrupted=self._on_save_interrupted_task
            )
        
        elif page_name == "running_tasks":
            from .running_tasks_page import RunningTasksPage
            return RunningTasksPage(self.main_container, self)
        
        elif page_name == "task_manage":
            from .task_manage_page import TaskManagePage
            return TaskManagePage(self.main_container, self)
        
        elif page_name == "recycle":
            from .recycle_page import RecyclePage
            return RecyclePage(self.main_container, self)
        
        elif page_name == "settings":
            from .settings_page import SettingsPage
            return SettingsPage(self.main_container, self)

        elif page_name == "toolkit":
            from .toolkit_page import ToolkitPage
            return ToolkitPage(self.main_container, self)

        elif page_name == "watch_task_select":
            from .watch_task_select_page import WatchTaskSelectPage
            return WatchTaskSelectPage(self.main_container, self)

        else:
            # 默认返回首页
            from .home_page import HomePage
            return HomePage(self.main_container, self)
    
    def _on_use_task(self, task):
        """使用选中任务的回调"""
        task_config = task.copy()
        if "last_snapshot" not in task_config:
            task_config["last_snapshot"] = None
        if "sync_delete_enabled" not in task_config:
            settings = self.config_manager.get_settings()
            task_config["sync_delete_enabled"] = settings.get("sync_delete_default", False)
        self.show_page("sync_confirm", task_config=task_config)
    
    def _on_create_task(self):
        """创建新任务的回调"""
        self.show_page("create_task")
    
    def _on_create_task_next(self, task_config):
        """创建任务下一步回调"""
        # 保存当前任务配置
        self.current_task_config = task_config
        self.show_page("folder_config", task_config=task_config)
    
    def _on_create_task_cancel(self):
        """创建任务取消回调"""
        self.show_page("sync")
    
    def _on_save_task_edit(self):
        """保存任务编辑回调"""
        self.show_page("task_manage")
    
    def _on_folder_config_from_create_task(self, task_config):
        """从创建任务页面跳转到文件夹配置的回调"""
        # 保存当前任务配置
        self.current_task_config = task_config
        self.show_page("folder_config", task_config=task_config)
    
    def _on_folder_config_prev(self):
        """文件夹配置上一步回调"""
        self.show_page("create_task")
    
    def _on_folder_config_next(self, task_config):
        """文件夹配置下一步回调"""
        # 保存更新后的任务配置
        self.current_task_config = task_config
        self.show_page("sync_confirm", task_config=task_config)
    
    def _on_folder_config_cancel(self):
        """文件夹配置取消回调"""
        self.show_page("sync")
    
    def _on_save_and_start_sync(self, task_config):
        """保存任务并开始同步回调"""
        task_name = task_config.get("name", "未命名任务")
        self.task_manager.create_task(
            name=task_name,
            source=task_config.get("source", ""),
            target=task_config.get("target", ""),
            mode=task_config.get("mode", task_config.get("run_mode", "fast")),
            sync_direction=task_config.get("sync_direction", "both"),
            folders=task_config.get("folders", []),
            default_strategy=task_config.get("default_strategy", "conservative"),
            folder_strategies=task_config.get("folder_strategies", {}),
            folder_filters=task_config.get("folder_filters", {}),
            root_included=task_config.get("root_included", False),
            root_strategy=task_config.get("root_strategy", "conservative"),
            use_multithreading_scan=task_config.get("use_multithreading_scan", False),
            use_multithreading_copy=task_config.get("use_multithreading_copy", False),
            last_snapshot=task_config.get("last_snapshot"),
            post_sync_command=task_config.get("post_sync_command", "")
        )
        self._start_sync(task_config)
    
    def _on_start_sync_without_save(self, task_config):
        """开始同步（不保存）回调"""
        self._start_sync(task_config)
    
    def _on_sync_confirm_cancel(self):
        """同步确认取消回调"""
        self.show_page("sync")
    
    def _start_sync(self, task_config):
        """开始同步"""
        import threading
        
        source_dir = task_config.get("source", "")
        target_dir = task_config.get("target", "")
        sync_direction = task_config.get("sync_direction", "both")
        mode = task_config.get("mode", task_config.get("run_mode", "safe"))
        use_multithreading_scan = task_config.get("use_multithreading_scan", False)
        use_multithreading_copy = task_config.get("use_multithreading_copy", False)
        folders = task_config.get("folders", [])
        folder_strategies = task_config.get("folder_strategies", {})
        default_strategy = task_config.get("default_strategy", "conservative")
        root_included = task_config.get("root_included", False)
        root_strategy = task_config.get("root_strategy", "conservative")
        sync_delete_enabled = task_config.get("sync_delete_enabled", False)
        
        # 检查目录是否存在
        missing_dirs = []
        if source_dir and not os.path.isdir(source_dir):
            missing_dirs.append("source")
        if target_dir and not os.path.isdir(target_dir):
            missing_dirs.append("target")

        if missing_dirs:
            # v7.6: 给出具体错误原因（未插 U 盘时常见于源/目标目录）
            detail_lines = []
            if "source" in missing_dirs:
                detail_lines.append(
                    self.get_text(
                        "error_source_dir_missing",
                        "同步失败：源目录不存在「{path}」\n请检查 U 盘是否已插入。"
                    ).format(path=source_dir or self.get_text("not_configured", "（未配置）"))
                )
            if "target" in missing_dirs:
                detail_lines.append(
                    self.get_text(
                        "error_target_dir_missing",
                        "同步失败：目标目录不存在「{path}」\n请检查 U 盘是否已插入。"
                    ).format(path=target_dir or self.get_text("not_configured", "（未配置）"))
                )
            error_msg = "\n".join(detail_lines)

            # 显示错误提示
            self.show_page("sync_progress", task_info={
                "name": task_config.get("name", "同步任务"),
                "source": source_dir,
                "target": target_dir
            })

            sync_progress_page = self.pages.get("sync_progress")
            if sync_progress_page:
                # set_complete 先设置右上角短状态，再展示带具体路径的错误明细
                sync_progress_page.set_complete(success=False)
                sync_progress_page.show_error(error_msg)
            return
        
        # ===== v7.5: 同目录并发同步检测 =====
        if self.task_manager.is_directory_in_use(source_dir, target_dir):
            import tkinter as tk
            from tkinter import messagebox
            try:
                root = tk.Tk()
                root.withdraw()
                messagebox.showwarning(
                    "目录冲突",
                    "该目录正在被其他任务同步，请等待完成后再试。"
                )
                root.destroy()
            except Exception:
                pass
            return
        
        # 获取上次同步的文件快照（如果有）
        last_snapshot = task_config.get("last_snapshot")
        
        # v7.5: 筛选策略为任务级配置（按文件夹独立，未配置的文件夹不启用筛选）
        folder_filters = task_config.get("folder_filters", {})
        
        # 先执行预扫描获取预估信息（使用带筛选配置的引擎）
        preview_engine = SyncEngine(
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
        
        task_info = {
            "id": task_config.get("id", "sync_task"),
            "name": task_config.get("name", "同步任务"),
            "source": source_dir,
            "target": target_dir,
            "total_files": preview.total_files,
            "total_size": preview.total_size,
            "estimated_time": preview.estimated_time,
            "config": task_config,
            "last_snapshot": last_snapshot
        }
        # 标记任务为运行中
        # v7.6: 本批首个任务启动时清空上一批的成败记录（自动关机判定用）
        with self._sync_outcomes_lock:
            if not self.task_manager.get_running_tasks():
                self._sync_outcomes.clear()
        self.task_manager.start_task(task_info)
        
        # 显示同步进度页面
        self.show_page("sync_progress", task_info=task_info)
        
        # 获取设置配置
        settings = self.config_manager.get_settings()
        scan_workers = settings.get("scan_workers", settings.get("max_workers", 4))
        sync_workers = settings.get("sync_workers", max(2, settings.get("max_workers", 4) // 2))
        life_protection_enabled = settings.get("life_protection_enabled", True)
        usb_level = settings.get("usb_level", "medium")
        protection_strength = settings.get("protection_strength", "balanced")
        chunk_size_mb = settings.get("chunk_size_mb", 8)
        chunk_size = int(chunk_size_mb) * 1024 * 1024
        
        # 在主线程创建同步引擎（确保进度页能正确引用）
        sync_engine = SyncEngine(
            mode=mode,
            use_multithreading_scan=use_multithreading_scan,
            use_multithreading_copy=use_multithreading_copy,
            scan_workers=scan_workers,
            sync_workers=sync_workers,
            default_strategy=default_strategy,
            folder_strategies=folder_strategies,
            root_included=root_included,
            root_strategy=root_strategy,
            life_protection_enabled=life_protection_enabled,
            usb_level=usb_level,
            protection_strength=protection_strength,
            sync_delete_enabled=sync_delete_enabled,
            recycle_manager=self.recycle_manager,
            chunk_size=chunk_size,
            folder_filters=folder_filters,
            prevent_sleep_during_sync=settings.get("prevent_sleep_during_sync", True),
        )
        sync_engine.config_manager = self.config_manager
        
        # 保存当前运行的引擎引用（供进度页恢复状态使用）
        self.current_sync_engine = sync_engine
        
        # 获取同步进度页面实例并设置同步引擎（用于进度回调）
        sync_progress_page = self.pages.get("sync_progress")
        if sync_progress_page:
            sync_progress_page.set_sync_engine(sync_engine)
        
        # 在后台线程中启动同步
        def run_sync():
            try:
                # 执行同步
                sync_success = bool(sync_engine.sync_directories(
                    source_dir=source_dir,
                    target_dir=target_dir,
                    direction=sync_direction,
                    last_snapshot=last_snapshot
                ))

                # 保存本次同步的文件快照
                if sync_engine.last_snapshot:
                    task_config["last_snapshot"] = sync_engine.last_snapshot
                    
                    # 持久化到任务配置（如果任务已保存）
                    task_id = task_config.get("id")
                    if task_id:
                        existing_task = self.task_manager.get_task_by_id(task_id)
                        if existing_task:
                            self.task_manager.update_task(task_id, {
                                "last_snapshot": sync_engine.last_snapshot
                            })
                
                # 同步完成
                self._on_sync_complete(task_info.get("id"), sync_success=sync_success)
            except Exception as e:
                print(f"同步错误: {e}")
                # 更新进度页面显示错误
                sync_progress_page = self.pages.get("sync_progress")
                if sync_progress_page:
                    error_msg = f"同步中断：{str(e)}"
                    sync_progress_page.status_label.configure(
                        text=error_msg,
                        text_color="red"
                    )
                    sync_progress_page.set_complete(success=False)
                self._on_sync_cancel(task_info.get("id"), failure=True)
        
        # 启动后台线程执行同步
        sync_thread = threading.Thread(target=run_sync, daemon=True)
        sync_thread.start()
    
    def start_sync_from_interrupted(self, task_info, interrupted_task_id=None):
        """从打断任务继续同步"""
        # 构建任务配置（兼容旧任务格式）
        thread_mode = task_info.get("thread_mode", False)
        task_config = {
            "id": interrupted_task_id,
            "name": task_info.get("name", "未命名任务"),
            "source": task_info.get("source", ""),
            "target": task_info.get("target", ""),
            "sync_direction": "both",
            "run_mode": task_info.get("mode", "safe"),
            "use_multithreading_scan": task_info.get("use_multithreading_scan", thread_mode),
            "use_multithreading_copy": task_info.get("use_multithreading_copy", False),
            "default_strategy": task_info.get("strategy", "conservative"),
            "folder_strategies": task_info.get("folder_strategies", {}),
            "folders": [],
            "root_included": True,
            "root_strategy": "conservative"
        }
        
        # 从配置管理器中移除该打断任务
        if interrupted_task_id:
            self.config_manager.remove_interrupted_task(interrupted_task_id)
        
        # 开始同步
        self._start_sync(task_config)
    
    def _on_sync_complete(self, task_id=None, sync_success=True):
        """同步完成回调（sync_success 为 sync_directories 的返回值）"""
        # 获取当前任务信息
        sync_progress_page = self.pages.get("sync_progress")
        blocked_files = []
        task_config = {}
        has_errors = False
        if sync_progress_page:
            task_name = sync_progress_page.task_info.get("name", "同步任务")
            file_count = sync_progress_page.current_file
            task_config = sync_progress_page.task_info.get("config", {}) or {}

            # 检查是否有错误
            if sync_progress_page.sync_engine:
                stats = sync_progress_page.sync_engine.get_stats()
                has_errors = len(stats.errors) > 0 or len(stats.permission_denied) > 0
                # v7.6: 记录被安全软件（如 Defender）拦截的文件，稍后弹窗列出
                blocked_files = list(stats.permission_denied)

        # v7.6: 最终成败 = 引擎返回值 且 无逐文件错误/权限错误
        final_success = bool(sync_success) and not has_errors

        if task_id:
            if final_success:
                self.task_manager.stop_task(task_id, "completed")
            else:
                # 失败：记录失败任务信息（供自动关机判定时保存为打断任务）
                self._record_sync_failure(task_id)
                self.task_manager.stop_task(task_id, "failed")
            self._mark_sync_outcome(task_id, final_success)

        # v7.5: 清除当前运行引擎引用
        self.current_sync_engine = None

        if sync_progress_page:
            # 发送通知
            self.notification_manager.send_sync_complete(task_name, file_count, has_errors)

        # v7.6: 同步成功后执行任务配置的命令（失败只记日志，不阻断流程）
        command = (task_config.get("post_sync_command") or "").strip()
        if command:
            try:
                from backend.cli_sync import run_post_sync_command
                run_post_sync_command(
                    command,
                    task_name=task_config.get("name", ""),
                    cwd=task_config.get("source") or None,
                )
            except Exception as e:
                print(f"⚠️ 同步后命令启动失败：{e}")

        # v7.6: Defender/安全软件拦截提示（GUI 线程中弹窗，明确到具体文件）
        if blocked_files:
            self.after(0, lambda files=blocked_files: self._show_blocked_files_dialog(files))

        self.show_page("home")

        # v7.6: 本批任务全部结束时，判定是否自动关机
        self._maybe_auto_shutdown()

    def _show_blocked_files_dialog(self, blocked_files: list):
        """弹窗列出被安全软件拦截、未完成同步的文件"""
        import tkinter as tk
        from tkinter import messagebox

        shown = blocked_files[:10]
        body = "\n".join(shown)
        if len(blocked_files) > 10:
            body += f"\n……（另有 {len(blocked_files) - 10} 个）"
        message = self.get_text(
            "blocked_files_message",
            "以下文件可能被 Windows Defender 等安全软件拦截，未能同步。\n"
            "请检查文件是否安全；如确认无误，请在安全软件中放行后重试：\n\n"
        ) + body

        root = tk._default_root
        messagebox.showwarning(
            self.get_text("blocked_files_title", "安全软件拦截提示"),
            message,
            parent=root,
        )
    
    def _on_sync_cancel(self, task_id=None, failure: bool = False):
        """
        同步取消/异常回调

        Args:
            task_id: 任务 ID
            failure: True 表示同步因异常失败（本批结束时弹窗并保存为打断任务）；
                     False 为用户手动取消（不自动关机，打断任务由用户手动保存）
        """
        if task_id:
            if failure:
                self._record_sync_failure(task_id)
            self.task_manager.stop_task(task_id, "interrupted")
            self._mark_sync_outcome(task_id, False)
        # v7.5: 清除当前运行引擎引用
        self.current_sync_engine = None
        self.show_page("home")
        # v7.6: 本批任务全部结束时，判定是否自动关机
        self._maybe_auto_shutdown()

    # ===================== v7.6: 同步后自动关机 =====================

    def _record_sync_failure(self, task_id):
        """记录失败任务的运行信息（必须在 stop_task 之前调用）"""
        with self._sync_outcomes_lock:
            info = self.task_manager.running_tasks.get(task_id)
            if info:
                self._sync_failures[task_id] = dict(info)

    def _mark_sync_outcome(self, task_id, success: bool):
        """记录本批中单个任务的成败结果"""
        with self._sync_outcomes_lock:
            self._sync_outcomes[task_id] = bool(success)

    def _maybe_auto_shutdown(self):
        """
        本批同步任务全部结束时调用：
        - 仍有任务运行：等待最后一个任务结束后再判定
        - 开启了自动关机且全部成功：由系统安排延迟关机，并启动状态栏倒计时
        - 存在失败任务：取消关机，失败任务保存为打断任务并弹窗提示
        - 仅有用户手动取消的任务：静默不关机
        """
        if self.task_manager.get_running_tasks():
            return

        with self._sync_outcomes_lock:
            outcomes = dict(self._sync_outcomes)
            failures = dict(self._sync_failures)
        self._sync_outcomes.clear()
        self._sync_failures.clear()

        settings = self.config_manager.get_settings()
        if not settings.get("auto_shutdown_enabled", False) or not outcomes:
            return

        if failures:
            # 有任务失败：保留任务状态（保存为打断任务），弹窗提示，不关机
            self._save_failed_as_interrupted(failures)
            self.after(0, lambda f=failures: self._show_sync_failure_dialog(f))
            return

        if not all(outcomes.values()):
            # 存在非成功结果（如用户手动取消），不关机
            return

        # 全部成功：安排系统关机（OS 计时器在 GUI 关闭后仍然有效）
        delay = int(settings.get("auto_shutdown_delay", 60) or 60)
        if delay not in (30, 60, 120):
            delay = 60
        from backend.platform_utils import schedule_shutdown
        if schedule_shutdown(delay):
            self.after(0, lambda d=delay: self._start_shutdown_countdown(d))
        # 平台不支持时静默跳过

    def _save_failed_as_interrupted(self, failures: Dict[str, Dict[str, Any]]):
        """将失败任务保存为打断任务，保留任务状态供下次继续"""
        from datetime import datetime
        import uuid
        for info in failures.values():
            try:
                interrupted_task = {
                    "id": str(uuid.uuid4()),
                    "name": info.get("name", "未命名任务"),
                    "source": info.get("source", ""),
                    "target": info.get("target", ""),
                    "completed_files": info.get("completed_files", 0),
                    "total_files": info.get("total_files", 0),
                    "percentage": info.get("progress", 0),
                    "elapsed_time": 0,
                    "remaining_time": 0,
                    "interrupted_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    "failed": True,
                    "task_config": info.get("task_config", info),
                }
                self.config_manager.add_interrupted_task(interrupted_task)
            except Exception as e:
                print(f"❌ 保存失败任务为打断任务失败: {e}")
        try:
            self.after(0, self.update_interrupted_tasks)
        except Exception:
            pass

    def _show_sync_failure_dialog(self, failures: Dict[str, Dict[str, Any]]):
        """弹窗告知用户：因任务失败已取消自动关机，任务已保存为打断任务"""
        import tkinter as tk
        from tkinter import messagebox

        names = "、".join(info.get("name", str(tid)) for tid, info in failures.items())
        message = self.get_text(
            "shutdown_aborted_failed",
            "以下任务同步失败，已取消自动关机，任务状态已保留为打断任务：\n\n{names}",
        ).format(names=names)
        try:
            messagebox.showwarning(
                self.get_text("auto_shutdown", "同步后自动关机"),
                message,
                parent=tk._default_root,
            )
        except Exception:
            pass

    def _start_shutdown_countdown(self, delay: int):
        """在状态栏显示关机倒计时（实际关机由系统计时器接管）"""
        self._shutdown_remaining = max(0, int(delay))
        self.shutdown_cancel_btn.configure(state="normal")
        self.shutdown_frame.grid()
        self._tick_shutdown_countdown()

    def _tick_shutdown_countdown(self):
        """每秒刷新倒计时显示"""
        n = self._shutdown_remaining
        if n <= 0:
            self.shutdown_label.configure(
                text=self.get_text("shutting_down", "正在关机…")
            )
            self.shutdown_cancel_btn.configure(state="disabled")
            self._shutdown_after_id = None
            return
        self.shutdown_label.configure(
            text=self.get_text("shutdown_countdown", "⏻ {n} 秒后关机").format(n=n)
        )
        self._shutdown_remaining = n - 1
        self._shutdown_after_id = self.after(1000, self._tick_shutdown_countdown)

    def _cancel_shutdown_countdown(self):
        """取消关机：通知系统取消计时器并隐藏状态栏倒计时"""
        from backend.platform_utils import cancel_scheduled_shutdown
        cancel_scheduled_shutdown()

        if self._shutdown_after_id is not None:
            try:
                self.after_cancel(self._shutdown_after_id)
            except Exception:
                pass
            self._shutdown_after_id = None
        self._shutdown_remaining = 0
        try:
            self.shutdown_frame.grid_remove()
            self.shutdown_cancel_btn.configure(state="normal")
            self._update_status("ready")
        except Exception:
            pass
    
    def _on_save_interrupted_task(self, task_info=None, progress_info=None):
        """保存打断任务回调"""
        if task_info:
            from datetime import datetime
            import uuid
            
            # 创建打断任务记录
            interrupted_task = {
                "id": task_info.get("id", str(uuid.uuid4())),
                "name": task_info.get("name", "未命名任务"),
                "source": task_info.get("source", ""),
                "target": task_info.get("target", ""),
                "completed_files": progress_info.get("completed_files", 0) if progress_info else 0,
                "total_files": progress_info.get("total_files", 0) if progress_info else task_info.get("total_files", 0),
                "percentage": progress_info.get("percentage", 0) if progress_info else 0,
                "elapsed_time": progress_info.get("elapsed_time", 0) if progress_info else 0,
                "remaining_time": progress_info.get("remaining_time", 0) if progress_info else 0,
                "interrupted_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "task_config": task_info.get("config", task_info)
            }
            
            # 保存到配置管理器
            self.config_manager.add_interrupted_task(interrupted_task)
            
            # 发送同步中断通知
            task_name = task_info.get("name", "未命名任务")
            self.notification_manager.send_sync_interrupted(task_name)
        
        # 刷新首页的打断任务列表
        self.update_interrupted_tasks()
        
        self.show_page("home")
    
    def get_text(self, key: str, default: str = None, **kwargs) -> str:
        """
        获取翻译文本（支持格式化）
        
        Args:
            key: 文本键名
            default: 默认文本
            **kwargs: 格式化参数
            
        Returns:
            翻译后的文本
        """
        if kwargs:
            # 如果有格式化参数，使用 format_text 方法
            return self.language_manager.format_text(key, **kwargs)
        else:
            # 否则使用普通的 get_text 方法
            return self.language_manager.get_text(key, default)
    
    def change_language(self, language: str) -> bool:
        """
        切换到指定语言（设置页语言下拉框调用）

        损坏或不存在的语言会被 LanguageManager 拒绝。

        Args:
            language: 目标语言代码

        Returns:
            是否切换成功
        """
        if not self.language_manager.set_language(language):
            return False

        self.config_manager.set_language(language)
        self._apply_language_change()
        return True

    def switch_language(self):
        """循环切换到下一个可用语言（由首页语言按钮触发，自动跳过损坏文件）"""
        next_language = self.language_manager.get_next_language()
        self.change_language(next_language)

    def _apply_language_change(self):
        """语言切换后的统一刷新：标题、状态栏字体与全部页面重建"""
        # 更新窗口标题
        self.title(self.get_text("app_title"))

        # 状态栏字体随当前语言 meta 刷新
        if getattr(self, "status_label", None) is not None:
            try:
                self.status_label.configure(font=self.language_manager.get_font(size=12))
                self.shutdown_label.configure(font=self.language_manager.get_font(size=12, weight="bold"))
                self.shutdown_cancel_btn.configure(
                    text=self.get_text("cancel_shutdown", "取消关机"),
                    font=self.language_manager.get_font(size=12),
                )
            except Exception:
                pass

        # 销毁全部已缓存页面（含当前页）：语言切换不仅影响当前页，
        # home/sync/task_manage 等缓存页也必须在下次显示时以新语言+新字体重建，
        # 否则会出现“设置页切了英文，回到首页按钮仍是中文”的问题
        cached_pages = list(self.pages.values())
        self.pages.clear()
        for page in cached_pages:
            try:
                if hasattr(page, 'on_page_destroy'):
                    page.on_page_destroy()
                page.destroy()
            except Exception:
                pass

        # 重新显示当前页面（会创建新页面实例）
        self.show_page(self.current_page)
    
    def add_running_task(self, task_info: Dict[str, Any]):
        """
        添加运行中的任务
        
        Args:
            task_info: 任务信息
        """
        self.task_manager.start_task(task_info)
    
    def remove_running_task(self, task_id: str):
        """
        移除运行中的任务
        
        Args:
            task_id: 任务 ID
        """
        self.task_manager.remove_task_from_running(task_id)
    
    def get_running_tasks(self) -> list:
        """获取运行中的任务列表（含监听子进程触发的同步）"""
        running = list(self.task_manager.get_running_tasks())

        # v7.6: 合并监听子进程触发的同步进度（跨进程状态文件）
        try:
            from backend import watch_process
            config_dir = self.config_manager.get_config_dir()
            watch_statuses = watch_process.get_watch_sync_statuses(config_dir)
            for name, info in watch_statuses.items():
                # 避免与 GUI 内已启动的同名任务重复
                if any(t.get("name") == name for t in running):
                    continue
                running.append({
                    "id": f"watch_{name}",
                    "name": name,
                    "source": info.get("source", ""),
                    "target": info.get("target", ""),
                    "remaining_time": info.get("estimated_remaining", 0),
                    "percentage": info.get("percentage", 0),
                    "current_file": info.get("current_file", ""),
                    "current_phase": info.get("current_phase", ""),
                    "total_files": info.get("total_files", 0),
                    "completed_files": info.get("completed_files", 0),
                    "origin": "watch",  # 标记为监听触发
                })
        except Exception:
            pass

        return running

    # ===================== v7.6: 配置/语言目录迁移辅助 =====================

    def has_active_sync_activity(self) -> bool:
        """
        是否存在同步活动：GUI 内正在运行的同步任务，或后台监听子进程
        （list_watchers 已按 PID 清理死记录，结果可靠）。
        """
        if self.task_manager.get_running_tasks():
            return True
        try:
            from backend import watch_process
            config_dir = self.config_manager.get_config_dir()
            return len(watch_process.list_watchers(config_dir)) > 0
        except Exception:
            return False

    def interrupt_sync_for_migration(self) -> bool:
        """
        迁移前中断全部同步活动（含后台监听子进程触发的同步）。

        中断引擎 → 停止监听子进程 → 等待 GUI 任务结束 →
        保存打断任务 → 清理临时文件（.sync.tmp / .sync_progress.json），
        确保不留下损坏的中间状态。

        Returns:
            是否全部成功停止（未全部停止时调用方应取消迁移）
        """
        import time as _time

        running = self.get_running_tasks()
        if not running:
            return True

        # 中断 GUI 内的同步引擎
        for engine in (getattr(self, 'sync_engine', None),
                       getattr(self, 'current_sync_engine', None)):
            if engine:
                try:
                    engine.interrupt()
                    print("✅ 同步引擎已中断")
                except Exception as e:
                    print(f"❌ 中断同步引擎失败: {e}")

        # 停止全部后台监听子进程（其触发的同步随之终止）
        try:
            from backend import watch_process
            config_dir = self.config_manager.get_config_dir()
            for task_name in list(watch_process.list_watchers(config_dir).keys()):
                try:
                    result = watch_process.stop_watcher(config_dir, task_name)
                    print(f"{'✅' if result.get('success') else '⚠️'} 停止监听 {task_name}: {result.get('message', '')}")
                except Exception as e:
                    print(f"❌ 停止监听失败 {task_name}: {e}")
            # 清空监听同步进度状态，避免陈旧记录被误报为仍在运行
            watch_process.clear_watch_sync_statuses(config_dir)
        except Exception as e:
            print(f"❌ 停止监听子进程失败: {e}")

        # 等待 GUI 内任务结束（最多 10 秒）
        timeout = 10
        start = _time.time()
        while _time.time() - start < timeout:
            if not self.task_manager.get_running_tasks():
                break
            _time.sleep(0.5)

        stopped = not self.task_manager.get_running_tasks()
        if not stopped:
            print("⚠️ 同步任务未能在限时内完全停止")
            return False

        # 保存打断任务（与退出流程一致，便于首页一键恢复）
        for task in running:
            try:
                task_info = {
                    "id": task.get("id", ""),
                    "name": task.get("name", "未知任务"),
                    "source": task.get("source", ""),
                    "target": task.get("target", ""),
                    "status": "interrupted",
                    "interrupted_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                self.config_manager.add_interrupted_task(task_info)
                print(f"✅ 已保存打断任务: {task.get('name')}")
            except Exception as e:
                print(f"❌ 保存打断任务失败: {e}")

        # 清理临时文件，确保不留损坏的中间状态
        try:
            self._cleanup_temp_files()
        except Exception as e:
            print(f"❌ 清理临时文件失败: {e}")

        return True

    def update_interrupted_tasks(self):
        """更新打断任务列表"""
        # 刷新首页的打断任务列表
        if "home" in self.pages:
            home_page = self.pages["home"]
            if hasattr(home_page, 'refresh_interrupted_tasks'):
                home_page.refresh_interrupted_tasks()


def main():
    """主函数：启动应用程序"""
    # 设置外观模式
    ctk.set_appearance_mode("light")
    
    # 设置默认颜色主题
    ctk.set_default_color_theme("blue")
    
    # 创建并运行应用
    app = FileSyncApp()
    app.mainloop()


if __name__ == "__main__":
    main()