"""
文件同步工具 - 设置页面
左侧导航 + 右侧内容区 + 顶部搜索框，设置项按分类拆分到独立 Frame
"""

import customtkinter as ctk
from pathlib import Path
from backend.language_manager import get_font
from typing import TYPE_CHECKING, List, Tuple, Union

if TYPE_CHECKING:
    from .app import FileSyncApp


# 搜索项：([关键字...], 控件 或 控件列表)
SearchWidgets = Union[ctk.CTkFrame, List[ctk.CTkFrame]]


class _SettingsSection(ctk.CTkFrame):
    """设置分区基类：持有 page 引用，并把共享状态代理到 page"""

    def __init__(self, master, page: "SettingsPage"):
        super().__init__(master)
        self.page = page
        # 搜索元组列表：([关键字], 控件或控件列表)，由 SettingsPage 遍历过滤
        self.search_items: List[Tuple[List[str], List[ctk.CTkFrame]]] = []
        self._row_index = 0
        self.grid_columnconfigure(0, weight=1)

    # ===================== 共享状态代理 =====================

    @property
    def app(self):
        return self.page.app

    @property
    def language_manager(self):
        return self.page.language_manager

    @property
    def config_manager(self):
        return self.page.config_manager

    @property
    def settings(self):
        """返回 page.settings 的同一个字典对象，直接下标赋值仍然生效"""
        return self.page.settings

    # ===================== 搜索支持 =====================

    def register_search(self, keywords: List[str], widgets: SearchWidgets):
        """
        登记一个可搜索项。

        除调用方手写的同义词外，还会在登记时一次性递归收集控件子树中的
        全部可见文本（标签、按钮、开关、输入框占位符等），
        这样用户直接输入界面上看到的关键字（如“多线程”）也能命中。
        """
        if not isinstance(widgets, (list, tuple)):
            widgets = [widgets]
        widget_list = list(widgets)
        collected = [str(k) for k in keywords]
        for widget in widget_list:
            collected.extend(self._collect_widget_texts(widget))
        # 去重并统一转小写做子串匹配
        normalized = []
        for text in collected:
            lowered = str(text).strip().lower()
            if lowered and lowered not in normalized:
                normalized.append(lowered)
        self.search_items.append((normalized, widget_list))

    @classmethod
    def _collect_widget_texts(cls, widget) -> List[str]:
        """一次性收集控件及其子控件的文本（仅在登记搜索项时调用）"""
        texts: List[str] = []
        stack = [widget]
        while stack:
            current = stack.pop()
            for option in ("text", "placeholder_text"):
                try:
                    value = current.cget(option)
                except Exception:
                    continue
                if isinstance(value, str) and value.strip():
                    texts.append(value)
            try:
                stack.extend(current.winfo_children())
            except Exception:
                continue
        return texts

    def filter_search(self, needle: str) -> int:
        """
        按关键字过滤本分区的设置项（跨分类全局搜索由 SettingsPage 遍历所有分区调用）。

        Returns:
            本分区命中的设置项数量；命中项显示、未命中项隐藏。
        """
        hit_count = 0
        terms = [term for term in needle.split() if term]
        if not terms:
            terms = [needle]
        for keywords, widgets in self.search_items:
            # 多词查询：所有词都能在同一个设置项的文本中找到才算命中
            matched = all(
                any(term in keyword for keyword in keywords) for term in terms
            )
            for widget in widgets:
                if matched:
                    widget.grid()
                else:
                    widget.grid_remove()
            if matched:
                hit_count += 1
        return hit_count

    def restore_all_items(self):
        """恢复本分区内全部已登记控件的显示（清空搜索时使用）"""
        for _keywords, widgets in self.search_items:
            for widget in widgets:
                widget.grid()

    # ===================== 布局辅助 =====================

    def _next_row(self) -> int:
        row = self._row_index
        self._row_index += 1
        return row

    def _create_card(self) -> ctk.CTkFrame:
        """创建一个纵向排列的设置卡片"""
        card = ctk.CTkFrame(self)
        card.grid(row=self._next_row(), column=0, padx=5, pady=10, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        return card

    # ===================== 共用逻辑 =====================

    def _update_running_sync_engine(self):
        """更新正在运行的同步引擎配置"""
        sync_progress_page = self.app.pages.get("sync_progress")
        if sync_progress_page and sync_progress_page.sync_engine:
            sync_progress_page.sync_engine.update_life_protection_config(
                enabled=self.settings.get("life_protection_enabled", True),
                usb_level=self.settings.get("usb_level", "medium"),
                protection_strength=self.settings.get("protection_strength", "balanced")
            )


class BasicSettingsFrame(_SettingsSection):
    """基础设置：语言设置、主题设置、配置预设"""

    # v7.7: 配置预设 —— 键, 翻译键, 默认文案, 底层参数
    _PRESETS = [
        (
            "balanced", "settings_preset_balanced", "默认均衡模式",
            {
                "scan_workers": 4, "sync_workers": 2,
                "life_protection_enabled": True, "usb_level": "auto",
                "protection_strength": "balanced", "chunk_size_mb": 8,
                "prevent_sleep_during_sync": True,
            },
        ),
        (
            "performance", "settings_preset_performance", "极致性能模式",
            {
                "scan_workers": 8, "sync_workers": 4,
                "life_protection_enabled": False, "usb_level": "high",
                "protection_strength": "aggressive", "chunk_size_mb": 32,
                "prevent_sleep_during_sync": True,
            },
        ),
        (
            "eco", "settings_preset_eco", "省电/U盘保护模式",
            {
                "scan_workers": 2, "sync_workers": 1,
                "life_protection_enabled": True, "usb_level": "low",
                "protection_strength": "conservative", "chunk_size_mb": 4,
                "prevent_sleep_during_sync": True,
            },
        ),
    ]

    def __init__(self, master, page: "SettingsPage"):
        super().__init__(master, page)
        self._language_options = []
        self._theme_buttons = {}
        self._create_language_section()
        self._create_theme_section()
        self._create_preset_section()

    # ===================== 语言设置 =====================

    def _create_language_section(self):
        """创建语言设置区域（下拉框动态扫描 translations 目录下的语言文件）"""
        self.language_frame = self._create_card()

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

        self.register_search(
            ["语言", "language", "界面语言", "语言设置", "language settings"],
            self.language_frame
        )

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

    # ===================== 主题设置 =====================

    def _create_theme_section(self):
        """创建主题设置区域"""
        self.theme_frame = self._create_card()

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

        self.theme_system_btn = self._create_theme_button(
            "theme_system", "跟随系统", "system", 0
        )
        self.theme_light_btn = self._create_theme_button(
            "theme_light", "始终浅色", "light", 1
        )
        self.theme_dark_btn = self._create_theme_button(
            "theme_dark", "始终深色", "dark", 2
        )

        # 系统主题显示（仅当跟随系统时显示）
        self._update_system_theme_label(current_theme)

        self.register_search(
            ["主题", "theme", "外观", "主题设置", "appearance"],
            self.theme_frame
        )

    def _create_theme_button(self, text_key: str, default: str, theme: str, column: int) -> ctk.CTkButton:
        """创建单个主题选项按钮"""
        selected = self.app.theme_manager.get_user_theme() == theme
        button = ctk.CTkButton(
            self.theme_options_frame,
            text=self.language_manager.get_text(text_key, default),
            height=40,
            font=get_font(size=14),
            command=lambda: self._on_theme_select(theme)
        )
        self._style_theme_button(button, selected)
        button.grid(row=0, column=column, padx=5, pady=5, sticky="ew")
        self._theme_buttons[theme] = button
        return button

    def _style_theme_button(self, button: ctk.CTkButton, selected: bool):
        """按选中状态刷新主题按钮样式"""
        button.configure(
            fg_color="#3B8ED0" if selected else "transparent",
            text_color="white" if selected else ("black", "white"),
            hover_color="#36719F" if selected else ("gray85", "gray25"),
            border_width=0 if selected else 2,
            border_color=("#3B8ED0", "#1F6AA5")
        )

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

    def _update_system_theme_label(self, theme: str):
        """跟随系统时显示/更新系统主题，其余情况隐藏"""
        if theme == "system":
            system_theme = self.app.theme_manager.get_system_theme()
            system_theme_text = self._get_system_theme_display_name(system_theme)
            text = self.language_manager.get_text("system_theme", "系统主题") + f": {system_theme_text}"
            if not hasattr(self, "system_theme_label"):
                self.system_theme_label = ctk.CTkLabel(
                    self.theme_frame,
                    text=text,
                    font=get_font(size=12),
                    text_color="gray"
                )
            else:
                self.system_theme_label.configure(text=text)
            self.system_theme_label.grid(row=4, column=0, padx=10, pady=(10, 10), sticky="w")
        elif hasattr(self, "system_theme_label"):
            self.system_theme_label.grid_forget()

    def _on_theme_select(self, theme: str):
        """选择主题"""
        # 更新按钮状态
        for t, btn in self._theme_buttons.items():
            self._style_theme_button(btn, t == theme)

        # 更新当前主题显示
        current_theme_text = self._get_theme_display_name(theme)
        self.current_theme_label.configure(
            text=self.language_manager.get_text("current_theme", "当前主题") + f": {current_theme_text}"
        )

        # 更新系统主题显示
        self._update_system_theme_label(theme)

        # 切换主题（主窗口会调用本页 refresh 刷新按钮状态）
        self.app.switch_theme(theme)

    # ===================== v7.7: 配置预设 =====================

    def _get_preset_displays(self):
        """预设下拉框显示文案列表"""
        return [
            self.language_manager.get_text(key, default)
            for _key, key, default, _params in self._PRESETS
        ]

    def _create_preset_section(self):
        """配置预设：一键写入线程数、寿命保护等底层参数"""
        self.preset_frame = self._create_card()

        self.preset_title = ctk.CTkLabel(
            self.preset_frame,
            text=self.language_manager.get_text("settings_preset_title", "参数预设"),
            font=get_font(size=16, weight="bold")
        )
        self.preset_title.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.preset_hint = ctk.CTkLabel(
            self.preset_frame,
            text=self.language_manager.get_text(
                "settings_preset_hint",
                "选择一种参数预设并应用，自动写入线程数、寿命保护与分块大小等参数。",
            ),
            font=get_font(size=12),
            text_color="gray",
            wraplength=600,
            justify="left"
        )
        self.preset_hint.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="w")

        self.preset_row = ctk.CTkFrame(self.preset_frame, fg_color="transparent")
        self.preset_row.grid(row=2, column=0, padx=10, pady=(0, 12), sticky="ew")
        self.preset_row.grid_columnconfigure(0, weight=1)

        self.preset_combo = ctk.CTkComboBox(
            self.preset_row,
            values=self._get_preset_displays(),
            font=get_font(size=13),
            state="readonly",
        )
        self.preset_combo.set(self._get_preset_displays()[0])
        self.preset_combo.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.preset_apply_btn = ctk.CTkButton(
            self.preset_row,
            text=self.language_manager.get_text("settings_preset_apply", "应用预设"),
            font=get_font(size=13),
            width=120,
            command=self._on_apply_preset,
        )
        self.preset_apply_btn.grid(row=0, column=1, sticky="e")

        self.register_search(
            ["配置预设", "预设", "性能", "省电", "均衡", "u盘保护", "preset", "performance", "eco"],
            self.preset_frame
        )

    def _on_apply_preset(self):
        """应用当前选中的预设并保存到配置"""
        selection = self.preset_combo.get()
        preset = next(
            (item for item in self._PRESETS
             if self.language_manager.get_text(item[1], item[2]) == selection),
            None,
        )
        if not preset:
            return
        _key, name_key, default_name, params = preset
        display_name = self.language_manager.get_text(name_key, default_name)

        self.settings.update(params)
        self.config_manager.update_settings(self.settings)

        # 同步刷新本页控件，并更新正在运行的引擎参数
        try:
            self.page.refresh()
        except Exception:
            pass
        try:
            self._update_running_sync_engine()
        except Exception:
            pass

        from tkinter import messagebox
        messagebox.showinfo(
            self.language_manager.get_text("settings_preset_title", "配置预设"),
            self.language_manager.get_text(
                "settings_preset_applied",
                "已应用「{name}」，新的同步任务将使用该配置。",
            ).format(name=display_name),
        )

    # ===================== 刷新与语言 =====================

    def refresh(self):
        """刷新语言下拉框与主题按钮的当前值"""
        # 语言
        self._language_options = self.language_manager.get_language_options()
        self.language_combobox.configure(
            values=[display for _, display, _ in self._language_options]
        )
        self.language_var.set(
            self._get_language_display(self.language_manager.get_language())
        )

        # 主题
        current_theme = self.app.theme_manager.get_user_theme()
        for theme, btn in self._theme_buttons.items():
            self._style_theme_button(btn, theme == current_theme)
        self.current_theme_label.configure(
            text=self.language_manager.get_text("current_theme", "当前主题")
            + f": {self._get_theme_display_name(current_theme)}"
        )
        self._update_system_theme_label(current_theme)

        # v7.7: 配置预设下拉框（语言切换后刷新文案并保持选择）
        preset_displays = self._get_preset_displays()
        current_preset = self.preset_combo.get()
        self.preset_combo.configure(values=preset_displays)
        if current_preset not in preset_displays:
            self.preset_combo.set(preset_displays[0])

    def update_language(self):
        """更新界面语言"""
        # 语言设置区域（重新扫描语言文件与当前选中项）
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

        # 主题区域
        self.theme_title.configure(
            text=self.language_manager.get_text("theme_settings", "主题设置")
        )
        self.theme_hint.configure(
            text=self.language_manager.get_text("theme_hint", "选择界面主题")
        )
        self.theme_system_btn.configure(
            text=self.language_manager.get_text("theme_system", "跟随系统")
        )
        self.theme_light_btn.configure(
            text=self.language_manager.get_text("theme_light", "始终浅色")
        )
        self.theme_dark_btn.configure(
            text=self.language_manager.get_text("theme_dark", "始终深色")
        )
        current_theme = self.app.theme_manager.get_user_theme()
        self.current_theme_label.configure(
            text=self.language_manager.get_text("current_theme", "当前主题")
            + f": {self._get_theme_display_name(current_theme)}"
        )
        self._update_system_theme_label(current_theme)

        # v7.7: 配置预设区域
        self.preset_title.configure(
            text=self.language_manager.get_text("settings_preset_title", "参数预设")
        )
        self.preset_hint.configure(
            text=self.language_manager.get_text(
                "settings_preset_hint",
                "选择一种参数预设并应用，自动写入线程数、寿命保护与分块大小等参数。",
            )
        )
        self.preset_apply_btn.configure(
            text=self.language_manager.get_text("settings_preset_apply", "应用预设")
        )
        preset_displays = self._get_preset_displays()
        old_values = list(self.preset_combo.cget("values"))
        old_value = self.preset_combo.get()
        preset_index = old_values.index(old_value) if old_value in old_values else 0
        self.preset_combo.configure(values=preset_displays)
        self.preset_combo.set(preset_displays[min(preset_index, len(preset_displays) - 1)])


class SyncSettingsFrame(_SettingsSection):
    """同步与性能：线程设置、寿命保护、同步行为"""

    def __init__(self, master, page: "SettingsPage"):
        super().__init__(master, page)
        self._create_thread_section()
        self._create_life_protection_section()
        self._create_sync_behavior_section()

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

    # ===================== 线程设置 =====================

    def _create_thread_section(self):
        """创建线程设置区域"""
        self.thread_frame = self._create_card()

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

        self.register_search(
            ["线程", "thread", "线程数", "多线程", "多线程扫描", "扫描线程", "同步线程", "workers"],
            self.thread_frame
        )

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

    # ===================== 寿命保护 =====================

    def _create_life_protection_section(self):
        """创建寿命保护设置区域"""
        self.life_protection_frame = self._create_card()

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

        self.register_search(
            ["寿命", "写入保护", "寿命保护", "u盘档位", "usb", "保护强度", "life protection"],
            self.life_protection_frame
        )

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

    # ===================== 同步行为（阻止休眠） =====================

    def _create_sync_behavior_section(self):
        """v7.6：同步行为区域 —— 同步时阻止系统休眠"""
        self.sync_behavior_frame = self._create_card()

        self.sync_behavior_title = ctk.CTkLabel(
            self.sync_behavior_frame,
            text=self.language_manager.get_text("sync_behavior", "同步行为"),
            font=get_font(size=16, weight="bold")
        )
        self.sync_behavior_title.grid(row=0, column=0, padx=10, pady=(10, 10), sticky="w")

        self.prevent_sleep_enabled = self.settings.get("prevent_sleep_during_sync", True)
        self.prevent_sleep_switch = ctk.CTkSwitch(
            self.sync_behavior_frame,
            text=self.language_manager.get_text(
                "prevent_sleep_during_sync", "同步时阻止系统休眠"
            ),
            font=get_font(size=14),
            command=self._on_prevent_sleep_switch_change,
        )
        if self.prevent_sleep_enabled:
            self.prevent_sleep_switch.select()
        else:
            self.prevent_sleep_switch.deselect()
        self.prevent_sleep_switch.grid(row=1, column=0, padx=10, pady=(0, 6), sticky="w")

        self.prevent_sleep_hint = ctk.CTkLabel(
            self.sync_behavior_frame,
            text=self.language_manager.get_text(
                "prevent_sleep_hint",
                "同步全过程（含寿命保护暂停期间）阻止电脑进入休眠；"
                "同步结束后自动恢复。同步结束（成功/失败/中断）后恢复系统休眠。",
            ),
            font=get_font(size=12),
            text_color="gray",
            wraplength=600,
            justify="left"
        )
        self.prevent_sleep_hint.grid(row=2, column=0, padx=10, pady=(0, 12), sticky="w")

        self.register_search(
            ["休眠", "阻止休眠", "sleep", "同步行为", "prevent sleep"],
            self.sync_behavior_frame
        )

    def _on_prevent_sleep_switch_change(self):
        """阻止系统休眠开关变化：写入设置"""
        self.prevent_sleep_enabled = bool(self.prevent_sleep_switch.get())
        self.settings["prevent_sleep_during_sync"] = self.prevent_sleep_enabled
        self.config_manager.update_settings(self.settings)

    # ===================== 刷新与语言 =====================

    def refresh(self):
        """刷新线程滑杆、寿命保护、同步行为的当前值"""
        # 线程设置
        current_scan_threads = self.settings.get("scan_workers", self.settings.get("max_workers", 4))
        current_sync_threads = self.settings.get("sync_workers", max(2, self.settings.get("max_workers", 4) // 2))
        self.scan_thread_slider.set(current_scan_threads)
        self.sync_thread_slider.set(current_sync_threads)
        self.scan_threads_label.configure(
            text=self.language_manager.get_text("scan_workers", "扫描线程数") + f": {current_scan_threads}"
        )
        self.sync_threads_label.configure(
            text=self.language_manager.get_text("sync_workers", "同步线程数") + f": {current_sync_threads}"
        )
        self.scan_thread_value_label.configure(
            text=self.language_manager.format_text("thread_count", count=current_scan_threads)
        )
        self.sync_thread_value_label.configure(
            text=self.language_manager.format_text("thread_count", count=current_sync_threads)
        )

        # 寿命保护
        self.life_protection_enabled = self.settings.get("life_protection_enabled", True)
        if self.life_protection_enabled:
            self.life_protection_switch.select()
        else:
            self.life_protection_switch.deselect()
        self.usb_level_var.set(self.settings.get("usb_level", "medium"))
        self.protection_strength_var.set(self.settings.get("protection_strength", "balanced"))

        # 同步行为
        self.prevent_sleep_enabled = bool(self.settings.get("prevent_sleep_during_sync", True))
        if self.prevent_sleep_enabled:
            self.prevent_sleep_switch.select()
        else:
            self.prevent_sleep_switch.deselect()

    def update_language(self):
        """更新界面语言"""
        # 线程设置区域
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
        self.scan_thread_value_label.configure(
            text=self.language_manager.format_text("thread_count", count=current_scan_threads)
        )
        self.sync_thread_value_label.configure(
            text=self.language_manager.format_text("thread_count", count=current_sync_threads)
        )

        # 寿命保护区域
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

        # 同步行为区域
        self.sync_behavior_title.configure(
            text=self.language_manager.get_text("sync_behavior", "同步行为")
        )
        self.prevent_sleep_switch.configure(
            text=self.language_manager.get_text(
                "prevent_sleep_during_sync", "同步时阻止系统休眠"
            )
        )
        self.prevent_sleep_hint.configure(
            text=self.language_manager.get_text(
                "prevent_sleep_hint",
                "同步全过程（含寿命保护暂停期间）阻止电脑进入休眠；"
                "同步结束后自动恢复。同步结束（成功/失败/中断）后恢复系统休眠。",
            )
        )


class UdiskSettingsFrame(_SettingsSection):
    """U 盘自动化：插入 U 盘时自动同步总开关"""

    def __init__(self, master, page: "SettingsPage"):
        super().__init__(master, page)
        self._create_usb_auto_sync_section()

    def _create_usb_auto_sync_section(self):
        """U 盘自动同步总开关区域"""
        self.usb_auto_sync_frame = self._create_card()

        self.usb_auto_sync_title = ctk.CTkLabel(
            self.usb_auto_sync_frame,
            text=self.language_manager.get_text(
                "usb_auto_sync_section", "插入 U 盘时自动同步"
            ),
            font=get_font(size=16, weight="bold")
        )
        self.usb_auto_sync_title.grid(row=0, column=0, padx=10, pady=(10, 10), sticky="w")

        self.usb_auto_sync_enabled = bool(
            self.settings.get("usb_auto_sync_enabled", True)
        )
        self.usb_auto_sync_switch = ctk.CTkSwitch(
            self.usb_auto_sync_frame,
            text=self.language_manager.get_text(
                "usb_auto_sync_switch", "插入 U 盘时自动同步"
            ),
            font=get_font(size=14),
            command=self._on_usb_auto_sync_switch_change,
        )
        if self.usb_auto_sync_enabled:
            self.usb_auto_sync_switch.select()
        else:
            self.usb_auto_sync_switch.deselect()
        self.usb_auto_sync_switch.grid(row=1, column=0, padx=10, pady=(0, 6), sticky="w")

        self.usb_auto_sync_hint = ctk.CTkLabel(
            self.usb_auto_sync_frame,
            text=self.language_manager.get_text(
                "usb_auto_sync_hint",
                "检测到已绑定的 U 盘插入后自动运行对应同步任务；关闭后不再监听。",
            ),
            font=get_font(size=12),
            text_color="gray",
            wraplength=600,
            justify="left"
        )
        self.usb_auto_sync_hint.grid(row=2, column=0, padx=10, pady=(0, 12), sticky="w")

        self.register_search(
            ["u盘", "usb", "自动同步", "插入u盘", "auto sync"],
            self.usb_auto_sync_frame
        )

    def _on_usb_auto_sync_switch_change(self):
        """总开关变化：写入设置并即时启停后台监听"""
        self.usb_auto_sync_enabled = bool(self.usb_auto_sync_switch.get())
        self.settings["usb_auto_sync_enabled"] = self.usb_auto_sync_enabled
        self.config_manager.update_settings(self.settings)
        try:
            self.app.apply_usb_auto_sync_setting()
        except Exception as exc:  # noqa: BLE001
            print(f"启停 U 盘监听失败: {exc}")

    # ===================== 刷新与语言 =====================

    def refresh(self):
        """刷新 U 盘自动同步开关的当前值"""
        self.usb_auto_sync_enabled = bool(self.settings.get("usb_auto_sync_enabled", True))
        if self.usb_auto_sync_enabled:
            self.usb_auto_sync_switch.select()
        else:
            self.usb_auto_sync_switch.deselect()

    def update_language(self):
        """更新界面语言"""
        self.usb_auto_sync_title.configure(
            text=self.language_manager.get_text(
                "usb_auto_sync_section", "插入 U 盘时自动同步"
            )
        )
        self.usb_auto_sync_switch.configure(
            text=self.language_manager.get_text(
                "usb_auto_sync_switch", "插入 U 盘时自动同步"
            )
        )
        self.usb_auto_sync_hint.configure(
            text=self.language_manager.get_text(
                "usb_auto_sync_hint",
                "检测到已绑定的 U 盘插入后自动运行对应同步任务；关闭后不再监听。",
            )
        )


class StorageSettingsFrame(_SettingsSection):
    """存储路径：配置存储路径、外挂语言目录"""

    def __init__(self, master, page: "SettingsPage"):
        super().__init__(master, page)
        self._create_config_path_section()
        self._create_external_language_section()

    # ===================== v7.5: 配置存储路径 =====================

    def _create_config_path_section(self):
        """创建配置存储路径设置区域"""
        self.config_path_frame = self._create_card()

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

        self.register_search(
            ["配置路径", "配置存储路径", "config path", "存储路径", "配置目录"],
            self.config_path_frame
        )

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

    # ===================== v7.6: 迁移通用流程与对话框辅助 =====================

    def _ask_yes_no(self, title: str, message: str) -> bool:
        """是/否询问对话框"""
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            return bool(messagebox.askyesno(title, message, icon=messagebox.QUESTION))
        finally:
            root.destroy()

    def _show_msg(self, kind: str, title: str, message: str):
        """信息/警告/错误对话框（kind: showinfo/showwarning/showerror）"""
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            getattr(messagebox, kind)(title, message)
        finally:
            root.destroy()

    def _migration_error_message(self, err: str) -> str:
        """根据后端错误类型返回对应的迁移失败提示（复制失败/验证失败）"""
        if err.startswith("验证"):
            base = self.language_manager.get_text(
                "migration_verify_failed_rollback",
                "新路径文件验证失败，已回滚。"
            )
        else:
            base = self.language_manager.get_text(
                "migration_failed_rollback",
                "迁移失败，已回滚。请检查磁盘空间或权限。"
            )
        return f"{base}\n{err}" if err else base

    def _check_and_stop_sync_for_migration(self) -> Tuple[bool, bool]:
        """
        迁移前检查同步活动；正在运行时弹窗询问，用户确认则中断同步。

        Returns:
            (can_proceed, interrupted_sync)
            can_proceed      —— True 表示无同步活动或已成功中断，可以继续迁移；
                                False 表示用户取消或同步未能完全停止，应中止迁移
            interrupted_sync —— 本次是否实际中断了同步活动
        """
        lm = self.language_manager
        if not self.app.has_active_sync_activity():
            return (True, False)

        title = lm.get_text("migration_confirm_title", "迁移确认")
        confirmed = self._ask_yes_no(
            title,
            lm.get_text(
                "migration_sync_running_confirm",
                "有同步任务正在运行。建议先停止同步再迁移，否则可能导致数据不一致。\n\n是否继续？"
            ),
        )
        if not confirmed:
            return (False, False)

        if not self.app.interrupt_sync_for_migration():
            self._show_msg(
                "showerror",
                title,
                lm.get_text(
                    "migration_sync_stop_failed",
                    "同步任务未能完全停止，已取消迁移。请稍后重试。"
                ),
            )
            return (False, False)
        return (True, True)

    def _finish_migration(self, interrupted_sync: bool, title: str):
        """迁移成功后的收尾提示：打断任务说明 + 重启建议"""
        lm = self.language_manager
        message = lm.get_text("migration_done_restart", "迁移完成，建议重启程序以生效。")
        if interrupted_sync:
            message += "\n" + lm.get_text(
                "migration_interrupt_note",
                "被中断的同步已保存为打断任务，请在迁移完成后手动重新同步。"
            )
        self._show_msg("showinfo", title, message)

    def _on_config_path_save(self):
        """保存配置路径：完整迁移流程（检测同步 → 复制 → 验证 → 询问删旧 → 提示重启）"""
        lm = self.language_manager
        title = lm.get_text("config_path_settings", "配置存储路径")
        path = self.config_path_entry.get().strip()
        if not path:
            return

        current = self.config_manager.get_config_dir()
        try:
            if Path(path).resolve() == Path(current).resolve():
                return  # 与当前路径相同，无需迁移
        except Exception:
            pass

        # 1. 检查并（经用户确认后）中断正在运行的同步
        can_proceed, interrupted_sync = self._check_and_stop_sync_for_migration()
        if not can_proceed:
            # 用户取消或中断失败：恢复输入框为原路径
            self.config_path_entry.delete(0, "end")
            self.config_path_entry.insert(0, current)
            return

        # 2. 执行迁移（复制 + 验证 + 切换内部路径 + 写指针）
        ok, err = self.config_manager.set_custom_config_dir(path)
        if not ok:
            self._show_msg("showerror", title, self._migration_error_message(err))
            self.config_path_entry.delete(0, "end")
            self.config_path_entry.insert(0, self.config_manager.get_config_dir())
            return

        # 3. 询问是否删除旧配置
        if self._ask_yes_no(
            title,
            lm.get_text("migration_success_delete_old", "迁移成功，是否删除旧配置？"),
        ):
            del_ok, del_err = self.config_manager.cleanup_old_config_dir(current)
            if not del_ok:
                self._show_msg(
                    "showwarning",
                    title,
                    lm.get_text("migration_delete_old_failed", "删除旧配置时出现问题：") + f"\n{del_err}",
                )

        # 4. 输入框同步为新路径，提示重启
        self.config_path_entry.delete(0, "end")
        self.config_path_entry.insert(0, self.config_manager.get_config_dir())
        self._finish_migration(interrupted_sync, title)

    def _on_config_path_reset(self):
        """恢复默认配置路径：走与保存相同的完整迁移流程"""
        from backend.platform_utils import get_default_config_dir
        default_dir = str(get_default_config_dir())
        self.config_path_entry.delete(0, "end")
        self.config_path_entry.insert(0, default_dir)
        self._on_config_path_save()

    # ===================== v7.6: 外挂语言目录 =====================

    def _create_external_language_section(self):
        """创建外挂语言目录区域：显示路径 + 打开目录按钮"""
        self.ext_lang_frame = self._create_card()

        self.ext_lang_title = ctk.CTkLabel(
            self.ext_lang_frame,
            text=self.language_manager.get_text("external_language_dir", "外挂语言目录"),
            font=get_font(size=16, weight="bold")
        )
        self.ext_lang_title.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.ext_lang_hint = ctk.CTkLabel(
            self.ext_lang_frame,
            text=self.language_manager.get_text(
                "external_language_dir_hint",
                "将自定义语言文件（.json）放入此目录，优先级高于内置语言；"
                "同名文件按键覆盖内置翻译，重启后生效"
            ),
            font=get_font(size=12),
            text_color="gray",
            wraplength=600,
            justify="left"
        )
        self.ext_lang_hint.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")

        lang_dir = str(getattr(self.language_manager, "user_translations_dir", ""))
        self.ext_lang_entry = ctk.CTkEntry(self.ext_lang_frame, font=get_font(size=13))
        self.ext_lang_entry.insert(0, lang_dir)
        self.ext_lang_entry.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        # v7.6: 浏览/保存/打开目录按钮（保存触发独立迁移流程）
        self.ext_lang_btn_frame = ctk.CTkFrame(self.ext_lang_frame, fg_color="transparent")
        self.ext_lang_btn_frame.grid(row=3, column=0, padx=10, pady=(8, 10), sticky="ew")

        self.ext_lang_browse_btn = ctk.CTkButton(
            self.ext_lang_btn_frame,
            text=self.language_manager.get_text("browse", "浏览..."),
            font=get_font(size=13),
            width=110,
            command=self._on_external_language_dir_browse
        )
        self.ext_lang_browse_btn.grid(row=0, column=0, padx=(0, 10), pady=2, sticky="w")

        self.ext_lang_save_btn = ctk.CTkButton(
            self.ext_lang_btn_frame,
            text=self.language_manager.get_text("save", "保存"),
            font=get_font(size=13),
            width=110,
            command=self._on_external_language_dir_save
        )
        self.ext_lang_save_btn.grid(row=0, column=1, padx=10, pady=2, sticky="w")

        self.ext_lang_open_btn = ctk.CTkButton(
            self.ext_lang_btn_frame,
            text=self.language_manager.get_text("open_directory", "打开目录"),
            font=get_font(size=13),
            width=110,
            command=self._on_open_external_language_dir
        )
        self.ext_lang_open_btn.grid(row=0, column=2, padx=10, pady=2, sticky="w")

        self.register_search(
            ["语言目录", "外挂语言", "语言文件夹", "language dir", "translations"],
            self.ext_lang_frame
        )

    def _on_external_language_dir_browse(self):
        """浏览选择外挂语言目录"""
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        try:
            selected = filedialog.askdirectory(
                title=self.language_manager.get_text("select_language_dir", "选择外挂语言目录"),
                initialdir=str(getattr(self.language_manager, "user_translations_dir", "")),
            )
        finally:
            root.destroy()
        if selected:
            self.ext_lang_entry.delete(0, "end")
            self.ext_lang_entry.insert(0, selected)

    def _on_external_language_dir_save(self):
        """保存外挂语言目录：独立迁移流程（不影响配置存储路径）"""
        lm = self.language_manager
        title = lm.get_text("external_language_dir", "外挂语言目录")
        path = self.ext_lang_entry.get().strip()
        if not path:
            return

        current = str(lm.user_translations_dir)
        try:
            if Path(path).resolve() == Path(current).resolve():
                return  # 与当前路径相同，无需迁移
        except Exception:
            pass

        # 1. 检查并（经用户确认后）中断正在运行的同步
        can_proceed, interrupted_sync = self._check_and_stop_sync_for_migration()
        if not can_proceed:
            self.ext_lang_entry.delete(0, "end")
            self.ext_lang_entry.insert(0, current)
            return

        # 2. 执行迁移（复制 + 验证 JSON + 切换内部路径 + 重新加载语言）
        ok, err = lm.migrate_user_translations_dir(path)
        if not ok:
            self._show_msg("showerror", title, self._migration_error_message(err))
            self.ext_lang_entry.delete(0, "end")
            self.ext_lang_entry.insert(0, current)
            return

        # 3. 持久化设置（与配置存储路径相互独立）
        self.settings["user_translations_dir"] = str(lm.user_translations_dir)
        self.config_manager.update_settings(self.settings)

        # 4. 询问是否删除旧语言目录
        if self._ask_yes_no(
            title,
            lm.get_text("migration_success_delete_old_lang", "迁移成功，是否删除旧语言目录？"),
        ):
            del_ok, del_err = lm.cleanup_old_translations_dir(current)
            if not del_ok:
                self._show_msg(
                    "showwarning",
                    title,
                    lm.get_text("migration_delete_old_failed", "删除旧配置时出现问题：") + f"\n{del_err}",
                )

        # 5. 提示重启
        self._finish_migration(interrupted_sync, title)

    def _on_open_external_language_dir(self):
        """用系统文件管理器打开外挂语言目录"""
        from backend.platform_utils import open_directory_in_file_manager

        lang_dir = getattr(self.language_manager, "user_translations_dir", None)
        if not lang_dir:
            return
        try:
            Path(lang_dir).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        ok = open_directory_in_file_manager(str(lang_dir))
        if not ok:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Toplevel(self)
            root.withdraw()
            messagebox.showinfo(
                self.language_manager.get_text("external_language_dir", "外挂语言目录"),
                f"{self.language_manager.get_text('open_directory_failed', '无法自动打开目录，请手动前往：')}\n{lang_dir}",
                parent=root
            )
            root.destroy()

    # ===================== 刷新与语言 =====================

    def refresh(self):
        """刷新配置路径与外挂语言目录"""
        # 配置存储路径
        self.config_path_entry.delete(0, "end")
        self.config_path_entry.insert(0, self.config_manager.get_config_dir())

        # 外挂语言目录
        self.ext_lang_entry.delete(0, "end")
        self.ext_lang_entry.insert(
            0, str(getattr(self.language_manager, "user_translations_dir", ""))
        )

    def update_language(self):
        """更新界面语言"""
        # 配置存储路径区域
        self.config_path_title.configure(
            text=self.language_manager.get_text("config_path_settings", "配置存储路径")
        )
        self.config_path_hint.configure(
            text=self.language_manager.get_text(
                "config_path_hint",
                "自定义配置文件的存储目录，修改后需重启程序生效"
            )
        )
        self.config_path_browse_btn.configure(
            text=self.language_manager.get_text("browse", "浏览...")
        )
        self.config_path_save_btn.configure(
            text=self.language_manager.get_text("save", "保存")
        )
        self.config_path_reset_btn.configure(
            text=self.language_manager.get_text("restore_default", "恢复默认")
        )

        # 外挂语言目录区域
        self.ext_lang_title.configure(
            text=self.language_manager.get_text("external_language_dir", "外挂语言目录")
        )
        self.ext_lang_hint.configure(
            text=self.language_manager.get_text(
                "external_language_dir_hint",
                "将自定义语言文件（.json）放入此目录，优先级高于内置语言；"
                "同名文件按键覆盖内置翻译，重启后生效"
            )
        )
        self.ext_lang_browse_btn.configure(
            text=self.language_manager.get_text("browse", "浏览...")
        )
        self.ext_lang_save_btn.configure(
            text=self.language_manager.get_text("save", "保存")
        )
        self.ext_lang_open_btn.configure(
            text=self.language_manager.get_text("open_directory", "打开目录")
        )


class DeletionSettingsFrame(_SettingsSection):
    """删除策略：同步删除默认状态、最近删除上限"""

    def __init__(self, master, page: "SettingsPage"):
        super().__init__(master, page)
        self._create_sync_delete_section()

    def _create_sync_delete_section(self):
        """创建同步删除和回收站设置区域"""
        self.sync_delete_frame = self._create_card()

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

        self.register_search(
            ["回收站", "删除", "同步删除", "recycle", "最近删除", "容量"],
            self.sync_delete_frame
        )

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

    # ===================== 刷新与语言 =====================

    def refresh(self):
        """刷新回收站限额与同步删除默认值"""
        # 同步删除默认状态
        self.sync_delete_default_enabled = self.settings.get("sync_delete_default", False)
        if self.sync_delete_default_enabled:
            self.sync_delete_default_switch.select()
        else:
            self.sync_delete_default_switch.deselect()

        # 最近删除上限
        current_limit_gb = self.settings.get("recycle_limit_gb", 5.0)
        self.recycle_limit_entry.delete(0, "end")
        self.recycle_limit_entry.insert(0, str(current_limit_gb))
        self.recycle_limit_save_btn.configure(
            text=self.language_manager.get_text("save", "保存")
        )

    def update_language(self):
        """更新界面语言"""
        # 同步删除和回收站设置区域
        self.sync_delete_title.configure(
            text=self.language_manager.get_text("sync_delete_settings", "同步删除设置")
        )
        self.recycle_limit_label.configure(
            text=self.language_manager.get_text("recycle_limit", "最近删除上限") + ":"
        )
        self.recycle_limit_hint.configure(
            text=self.language_manager.get_text("recycle_limit_hint", "设置最近删除文件夹的最大容量，达到上限时将提示清理")
        )
        self.recycle_limit_save_btn.configure(
            text=self.language_manager.get_text("save", "保存")
        )
        self.sync_delete_default_label.configure(
            text=self.language_manager.get_text("sync_delete_default", "同步删除默认状态") + ":"
        )
        self.sync_delete_default_hint.configure(
            text=self.language_manager.get_text("sync_delete_default_hint", "设置同步删除功能的默认开启状态，可在同步确认界面临时修改")
        )
        self.sync_delete_default_switch.configure(
            text=self.language_manager.get_text("enable_sync_delete_default", "默认开启同步删除")
        )


class SettingsPage(ctk.CTkFrame):
    """设置页面：顶部搜索 + 左侧导航 + 右侧内容区"""

    # 左侧导航项：(分区键, 翻译键, 默认文案)
    _NAV_ITEMS = [
        ("basic", "settings_nav_basic", "基础设置"),
        ("sync", "settings_nav_sync", "同步与性能"),
        ("udisk", "settings_nav_udisk", "U 盘自动化"),
        ("storage", "settings_nav_storage", "存储路径"),
        ("deletion", "settings_nav_deletion", "删除策略"),
    ]

    # 右侧分区：(分区键, 分区类)
    _SECTION_CLASSES = [
        ("basic", BasicSettingsFrame),
        ("sync", SyncSettingsFrame),
        ("udisk", UdiskSettingsFrame),
        ("storage", StorageSettingsFrame),
        ("deletion", DeletionSettingsFrame),
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

        # 获取当前设置（子 Frame 通过属性代理共享同一个字典对象）
        self.settings = self.config_manager.get_settings()

        self.current_section = "basic"
        self.sections = {}
        # 是否处于全局搜索模式（搜索模式下右侧展示跨分类的搜索结果视图）
        self._search_mode = False

        # 创建界面
        self._create_widgets()

    def _create_widgets(self):
        """创建界面组件"""
        # 配置网格权重
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ========== 顶部标题 + 搜索框 ==========
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text=self.language_manager.get_text("settings", "设置"),
            font=get_font(size=18, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(
            self.header_frame,
            textvariable=self.search_var,
            placeholder_text=self.app.get_text("settings_search_placeholder", "搜索设置项"),
            font=get_font(size=13),
            width=240
        )
        self.search_entry.grid(row=0, column=1, padx=10, pady=10, sticky="e")
        self.search_entry.bind("<KeyRelease>", self._on_search_key)

        # ========== 左侧导航 ==========
        self.nav_frame = ctk.CTkFrame(self)
        self.nav_frame.grid(row=1, column=0, padx=(10, 0), pady=(0, 10), sticky="nsw")
        self.nav_frame.grid_columnconfigure(0, weight=1)

        self.nav_buttons = {}
        for index, (key, text_key, default) in enumerate(self._NAV_ITEMS):
            btn = ctk.CTkButton(
                self.nav_frame,
                text=self.app.get_text(text_key, default),
                anchor="w",
                width=150,
                height=42,
                font=get_font(size=14),
                command=lambda k=key: self._on_nav_click(k)
            )
            btn.grid(row=index, column=0, padx=8, pady=(8 if index == 0 else 0, 8), sticky="ew")
            self.nav_buttons[key] = btn

        # ========== 右侧内容区（独立滚动容器） ==========
        self.content_frame = ctk.CTkScrollableFrame(self)
        self.content_frame.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(1, weight=1)

        # 搜索结果视图标题（仅搜索模式显示）
        self.search_results_label = ctk.CTkLabel(
            self.content_frame,
            text="",
            font=get_font(size=15, weight="bold")
        )
        self.search_results_label.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")
        self.search_results_label.grid_remove()

        for key, frame_cls in self._SECTION_CLASSES:
            section = frame_cls(self.content_frame, self)
            section.grid(row=1, column=0, sticky="nsew")
            self.sections[key] = section

        # 搜索无结果提示（与分区同格，二者不会同时显示）
        self.no_result_label = ctk.CTkLabel(
            self.content_frame,
            text=self.app.get_text("settings_search_no_result", "未找到该设置"),
            font=get_font(size=14),
            text_color="gray"
        )
        self.no_result_label.grid(row=1, column=0, padx=20, pady=40, sticky="n")
        self.no_result_label.grid_remove()

        # ========== 底部按钮区域 ==========
        self.bottom_frame = ctk.CTkFrame(self)
        self.bottom_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
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

        # 默认显示基础设置
        self._show_section(self.current_section)

    # ===================== 导航与搜索 =====================

    def _update_nav_buttons(self):
        """刷新左侧导航按钮的选中样式（全局搜索模式下不突出任何分类）"""
        for key, btn in self.nav_buttons.items():
            active = (not self._search_mode) and key == self.current_section
            btn.configure(
                fg_color="#3B8ED0" if active else "transparent",
                text_color="white" if active else ("black", "white"),
                hover_color="#36719F" if active else ("gray85", "gray25"),
                border_width=0 if active else 1,
                border_color=("#3B8ED0", "#1F6AA5")
            )

    def _scroll_content_to_top(self):
        """搜索结果或分类切换后回到右侧内容区顶部"""
        try:
            self.content_frame._parent_canvas.yview_moveto(0)
        except Exception:
            pass

    def _show_section(self, key: str):
        """显示指定分区，隐藏其余分区，并退出搜索模式"""
        if key not in self.sections:
            key = "basic"
        self.current_section = key
        self._search_mode = False

        for name, section in self.sections.items():
            if name == key:
                section.grid(row=1, column=0, sticky="nsew")
            else:
                section.grid_remove()

        for section in self.sections.values():
            section.restore_all_items()

        self.search_results_label.grid_remove()
        self.no_result_label.grid_remove()
        self._scroll_content_to_top()
        self._update_nav_buttons()

    def _on_nav_click(self, key: str):
        """左侧导航点击事件：退出搜索模式并切换分区"""
        if self.search_var.get():
            self.search_var.set("")
        self._show_section(key)

    def _on_search_key(self, event=None):
        """搜索框实时输入：触发跨分类全局搜索"""
        self._apply_search(self.search_entry.get().strip())

    def _apply_search(self, query: str):
        """
        跨分类全局搜索：遍历全部设置分区，把命中项堆叠展示为“搜索结果视图”。

        - 命中：右侧只显示命中的设置卡片，顶部显示命中数量
        - 无命中：显示“未找到该设置”
        - 清空关键词：退出搜索，恢复当前分类
        """
        if not query:
            self._show_section(self.current_section)
            return

        needle = query.lower()
        self._search_mode = True

        matched_count = 0
        hit_row = 1
        for section in self.sections.values():
            count = section.filter_search(needle)
            matched_count += count
            if count:
                # 命中多个分区时按行堆叠，避免同一单元格内重叠
                section.grid(row=hit_row, column=0, sticky="nsew")
                hit_row += 1
            else:
                section.grid_remove()

        if matched_count:
            self.no_result_label.grid_remove()
            self.search_results_label.configure(
                text=self.language_manager.format_text(
                    "settings_search_results", count=matched_count
                )
            )
            self.search_results_label.grid()
        else:
            self.search_results_label.grid_remove()
            self.no_result_label.grid()

        self._scroll_content_to_top()
        self._update_nav_buttons()

    # ===================== 底部按钮 =====================

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
            "确定要恢复所有设置项为默认值吗？\n\n"
            "• 仅「设置」中的选项会恢复默认\n"
            "• 已创建的同步任务、同步历史与打断任务记录都会保留\n\n"
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

    # ===================== 刷新与语言 =====================

    def refresh(self):
        """刷新页面（刷新各分区当前值，不重建控件）"""
        for section in self.sections.values():
            section.refresh()

    def update_language(self):
        """更新界面语言"""
        # 更新标题
        self.title_label.configure(
            text=self.language_manager.get_text("settings", "设置")
        )

        # 更新搜索框
        self.search_entry.configure(
            placeholder_text=self.app.get_text("settings_search_placeholder", "搜索设置项")
        )
        self.no_result_label.configure(
            text=self.app.get_text("settings_search_no_result", "未找到该设置")
        )

        # 更新左侧导航
        for key, text_key, default in self._NAV_ITEMS:
            self.nav_buttons[key].configure(
                text=self.app.get_text(text_key, default)
            )

        # 更新底部按钮
        self.reset_btn.configure(
            text=self.language_manager.get_text("restore_default_config", "恢复默认配置")
        )
        self.back_btn.configure(
            text=self.language_manager.get_text("return_home", "返回首页")
        )

        # 委托各分区更新自身文案
        for section in self.sections.values():
            section.update_language()

        # 搜索模式下重新计算命中项数量（文案随语言切换）
        if self._search_mode:
            self._apply_search(self.search_entry.get().strip())
