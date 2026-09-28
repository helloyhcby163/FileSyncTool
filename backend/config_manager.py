"""
文件同步工具 v7.5 - 配置管理器
负责配置文件的加载、保存和版本升级

v7.5 新增：
- 日期过滤（按文件修改日期筛选）
- 扩展名过滤（与日期过滤 AND 关系）
- 任务导入导出（JSON 配置文件跨电脑迁移）
- 配置存储路径自定义（默认 %APPDATA%/FileSyncTool/）
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from .platform_utils import get_default_config_dir, get_app_root_dir


class ConfigManager:
    """配置管理器：处理配置文件的读写和版本升级"""
    
    # 配置文件版本
    CURRENT_VERSION = "7.5"
    CONFIG_FILE_NAME = "sync_config_v7_5.json"
    OLD_CONFIG_FILE_NAME = "sync_config_v7_3.json"
    BACKUP_SUFFIX = ".bak"
    # 配置路径指针文件（存储在默认目录，指向自定义配置目录）
    CONFIG_PATH_POINTER = "config_path.json"
    
    # 默认配置
    DEFAULT_CONFIG = {
        "version": "7.5",
        "tasks": [],
        "settings": {
            "language": "zh",
            "scan_workers": 4,
            "sync_workers": 2,
            "recycle_limit_mb": 5120,
            "recycle_limit_gb": 5.0,
            "sync_delete_default": False,
            "theme": "light",
            "auto_check_updates": True,
            "life_protection_enabled": True,
            "usb_level": "auto",
            "protection_strength": "balanced",
            "chunk_size_mb": 8,
        },
        "recent_paths": [],
        "interrupted_tasks": [],
        "deleted_files": [],
        "sync_history": []
    }
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录，默认使用跨平台用户配置目录
                        (Windows: %APPDATA%/FileSyncTool,
                         macOS: ~/Library/Application Support/FileSyncTool,
                         Linux: ~/.config/filesynctool)
                        若默认目录下存在 config_path.json 指针文件，
                        则从该文件读取自定义配置目录。
        """
        # 先确定默认配置目录
        default_dir = Path(get_default_config_dir())
        default_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查是否存在自定义配置路径指针文件
        custom_dir = self._read_config_path_pointer(default_dir)
        if custom_dir:
            config_dir = str(custom_dir)
        elif config_dir is None:
            config_dir = str(default_dir)
        
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / self.CONFIG_FILE_NAME
        
        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 从旧位置迁移配置文件（兼容 v7.2/v7.3 打包前的 data/ 目录）
        self._migrate_from_old_location()
        
        # 加载配置（包含自动升级）
        self.config = self.load_config()
    
    @staticmethod
    def _read_config_path_pointer(default_dir: Path) -> Optional[Path]:
        """
        读取配置路径指针文件，获取自定义配置目录。
        
        Args:
            default_dir: 默认配置目录
            
        Returns:
            自定义配置目录 Path，若不存在或无效则返回 None
        """
        pointer_file = default_dir / ConfigManager.CONFIG_PATH_POINTER
        if not pointer_file.exists():
            return None
        try:
            with open(pointer_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            custom_path = data.get("config_dir")
            if custom_path and os.path.isdir(custom_path):
                return Path(custom_path)
        except Exception:
            pass
        return None
    
    @staticmethod
    def _write_config_path_pointer(default_dir: Path, custom_dir: str):
        """
        写入配置路径指针文件。
        
        Args:
            default_dir: 默认配置目录
            custom_dir: 自定义配置目录
        """
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
            pointer_file = default_dir / ConfigManager.CONFIG_PATH_POINTER
            with open(pointer_file, 'w', encoding='utf-8') as f:
                json.dump({"config_dir": str(custom_dir)}, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    @staticmethod
    def _remove_config_path_pointer(default_dir: Path):
        """移除配置路径指针文件，恢复使用默认目录。"""
        try:
            pointer_file = default_dir / ConfigManager.CONFIG_PATH_POINTER
            if pointer_file.exists():
                pointer_file.unlink()
            return True
        except Exception:
            return False
    
    def _migrate_from_old_location(self):
        """
        从旧的 data/ 目录迁移配置文件到新的用户配置目录
        
        如果新位置尚无配置文件，但旧的 data/ 目录中存在配置，
        则复制过来以保留用户数据。
        """
        if self.config_file.exists():
            return  # 新位置已有配置，无需迁移
        
        # 旧的 data/ 目录（程序根目录下）
        old_data_dir = get_app_root_dir() / "data"
        
        # 优先查找当前版本配置文件
        old_config = old_data_dir / self.CONFIG_FILE_NAME
        if old_config.exists():
            try:
                shutil.copy2(str(old_config), str(self.config_file))
                print(f"已迁移配置文件: {old_config} -> {self.config_file}")
                return
            except Exception as e:
                print(f"迁移配置文件失败: {e}")
        
        # 查找旧版本配置文件（sync_config_v7_2.json 等）
        if old_data_dir.exists():
            for old_file in old_data_dir.glob("sync_config_v7*.json"):
                if not old_file.name.endswith(".bak"):
                    try:
                        shutil.copy2(str(old_file), str(self.config_file))
                        print(f"已迁移旧版配置文件: {old_file} -> {self.config_file}")
                        return
                    except Exception as e:
                        print(f"迁移旧版配置文件失败: {e}")
    
    def load_config(self) -> Dict[str, Any]:
        """
        加载配置文件，自动处理版本升级
        
        Returns:
            配置字典
        """
        # 检查是否存在当前版本配置文件
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 检查版本号
                if config.get("version") == self.CURRENT_VERSION:
                    return config
                else:
                    # 版本不匹配，尝试升级
                    return self._upgrade_config(config)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                return self.DEFAULT_CONFIG.copy()
        
        # 扫描目录查找所有旧版本配置文件
        old_files = self._scan_old_config_files()
        
        if old_files:
            # 按版本号排序，选择最新的旧版本文件
            selected_file = self._select_latest_old_file(old_files)
            if selected_file:
                # 提示用户是否升级
                if self._ask_user_to_upgrade(selected_file):
                    return self._upgrade_from_old_version(selected_file)
        
        # 没有任何配置文件，首次运行：检测系统语言并保存初始配置
        config = self.DEFAULT_CONFIG.copy()
        try:
            from .platform_utils import detect_system_language
            detected_lang = detect_system_language()
            config["settings"]["language"] = detected_lang
            print(f"首次运行，检测到系统语言: {detected_lang}")
        except Exception:
            pass  # 检测失败则使用默认语言
        
        # 保存初始配置以便下次启动直接使用
        self.save_config(config)
        return config
    
    def _scan_old_config_files(self) -> List[Path]:
        """
        扫描配置目录，查找所有旧版本配置文件

        Returns:
            旧版本配置文件列表
        """
        old_files = []
        
        # 扫描当前配置目录
        if self.config_dir.exists():
            for file in self.config_dir.glob("sync_config*.json"):
                if file != self.config_file and not file.name.endswith(".bak"):
                    old_files.append(file)
        
        # 扫描旧的 data/ 目录（兼容 v7.2/v7.3 打包前的配置文件位置）
        old_data_dir = get_app_root_dir() / "data"
        if old_data_dir.exists():
            for file in old_data_dir.glob("sync_config*.json"):
                if file != self.config_file and not file.name.endswith(".bak"):
                    if file not in old_files:
                        old_files.append(file)
        
        return old_files
    
    def _select_latest_old_file(self, old_files: List[Path]) -> Optional[Path]:
        """
        从旧版本配置文件中选择最新的一个
        
        Args:
            old_files: 旧版本配置文件列表
            
        Returns:
            最新的旧版本配置文件，如果无法确定则返回 None
        """
        if not old_files:
            return None
        
        version_map = {}
        for file in old_files:
            version = self._extract_version_from_filename(file.name)
            if version:
                version_map[file] = version
        
        if not version_map:
            return None
        
        # 按版本号降序排序
        sorted_files = sorted(version_map.items(), key=lambda x: x[1], reverse=True)
        return sorted_files[0][0]
    
    def _extract_version_from_filename(self, filename: str) -> Optional[str]:
        """
        从文件名中提取版本号
        
        Args:
            filename: 文件名
            
        Returns:
            版本号字符串，如果无法提取则返回 None
        """
        # 匹配模式：sync_config_vX.json 或 sync_config_vX_Y.json
        import re
        
        # 尝试匹配 sync_config_vX_Y.json 格式
        match = re.match(r'sync_config_v(\d+)(?:_(\d+))?\.json', filename)
        if match:
            major = match.group(1)
            minor = match.group(2) or "0"
            return f"{major}.{minor}"
        
        # 尝试匹配 sync_config.json（没有版本号）
        if filename == "sync_config.json":
            return "1.0"
        
        return None
    
    def _ask_user_to_upgrade(self, old_file: Path) -> bool:
        """
        提示用户是否升级旧版本配置文件
        
        Args:
            old_file: 旧版本配置文件路径
            
        Returns:
            用户是否同意升级
        """
        try:
            # 尝试使用 GUI 对话框
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()
            
            version = self._extract_version_from_filename(old_file.name) or "未知版本"
            
            message = (
                f"检测到旧版本配置文件：\n\n"
                f"文件名：{old_file.name}\n"
                f"版本：v{version}\n\n"
                f"是否升级到 v{self.CURRENT_VERSION}？\n\n"
                f"升级后旧配置文件将被备份，不会丢失数据。"
            )
            
            result = messagebox.askyesno(
                "配置文件升级",
                message,
                icon=messagebox.QUESTION
            )
            
            return result
        except Exception:
            # 如果 GUI 失败，使用命令行提示
            version = self._extract_version_from_filename(old_file.name) or "未知版本"
            
            print(f"\n{'='*50}")
            print(f"检测到旧版本配置文件：")
            print(f"  文件名：{old_file.name}")
            print(f"  版本：v{version}")
            print(f"{'='*50}")
            
            while True:
                answer = input(f"是否升级到 v{self.CURRENT_VERSION}？(y/n): ").strip().lower()
                if answer in ['y', 'yes']:
                    return True
                elif answer in ['n', 'no']:
                    return False
                else:
                    print("请输入 y 或 n")
    
    def _upgrade_from_old_version(self, old_file: Path) -> Dict[str, Any]:
        """
        从旧版本配置文件升级到当前版本
        
        Args:
            old_file: 旧版本配置文件路径
            
        Returns:
            升级后的配置字典
        """
        try:
            # 读取旧配置
            with open(old_file, 'r', encoding='utf-8') as f:
                old_config = json.load(f)
            
            # 获取旧版本号
            old_version = old_config.get("version", self._extract_version_from_filename(old_file.name) or "1.0")
            
            print(f"正在从 v{old_version} 升级到 v{self.CURRENT_VERSION}...")
            
            # 创建新版本配置
            new_config = self.DEFAULT_CONFIG.copy()
            
            # 通用升级逻辑：复制所有可识别的字段
            if "recent_paths" in old_config:
                new_config["recent_paths"] = old_config["recent_paths"]
            
            if "sync_history" in old_config:
                new_config["sync_history"] = old_config["sync_history"]
            
            if "deleted_files" in old_config:
                new_config["deleted_files"] = old_config["deleted_files"]
            
            if "interrupted_tasks" in old_config:
                new_config["interrupted_tasks"] = old_config["interrupted_tasks"]
            
            # 处理任务转换
            if "saved_tasks" in old_config:
                new_config["tasks"] = self._convert_v6_tasks_to_v7(old_config["saved_tasks"])
            elif "tasks" in old_config:
                new_config["tasks"] = self._convert_old_tasks(old_config["tasks"])
            
            # 处理设置
            if "settings" in old_config:
                old_settings = old_config["settings"]
                if "language" in old_settings:
                    new_config["settings"]["language"] = old_settings["language"]
                if "max_workers" in old_settings:
                    new_config["settings"]["max_workers"] = old_settings["max_workers"]
                if "recycle_limit_mb" in old_settings:
                    new_config["settings"]["recycle_limit_mb"] = old_settings["recycle_limit_mb"]
                if "theme" in old_settings:
                    new_config["settings"]["theme"] = old_settings["theme"]
                if "auto_check_updates" in old_settings:
                    new_config["settings"]["auto_check_updates"] = old_settings["auto_check_updates"]
            
            # 处理顶级设置（旧版本可能没有 settings 嵌套）
            if "max_workers" in old_config and "settings" not in old_config:
                new_config["settings"]["scan_workers"] = old_config["max_workers"]
                new_config["settings"]["sync_workers"] = max(2, old_config["max_workers"] // 2)
            
            # 保存新版本配置
            self.save_config(new_config)
            
            # 备份旧配置文件
            backup_file = old_file.parent / (old_file.name + self.BACKUP_SUFFIX)
            shutil.move(str(old_file), str(backup_file))
            
            print(f"✅ 配置文件已成功升级到 v{self.CURRENT_VERSION}")
            print(f"   原配置文件已备份为: {backup_file.name}")
            
            return new_config
            
        except Exception as e:
            print(f"配置升级失败: {e}")
            return self.DEFAULT_CONFIG.copy()
    
    def _convert_old_tasks(self, old_tasks: List[Dict]) -> List[Dict]:
        """
        将旧版本任务格式转换为当前格式
        
        Args:
            old_tasks: 旧版本任务列表
            
        Returns:
            转换后的任务列表
        """
        new_tasks = []
        
        for task in old_tasks:
            new_task = task.copy()
            
            # 处理字段重命名
            if "run_mode" in new_task and "mode" not in new_task:
                new_task["mode"] = new_task.pop("run_mode")
            
            # 处理多线程字段拆分（兼容旧格式）
            if "use_multithreading" in new_task:
                use_multi = new_task["use_multithreading"]
                if "use_multithreading_scan" not in new_task:
                    new_task["use_multithreading_scan"] = use_multi
                if "use_multithreading_copy" not in new_task:
                    new_task["use_multithreading_copy"] = False
            
            new_tasks.append(new_task)
        
        return new_tasks
    
    def _upgrade_from_v6(self, old_config_file: Path) -> Dict[str, Any]:
        """
        从 v6 配置文件升级到 v7
        
        Args:
            old_config_file: v6 配置文件路径
            
        Returns:
            升级后的 v7 配置字典
        """
        try:
            # 读取 v6 配置
            with open(old_config_file, 'r', encoding='utf-8') as f:
                v6_config = json.load(f)
            
            # 创建 v7 配置
            v7_config = self.DEFAULT_CONFIG.copy()
            
            # 转换 recent_paths
            if "recent_paths" in v6_config:
                v7_config["recent_paths"] = v6_config["recent_paths"]
            
            # 转换 saved_tasks → tasks
            if "saved_tasks" in v6_config:
                v7_config["tasks"] = self._convert_v6_tasks_to_v7(v6_config["saved_tasks"])
            
            # 转换 sync_history
            if "sync_history" in v6_config:
                v7_config["sync_history"] = v6_config["sync_history"]
            
            # 转换 settings
            if "max_workers" in v6_config:
                v7_config["settings"]["scan_workers"] = v6_config["max_workers"]
                v7_config["settings"]["sync_workers"] = max(2, v6_config["max_workers"] // 2)
            
            # 保存 v7 配置
            self.save_config(v7_config)
            
            # 重命名 v6 配置文件为备份
            backup_file = old_config_file.parent / (old_config_file.name + self.BACKUP_SUFFIX)
            shutil.move(str(old_config_file), str(backup_file))
            
            print(f"✅ 配置文件已成功升级到 v7.0")
            print(f"   原配置文件已备份为: {backup_file.name}")
            
            return v7_config
            
        except Exception as e:
            print(f"配置升级失败: {e}")
            return self.DEFAULT_CONFIG.copy()
    
    def _convert_v6_tasks_to_v7(self, v6_tasks: List[Dict]) -> List[Dict]:
        """
        将 v6 任务格式转换为 v7 格式
        
        Args:
            v6_tasks: v6 任务列表
            
        Returns:
            v7 任务列表
        """
        v7_tasks = []
        
        for v6_task in v6_tasks:
            # 创建 v7 任务
            v7_task = {
                "id": self._generate_uuid(),
                "name": v6_task.get("name", "未命名任务"),
                "source": v6_task.get("source", ""),
                "target": v6_task.get("target", ""),
                "mode": v6_task.get("mode", "fast"),
                "sync_direction": "both",  # v6 默认双向同步
                "folders": v6_task.get("selected_folders", []),
                "default_strategy": v6_task.get("default_strategy", "conservative"),
                "folder_strategies": v6_task.get("folder_strategies", {}),
                "root_included": v6_task.get("root_included", False),
                "root_strategy": v6_task.get("root_strategy", "conservative"),
                "created_at": v6_task.get("created", datetime.now().strftime("%Y-%m-%dT%H:%M:%S")),
                "last_used": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "status": "active"
            }
            
            v7_tasks.append(v7_task)
        
        return v7_tasks
    
    def _upgrade_config(self, old_config: Dict) -> Dict:
        """
        升级旧版本配置到当前版本
        
        Args:
            old_config: 旧版本配置
            
        Returns:
            升级后的配置
        """
        version = old_config.get("version", "unknown")
        
        if version.startswith("6"):
            return self._upgrade_from_v6_dict(old_config)
        elif version == "7.0":
            return self._upgrade_from_v7_0(old_config)
        elif version == "7.1":
            return self._upgrade_from_v7_1(old_config)
        elif version == "7.2":
            return self._upgrade_from_v7_2(old_config)
        elif version == "7.3":
            return self._upgrade_from_v7_3(old_config)
        
        # 未知版本，使用默认配置
        return self.DEFAULT_CONFIG.copy()
    
    def _upgrade_from_v7_0(self, v7_0_config: Dict) -> Dict:
        """
        从 v7.0 配置升级到 v7.3
        
        Args:
            v7_0_config: v7.0 配置字典
            
        Returns:
            升级后的 v7.3 配置字典
        """
        v7_3_config = self.DEFAULT_CONFIG.copy()
        
        # 复制所有现有配置
        for key, value in v7_0_config.items():
            if key != "version":
                v7_3_config[key] = value
        
        # 确保 settings 包含新配置项
        if "settings" not in v7_3_config:
            v7_3_config["settings"] = {}
        
        settings = v7_3_config["settings"]
        default_settings = self.DEFAULT_CONFIG["settings"]
        
        # 添加新的配置项（如果不存在）
        settings.setdefault("life_protection_enabled", default_settings["life_protection_enabled"])
        settings.setdefault("usb_level", default_settings["usb_level"])
        settings.setdefault("protection_strength", default_settings["protection_strength"])
        
        # 将 max_workers 拆分为 scan_workers 和 sync_workers
        if "max_workers" in settings and "scan_workers" not in settings:
            settings["scan_workers"] = settings["max_workers"]
        if "max_workers" in settings and "sync_workers" not in settings:
            settings["sync_workers"] = max(2, settings["max_workers"] // 2)
        
        settings.setdefault("scan_workers", default_settings["scan_workers"])
        settings.setdefault("sync_workers", default_settings["sync_workers"])
        
        # 添加 v7.2 新配置项
        settings.setdefault("recycle_limit_gb", default_settings["recycle_limit_gb"])
        settings.setdefault("sync_delete_default", default_settings["sync_delete_default"])
        
        # 添加 v7.3 新配置项
        settings.setdefault("chunk_size_mb", default_settings["chunk_size_mb"])
        
        v7_3_config["settings"] = settings
        v7_3_config["version"] = self.CURRENT_VERSION
        
        return v7_3_config
    
    def _upgrade_from_v7_1(self, v7_1_config: Dict) -> Dict:
        """
        从 v7.1 配置升级到 v7.3
        
        Args:
            v7_1_config: v7.1 配置字典
            
        Returns:
            升级后的 v7.3 配置字典
        """
        v7_3_config = self.DEFAULT_CONFIG.copy()
        
        # 复制所有现有配置
        for key, value in v7_1_config.items():
            if key != "version":
                v7_3_config[key] = value
        
        # 确保 settings 包含新配置项
        if "settings" not in v7_3_config:
            v7_3_config["settings"] = {}
        
        settings = v7_3_config["settings"]
        default_settings = self.DEFAULT_CONFIG["settings"]
        
        # 添加 v7.2 新配置项（如果不存在）
        settings.setdefault("recycle_limit_gb", default_settings["recycle_limit_gb"])
        settings.setdefault("sync_delete_default", default_settings["sync_delete_default"])
        
        # 如果存在旧的 recycle_limit_mb，转换为 recycle_limit_gb
        if "recycle_limit_mb" in settings and "recycle_limit_gb" not in settings:
            settings["recycle_limit_gb"] = settings["recycle_limit_mb"] / 1024
        
        # 添加 v7.3 新配置项
        settings.setdefault("chunk_size_mb", default_settings["chunk_size_mb"])
        
        v7_3_config["settings"] = settings
        v7_3_config["version"] = self.CURRENT_VERSION
        
        return v7_3_config
    
    def _upgrade_from_v7_2(self, v7_2_config: Dict) -> Dict:
        """
        从 v7.2 配置升级到 v7.5
        
        v7.3 新增 chunk_size_mb 配置项（分块复制块大小，默认 8MB）
        
        Args:
            v7_2_config: v7.2 配置字典
            
        Returns:
            升级后的 v7.5 配置字典
        """
        v7_5_config = self.DEFAULT_CONFIG.copy()
        
        # 复制所有现有配置
        for key, value in v7_2_config.items():
            if key != "version":
                v7_5_config[key] = value
        
        # 确保 settings 包含新配置项
        if "settings" not in v7_5_config:
            v7_5_config["settings"] = {}
        
        settings = v7_5_config["settings"]
        default_settings = self.DEFAULT_CONFIG["settings"]
        
        # 添加 v7.3 新配置项
        settings.setdefault("chunk_size_mb", default_settings["chunk_size_mb"])
        
        v7_5_config["settings"] = settings
        v7_5_config["version"] = self.CURRENT_VERSION
        
        return v7_5_config
    
    def _upgrade_from_v7_3(self, v7_3_config: Dict) -> Dict:
        """
        从 v7.3 配置升级到 v7.5
        
        v7.5 新增日期过滤、扩展名过滤配置项（默认关闭，向后兼容）
        
        Args:
            v7_3_config: v7.3 配置字典
            
        Returns:
            升级后的 v7.5 配置字典
        """
        v7_5_config = self.DEFAULT_CONFIG.copy()
        
        # 复制所有现有配置
        for key, value in v7_3_config.items():
            if key != "version":
                v7_5_config[key] = value
        
        # 确保 settings 包含新配置项
        if "settings" not in v7_5_config:
            v7_5_config["settings"] = {}
        
        settings = v7_5_config["settings"]
        
        v7_5_config["settings"] = settings
        v7_5_config["version"] = self.CURRENT_VERSION
        
        # 保存升级后的配置
        self.save_config(v7_5_config)
        
        return v7_5_config
    
    def _upgrade_from_v6_dict(self, v6_config: Dict) -> Dict:
        """
        从 v6 配置字典升级（不涉及文件操作）
        
        Args:
            v6_config: v6 配置字典
            
        Returns:
            v7.1 配置字典
        """
        v7_config = self.DEFAULT_CONFIG.copy()
        
        # 转换各个字段
        if "recent_paths" in v6_config:
            v7_config["recent_paths"] = v6_config["recent_paths"]
        
        if "saved_tasks" in v6_config:
            v7_config["tasks"] = self._convert_v6_tasks_to_v7(v6_config["saved_tasks"])
        
        if "sync_history" in v6_config:
            v7_config["sync_history"] = v6_config["sync_history"]
        
        if "max_workers" in v6_config:
            v7_config["settings"]["max_workers"] = v6_config["max_workers"]
        
        v7_config["version"] = self.CURRENT_VERSION
        
        return v7_config
    
    def save_config(self, config: Optional[Dict] = None):
        """
        保存配置文件
        
        Args:
            config: 要保存的配置字典，默认为当前配置
        """
        if config is None:
            config = self.config
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def _generate_uuid(self) -> str:
        """
        生成唯一 ID
        
        Returns:
            UUID 字符串
        """
        import uuid
        return str(uuid.uuid4())
    
    def get_tasks(self) -> List[Dict]:
        """获取所有任务"""
        return self.config.get("tasks", [])
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict]:
        """根据 ID 获取任务"""
        for task in self.config.get("tasks", []):
            if task.get("id") == task_id:
                return task
        return None
    
    def get_task_by_name(self, task_name: str) -> Optional[Dict]:
        """根据名称获取任务"""
        for task in self.config.get("tasks", []):
            if task.get("name") == task_name:
                return task
        return None
    
    def get_settings(self) -> Dict:
        """获取设置"""
        return self.config.get("settings", self.DEFAULT_CONFIG["settings"])
    
    def update_settings(self, settings: Dict):
        """更新设置"""
        self.config["settings"] = settings
        self.save_config()
    
    def get_recent_paths(self) -> List[str]:
        """获取最近使用的路径"""
        return self.config.get("recent_paths", [])
    
    def add_recent_path(self, path: str):
        """添加最近使用的路径"""
        recent_paths = self.config.get("recent_paths", [])
        
        # 移除已存在的路径
        if path in recent_paths:
            recent_paths.remove(path)
        
        # 添加到开头
        recent_paths.insert(0, path)
        
        # 保留最近 10 个
        recent_paths = recent_paths[:10]
        
        self.config["recent_paths"] = recent_paths
        self.save_config()
    
    def get_interrupted_tasks(self) -> List[Dict]:
        """获取被打断的任务列表"""
        return self.config.get("interrupted_tasks", [])
    
    def add_interrupted_task(self, task_info: Dict):
        """添加打断任务"""
        interrupted_tasks = self.config.get("interrupted_tasks", [])
        interrupted_tasks.append(task_info)
        self.config["interrupted_tasks"] = interrupted_tasks
        self.save_config()
    
    def remove_interrupted_task(self, task_id: str):
        """移除打断任务"""
        interrupted_tasks = self.config.get("interrupted_tasks", [])
        interrupted_tasks = [t for t in interrupted_tasks if t.get("id") != task_id]
        self.config["interrupted_tasks"] = interrupted_tasks
        self.save_config()
    
    def get_deleted_files(self) -> List[Dict]:
        """获取已删除文件列表"""
        return self.config.get("deleted_files", [])
    
    def add_deleted_file(self, file_info: Dict):
        """添加已删除文件记录"""
        deleted_files = self.config.get("deleted_files", [])
        deleted_files.append(file_info)
        self.config["deleted_files"] = deleted_files
        self.save_config()
    
    def remove_deleted_file(self, file_id: str):
        """移除已删除文件记录"""
        deleted_files = self.config.get("deleted_files", [])
        deleted_files = [f for f in deleted_files if f.get("id") != file_id]
        self.config["deleted_files"] = deleted_files
        self.save_config()
    
    def clear_deleted_files(self):
        """清空已删除文件列表"""
        self.config["deleted_files"] = []
        self.save_config()
    
    def get_sync_history(self) -> List[Dict]:
        """获取同步历史"""
        return self.config.get("sync_history", [])
    
    def add_sync_history(self, history_entry: Dict):
        """添加同步历史记录"""
        sync_history = self.config.get("sync_history", [])
        sync_history.append(history_entry)
        
        # 保留最近 10 条
        sync_history = sync_history[-10:]
        
        self.config["sync_history"] = sync_history
        self.save_config()
    
    def get_language(self) -> str:
        """获取当前语言设置"""
        settings = self.get_settings()
        return settings.get("language", "zh")
    
    def set_language(self, language: str):
        """设置语言"""
        settings = self.get_settings()
        settings["language"] = language
        self.update_settings(settings)
    
    def reset_to_default(self):
        """
        重置所有配置为默认值
        
        保留版本号，清除所有任务、历史、打断任务、删除文件记录，
        将设置恢复为默认值并保存。
        """
        self.config = self.DEFAULT_CONFIG.copy()
        self.save_config()
    
    def get_theme(self) -> str:
        """获取主题设置"""
        settings = self.get_settings()
        return settings.get("theme", "system")
    
    def set_theme(self, theme: str):
        """设置主题"""
        settings = self.get_settings()
        settings["theme"] = theme
        self.update_settings(settings)
    
    # ===================== v7.5 新增：配置路径自定义 =====================
    
    def get_config_dir(self) -> str:
        """获取当前配置文件存储目录的绝对路径。"""
        return str(self.config_dir)
    
    def set_custom_config_dir(self, new_dir: str) -> bool:
        """
        将配置文件迁移到自定义目录，并写入指针文件以便下次启动识别。
        
        Args:
            new_dir: 目标配置目录（绝对路径）
            
        Returns:
            是否迁移成功
        """
        try:
            new_dir_path = Path(new_dir)
            new_dir_path.mkdir(parents=True, exist_ok=True)
            
            # 复制当前配置文件到新目录
            if self.config_file.exists():
                shutil.copy2(str(self.config_file), str(new_dir_path / self.CONFIG_FILE_NAME))
            
            # 写入指针文件到默认目录
            default_dir = Path(get_default_config_dir())
            self._write_config_path_pointer(default_dir, str(new_dir_path))
            
            # 更新当前实例的路径
            self.config_dir = new_dir_path
            self.config_file = self.config_dir / self.CONFIG_FILE_NAME
            
            print(f"✅ 配置目录已切换到: {self.config_dir}")
            return True
        except Exception as e:
            print(f"❌ 切换配置目录失败: {e}")
            return False
    
    def reset_config_dir_to_default(self) -> bool:
        """
        将配置目录恢复为默认目录，移除指针文件。
        
        Returns:
            是否恢复成功
        """
        try:
            default_dir = Path(get_default_config_dir())
            default_dir.mkdir(parents=True, exist_ok=True)
            
            # 如果当前配置不在默认目录，将配置复制回默认目录
            if self.config_file.exists() and self.config_dir != default_dir:
                shutil.copy2(str(self.config_file), str(default_dir / self.CONFIG_FILE_NAME))
            
            # 移除指针文件
            self._remove_config_path_pointer(default_dir)
            
            # 更新当前实例路径
            self.config_dir = default_dir
            self.config_file = self.config_dir / self.CONFIG_FILE_NAME
            
            print(f"✅ 配置目录已恢复为默认: {self.config_dir}")
            return True
        except Exception as e:
            print(f"❌ 恢复默认配置目录失败: {e}")
            return False