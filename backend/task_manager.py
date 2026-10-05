"""
文件同步工具 v7.5 - 任务管理器
负责任务的创建、编辑、删除、复制、重命名、导入导出等操作

v7.5 新增：
- 任务导入导出（JSON 配置文件，支持跨电脑迁移）
- 目录冲突检测（防止同目录并发同步）
"""

import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from .config_manager import ConfigManager


class TaskManager:
    """任务管理器：处理任务的各种操作"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化任务管理器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        # 运行中的任务状态（内存存储）
        self.running_tasks: Dict[str, Dict] = {}
    
    def create_task(self, name: str, source: str, target: str,
                   mode: str = "fast", sync_direction: str = "both",
                   folders: List[str] = None, default_strategy: str = "conservative",
                   folder_strategies: Dict[str, str] = None,
                   folder_filters: Dict[str, Dict] = None,
                   root_included: bool = False, root_strategy: str = "conservative",
                   use_multithreading_scan: bool = False, use_multithreading_copy: bool = False,
                   last_snapshot: Optional[Dict] = None,
                   post_sync_command: str = "") -> Dict:
        """
        创建新任务

        Args:
            name: 任务名称
            source: 源目录路径
            target: 目标目录路径
            mode: 运行模式 (fast/safe)
            sync_direction: 同步方向 (both/source_to_target/target_to_source)
            folders: 选中的子文件夹列表
            default_strategy: 默认策略
            folder_strategies: 文件夹单独策略
            folder_filters: 按文件夹的筛选策略（扩展名过滤 + 日期过滤，未配置的文件夹不启用筛选）
            root_included: 是否包含根目录文件
            root_strategy: 根目录策略
            use_multithreading_scan: 是否使用多线程扫描
            use_multithreading_copy: 是否使用多线程复制

        Returns:
            创建的任务字典
        """
        task = {
            "id": str(uuid.uuid4()),
            "name": name,
            "source": source,
            "target": target,
            "mode": mode,
            "sync_direction": sync_direction,
            "folders": folders or [],
            "default_strategy": default_strategy,
            "folder_strategies": folder_strategies or {},
            "folder_filters": folder_filters or {},
            "root_included": root_included,
            "root_strategy": root_strategy,
            "use_multithreading_scan": use_multithreading_scan,
            "use_multithreading_copy": use_multithreading_copy,
            "post_sync_command": post_sync_command or "",
            "last_snapshot": last_snapshot,
            "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "last_used": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "active"
        }
        
        # 保存到配置
        tasks = self.config_manager.get_tasks()
        tasks.append(task)
        self.config_manager.config["tasks"] = tasks
        self.config_manager.save_config()
        
        return task
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        return self.config_manager.get_tasks()
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict]:
        """根据 ID 获取任务"""
        return self.config_manager.get_task_by_id(task_id)
    
    def get_task_by_name(self, task_name: str) -> Optional[Dict]:
        """根据名称获取任务"""
        return self.config_manager.get_task_by_name(task_name)
    
    def update_task(self, task_id: str, updates: Dict) -> Optional[Dict]:
        """
        更新任务
        
        Args:
            task_id: 任务 ID
            updates: 要更新的字段
            
        Returns:
            更新后的任务，如果任务不存在则返回 None
        """
        tasks = self.config_manager.get_tasks()
        
        for i, task in enumerate(tasks):
            if task.get("id") == task_id:
                # 更新字段
                for key, value in updates.items():
                    if key != "id":  # 不允许修改 ID
                        task[key] = value
                
                # 更新最后使用时间
                task["last_used"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                
                # 保存
                tasks[i] = task
                self.config_manager.config["tasks"] = tasks
                self.config_manager.save_config()
                
                return task
        
        return None
    
    def delete_task(self, task_id: str) -> bool:
        """
        删除任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            是否成功删除
        """
        tasks = self.config_manager.get_tasks()
        original_count = len(tasks)
        
        tasks = [t for t in tasks if t.get("id") != task_id]
        
        if len(tasks) < original_count:
            self.config_manager.config["tasks"] = tasks
            self.config_manager.save_config()
            return True
        
        return False
    
    def delete_tasks(self, task_ids: List[str]) -> int:
        """
        删除多个任务
        
        Args:
            task_ids: 任务 ID 列表
            
        Returns:
            成功删除的任务数量
        """
        tasks = self.config_manager.get_tasks()
        original_count = len(tasks)
        
        tasks = [t for t in tasks if t.get("id") not in task_ids]
        deleted_count = original_count - len(tasks)
        
        if deleted_count > 0:
            self.config_manager.config["tasks"] = tasks
            self.config_manager.save_config()
        
        return deleted_count
    
    def copy_task(self, task_id: str, new_name: str = None) -> Optional[Dict]:
        """
        复制任务
        
        Args:
            task_id: 要复制的任务 ID
            new_name: 新任务名称（默认为原名称 + "_副本")
            
        Returns:
            复制后的新任务
        """
        original_task = self.get_task_by_id(task_id)
        
        if original_task is None:
            return None
        
        # 创建新任务
        new_task = original_task.copy()
        new_task["id"] = str(uuid.uuid4())
        new_task["name"] = new_name or f"{original_task['name']}_副本"
        new_task["created_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        new_task["last_used"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        # 保存
        tasks = self.config_manager.get_tasks()
        tasks.append(new_task)
        self.config_manager.config["tasks"] = tasks
        self.config_manager.save_config()
        
        return new_task
    
    def rename_task(self, task_id: str, new_name: str) -> Optional[Dict]:
        """
        重命名任务
        
        Args:
            task_id: 任务 ID
            new_name: 新名称
            
        Returns:
            重命名后的任务
        """
        return self.update_task(task_id, {"name": new_name})
    
    def archive_task(self, task_id: str) -> Optional[Dict]:
        """
        归档任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            归档后的任务
        """
        return self.update_task(task_id, {"status": "archived"})
    
    def activate_task(self, task_id: str) -> Optional[Dict]:
        """
        激活任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            激活后的任务
        """
        return self.update_task(task_id, {"status": "active"})
    
    def get_active_tasks(self) -> List[Dict]:
        """获取所有活跃任务"""
        tasks = self.get_all_tasks()
        return [t for t in tasks if t.get("status") == "active"]
    
    def get_archived_tasks(self) -> List[Dict]:
        """获取所有归档任务"""
        tasks = self.get_all_tasks()
        return [t for t in tasks if t.get("status") == "archived"]
    
    def search_tasks(self, keyword: str) -> List[Dict]:
        """
        搜索任务
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的任务列表
        """
        tasks = self.get_all_tasks()
        keyword_lower = keyword.lower()
        
        return [t for t in tasks if 
                keyword_lower in t.get("name", "").lower() or
                keyword_lower in t.get("source", "").lower() or
                keyword_lower in t.get("target", "").lower()]
    
    def check_directory_conflict(self, source: str, target: str, 
                                 running_tasks: List[Dict]) -> bool:
        """
        检查目录冲突
        
        Args:
            source: 源目录
            target: 目标目录
            running_tasks: 正在运行的任务列表
            
        Returns:
            是否存在冲突
        """
        for task in running_tasks:
            task_source = task.get("source")
            task_target = task.get("target")
            
            # 检查源目录冲突
            if source == task_source or source == task_target:
                return True
            
            # 检查目标目录冲突
            if target == task_source or target == task_target:
                return True
        
        return False
    
    def get_tasks_using_directory(self, directory: str) -> List[Dict]:
        """
        获取使用指定目录的任务
        
        Args:
            directory: 目录路径
            
        Returns:
            使用该目录的任务列表
        """
        tasks = self.get_all_tasks()
        return [t for t in tasks if 
                t.get("source") == directory or 
                t.get("target") == directory]
    
    def start_task(self, task_info: Dict):
        """
        标记任务为运行中
        
        Args:
            task_info: 任务信息字典，包含任务配置
        """
        task_id = task_info.get("id", task_info.get("name", "unknown"))
        self.running_tasks[task_id] = {
            "id": task_id,
            "name": task_info.get("name", "未命名任务"),
            "source": task_info.get("source", ""),
            "target": task_info.get("target", ""),
            "status": "running",
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "progress": 0,
            "current_file": "",
            "total_files": 0,
            "completed_files": 0,
            "task_config": task_info
        }
    
    def stop_task(self, task_id: str, status: str = "completed"):
        """
        停止运行中的任务
        
        Args:
            task_id: 任务 ID
            status: 停止后的状态 (completed/interrupted/failed)
        """
        if task_id in self.running_tasks:
            self.running_tasks[task_id]["status"] = status
            self.running_tasks[task_id]["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def get_running_tasks(self) -> List[Dict]:
        """
        获取正在运行的任务列表
        
        Returns:
            正在运行的任务列表
        """
        return [task for task in self.running_tasks.values() 
                if task.get("status") == "running"]
    
    def update_task_progress(self, task_id: str, progress: int, 
                            current_file: str = "", 
                            completed_files: int = 0,
                            total_files: int = 0):
        """
        更新任务进度
        
        Args:
            task_id: 任务 ID
            progress: 进度百分比 (0-100)
            current_file: 当前正在同步的文件
            completed_files: 已完成的文件数
            total_files: 总文件数
        """
        if task_id in self.running_tasks:
            self.running_tasks[task_id]["progress"] = progress
            if current_file:
                self.running_tasks[task_id]["current_file"] = current_file
            if completed_files > 0:
                self.running_tasks[task_id]["completed_files"] = completed_files
            if total_files > 0:
                self.running_tasks[task_id]["total_files"] = total_files
    
    def remove_task_from_running(self, task_id: str):
        """
        从运行任务列表中移除任务
        
        Args:
            task_id: 任务 ID
        """
        if task_id in self.running_tasks:
            del self.running_tasks[task_id]
    
    # ===================== v7.5 新增：任务导入导出 =====================
    
    def export_task(self, task_id: str, file_path: str) -> bool:
        """
        导出单个任务为 JSON 配置文件。
        
        Args:
            task_id: 要导出的任务 ID
            file_path: 导出文件路径（.json）
            
        Returns:
            是否导出成功
        """
        task = self.get_task_by_id(task_id)
        if task is None:
            return False
        return self._export_tasks_to_file([task], file_path)
    
    def export_tasks(self, task_ids: List[str], file_path: str) -> bool:
        """
        导出多个任务（按任务 ID 列表）为 JSON 配置文件。

        Args:
            task_ids: 要导出的任务 ID 列表
            file_path: 导出文件路径（.json）

        Returns:
            是否导出成功
        """
        tasks = []
        for task_id in task_ids:
            task = self.get_task_by_id(task_id)
            if task is not None:
                tasks.append(task)
        if not tasks:
            return False
        return self._export_tasks_to_file(tasks, file_path)

    def export_all_tasks(self, file_path: str) -> bool:
        """
        导出所有任务为 JSON 配置文件。
        
        Args:
            file_path: 导出文件路径（.json）
            
        Returns:
            是否导出成功
        """
        tasks = self.get_all_tasks()
        return self._export_tasks_to_file(tasks, file_path)
    
    def _export_tasks_to_file(self, tasks: List[Dict], file_path: str) -> bool:
        """
        将任务列表导出到 JSON 文件。
        
        Args:
            tasks: 任务列表
            file_path: 导出文件路径
            
        Returns:
            是否导出成功
        """
        try:
            export_data = {
                "version": "7.5",
                "exported_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "task_count": len(tasks),
                "tasks": tasks
            }
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ 导出任务失败: {e}")
            return False
    
    def import_tasks(self, file_path: str, replace_existing: bool = False) -> Dict:
        """
        从 JSON 配置文件导入任务。
        
        跨电脑迁移时，任务 ID 会重新生成以避免冲突；
        若同名任务已存在，自动重命名（追加 _imported 后缀）。
        
        Args:
            file_path: 导入文件路径（.json）
            replace_existing: 是否替换同名任务（默认 False，自动重命名）
            
        Returns:
            {"success": bool, "imported": int, "skipped": int, "message": str}
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return {"success": False, "imported": 0, "skipped": 0, "message": "文件不存在"}
            
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 兼容两种格式：直接任务列表 或 {tasks: [...]} 包装
            if isinstance(data, list):
                imported_tasks = data
            elif isinstance(data, dict):
                imported_tasks = data.get("tasks", [])
            else:
                imported_tasks = []
            
            if not imported_tasks:
                return {"success": False, "imported": 0, "skipped": 0, "message": "文件中没有任务"}
            
            existing_tasks = self.get_all_tasks()
            existing_names = {t.get("name") for t in existing_tasks}
            
            imported_count = 0
            skipped_count = 0
            
            for task in imported_tasks:
                # 重新生成 ID，避免跨电脑冲突
                new_task = task.copy()
                new_task["id"] = str(uuid.uuid4())
                new_task["created_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                new_task["last_used"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                new_task.setdefault("status", "active")
                # 清空运行时快照（跨电脑无意义）
                new_task.pop("last_snapshot", None)
                
                # 处理同名任务
                name = new_task.get("name", "未命名任务")
                if name in existing_names:
                    if replace_existing:
                        # 删除同名旧任务
                        existing_tasks = [t for t in existing_tasks if t.get("name") != name]
                        existing_names.discard(name)
                    else:
                        # 自动重命名
                        base_name = name
                        suffix = 1
                        while name in existing_names:
                            name = f"{base_name}_imported{suffix}"
                            suffix += 1
                        new_task["name"] = name
                
                existing_names.add(new_task["name"])
                existing_tasks.append(new_task)
                imported_count += 1
            
            # 保存到配置
            self.config_manager.config["tasks"] = existing_tasks
            self.config_manager.save_config()
            
            return {
                "success": True,
                "imported": imported_count,
                "skipped": skipped_count,
                "message": f"成功导入 {imported_count} 个任务"
            }
        except json.JSONDecodeError:
            return {"success": False, "imported": 0, "skipped": 0, "message": "JSON 格式错误"}
        except Exception as e:
            print(f"❌ 导入任务失败: {e}")
            return {"success": False, "imported": 0, "skipped": 0, "message": str(e)}
    
    # ===================== v7.5 新增：目录冲突检测 =====================
    
    def is_directory_in_use(self, source: str, target: str) -> bool:
        """
        检查源/目标目录是否正在被运行中的任务使用（防止同目录并发同步）。
        
        Args:
            source: 源目录
            target: 目标目录
            
        Returns:
            是否存在冲突（目录正在被使用）
        """
        import os
        source_norm = os.path.normcase(os.path.abspath(source)) if source else ""
        target_norm = os.path.normcase(os.path.abspath(target)) if target else ""
        
        for task in self.get_running_tasks():
            task_source = os.path.normcase(os.path.abspath(task.get("source", ""))) if task.get("source") else ""
            task_target = os.path.normcase(os.path.abspath(task.get("target", ""))) if task.get("target") else ""
            
            if source_norm and (source_norm == task_source or source_norm == task_target):
                return True
            if target_norm and (target_norm == task_source or target_norm == task_target):
                return True
        
        return False