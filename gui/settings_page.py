"""
文件同步工具 v7.3 - 设置页面
用于管理应用程序设置，包括主题切换、线程数、寿命保护等
"""

import customtkinter as ctk
from backend.language_manager import get_font
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import FileSyncApp


class SettingsPage(ctk.CTkFrame):
    """设置页面：管理应用程序设置"""
    
    USB_LEVEL_KEYS = ["auto", "low", "medium", "high"]
    PROTECTION_STRENGTH_KEYS = ["aggressive", "balanced", "conservative"]
    
    def _get_usb_levels(self):
        """获取U盘档位的多语言列表"""
        return [
            ("auto", self.language_manager.get_text("usb_level_auto", "自动检测")),
            ("low", self.language_manager.get_text("usb_level_low", "老旧U盘")),
            ("medium", self.language_manager.get_text("usb_level_medium", "普通U盘")),
            ("high", self.language_manager.get_text("usb_level_high", "高速U盘"))
        ]
    
    def _get_protection_strengths(self):
        """获取保护强度的多语言列表"""
        return [
            ("aggressive", self.language_manager.get_text("protection_strength_aggressive", "激进")),
            ("balanced", self.language_manager.get_text("protection_strength_balanced", "均衡")),
            ("conservative", self.language_manager.get_text("protection_strength_conservative", "保守"))
        ]
    
    def __init__(self, master, app: "FileSyncApp"):
        """
        初始化设置页面
        
        Args:
            master: 父容器
            app: 主窗口实例
        """
        super().__init__(master)
        
        self.app = app
        self.language_manager = app.language_manager
        self.config_manager = app.config_manager
        
        # 获取当前设置
        self.settings = self.config_manager.get_settings()
        
        # 创建界面
        self._create_widgets()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 配置网格权重
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        
        # ========== 顶部标题区域 ==========
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text=self.language_manager.get_text("settings", "设置"),
            font=get_font(size=18, weight="bold")
        )
        self.title_label.pack(padx=10, pady=10)
        
        # ========== 中间内容区域 ==========
        self.content_frame = ctk.CTkScrollableFrame(self)
        self.content_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        
        # v7.5.1: 语言设置区域（下拉框，动态扫描 translations 目录）
        self._create_language_section()

        # 主题设置区域
        self._create_theme_section()
        
        # 线程设置区域
        self._create_thread_section()
        
        # 寿命保护设置区域
        self._create_life_protection_section()
        
        # 同步删除和回收站设置区域
        self._create_sync_delete_section()
        
        # v7.5: 配置存储路径设置区域
        self._create_config_path_section()
        
        # v7.5: 任务导入导出区域
        self._create_task_import_export_section()
        
        # ========== 底部按钮区域 ==========
        self.bottom_frame = ctk.CTkFrame(self)
        self.bottom_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.bottom_frame.grid_columnconfigure(0, weight=1)
        self.bottom_frame.grid_columnconfigure(1, weight=1)
        
        # 恢复默认配置按钮
        self.reset_btn = ctk.CTkButton(
            self.bottom_frame,
            text=self.language_manager.get_text("restore_default_config", "恢复默认配置"),
            height=45,
            font=get_font(size=15, weight="bold"),
            fg_color=("#D32F2F", "#C62828"),
            hover_color=("#B71C1C", "#B71C1C"),
            command=self._on_reset_config_click
        )
        self.reset_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # 返回首页按钮
        self.back_btn = ctk.CTkButton(
            self.bottom_frame,
            text=self.language_manager.get_text("return_home", "返回首页"),
            height=45,
            font=get_font(size=15, weight="bold"),
            command=self._on_back_click
        )
        self.back_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

    # ===================== v7.5.1: 语言设置 =====================

    def _create_language_section(self):
        """创建语言设置区域（下拉框动态扫描 translations 目录下的语言文件）"""
        self.language_frame = ctk.CTkFrame(self.content_frame)
        self.language_frame.grid(row=0, column=0, padx=5, pady=10, sticky="ew")
        self.language_frame.grid_columnconfigure(0, weight=1)

        # 区域标题
        self.language_title = ctk.CTkLabel(
            self.language_frame,
            text=self.language_manager.get_text("language_settings", "语言设置"),
            font=get_font(size=16, weight="bold")
        )
        self.language_title.grid(row=0, column=0, padx=10, pady=(10, 15), sticky="w")

        # 说明文字
        self.language_hint = ctk.CTkLabel(
            self.language_frame,
            text=self.language_manager.get_text(
                "language_hint", "选择界面显示语言，切换后立即生效"
            ),
            font=get_font(size=12),
            text_color="gray"
        )
        self.language_hint.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")

        # 动态扫描语言文件：[(语言代码, 显示名, 是否损坏)]
        self._language_options = self.language_manager.get_language_options()
        display_values = [display for _, display, _ in self._language_options]

        self.language_var = ctk.StringVar(
            value=self._get_language_display(self.language_manager.get_language())
        )
        self.language_combobox = ctk.CTkComboBox(
            self.language_frame,
            values=display_values,
            variable=self.language_var,
            command=self._on_language_select,
            font=get_font(size=14),
            dropdown_font=get_font(size=14),
            state="readonly"
        )
        self.language_combobox.grid(row=2, column=0, padx=10, pady=(0, 15), sticky="ew")

    def _get_language_display(self, language_code: str) -> str:
        """根据语言代码获取下拉框中的显示名，找不到时回退为语言名/代码"""
        for code, display, _broken in self._language_options:
            if code == language_code:
                return display
        return self.language_manager.get_language_name(language_code)

    def _on_language_select(self, value: str):
        """语言下拉框选择事件：损坏文件标注“损坏”且不允许选择"""
        selected_code = None
        selected_broken = False
        for code, display, broken in self._language_options:
            if display == value:
                selected_code = code
                selected_broken = broken
                break

        current_language = self.language_manager.get_language()

        if selected_code is None:
            # 非列表内的值（readonly 状态下理论上不会出现），恢复当前语言
            self.language_var.set(self._get_language_display(current_language))
            return

        if selected_broken:
            # 损坏的语言文件不允许选择：提示并复位为当前语言
            import tkinter as tk
            from tkinter import messagebox

            filename = f"{selected_code}.json"
            warning_template = self.language_manager.get_text(
                "language_broken_warning",
                "语言文件 {filename} 已损坏，无法选择，请检查该文件。"
            )
            warning_text = warning_template.replace("{filename}", filename)

            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning(
                self.language_manager.get_text("language_settings", "语言设置"),
                warning_text
            )
            root.destroy()

            self.language_var.set(self._get_language_display(current_language))
            return

        if selected_code == current_language:
            return

        # 切换语言（主窗口会销毁并重建当前页面，字体随语言 meta 一并刷新）
        self.app.change_language(selected_code)

    def _create_theme_section(self):
        """创建主题设置区域"""
        self.theme_frame = ctk.CTkFrame(self.content_frame)
        self.theme_frame.grid(row=1, column=0, padx=5, pady=10, sticky="ew")
        self.theme_frame.grid_columnconfigure(0, weight=1)
        
        # 区域标题
        self.theme_title = ctk.CTkLabel(
            self.theme_frame,
            text=self.language_manager.get_text("theme_settings", "主题设置"),
            font=get_font(size=16, weight="bold")
        )
        self.theme_title.grid(row=0, column=0, padx=10, pady=(10, 15), sticky="w")
        
        # 主题模式说明
        self.theme_hint = ctk.CTkLabel(
            self.theme_frame,
            text=self.language_manager.get_text("theme_hint", "选择界面主题"),
            font=get_font(size=12),
            text_color="gray"
        )
        self.theme_hint.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")
        
        # 当前主题显示
        current_theme = self.app.theme_manager.get_user_theme()
        current_theme_text = self._get_theme_display_name(current_theme)
        
        self.current_theme_label = ctk.CTkLabel(
            self.theme_frame,
            text=self.language_manager.get_text("current_theme", "当前主题") + f": {current_theme_text}",
            font=get_font(size=13),
            text_color=("#3B8ED0", "#1F6AA5")
        )
        self.current_theme_label.grid(row=2, column=0, padx=10, pady=(0, 15), sticky="w")
        
        # 主题选项按钮容器
        self.theme_options_frame = ctk.CTkFrame(self.theme_frame)
        self.theme_options_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        self.theme_options_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # 跟随系统按钮
        self.theme_system_btn = ctk.CTkButton(
            self.theme_options_frame,
            text=self.language_manager.get_text("theme_system", "跟随系统"),
            height=40,
            font=get_font(size=14),
            command=lambda: self._on_theme_select("system"),
            fg_color="#3B8ED0" if current_theme == "system" else "transparent",
            text_color="white" if current_theme == "system" else ("black", "white"),
            hover_color="#36719F" if current_theme == "system" else ("gray85", "gray25"),
            border_width=0 if current_theme == "system" else 2,
            border_color=("#3B8ED0", "#1F6AA5")
        )
        self.theme_system_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        # 始终浅色按钮
        self.theme_light_btn = ctk.CTkButton(
            self.theme_options_frame,
            text=self.language_manager.get_text("theme_light", "始终浅色"),
            height=40,
            font=get_font(size=14),
            command=lambda: self._on_theme_select("light"),
            fg_color="#3B8ED0" if current_theme == "light" else "transparent",
            text_color="white" if current_theme == "light" else ("black", "white"),
            hover_color="#36719F" if current_theme == "light" else ("gray85", "gray25"),
            border_width=0 if current_theme == "light" else 2,
            border_color=("#3B8ED0", "#1F6AA5")
        )
        self.theme_light_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # 始终深色按钮
        self.theme_dark_btn = ctk.CTkButton(
            self.theme_options_frame,
            text=self.language_manager.get_text("theme_dark", "始终深色"),
            height=40,
            font=get_font(size=14),
            command=lambda: self._on_theme_select("dark"),
            fg_color="#3B8ED0" if current_theme == "dark" else "transparent",
            text_color="white" if current_theme == "dark" else ("black", "white"),
            hover_color="#36719F" if current_theme == "dark" else ("gray85", "gray25"),
            border_width=0 if current_theme == "dark" else 2,
            border_color=("#3B8ED0", "#1F6AA5")
        )
        self.theme_dark_btn.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        # 系统主题显示（仅当跟随系统时显示）
        if current_theme == "system":
            system_theme = self.app.theme_manager.get_system_theme()
            system_theme_text = self._get_system_theme_display_name(system_theme)
            
            self.system_theme_label = ctk.CTkLabel(
                self.theme_frame,
                text=self.language_manager.get_text("system_theme", "系统主题") + f": {system_theme_text}",
                font=get_font(size=12),
                text_color="gray"
            )
            self.system_theme_label.grid(row=4, column=0, padx=10, pady=(10, 10), sticky="w")
    
    def _get_theme_display_name(self, theme: str) -> str:
        """获取主题显示名称"""
        theme_names = {
            "system": self.language_manager.get_text("theme_system", "跟随系统"),
            "light": self.language_manager.get_text("theme_light", "始终浅色"),
            "dark": self.language_manager.get_text("theme_dark", "始终深色")
        }
        return theme_names.get(theme, theme)
    
    def _get_system_theme_display_name(self, theme: str) -> str:
        """获取系统主题显示名称"""
        theme_names = {
            "light": self.language_manager.get_text("theme_light", "浅色"),
            "dark": self.language_manager.get_text("theme_dark", "深色")
        }
        return theme_names.get(theme, theme)
    
    def _on_theme_select(self, theme: str):
        """选择主题"""
        # 更新按钮状态
        themes = ["system", "light", "dark"]
        buttons = [self.theme_system_btn, self.theme_light_btn, self.theme_dark_btn]
        
        for t, btn in zip(themes, buttons):
            is_selected = t == theme
            btn.configure(
                fg_color="#3B8ED0" if is_selected else "transparent",
                text_color="white" if is_selected else ("black", "white"),
                hover_color="#36719F" if is_selected else ("gray85", "gray25"),
                border_width=0 if is_selected else 2,
                border_color=("#3B8ED0", "#1F6AA5")
            )
        
        # 更新当前主题显示
        current_theme_text = self._get_theme_display_name(theme)
        self.current_theme_label.configure(
            text=self.language_manager.get_text("current_theme", "当前主题") + f": {current_theme_text}"
        )
        
        # 更新系统主题显示
        if theme == "system":
            system_theme = self.app.theme_manager.get_system_theme()
            system_theme_text = self._get_system_theme_display_name(system_theme)
            
            if hasattr(self, 'system_theme_label'):
                self.system_theme_label.configure(
                    text=self.language_manager.get_text("system_theme", "系统主题") + f": {system_theme_text}"
                )
                self.system_theme_label.grid(row=4, column=0, padx=10, pady=(10, 10), sticky="w")
        elif hasattr(self, 'system_theme_label'):
            self.system_theme_label.grid_forget()
        
        # 切换主题
        self.app.switch_theme(theme)
    
    def _create_thread_section(self):
        """创建线程设置区域"""
        self.thread_frame = ctk.CTkFrame(self.content_frame)
        self.thread_frame.grid(row=2, column=0, padx=5, pady=10, sticky="ew")
        self.thread_frame.grid_columnconfigure(0, weight=1)
        
        # 区域标题
        self.thread_title = ctk.CTkLabel(
            self.thread_frame,
            text=self.language_manager.get_text("thread_settings", "线程设置"),
            font=get_font(size=16, weight="bold")
        )
        self.thread_title.grid(row=0, column=0, padx=10, pady=(10, 15), sticky="w")
        
        # 线程数说明
        self.thread_hint = ctk.CTkLabel(
            self.thread_frame,
            text=self.language_manager.get_text("thread_hint", "设置扫描和同步时使用的线程数，范围 2-8"),
            font=get_font(size=12),
            text_color="gray"
        )
        self.thread_hint.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")
        
        # 扫描线程数区域
        self.scan_thread_frame = ctk.CTkFrame(self.thread_frame)
        self.scan_thread_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.scan_thread_frame.grid_columnconfigure(0, weight=1)
        
        current_scan_threads = self.settings.get("scan_workers", self.settings.get("max_workers", 4))
        self.scan_threads_label = ctk.CTkLabel(
            self.scan_thread_frame,
            text=self.language_manager.get_text("scan_workers", "扫描线程数") + f": {current_scan_threads}",
            font=get_font(size=13),
            text_color=("#3B8ED0", "#1F6AA5")
        )
        self.scan_threads_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.scan_thread_slider = ctk.CTkSlider(
            self.scan_thread_frame,
            from_=2,
            to=8,
            number_of_steps=6,
            command=self._on_scan_thread_slider_change
        )
        self.scan_thread_slider.set(current_scan_threads)
        self.scan_thread_slider.grid(row=1, column=0, padx=20, pady=(0, 5), sticky="ew")
        
        self.scan_thread_value_label = ctk.CTkLabel(
            self.scan_thread_frame,
            text=self.language_manager.format_text("thread_count", count=current_scan_threads),
            font=get_font(size=14, weight="bold")
        )
        self.scan_thread_value_label.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="w")
        
        # 同步线程数区域
        self.sync_thread_frame = ctk.CTkFrame(self.thread_frame)
        self.sync_thread_frame.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.sync_thread_frame.grid_columnconfigure(0, weight=1)
        
        current_sync_threads = self.settings.get("sync_workers", max(2, self.settings.get("max_workers", 4) // 2))
        self.sync_threads_label = ctk.CTkLabel(
            self.sync_thread_frame,
            text=self.language_manager.get_text("sync_workers", "同步线程数") + f": {current_sync_threads}",
            font=get_font(size=13),
            text_color=("#3B8ED0", "#1F6AA5")
        )
        self.sync_threads_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.sync_thread_slider = ctk.CTkSlider(
            self.sync_thread_frame,
            from_=2,
            to=8,
            number_of_steps=6,
            command=self._on_sync_thread_slider_change
        )
        self.sync_thread_slider.set(current_sync_threads)
        self.sync_thread_slider.grid(row=1, column=0, padx=20, pady=(0, 5), sticky="ew")
        
        self.sync_thread_value_label = ctk.CTkLabel(
            self.sync_thread_frame,
            text=self.language_manager.format_text("thread_count", count=current_sync_threads),
            font=get_font(size=14, weight="bold")
        )
        self.sync_thread_value_label.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="w")
    
    def _on_scan_thread_slider_change(self, value):
        """扫描线程数滑块变化事件"""
        threads = int(value)
        self.scan_thread_value_label.configure(
            text=self.language_manager.format_text("thread_count", count=threads)
        )
        self.scan_threads_label.configure(
            text=self.language_manager.get_text("scan_workers", "扫描线程数") + f": {threads}"
        )
        self.settings["scan_workers"] = threads
        self.config_manager.update_settings(self.settings)
        
        # 如果有正在运行的同步任务，更新引擎配置
        self._update_running_sync_engine()
    
    def _on_sync_thread_slider_change(self, value):
        """同步线程数滑块变化事件"""
        threads = int(value)
        self.sync_thread_value_label.configure(
            text=self.language_manager.format_text("thread_count", count=threads)
        )
        self.sync_threads_label.configure(
            text=self.language_manager.get_text("sync_workers", "同步线程数") + f": {threads}"
        )
        self.settings["sync_workers"] = threads
        self.config_manager.update_settings(self.settings)
        
        # 如果有正在运行的同步任务，更新引擎配置
        self._update_running_sync_engine()
    
    def _create_life_protection_section(self):
        """创建寿命保护设置区域"""
        self.life_protection_frame = ctk.CTkFrame(self.content_frame)
        self.life_protection_frame.grid(row=3, column=0, padx=5, pady=10, sticky="ew")
        self.life_protection_frame.grid_columnconfigure(0, weight=1)
        
        # 区域标题
        self.life_protection_title = ctk.CTkLabel(
            self.life_protection_frame,
            text=self.language_manager.get_text("life_protection", "写入寿命保护"),
            font=get_font(size=16, weight="bold")
        )
        self.life_protection_title.grid(row=0, column=0, padx=10, pady=(10, 15), sticky="w")
        
        # 启用开关
        self.life_protection_enabled = self.settings.get("life_protection_enabled", True)
        self.life_protection_switch = ctk.CTkSwitch(
            self.life_protection_frame,
            text=self.language_manager.get_text("enable_life_protection", "启用寿命保护"),
            command=self._on_life_protection_switch_change,
            switch_width=60,
            switch_height=30
        )
        self.life_protection_switch.select() if self.life_protection_enabled else self.life_protection_switch.deselect()
        self.life_protection_switch.grid(row=1, column=0, padx=10, pady=(0, 15), sticky="w")
        
        # U盘档位设置
        self.usb_level_frame = ctk.CTkFrame(self.life_protection_frame)
        self.usb_level_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.usb_level_frame.grid_columnconfigure(0, weight=1)
        
        self.usb_level_label = ctk.CTkLabel(
            self.usb_level_frame,
            text=self.language_manager.get_text("usb_level", "U盘档位") + ":",
            font=get_font(size=13, weight="bold")
        )
        self.usb_level_label.grid(row=0, column=0, padx=10, pady=8, sticky="w")
        
        self.usb_level_var = ctk.StringVar(value=self.settings.get("usb_level", "medium"))
        self.usb_level_combobox = ctk.CTkComboBox(
            self.usb_level_frame,
            values=[name for _, name in self._get_usb_levels()],
            command=self._on_usb_level_change,
            variable=self.usb_level_var
        )
        self.usb_level_combobox.grid(row=1, column=0, padx=10, pady=8, sticky="ew")
        
        # 保护强度设置
        self.protection_strength_frame = ctk.CTkFrame(self.life_protection_frame)
        self.protection_strength_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        self.protection_strength_frame.grid_columnconfigure(0, weight=1)
        
        self.protection_strength_label = ctk.CTkLabel(
            self.protection_strength_frame,
            text=self.language_manager.get_text("protection_strength", "保护强度") + ":",
            font=get_font(size=13, weight="bold")
        )
        self.protection_strength_label.grid(row=0, column=0, padx=10, pady=8, sticky="w")
        
        self.protection_strength_var = ctk.StringVar(value=self.settings.get("protection_strength", "balanced"))
        self.protection_strength_combobox = ctk.CTkComboBox(
            self.protection_strength_frame,
            values=[name for _, name in self._get_protection_strengths()],
            command=self._on_protection_strength_change,
            variable=self.protection_strength_var
        )
        self.protection_strength_combobox.grid(row=1, column=0, padx=10, pady=8, sticky="ew")
    
    def _on_life_protection_switch_change(self):
        """寿命保护开关变化事件"""
        self.life_protection_enabled = self.life_protection_switch.get()
        self.settings["life_protection_enabled"] = self.life_protection_enabled
        self.config_manager.update_settings(self.settings)
        
        # 如果有正在运行的同步任务，更新引擎配置
        self._update_running_sync_engine()
    
    def _on_usb_level_change(self, value):
        """U盘档位变化事件"""
        for key, name in self._get_usb_levels():
            if name == value:
                self.settings["usb_level"] = key
                break
        self.config_manager.update_settings(self.settings)
        
        # 如果有正在运行的同步任务，更新引擎配置
        self._update_running_sync_engine()
    
    def _on_protection_strength_change(self, value):
        """保护强度变化事件"""
        for key, name in self._get_protection_strengths():
            if name == value:
                self.settings["protection_strength"] = key
                break
        self.config_manager.update_settings(self.settings)
        
        # 如果有正在运行的同步任务，更新引擎配置
        self._update_running_sync_engine()
    
    def _update_running_sync_engine(self):
        """更新正在运行的同步引擎配置"""
        sync_progress_page = self.app.pages.get("sync_progress")
        if sync_progress_page and sync_progress_page.sync_engine:
            sync_progress_page.sync_engine.update_life_protection_config(
                enabled=self.settings.get("life_protection_enabled", True),
                usb_level=self.settings.get("usb_level", "medium"),
                protection_strength=self.settings.get("protection_strength", "balanced")
            )
    
    def _create_sync_delete_section(self):
        """创建同步删除和回收站设置区域"""
        self.sync_delete_frame = ctk.CTkFrame(self.content_frame)
        self.sync_delete_frame.grid(row=4, column=0, padx=5, pady=10, sticky="ew")
        self.sync_delete_frame.grid_columnconfigure(0, weight=1)
        
        # 区域标题
        self.sync_delete_title = ctk.CTkLabel(
            self.sync_delete_frame,
            text=self.language_manager.get_text("sync_delete_settings", "同步删除设置"),
            font=get_font(size=16, weight="bold")
        )
        self.sync_delete_title.grid(row=0, column=0, padx=10, pady=(10, 15), sticky="w")
        
        # 最近删除上限设置
        self.recycle_limit_frame = ctk.CTkFrame(self.sync_delete_frame)
        self.recycle_limit_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.recycle_limit_frame.grid_columnconfigure(0, weight=1)
        
        self.recycle_limit_label = ctk.CTkLabel(
            self.recycle_limit_frame,
            text=self.language_manager.get_text("recycle_limit", "最近删除上限") + ":",
            font=get_font(size=13, weight="bold")
        )
        self.recycle_limit_label.grid(row=0, column=0, padx=10, pady=8, sticky="w")
        
        self.recycle_limit_hint = ctk.CTkLabel(
            self.recycle_limit_frame,
            text=self.language_manager.get_text("recycle_limit_hint", "设置最近删除文件夹的最大容量，达到上限时将提示清理"),
            font=get_font(size=12),
            text_color="gray"
        )
        self.recycle_limit_hint.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")
        
        # 输入框和单位标签
        self.recycle_limit_input_frame = ctk.CTkFrame(self.recycle_limit_frame)
        self.recycle_limit_input_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.recycle_limit_input_frame.grid_columnconfigure(0, weight=1)
        self.recycle_limit_input_frame.grid_columnconfigure(1, weight=0)
        
        current_limit_gb = self.settings.get("recycle_limit_gb", 5.0)
        self.recycle_limit_entry = ctk.CTkEntry(
            self.recycle_limit_input_frame,
            placeholder_text="5.0",
            font=get_font(size=14)
        )
        self.recycle_limit_entry.insert(0, str(current_limit_gb))
        self.recycle_limit_entry.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="ew")
        
        self.recycle_limit_unit_label = ctk.CTkLabel(
            self.recycle_limit_input_frame,
            text="GB",
            font=get_font(size=14, weight="bold")
        )
        self.recycle_limit_unit_label.grid(row=0, column=1, padx=0, pady=5, sticky="w")
        
        self.recycle_limit_save_btn = ctk.CTkButton(
            self.recycle_limit_frame,
            text=self.language_manager.get_text("save", "保存"),
            font=get_font(size=13),
            command=self._on_recycle_limit_save
        )
        self.recycle_limit_save_btn.grid(row=3, column=0, padx=10, pady=(0, 15), sticky="w")
        
        # 同步删除默认状态设置
        self.sync_delete_default_frame = ctk.CTkFrame(self.sync_delete_frame)
        self.sync_delete_default_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.sync_delete_default_frame.grid_columnconfigure(0, weight=1)
        
        self.sync_delete_default_label = ctk.CTkLabel(
            self.sync_delete_default_frame,
            text=self.language_manager.get_text("sync_delete_default", "同步删除默认状态") + ":",
            font=get_font(size=13, weight="bold")
        )
        self.sync_delete_default_label.grid(row=0, column=0, padx=10, pady=8, sticky="w")
        
        self.sync_delete_default_hint = ctk.CTkLabel(
            self.sync_delete_default_frame,
            text=self.language_manager.get_text("sync_delete_default_hint", "设置同步删除功能的默认开启状态，可在同步确认界面临时修改"),
            font=get_font(size=12),
            text_color="gray"
        )
        self.sync_delete_default_hint.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")
        
        self.sync_delete_default_enabled = self.settings.get("sync_delete_default", False)
        self.sync_delete_default_switch = ctk.CTkSwitch(
            self.sync_delete_default_frame,
            text=self.language_manager.get_text("enable_sync_delete_default", "默认开启同步删除"),
            command=self._on_sync_delete_default_switch_change,
            switch_width=60,
            switch_height=30
        )
        self.sync_delete_default_switch.select() if self.sync_delete_default_enabled else self.sync_delete_default_switch.deselect()
        self.sync_delete_default_switch.grid(row=2, column=0, padx=10, pady=(0, 15), sticky="w")
    
    def _on_recycle_limit_save(self):
        """保存最近删除上限设置"""
        try:
            limit_gb = float(self.recycle_limit_entry.get())
            if limit_gb <= 0:
                raise ValueError("必须大于0")
            
            self.settings["recycle_limit_gb"] = limit_gb
            self.settings["recycle_limit_mb"] = int(limit_gb * 1024)
            self.config_manager.update_settings(self.settings)
            
            if self.app.recycle_manager:
                self.app.recycle_manager.set_limit_gb(limit_gb)
            
            self.recycle_limit_save_btn.configure(
                text=self.language_manager.get_text("saved", "已保存")
            )
        except ValueError as e:
            self.recycle_limit_save_btn.configure(
                text=f"{self.language_manager.get_text('save', '保存')} ({e})"
            )
    
    def _on_sync_delete_default_switch_change(self):
        """同步删除默认状态开关变化事件"""
        self.sync_delete_default_enabled = self.sync_delete_default_switch.get()
        self.settings["sync_delete_default"] = self.sync_delete_default_enabled
        self.config_manager.update_settings(self.settings)
    
    # ===================== v7.5: 配置存储路径 =====================
    
    def _create_config_path_section(self):
        """创建配置存储路径设置区域"""
        self.config_path_frame = ctk.CTkFrame(self.content_frame)
        self.config_path_frame.grid(row=5, column=0, padx=5, pady=10, sticky="ew")
        self.config_path_frame.grid_columnconfigure(0, weight=1)
        
        self.config_path_title = ctk.CTkLabel(
            self.config_path_frame,
            text=self.language_manager.get_text("config_path_settings", "配置存储路径"),
            font=get_font(size=16, weight="bold")
        )
        self.config_path_title.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.config_path_hint = ctk.CTkLabel(
            self.config_path_frame,
            text=self.language_manager.get_text(
                "config_path_hint",
                "自定义配置文件的存储目录，修改后需重启程序生效"
            ),
            font=get_font(size=12),
            text_color="gray",
            wraplength=600
        )
        self.config_path_hint.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")
        
        current_path = self.config_manager.get_config_dir()
        self.config_path_entry = ctk.CTkEntry(
            self.config_path_frame,
            font=get_font(size=13)
        )
        self.config_path_entry.insert(0, current_path)
        self.config_path_entry.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        self.config_path_btn_frame = ctk.CTkFrame(self.config_path_frame, fg_color="transparent")
        self.config_path_btn_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        
        self.config_path_browse_btn = ctk.CTkButton(
            self.config_path_btn_frame,
            text=self.language_manager.get_text("browse", "浏览..."),
            font=get_font(size=13),
            command=self._on_config_path_browse
        )
        self.config_path_browse_btn.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
        
        self.config_path_save_btn = ctk.CTkButton(
            self.config_path_btn_frame,
            text=self.language_manager.get_text("save", "保存"),
            font=get_font(size=13),
            command=self._on_config_path_save
        )
        self.config_path_save_btn.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        
        self.config_path_reset_btn = ctk.CTkButton(
            self.config_path_btn_frame,
            text=self.language_manager.get_text("restore_default", "恢复默认"),
            font=get_font(size=13),
            command=self._on_config_path_reset
        )
        self.config_path_reset_btn.grid(row=0, column=2, padx=10, pady=5, sticky="w")
    
    def _on_config_path_browse(self):
        """浏览选择配置目录"""
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        selected = filedialog.askdirectory(
            title=self.language_manager.get_text("select_config_dir", "选择配置存储目录")
        )
        root.destroy()
        if selected:
            self.config_path_entry.delete(0, "end")
            self.config_path_entry.insert(0, selected)
    
    def _on_config_path_save(self):
        """保存配置路径"""
        path = self.config_path_entry.get().strip()
        if not path:
            return
        success = self.config_manager.set_custom_config_dir(path)
        if success:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(
                self.language_manager.get_text("config_path_settings", "配置存储路径"),
                self.language_manager.get_text(
                    "config_path_saved",
                    "配置路径已保存，请重启程序以使用新路径。"
                )
            )
            root.destroy()
        else:
            self.config_path_save_btn.configure(
                text=self.language_manager.get_text("save_failed", "保存失败")
            )
    
    def _on_config_path_reset(self):
        """恢复默认配置路径"""
        self.config_manager.reset_config_dir_to_default()
        self.config_path_entry.delete(0, "end")
        self.config_path_entry.insert(0, self.config_manager.get_config_dir())
    
    # ===================== v7.5: 任务导入导出 =====================
    
    def _create_task_import_export_section(self):
        """创建任务导入导出区域"""
        self.import_export_frame = ctk.CTkFrame(self.content_frame)
        self.import_export_frame.grid(row=6, column=0, padx=5, pady=10, sticky="ew")
        self.import_export_frame.grid_columnconfigure(0, weight=1)
        
        self.import_export_title = ctk.CTkLabel(
            self.import_export_frame,
            text=self.language_manager.get_text("task_import_export", "任务导入导出"),
            font=get_font(size=16, weight="bold")
        )
        self.import_export_title.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.import_export_hint = ctk.CTkLabel(
            self.import_export_frame,
            text=self.language_manager.get_text(
                "task_import_export_hint",
                "将任务导出为 JSON 配置文件，可在另一台电脑导入恢复"
            ),
            font=get_font(size=12),
            text_color="gray",
            wraplength=600
        )
        self.import_export_hint.grid(row=1, column=0, padx=10, pady=(0, 15), sticky="w")
        
        self.import_export_btn_frame = ctk.CTkFrame(self.import_export_frame, fg_color="transparent")
        self.import_export_btn_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        self.export_all_btn = ctk.CTkButton(
            self.import_export_btn_frame,
            text=self.language_manager.get_text("export_all_tasks", "导出所有任务"),
            font=get_font(size=14),
            height=40,
            command=self._on_export_all_tasks
        )
        self.export_all_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        self.import_tasks_btn = ctk.CTkButton(
            self.import_export_btn_frame,
            text=self.language_manager.get_text("import_tasks", "导入任务"),
            font=get_font(size=14),
            height=40,
            fg_color=("#2E7D32", "#2E7D32"),
            hover_color=("#1B5E20", "#1B5E20"),
            command=self._on_import_tasks
        )
        self.import_tasks_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # v7.5.1: 提示可在任务配置页多选任务导出
        self.multi_export_hint_label = ctk.CTkLabel(
            self.import_export_frame,
            text=self.language_manager.get_text(
                "multi_export_hint",
                "提示：如需只导出部分任务，请到「任务配置」页多选后导出"
            ),
            font=get_font(size=12),
            text_color="gray",
            wraplength=600
        )
        self.multi_export_hint_label.grid(row=3, column=0, padx=10, pady=(5, 10), sticky="w")
    
    def _on_export_all_tasks(self):
        """导出所有任务"""
        import tkinter as tk
        from tkinter import filedialog, messagebox
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.asksaveasfilename(
            title=self.language_manager.get_text("export_all_tasks", "导出所有任务"),
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        root.destroy()
        if not file_path:
            return
        success = self.app.task_manager.export_all_tasks(file_path)
        root = tk.Tk()
        root.withdraw()
        if success:
            messagebox.showinfo(
                self.language_manager.get_text("export_all_tasks", "导出所有任务"),
                self.language_manager.get_text("export_success", "任务导出成功")
            )
        else:
            messagebox.showerror(
                self.language_manager.get_text("export_all_tasks", "导出所有任务"),
                self.language_manager.get_text("export_failed", "任务导出失败")
            )
        root.destroy()
    
    def _on_import_tasks(self):
        """导入任务"""
        import tkinter as tk
        from tkinter import filedialog, messagebox
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            title=self.language_manager.get_text("import_tasks", "导入任务"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        root.destroy()
        if not file_path:
            return
        result = self.app.task_manager.import_tasks(file_path)
        root = tk.Tk()
        root.withdraw()
        if result["success"]:
            messagebox.showinfo(
                self.language_manager.get_text("import_tasks", "导入任务"),
                result["message"]
            )
        else:
            messagebox.showerror(
                self.language_manager.get_text("import_tasks", "导入任务"),
                result["message"]
            )
        root.destroy()
    
    def _on_back_click(self):
        """返回首页按钮点击事件"""
        self.app.show_page("home")
    
    def _on_reset_config_click(self):
        """恢复默认配置按钮点击事件"""
        import tkinter as tk
        from tkinter import messagebox
        
        # 确认对话框
        confirm_msg = self.language_manager.get_text(
            "restore_default_config_confirm",
            "确定要恢复所有配置为默认值吗？\n\n"
            "• 所有任务配置将被清除\n"
            "• 所有设置将恢复为默认值\n"
            "• 同步历史和打断任务记录将被清除\n\n"
            "此操作不可撤销，恢复后需要重启程序。"
        )
        
        root = tk.Tk()
        root.withdraw()
        result = messagebox.askyesno(
            self.language_manager.get_text("restore_default_config", "恢复默认配置"),
            confirm_msg,
            icon=messagebox.WARNING,
            default=messagebox.NO
        )
        root.destroy()
        
        if not result:
            return
        
        try:
            # 重置配置为默认值
            self.config_manager.reset_to_default()
            
            # 提示重启
            root = tk.Tk()
            root.withdraw()
            restart_msg = self.language_manager.get_text(
                "restore_default_config_done",
                "配置已恢复为默认值。\n\n请重启程序以使更改完全生效。"
            )
            messagebox.showinfo(
                self.language_manager.get_text("restore_default_config", "恢复默认配置"),
                restart_msg
            )
            root.destroy()
            
            # 退出程序（用户需手动重启）
            self.app.destroy()
            
        except Exception as e:
            # 错误反馈
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                self.language_manager.get_text("restore_default_config", "恢复默认配置"),
                f"恢复默认配置失败：\n{str(e)}"
            )
            root.destroy()
    
    def refresh(self):
        """刷新页面"""
        self._create_widgets()
    
    def update_language(self):
        """更新界面语言"""
        # 更新标题
        self.title_label.configure(
            text=self.language_manager.get_text("settings", "设置")
        )

        # v7.5.1: 更新语言设置区域（重新扫描语言文件与当前选中项）
        if hasattr(self, "language_title"):
            self.language_title.configure(
                text=self.language_manager.get_text("language_settings", "语言设置")
            )
            self.language_hint.configure(
                text=self.language_manager.get_text(
                    "language_hint", "选择界面显示语言，切换后立即生效"
                )
            )
            self._language_options = self.language_manager.get_language_options()
            self.language_combobox.configure(
                values=[display for _, display, _ in self._language_options]
            )
            self.language_var.set(
                self._get_language_display(self.language_manager.get_language())
            )
        
        # 更新主题区域
        self.theme_title.configure(
            text=self.language_manager.get_text("theme_settings", "主题设置")
        )
        self.theme_hint.configure(
            text=self.language_manager.get_text("theme_hint", "选择界面主题")
        )
        
        # 更新主题按钮
        self.theme_system_btn.configure(
            text=self.language_manager.get_text("theme_system", "跟随系统")
        )
        self.theme_light_btn.configure(
            text=self.language_manager.get_text("theme_light", "始终浅色")
        )
        self.theme_dark_btn.configure(
            text=self.language_manager.get_text("theme_dark", "始终深色")
        )
        
        # 更新线程设置区域
        if hasattr(self, 'thread_title'):
            self.thread_title.configure(
                text=self.language_manager.get_text("thread_settings", "线程设置")
            )
            self.thread_hint.configure(
                text=self.language_manager.get_text("thread_hint", "设置扫描和同步时使用的线程数，范围 2-8")
            )
            current_scan_threads = self.settings.get("scan_workers", self.settings.get("max_workers", 4))
            current_sync_threads = self.settings.get("sync_workers", max(2, self.settings.get("max_workers", 4) // 2))
            self.scan_threads_label.configure(
                text=self.language_manager.get_text("scan_workers", "扫描线程数") + f": {current_scan_threads}"
            )
            self.sync_threads_label.configure(
                text=self.language_manager.get_text("sync_workers", "同步线程数") + f": {current_sync_threads}"
            )
        
        # 更新寿命保护区域
        if hasattr(self, 'life_protection_title'):
            self.life_protection_title.configure(
                text=self.language_manager.get_text("life_protection", "写入寿命保护")
            )
            self.life_protection_switch.configure(
                text=self.language_manager.get_text("enable_life_protection", "启用寿命保护")
            )
            self.usb_level_label.configure(
                text=self.language_manager.get_text("usb_level", "U盘档位") + ":"
            )
            self.protection_strength_label.configure(
                text=self.language_manager.get_text("protection_strength", "保护强度") + ":"
            )
            
            # 更新U盘档位下拉框
            current_usb_level = self.settings.get("usb_level", "medium")
            self.usb_level_combobox.configure(
                values=[name for _, name in self._get_usb_levels()]
            )
            self.usb_level_var.set(current_usb_level)
            
            # 更新保护强度下拉框
            current_strength = self.settings.get("protection_strength", "balanced")
            self.protection_strength_combobox.configure(
                values=[name for _, name in self._get_protection_strengths()]
            )
            self.protection_strength_var.set(current_strength)
        
        # 更新同步删除和回收站设置区域
        if hasattr(self, 'sync_delete_title'):
            self.sync_delete_title.configure(
                text=self.language_manager.get_text("sync_delete_settings", "同步删除设置")
            )
        if hasattr(self, 'recycle_limit_label'):
            self.recycle_limit_label.configure(
                text=self.language_manager.get_text("recycle_limit", "最近删除上限") + ":"
            )
            self.recycle_limit_hint.configure(
                text=self.language_manager.get_text("recycle_limit_hint", "设置最近删除文件夹的最大容量，达到上限时将提示清理")
            )
            self.recycle_limit_save_btn.configure(
                text=self.language_manager.get_text("save", "保存")
            )
        if hasattr(self, 'sync_delete_default_label'):
            self.sync_delete_default_label.configure(
                text=self.language_manager.get_text("sync_delete_default", "同步删除默认状态") + ":"
            )
            self.sync_delete_default_hint.configure(
                text=self.language_manager.get_text("sync_delete_default_hint", "设置同步删除功能的默认开启状态，可在同步确认界面临时修改")
            )
            self.sync_delete_default_switch.configure(
                text=self.language_manager.get_text("enable_sync_delete_default", "默认开启同步删除")
            )
        
        # 更新底部按钮
        self.reset_btn.configure(
            text=self.language_manager.get_text("restore_default_config", "恢复默认配置")
        )
        self.back_btn.configure(
            text=self.language_manager.get_text("return_home", "返回首页")
        )