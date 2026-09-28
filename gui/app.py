"""
文件同步工具 v7.3 - 主窗口
基于 CustomTkinter 的主应用程序窗口
"""

import os
import customtkinter as ctk
from typing import Optional, Dict, Any

from backend.config_manager import ConfigManager
from backend.language_manager import LanguageManager, get_font
from backend.task_manager import TaskManager
from backend.recycle_manager import RecycleManager
from backend.sync_engine import FileSyncEngine as SyncEngine
from backend.notification_manager import NotificationManager
from backend.theme_manager import ThemeManager


class FileSyncApp(ctk.CTk):
    """主窗口类：管理整个应用程序的主窗口"""
    
    # 窗口默认尺寸
    DEFAULT_WIDTH = 1200
    DEFAULT_HEIGHT = 800
    MIN_WIDTH = 900
    MIN_HEIGHT = 600
    
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
        self.language_manager = LanguageManager(language)

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
            last_snapshot=task_config.get("last_snapshot")
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
            missing_dirs.append(f"源目录「{source_dir}」")
        if target_dir and not os.path.isdir(target_dir):
            missing_dirs.append(f"目标目录「{target_dir}」")
        
        if missing_dirs:
            # 显示错误提示
            self.show_page("sync_progress", task_info={
                "name": task_config.get("name", "同步任务"),
                "source": source_dir,
                "target": target_dir
            })
            
            sync_progress_page = self.pages.get("sync_progress")
            if sync_progress_page:
                error_msg = "同步中断：找不到" + "、".join(missing_dirs)
                sync_progress_page.status_label.configure(
                    text=error_msg,
                    text_color="red"
                )
                sync_progress_page.set_complete(success=False)
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
            folder_filters=folder_filters
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
                sync_engine.sync_directories(
                    source_dir=source_dir,
                    target_dir=target_dir,
                    direction=sync_direction,
                    last_snapshot=last_snapshot
                )
                
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
                self._on_sync_complete(task_info.get("id"))
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
                self._on_sync_cancel(task_info.get("id"))
        
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
    
    def _on_sync_complete(self, task_id=None):
        """同步完成回调"""
        if task_id:
            self.task_manager.stop_task(task_id, "completed")
        
        # v7.5: 清除当前运行引擎引用
        self.current_sync_engine = None
        
        # 获取当前任务信息
        sync_progress_page = self.pages.get("sync_progress")
        if sync_progress_page:
            task_name = sync_progress_page.task_info.get("name", "同步任务")
            file_count = sync_progress_page.current_file
            
            # 检查是否有错误
            has_errors = False
            if sync_progress_page.sync_engine:
                stats = sync_progress_page.sync_engine.get_stats()
                has_errors = len(stats.errors) > 0 or len(stats.permission_denied) > 0
            
            # 发送通知
            self.notification_manager.send_sync_complete(task_name, file_count, has_errors)
        
        self.show_page("home")
    
    def _on_sync_cancel(self, task_id=None):
        """同步取消回调"""
        if task_id:
            self.task_manager.stop_task(task_id, "interrupted")
        # v7.5: 清除当前运行引擎引用
        self.current_sync_engine = None
        self.show_page("home")
    
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
        """获取运行中的任务列表"""
        return self.task_manager.get_running_tasks()
    
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