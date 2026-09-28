"""
文件同步工具 v7.0 - 最近删除管理器
负责已删除文件的备份和管理
"""

import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from .config_manager import ConfigManager
from .platform_utils import get_default_recycle_dir


class RecycleManager:
    """最近删除管理器：处理已删除文件的备份和恢复"""
    
    # 默认存储上限（GB）
    DEFAULT_LIMIT_GB = 5.0
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化最近删除管理器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        
        # 使用跨平台用户配置目录下的 recycle 子目录，确保打包后有写权限
        self.recycle_dir = get_default_recycle_dir()
        
        # 确保回收站目录存在
        self.recycle_dir.mkdir(parents=True, exist_ok=True)
    
    def get_limit_gb(self) -> float:
        """获取存储上限（GB）"""
        settings = self.config_manager.get_settings()
        return settings.get("recycle_limit_gb", self.DEFAULT_LIMIT_GB)
    
    def set_limit_gb(self, limit_gb: float):
        """设置存储上限（GB）"""
        settings = self.config_manager.get_settings()
        settings["recycle_limit_gb"] = limit_gb
        settings["recycle_limit_mb"] = int(limit_gb * 1024)
        self.config_manager.update_settings(settings)
    
    def get_limit_mb(self) -> int:
        """获取存储上限（MB）"""
        return int(self.get_limit_gb() * 1024)
    
    def set_limit_mb(self, limit_mb: int):
        """设置存储上限（MB）"""
        self.set_limit_gb(limit_mb / 1024)
    
    def get_current_size_mb(self) -> float:
        """
        获取当前回收站大小（MB）
        
        Returns:
            当前大小（MB）
        """
        return self.get_current_size_gb() * 1024
    
    def get_current_size_gb(self) -> float:
        """
        获取当前回收站大小（GB）
        
        Returns:
            当前大小（GB）
        """
        total_size = 0
        
        try:
            for root, dirs, files in os.walk(self.recycle_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(file_path)
                    except Exception:
                        pass
        except Exception:
            pass
        
        return total_size / (1024 * 1024 * 1024)  # 转换为 GB
    
    def is_over_limit(self) -> bool:
        """检查是否超过存储上限"""
        current_size_gb = self.get_current_size_gb()
        limit_gb = self.get_limit_gb()
        return current_size_gb > limit_gb
    
    def check_limit_and_notify(self) -> bool:
        """
        检查是否超过存储上限并弹出提示
        
        Returns:
            是否超过上限
        """
        if self.is_over_limit():
            self._show_limit_warning()
            return True
        return False
    
    def _show_limit_warning(self):
        """显示存储上限警告弹窗"""
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()
            
            current_size = self.get_current_size_gb()
            limit_size = self.get_limit_gb()
            
            message = (
                f"⚠️ 最近删除文件夹已达到存储上限！\n\n"
                f"当前大小：{current_size:.2f} GB\n"
                f"存储上限：{limit_size:.2f} GB\n\n"
                f"请及时清理最近删除中的文件，否则新删除的文件将无法保存。"
            )
            
            messagebox.showwarning(
                "存储上限警告",
                message
            )
            
            root.destroy()
        except Exception:
            print(f"最近删除已达到存储上限：{current_size:.2f} GB / {limit_size:.2f} GB")
    
    def add_deleted_file(self, original_path: str, file_size: int = None) -> Optional[Dict]:
        """
        添加已删除文件
        
        Args:
            original_path: 原文件路径
            file_size: 文件大小（字节），如果未提供则自动获取
            
        Returns:
            已删除文件记录，如果失败则返回 None
        """
        try:
            # 获取文件信息
            original_file = Path(original_path)
            
            if not original_file.exists():
                return None
            
            # 获取文件大小
            if file_size is None:
                file_size = original_file.stat().st_size
            
            # 获取文件类型
            file_type = original_file.suffix
            
            # 创建备份路径（保持原目录结构）
            # 例如：原路径 E:\folder\file.txt → 备份路径 .recycle\E_folder_file.txt
            from backend.platform_utils import get_path_identifier
            relative_backup_path = get_path_identifier(original_file)
            backup_path = self.recycle_dir / relative_backup_path
            
            # 确保备份目录存在
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 移动文件到回收站
            shutil.move(str(original_file), str(backup_path))
            
            # 创建删除记录
            deleted_file = {
                "id": str(uuid.uuid4()),
                "original_path": original_path,
                "backup_path": str(backup_path),
                "deleted_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "size": file_size,
                "file_type": file_type
            }
            
            # 保存到配置
            self.config_manager.add_deleted_file(deleted_file)
            
            return deleted_file
            
        except Exception as e:
            print(f"添加已删除文件失败: {e}")
            return None
    
    def get_all_deleted_files(self) -> List[Dict]:
        """获取所有已删除文件列表"""
        return self.config_manager.get_deleted_files()
    
    def get_deleted_file_by_id(self, file_id: str) -> Optional[Dict]:
        """根据 ID 获取已删除文件记录"""
        deleted_files = self.get_all_deleted_files()
        for file_info in deleted_files:
            if file_info.get("id") == file_id:
                return file_info
        return None
    
    def restore_deleted_file(self, file_id: str) -> bool:
        """
        恢复已删除文件
        
        Args:
            file_id: 文件 ID
            
        Returns:
            是否成功恢复
        """
        file_info = self.get_deleted_file_by_id(file_id)
        
        if file_info is None:
            return False
        
        try:
            backup_path = Path(file_info["backup_path"])
            original_path = Path(file_info["original_path"])
            
            # 确保原目录存在
            original_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 移动文件回原位置
            shutil.move(str(backup_path), str(original_path))
            
            # 从配置中移除记录
            self.config_manager.remove_deleted_file(file_id)
            
            return True
            
        except Exception as e:
            print(f"恢复文件失败: {e}")
            return False
    
    def permanently_delete_file(self, file_id: str) -> bool:
        """
        永久删除文件
        
        Args:
            file_id: 文件 ID
            
        Returns:
            是否成功删除
        """
        file_info = self.get_deleted_file_by_id(file_id)
        
        if file_info is None:
            return False
        
        try:
            backup_path = Path(file_info["backup_path"])
            
            # 删除备份文件
            if backup_path.exists():
                os.remove(str(backup_path))
            
            # 从配置中移除记录
            self.config_manager.remove_deleted_file(file_id)
            
            return True
            
        except Exception as e:
            print(f"永久删除文件失败: {e}")
            return False
    
    def clear_all_deleted_files(self) -> int:
        """
        清空所有已删除文件
        
        Returns:
            成功删除的文件数量
        """
        deleted_files = self.get_all_deleted_files()
        deleted_count = 0
        
        for file_info in deleted_files:
            try:
                backup_path = Path(file_info["backup_path"])
                
                if backup_path.exists():
                    os.remove(str(backup_path))
                    deleted_count += 1
            except Exception:
                pass
        
        # 清空配置中的记录
        self.config_manager.clear_deleted_files()
        
        return deleted_count
    
    def search_deleted_files(self, keyword: str) -> List[Dict]:
        """
        搜索已删除文件
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的文件列表
        """
        deleted_files = self.get_all_deleted_files()
        keyword_lower = keyword.lower()
        
        return [f for f in deleted_files if
                keyword_lower in Path(f.get("original_path", "")).name.lower() or
                keyword_lower in f.get("deleted_at", "").lower() or
                keyword_lower in f.get("file_type", "").lower()]
    
    def open_backup_directory(self, file_id: str = None) -> bool:
        """
        打开备份目录
        
        Args:
            file_id: 文件 ID（可选，如果提供则打开该文件所在目录）
            
        Returns:
            是否成功打开
        """
        try:
            if file_id:
                file_info = self.get_deleted_file_by_id(file_id)
                if file_info:
                    backup_path = Path(file_info["backup_path"])
                    directory = backup_path.parent
                else:
                    directory = self.recycle_dir
            else:
                directory = self.recycle_dir
            
            # 跨平台打开目录
            import platform
            system = platform.system()
            
            if system == "Windows":
                os.startfile(str(directory))
            elif system == "Darwin":  # macOS
                os.system(f"open '{directory}'")
            else:  # Linux
                os.system(f"xdg-open '{directory}'")
            
            return True
            
        except Exception as e:
            print(f"打开目录失败: {e}")
            return False
    
    def get_deleted_files_by_type(self, file_type: str) -> List[Dict]:
        """
        根据文件类型获取已删除文件
        
        Args:
            file_type: 文件类型（扩展名）
            
        Returns:
            该类型的文件列表
        """
        deleted_files = self.get_all_deleted_files()
        return [f for f in deleted_files if f.get("file_type") == file_type]
    
    def get_deleted_files_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """
        根据日期范围获取已删除文件
        
        Args:
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            
        Returns:
            该日期范围内的文件列表
        """
        deleted_files = self.get_all_deleted_files()
        
        result = []
        for file_info in deleted_files:
            deleted_at = file_info.get("deleted_at", "")
            if deleted_at:
                # 提取日期部分
                file_date = deleted_at.split("T")[0]
                if start_date <= file_date <= end_date:
                    result.append(file_info)
        
        return result