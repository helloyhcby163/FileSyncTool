"""
文件同步工具 v7.0 - 任务配置页面
用于管理任务的复制、重命名、删除、编辑、导出等操作
"""

import customtkinter as ctk
from backend.language_manager import get_font
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .app import FileSyncApp


class TaskManagePage(ctk.CTkFrame):
    """任务配置页面：管理任务的复制、重命名、删除、编辑"""
    
    def __init__(self, master, app: "FileSyncApp"):
        """
        初始化任务配置页面
        
        Args:
            master: 父容器
            app: 主窗口实例
        """
        super().__init__(master)
        
        self.app = app
        
        # 选中的任务列表（支持多选）
        self.selected_tasks: List[Dict] = []
        self.selected_indices: List[int] = []
        
        # 复选框变量映射：task_id -> BooleanVar
        self.check_vars: Dict[str, ctk.BooleanVar] = {}
        
        # 任务列表数据
        self.tasks: List[Dict] = []
        self.filtered_tasks: List[Dict] = []
        
        # 任务项组件列表
        self.task_items: List[ctk.CTkFrame] = []
        
        # 设置布局
        self._setup_layout()
        
        # 加载任务数据
        self._load_tasks()
    
    def _setup_layout(self):
        """设置布局"""
        # 配置网格权重
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # ========== 上方：搜索框区域 ==========
        self._create_search_panel()
        
        # ========== 中间：任务列表区域 ==========
        self._create_task_list_panel()
        
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
            text=self.app.get_text("task_config_page"),
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
        
        # 全选 / 取消全选按钮
        self.select_all_btn = ctk.CTkButton(
            self.search_frame,
            text=self.app.get_text("select_all", "全选"),
            width=80,
            height=35,
            font=get_font(size=13),
            command=self._on_select_all_click
        )
        self.select_all_btn.grid(row=0, column=3, padx=(5, 2), pady=10)
        
        self.deselect_all_btn = ctk.CTkButton(
            self.search_frame,
            text=self.app.get_text("deselect_all", "取消全选"),
            width=90,
            height=35,
            font=get_font(size=13),
            command=self._on_deselect_all_click
        )
        self.deselect_all_btn.grid(row=0, column=4, padx=(2, 10), pady=10)
    
    def _create_task_list_panel(self):
        """创建任务列表区域"""
        self.list_frame = ctk.CTkFrame(self)
        self.list_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(0, weight=1)
        
        # 任务列表（使用 ScrollableFrame）
        self.task_scrollable = ctk.CTkScrollableFrame(
            self.list_frame,
            label_text=self.app.get_text("task_list")
        )
        self.task_scrollable.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.task_scrollable.grid_columnconfigure(0, weight=1)
        
        # 空列表提示
        self.empty_label = ctk.CTkLabel(
            self.task_scrollable,
            text=self.app.get_text("no_folders"),
            font=get_font(size=14),
            text_color="gray"
        )
        
        # 多选提示
        self.multi_select_hint = ctk.CTkLabel(
            self.list_frame,
            text=self.app.get_text(
                "multi_select_hint", "提示：Ctrl+单击多选，Shift+单击范围选择"
            ),
            font=get_font(size=12),
            text_color="gray"
        )
        self.multi_select_hint.grid(row=1, column=0, padx=10, pady=(5, 5), sticky="w")
    
    def _create_button_panel(self):
        """创建底部按钮区域"""
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.button_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        
        # 复制按钮
        self.copy_btn = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("copy"),
            height=40,
            font=get_font(size=14),
            command=self._on_copy_click,
            state="disabled"
        )
        self.copy_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # 重命名按钮
        self.rename_btn = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("rename"),
            height=40,
            font=get_font(size=14),
            command=self._on_rename_click,
            state="disabled"
        )
        self.rename_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        # 删除按钮
        self.delete_btn = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("delete"),
            height=40,
            font=get_font(size=14),
            fg_color="red",
            hover_color="darkred",
            command=self._on_delete_click,
            state="disabled"
        )
        self.delete_btn.grid(row=0, column=2, padx=10, pady=10, sticky="ew")
        
        # 编辑按钮
        self.edit_btn = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("edit"),
            height=40,
            font=get_font(size=14),
            fg_color="#2CC985",
            hover_color="#229E6A",
            command=self._on_edit_click,
            state="disabled"
        )
        self.edit_btn.grid(row=0, column=3, padx=10, pady=10, sticky="ew")
        
        # 导出按钮（选中任务导出；未选中时询问是否导出全部）
        self.export_btn = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("export_tasks", "导出任务"),
            height=40,
            font=get_font(size=14),
            fg_color="#3B8ED0",
            hover_color="#36719F",
            command=self._on_export_click
        )
        self.export_btn.grid(row=0, column=4, padx=10, pady=10, sticky="ew")
        
        # 返回首页按钮
        self.back_home_btn = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("back_home", "返回首页"),
            height=40,
            font=get_font(size=14),
            fg_color="#6B7280",
            hover_color="#4B5563",
            command=self._on_back_home_click
        )
        self.back_home_btn.grid(row=0, column=5, padx=10, pady=10, sticky="ew")
    
    def _on_back_home_click(self):
        """返回首页按钮点击事件"""
        self.app.show_page("home")
    
    def _load_tasks(self):
        """加载任务列表"""
        self.tasks = self.app.task_manager.get_all_tasks()
        self.filtered_tasks = self.tasks.copy()
        self._update_task_list()
    
    def _update_task_list(self):
        """更新任务列表显示"""
        # 清除现有任务项
        for item in self.task_items:
            item.destroy()
        self.task_items.clear()
        
        # 显示/隐藏空列表提示
        if not self.filtered_tasks:
            self.empty_label.grid(row=0, column=0, padx=10, pady=20)
            return
        else:
            self.empty_label.grid_forget()
        
        # 创建任务项
        for i, task in enumerate(self.filtered_tasks):
            self._create_task_item(i, task)
    
    def _create_task_item(self, index: int, task: Dict):
        """
        创建单个任务项
        
        Args:
            index: 任务索引
            task: 任务数据
        """
        # 任务项容器
        item_frame = ctk.CTkFrame(self.task_scrollable)
        item_frame.grid(row=index, column=0, padx=5, pady=3, sticky="ew")
        item_frame.grid_columnconfigure(2, weight=1)
        
        # 存储任务信息
        item_frame.task_info = task
        item_frame.task_index = index
        
        # 复选框
        task_id = task.get("id", "")
        if task_id not in self.check_vars:
            self.check_vars[task_id] = ctk.BooleanVar(value=False)
        else:
            # 确保变量类型正确
            if not isinstance(self.check_vars[task_id], ctk.BooleanVar):
                self.check_vars[task_id] = ctk.BooleanVar(value=self.check_vars[task_id].get() if hasattr(self.check_vars[task_id], 'get') else False)
        
        checkbox = ctk.CTkCheckBox(
            item_frame,
            text="",
            width=20,
            variable=self.check_vars[task_id],
            command=lambda tid=task_id, idx=index, t=task: self._on_checkbox_toggle(tid, idx, t)
        )
        checkbox.grid(row=0, column=0, padx=(10, 5), pady=8)
        
        # 序号标签
        index_label = ctk.CTkLabel(
            item_frame,
            text=f"{index + 1}",
            font=get_font(size=14, weight="bold"),
            width=40
        )
        index_label.grid(row=0, column=1, padx=(5, 5), pady=8)
        
        # 任务名称
        task_name = task.get("name", "未命名任务")
        name_label = ctk.CTkLabel(
            item_frame,
            text=task_name,
            font=get_font(size=14),
            anchor="w"
        )
        name_label.grid(row=0, column=2, padx=5, pady=8, sticky="ew")
        
        # 绑定点击事件（支持多选）- 点击行也可切换选中
        def on_click(event, idx=index, t=task, frame=item_frame):
            self._on_task_click(event, idx, t, frame)
        
        item_frame.bind("<Button-1>", on_click)
        index_label.bind("<Button-1>", on_click)
        name_label.bind("<Button-1>", on_click)
        
        # 保存引用
        self.task_items.append(item_frame)
    
    def _on_checkbox_toggle(self, task_id: str, index: int, task: Dict):
        """复选框状态变化时同步选中列表"""
        is_checked = self.check_vars[task_id].get()
        if is_checked:
            if index not in self.selected_indices:
                self.selected_indices.append(index)
            if not any(t.get("id") == task_id for t in self.selected_tasks):
                self.selected_tasks.append(task)
        else:
            if index in self.selected_indices:
                self.selected_indices.remove(index)
            self.selected_tasks = [t for t in self.selected_tasks if t.get("id") != task_id]
        
        self._update_selection_visual()
        self._update_button_states()
    
    def _on_select_all_click(self):
        """全选当前列表中的所有任务"""
        self.selected_indices.clear()
        self.selected_tasks.clear()
        for i, task in enumerate(self.filtered_tasks):
            task_id = task.get("id", "")
            if task_id in self.check_vars:
                self.check_vars[task_id].set(True)
            self.selected_indices.append(i)
            self.selected_tasks.append(task)
        self._update_selection_visual()
        self._update_button_states()
    
    def _on_deselect_all_click(self):
        """取消全选"""
        for task_id, var in self.check_vars.items():
            var.set(False)
        self.selected_indices.clear()
        self.selected_tasks.clear()
        self._update_selection_visual()
        self._update_button_states()
    
    def _on_task_click(self, event, index: int, task: Dict, frame: ctk.CTkFrame):
        """
        任务项点击事件（支持多选）
        
        Args:
            event: 点击事件
            index: 任务索引
            task: 任务数据
            frame: 任务项容器
        """
        # Ctrl+单击：添加/移除选中
        if event.state & 0x4:  # Ctrl 键
            if index in self.selected_indices:
                # 移除选中
                self.selected_indices.remove(index)
                self.selected_tasks = [t for t in self.selected_tasks 
                                       if t.get("id") != task.get("id")]
            else:
                # 添加选中
                self.selected_indices.append(index)
                self.selected_tasks.append(task)
        
        # Shift+单击：范围选择
        elif event.state & 0x1:  # Shift 键
            if self.selected_indices:
                # 从最后一个选中项到当前项
                last_index = self.selected_indices[-1]
                start = min(last_index, index)
                end = max(last_index, index)
                
                # 清空当前选中
                self.selected_indices.clear()
                self.selected_tasks.clear()
                
                # 范围选择
                for i in range(start, end + 1):
                    self.selected_indices.append(i)
                    self.selected_tasks.append(self.filtered_tasks[i])
            else:
                # 没有已选中项，单选
                self.selected_indices = [index]
                self.selected_tasks = [task]
        
        # 普通单击：单选
        else:
            self.selected_indices = [index]
            self.selected_tasks = [task]
        
        # 同步复选框状态
        self._sync_checkboxes_from_selection()
        
        # 更新视觉反馈
        self._update_selection_visual()
        
        # 更新按钮状态
        self._update_button_states()
    
    def _sync_checkboxes_from_selection(self):
        """根据当前选中列表同步所有复选框状态"""
        selected_ids = {t.get("id") for t in self.selected_tasks}
        for task_id, var in self.check_vars.items():
            var.set(task_id in selected_ids)
    
    def _update_selection_visual(self):
        """更新选中状态的视觉反馈"""
        for item in self.task_items:
            index = item.task_index
            if index in self.selected_indices:
                item.configure(border_width=2, border_color=("#3B8ED0", "#1F6AA5"))
            else:
                item.configure(border_width=0)
    
    def _update_button_states(self):
        """更新按钮状态"""
        has_selection = len(self.selected_tasks) > 0
        single_selection = len(self.selected_tasks) == 1
        
        # 复制按钮：有选中即可
        self.copy_btn.configure(state="normal" if has_selection else "disabled")
        
        # 重命名按钮：仅单选可用
        self.rename_btn.configure(state="normal" if single_selection else "disabled")
        
        # 删除按钮：有选中即可
        self.delete_btn.configure(state="normal" if has_selection else "disabled")
        
        # 编辑按钮：仅单选可用
        self.edit_btn.configure(state="normal" if single_selection else "disabled")
    
    def _on_search_change(self, event):
        """搜索框内容变化事件"""
        keyword = self.search_var.get().strip().lower()
        
        if keyword:
            self.filtered_tasks = [
                task for task in self.tasks
                if keyword in task.get("name", "").lower()
            ]
        else:
            self.filtered_tasks = self.tasks.copy()
        
        # 重置选中状态
        self.selected_tasks.clear()
        self.selected_indices.clear()
        for var in self.check_vars.values():
            var.set(False)
        self._update_button_states()
        
        # 更新列表
        self._update_task_list()
    
    def _clear_search(self):
        """清除搜索"""
        self.search_var.set("")
        self._on_search_change(None)
    
    def _on_copy_click(self):
        """复制按钮点击事件"""
        if not self.selected_tasks:
            return
        
        # 复制选中的任务
        for task in self.selected_tasks:
            task_id = task.get("id")
            self.app.task_manager.copy_task(task_id)
        
        # 显示成功提示
        self._show_message(self.app.get_text("task_copied"))
        
        # 刷新列表
        self._load_tasks()
    
    def _on_rename_click(self):
        """重命名按钮点击事件"""
        if len(self.selected_tasks) != 1:
            return
        
        task = self.selected_tasks[0]
        current_name = task.get("name", "")
        
        # 弹出重命名对话框
        dialog = ctk.CTkInputDialog(
            text=self.app.get_text("rename_task_dialog_text", name=current_name),
            title=self.app.get_text("rename")
        )
        
        new_name = dialog.get_input()
        
        if new_name and new_name.strip():
            new_name = new_name.strip()
            
            # 检查名称是否已存在
            existing_task = self.app.task_manager.get_task_by_name(new_name)
            if existing_task and existing_task.get("id") != task.get("id"):
                self._show_message("任务名称已存在，请使用其他名称")
                return
            
            # 重命名任务
            self.app.task_manager.rename_task(task.get("id"), new_name)
            
            # 显示成功提示
            self._show_message(self.app.get_text("task_renamed"))
            
            # 刷新列表
            self._load_tasks()
    
    def _on_delete_click(self):
        """删除按钮点击事件"""
        if not self.selected_tasks:
            return
        
        # 弹出确认对话框
        count = len(self.selected_tasks)
        confirm_text = f"确定要删除选中的 {count} 个任务吗？"
        
        # 创建确认对话框
        dialog = ConfirmDialog(
            self,
            title=self.app.get_text("delete_confirm"),
            message=confirm_text,
            app=self.app
        )
        
        if dialog.get_result():
            # 删除选中的任务
            task_ids = [t.get("id") for t in self.selected_tasks]
            self.app.task_manager.delete_tasks(task_ids)
            
            # 显示成功提示
            self._show_message(self.app.get_text("task_deleted"))
            
            # 清空选中状态
            self.selected_tasks.clear()
            self.selected_indices.clear()
            
            # 刷新列表
            self._load_tasks()
    
    def _on_edit_click(self):
        """编辑按钮点击事件"""
        if len(self.selected_tasks) != 1:
            return
        
        task = self.selected_tasks[0]
        task_id = task.get("id", "")
        
        # 跳转到创建任务页面，传递任务ID和编辑模式
        self.app.current_task_config = task
        self.app.show_page("create_task", task_id=task_id, edit_mode=True)
    
    def _on_export_click(self):
        """导出按钮点击事件：导出选中的任务；未选中时询问是否导出全部任务"""
        from tkinter import filedialog
        
        # 确定要导出的任务
        if self.selected_tasks:
            tasks_to_export = self.selected_tasks
        else:
            # 未选中任何任务：询问是否导出全部
            if not self.tasks:
                self._show_message(self.app.get_text("no_tasks_to_export", "没有可导出的任务"))
                return
            
            confirm_text = self.app.get_text(
                "export_all_confirm",
                "未选中任何任务，是否导出全部任务？"
            )
            dialog = ConfirmDialog(
                self,
                title=self.app.get_text("export_tasks", "导出任务"),
                message=confirm_text,
                app=self.app
            )
            if not dialog.get_result():
                return
            tasks_to_export = self.tasks
        
        task_ids = [t.get("id") for t in tasks_to_export if t.get("id")]
        if not task_ids:
            self._show_message(self.app.get_text("no_tasks_to_export", "没有可导出的任务"))
            return
        
        # 选择导出文件路径
        default_name = "tasks_export.json" if len(task_ids) > 1 else "task_export.json"
        file_path = filedialog.asksaveasfilename(
            title=self.app.get_text("export_tasks", "导出任务"),
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not file_path:
            return
        
        # 执行导出
        success = self.app.task_manager.export_tasks(task_ids, file_path)
        
        if success:
            self._show_message(
                self.app.get_text("export_success", "任务导出成功") + f" ({len(task_ids)})"
            )
        else:
            self._show_message(self.app.get_text("export_failed", "任务导出失败"))
    
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
        # 刷新任务列表
        self._load_tasks()
        
        # 清空选中状态
        self.selected_tasks.clear()
        self.selected_indices.clear()
        for var in self.check_vars.values():
            var.set(False)
        self._update_button_states()
        
        # 更新文本
        self._update_texts()
    
    def _update_texts(self):
        """更新所有文本"""
        # 更新标题
        self.title_label.configure(text=self.app.get_text("task_config_page"))
        
        # 更新搜索框
        self.search_entry.configure(placeholder_text=self.app.get_text("search"))
        
        # 更新任务列表标题
        self.task_scrollable.configure(label_text=self.app.get_text("task_list"))
        
        # 更新全选/取消全选按钮
        self.select_all_btn.configure(text=self.app.get_text("select_all", "全选"))
        self.deselect_all_btn.configure(text=self.app.get_text("deselect_all", "取消全选"))
        
        # 更新按钮文本
        self.copy_btn.configure(text=self.app.get_text("copy"))
        self.rename_btn.configure(text=self.app.get_text("rename"))
        self.delete_btn.configure(text=self.app.get_text("delete"))
        self.edit_btn.configure(text=self.app.get_text("edit"))
        self.export_btn.configure(text=self.app.get_text("export_tasks", "导出任务"))


class ConfirmDialog(ctk.CTkToplevel):
    """确认对话框"""
    
    def __init__(self, master, title: str, message: str, app: "FileSyncApp"):
        """
        初始化确认对话框
        
        Args:
            master: 父容器
            title: 对话框标题
            message: 消息内容
            app: 主窗口实例
        """
        super().__init__(master)
        
        self.app = app
        self.result = False
        
        # 设置窗口属性
        self.title(title)
        self.geometry("300x150")
        self.resizable(False, False)
        
        # 模态对话框
        self.transient(master)
        self.grab_set()
        
        # 创建组件
        self._create_widgets(message)
        
        # 等待用户响应
        self.wait_window()
    
    def _create_widgets(self, message: str):
        """创建对话框组件"""
        # 消息标签
        self.message_label = ctk.CTkLabel(
            self,
            text=message,
            font=get_font(size=14),
            wraplength=250
        )
        self.message_label.pack(padx=20, pady=(20, 10))
        
        # 按钮容器
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.pack(padx=20, pady=10, fill="x")
        
        # 确认按钮
        self.confirm_btn = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("confirm"),
            width=100,
            command=self._on_confirm
        )
        self.confirm_btn.pack(side="left", padx=10, expand=True)
        
        # 取消按钮
        self.cancel_btn = ctk.CTkButton(
            self.button_frame,
            text=self.app.get_text("cancel"),
            width=100,
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            border_width=2,
            command=self._on_cancel
        )
        self.cancel_btn.pack(side="right", padx=10, expand=True)
    
    def _on_confirm(self):
        """确认按钮点击"""
        self.result = True
        self.destroy()
    
    def _on_cancel(self):
        """取消按钮点击"""
        self.result = False
        self.destroy()
    
    def get_result(self) -> bool:
        """获取对话框结果"""
        return self.result