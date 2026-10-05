"""
文件同步工具 v7.3 - 同步引擎
提供核心文件同步功能，支持进度回调、中断恢复、多线程复制和写入寿命保护
v7.3 性能优化：大文件分块复制（可配置块大小、内部断点续传）、批量预创建目录、块级寿命保护
"""

import os
import shutil
import time
import json
import ctypes
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum

# 冲突策略常量
class ConflictStrategy(Enum):
    """冲突处理策略"""
    CONSERVATIVE = "conservative"      # 保守模式：不覆盖已有文件
    NEWEST_WINS = "newest_wins"        # 时间优先模式：保留修改时间更新的文件
    SOURCE_WINS = "source_wins"        # 源目录优先：强制用源目录文件覆盖目标
    TARGET_WINS = "target_wins"        # 目标目录优先：保留目标目录文件
    SKIP = "skip"                       # 跳过模式：不同步该文件夹


# 同步方向
class SyncDirection(Enum):
    """同步方向"""
    BOTH = "both"                      # 双向同步
    SOURCE_TO_TARGET = "source_to_target"  # 单向：源到目标
    TARGET_TO_SOURCE = "target_to_source"  # 单向：目标到源


# 同步模式
class SyncMode(Enum):
    """同步模式"""
    FAST = "fast"    # 快速模式：多线程
    SAFE = "safe"    # 安全模式：单线程


# USB档位配置
USB_LEVEL_CONFIG = {
    "low": {
        "name": "老旧U盘",
        "time_threshold": 120,
        "size_threshold": 1 * 1024 * 1024 * 1024,
        "initial_pause_time": 60,
        "speed_threshold_low": 0,
        "speed_threshold_high": 30 * 1024 * 1024
    },
    "medium": {
        "name": "普通U盘",
        "time_threshold": 300,
        "size_threshold": 4 * 1024 * 1024 * 1024,
        "initial_pause_time": 45,
        "speed_threshold_low": 30 * 1024 * 1024,
        "speed_threshold_high": 100 * 1024 * 1024
    },
    "high": {
        "name": "高速U盘",
        "time_threshold": 600,
        "size_threshold": 10 * 1024 * 1024 * 1024,
        "initial_pause_time": 30,
        "speed_threshold_low": 100 * 1024 * 1024,
        "speed_threshold_high": float('inf')
    },
    "auto": {
        "name": "自动检测",
        "time_threshold": 300,
        "size_threshold": 4 * 1024 * 1024 * 1024,
        "initial_pause_time": 45,
        "speed_threshold_low": 0,
        "speed_threshold_high": float('inf')
    }
}

# 保护强度乘数
PROTECTION_STRENGTH_MULTIPLIER = {
    "aggressive": 0.7,
    "balanced": 1.0,
    "conservative": 1.5
}


def is_removable_disk(path: str) -> bool:
    """
    检测路径是否在可移动磁盘上（跨平台）
    
    Args:
        path: 文件路径
        
    Returns:
        是否为可移动磁盘
    """
    from backend.platform_utils import is_removable_disk as platform_is_removable
    return platform_is_removable(path)


# 临时文件后缀（用于事务性复制）
TEMP_FILE_SUFFIX = ".sync.tmp"
# 进度文件名称
PROGRESS_FILE = ".sync_progress.json"


@dataclass
class SyncStats:
    """同步统计信息"""
    files_scanned: int = 0
    files_copied: int = 0
    files_updated: int = 0
    files_skipped: int = 0
    total_size_copied: int = 0
    errors: List[tuple] = field(default_factory=list)
    permission_denied: List[str] = field(default_factory=list)
    skipped_system_files: List[str] = field(default_factory=list)
    
    # 性能统计
    scan_time: float = 0.0
    copy_time: float = 0.0
    total_time: float = 0.0
    
    # 速度统计
    avg_speed: float = 0.0
    max_speed: float = 0.0
    min_speed: float = 0.0
    speed_samples: int = 0


@dataclass
class SyncProgress:
    """同步进度信息"""
    current_file: str = ""
    current_phase: str = ""  # "scanning" | "copying" | "finishing"
    total_files: int = 0
    completed_files: int = 0
    total_size: int = 0
    copied_size: int = 0
    percentage: float = 0.0
    elapsed_time: float = 0.0
    estimated_remaining: float = 0.0
    speed: float = 0.0  # bytes/秒


@dataclass
class SyncPreview:
    """同步预览信息"""
    files_to_copy_source_to_target: List[str] = field(default_factory=list)
    files_to_copy_target_to_source: List[str] = field(default_factory=list)
    reasons_source_to_target: List[str] = field(default_factory=list)
    reasons_target_to_source: List[str] = field(default_factory=list)
    total_files: int = 0
    total_size: int = 0
    estimated_time: float = 0.0
    scan_time: float = 0.0
    copy_time: float = 0.0
    speed_mbps: float = 0.0


class ProgressManager:
    """进度管理器：保存/恢复同步进度"""
    
    def __init__(self, target_dir: str):
        self.progress_file = os.path.join(target_dir, PROGRESS_FILE)
        self.last_save_time = time.time()
        self.files_since_last_save = 0
        self.completed_files: Set[str] = set()
        self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 每10个文件或每5秒保存一次
        self.save_interval_files = 10
        self.save_interval_seconds = 5.0
    
    def load_progress(self) -> Optional[Dict]:
        """加载已保存的进度"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data
            except Exception:
                pass
        return None
    
    def save_progress(self, completed_files: Set[str], total_files: Optional[int] = None):
        """保存当前进度"""
        progress_data = {
            "session_id": self.current_session_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "completed_files": list(completed_files),
            "total_completed": len(completed_files),
            "total_files": total_files
        }
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
            self.last_save_time = time.time()
            self.files_since_last_save = 0
        except Exception as e:
            print(f"  ⚠️  保存进度失败: {e}")
    
    def should_save(self) -> bool:
        """检查是否需要保存进度"""
        self.files_since_last_save += 1
        current_time = time.time()
        
        if self.files_since_last_save >= self.save_interval_files:
            return True
        if current_time - self.last_save_time >= self.save_interval_seconds:
            return True
        return False
    
    def clear_progress(self):
        """清除进度文件"""
        if os.path.exists(self.progress_file):
            try:
                os.remove(self.progress_file)
            except Exception:
                pass


class FileSyncEngine:
    """
    文件同步引擎
    
    核心同步逻辑，支持：
    - 多种冲突策略
    - 多线程同步（扫描和复制独立控制）
    - 进度回调
    - 中断恢复
    - 事务性复制
    - 写入寿命保护
    - v7.5: 按文件夹的筛选策略（日期过滤 + 扩展名过滤，仅对配置了的文件夹生效）
    """
    
    # 类级别的活动同步目录集合，用于检测同目录并发同步
    _active_sync_dirs: Set[str] = set()
    _active_sync_dirs_lock = threading.Lock()
    
    def __init__(
        self,
        mode: str = "safe",
        use_multithreading_scan: bool = True,
        use_multithreading_copy: bool = False,
        scan_workers: int = 4,
        sync_workers: int = 2,
        default_strategy: str = "conservative",
        folder_strategies: Optional[Dict[str, str]] = None,
        root_included: bool = False,
        root_strategy: str = "conservative",
        life_protection_enabled: bool = True,
        usb_level: str = "medium",
        protection_strength: str = "balanced",
        sync_delete_enabled: bool = False,
        recycle_manager=None,
        chunk_size: int = 8 * 1024 * 1024,
        # ===== v7.5 筛选策略（任务级配置：每个文件夹独立，未配置的文件夹不启用筛选）=====
        folder_filters: Optional[Dict[str, Dict]] = None,
        # ===== v7.6 静默模式（命令行 --silent）：抑制 info 级日志 =====
        quiet: bool = False,
        # ===== v7.6 同步期间阻止系统休眠（含寿命保护暂停期间）=====
        prevent_sleep_during_sync: bool = True,
    ):
        """
        初始化同步引擎

        Args:
            mode: 同步模式 ("fast" 或 "safe")
            use_multithreading_scan: 是否使用多线程扫描
            use_multithreading_copy: 是否使用多线程复制
            scan_workers: 扫描线程数
            sync_workers: 同步线程数
            default_strategy: 默认冲突策略
            folder_strategies: 文件夹策略字典
            root_included: 是否包含根目录文件
            root_strategy: 根目录策略
            life_protection_enabled: 是否启用写入寿命保护
            usb_level: U盘档位 ("low", "medium", "high", "auto")
            protection_strength: 保护强度 ("aggressive", "balanced", "conservative")
            sync_delete_enabled: 是否启用同步删除功能
            recycle_manager: 回收站管理器实例（用于删除文件时移入回收站）
            chunk_size: 大文件分块复制的块大小（字节，默认 8MB）
            folder_filters: 按文件夹的筛选策略字典（扩展名过滤 + 日期过滤），
                键为顶层文件夹名，值为筛选配置：
                {"date_filter_enabled": bool, "date_start": "YYYY-MM-DD", "date_end": "YYYY-MM-DD",
                 "extension_filter_enabled": bool, "extension_filter_mode": "include"/"exclude",
                 "extension_filter_list": [".txt", ".pdf"]}
                未出现在字典中的文件夹不启用筛选（同步全部文件）
        """
        self.mode = mode
        self.use_multithreading_scan = use_multithreading_scan
        self.use_multithreading_copy = use_multithreading_copy
        self.scan_workers = scan_workers
        self.sync_workers = sync_workers
        self.default_strategy = default_strategy
        self.folder_strategies = folder_strategies or {}
        self.root_included = root_included
        self.root_strategy = root_strategy
        
        # 寿命保护配置
        self.life_protection_enabled = life_protection_enabled
        self.usb_level = usb_level
        self.protection_strength = protection_strength
        
        # 同步删除配置
        self.sync_delete_enabled = sync_delete_enabled

        self.recycle_manager = recycle_manager
        
        # 分块复制块大小（字节）
        self.chunk_size = max(1024, chunk_size)  # 最小 1KB
        
        # ===== v7.5 筛选策略（按文件夹独立配置）=====
        self.folder_filters = self._normalize_folder_filters(folder_filters)

        # v7.6：静默模式（仅命令行 --silent 使用）
        self.quiet = quiet
        # v7.6：同步全程阻止系统休眠（寿命保护暂停期间同样保持，结束后在 finally 恢复）
        self.prevent_sleep_during_sync = prevent_sleep_during_sync
        # v7.6：逐文件日志节流状态（每 100 个文件或每 2 秒最多输出一条汇总）
        self._file_log_pending = 0
        self._file_log_last_emit = 0.0
        self._file_log_last_msg = ""
        self._file_log_batch = 100
        self._file_log_interval = 2.0
        
        # 统计信息
        self.stats = SyncStats()
        
        # 进度管理
        self.progress_manager: Optional[ProgressManager] = None
        self.completed_files: Set[str] = set()
        self.total_files_to_sync = 0
        
        # 中断控制
        self._interrupted = False
        self._paused = False
        
        # 进度回调
        self._progress_callback: Optional[Callable[[SyncProgress], None]] = None
        self._log_callback: Optional[Callable[[str], None]] = None
        
        # 实测速度记录（bytes/秒）
        self.actual_speeds: List[float] = []
        self._current_copy_start_time: float = 0
        self._current_copy_bytes: int = 0
        
        # 同步开始时间
        self._start_time: float = 0
        
        # 配置管理器引用（用于保存历史速度）
        self.config_manager = None
        
        # 当前进度信息
        self._current_progress = SyncProgress()
        
        # 寿命保护状态
        self._life_protection_active = False
        self._continuous_write_time = 0.0
        self._continuous_write_size = 0
        self._pause_count = 0
        self._last_write_time = 0.0
        self._target_is_removable = False
        self._pause_start_time = 0.0
        self._current_pause_duration = 0.0
        
        # 寿命保护配置回调（用于动态更新配置）
        self._life_protection_config_callback: Optional[Callable[[], Dict[str, Any]]] = None
        
        # 文件快照（记录上次同步时的文件列表）
        self.last_snapshot = None
    
    def set_progress_callback(self, callback: Optional[Callable[[SyncProgress], None]]):
        """
        设置进度回调函数
        
        Args:
            callback: 回调函数，接收 SyncProgress 对象
        """
        self._progress_callback = callback
    
    def is_running(self) -> bool:
        """
        检查同步引擎是否正在运行
        
        Returns:
            是否正在运行
        """
        return not self._interrupted
    
    def get_current_progress(self) -> SyncProgress:
        """
        获取当前进度信息
        
        Returns:
            当前进度信息
        """
        return self._current_progress
    
    def get_total_files(self) -> int:
        """
        获取总文件数
        
        Returns:
            总文件数
        """
        return self._current_progress.total_files
    
    def get_completed_files(self) -> int:
        """
        获取已完成文件数
        
        Returns:
            已完成文件数
        """
        return self._current_progress.completed_files

    def set_log_callback(self, callback: Optional[Callable[[str], None]]):
        """
        设置日志回调函数
        
        Args:
            callback: 回调函数，接收日志消息字符串
        """
        self._log_callback = callback
    
    def set_life_protection_config_callback(self, callback: Callable[[], Dict[str, Any]]):
        """
        设置寿命保护配置回调函数，用于动态更新配置
        
        Args:
            callback: 返回配置字典的回调函数
        """
        self._life_protection_config_callback = callback
    
    def update_life_protection_config(self, enabled: bool, usb_level: str, protection_strength: str):
        """
        动态更新寿命保护配置
        
        Args:
            enabled: 是否启用
            usb_level: U盘档位
            protection_strength: 保护强度
        """
        self.life_protection_enabled = enabled
        self.usb_level = usb_level
        self.protection_strength = protection_strength
    
    def _auto_detect_usb_level(self, write_speed: float) -> str:
        """
        根据写入速度自动检测U盘档位
        
        Args:
            write_speed: 当前写入速度（bytes/秒）
            
        Returns:
            U盘档位 ("low", "medium", "high")
        """
        if write_speed < 30 * 1024 * 1024:
            return "low"
        elif write_speed < 100 * 1024 * 1024:
            return "medium"
        else:
            return "high"
    
    def _check_life_protection(self, file_size: int):
        """
        检查是否需要触发寿命保护暂停
        
        Args:
            file_size: 本次写入的文件大小，0表示仅检查状态
            
        Returns:
            需要暂停的秒数，如果不需要暂停返回0
        """
        if not self.life_protection_enabled or not self._target_is_removable:
            return 0
        
        current_time = time.time()
        
        if self._last_write_time > 0:
            time_since_last_write = current_time - self._last_write_time
            if time_since_last_write > 60:
                self._continuous_write_time = 0
                self._continuous_write_size = 0
        
        if self._last_write_time > 0:
            self._continuous_write_time = current_time - self._last_write_time
        
        if file_size > 0:
            self._continuous_write_size += file_size
            self._last_write_time = current_time
        
        current_usb_level = self.usb_level
        if self.usb_level == "auto" and self._current_progress.speed > 0:
            current_usb_level = self._auto_detect_usb_level(self._current_progress.speed)
        
        config = USB_LEVEL_CONFIG.get(current_usb_level, USB_LEVEL_CONFIG["medium"])
        strength_multiplier = PROTECTION_STRENGTH_MULTIPLIER.get(self.protection_strength, 1.0)
        
        time_threshold = config["time_threshold"]
        size_threshold = config["size_threshold"]
        initial_pause_time = config["initial_pause_time"] * strength_multiplier
        
        if (self._continuous_write_time >= time_threshold or 
            self._continuous_write_size >= size_threshold):
            
            self._pause_count += 1
            
            base_time = config["time_threshold"]
            pause_factor = min((self._continuous_write_time / base_time) * 0.5, 2.0)
            pause_duration = initial_pause_time * (1 + pause_factor)
            
            self._continuous_write_time = 0
            self._continuous_write_size = 0
            
            return pause_duration
        
        return 0
    
    def _do_life_protection_pause(self, pause_duration: float):
        """
        执行寿命保护暂停
        
        Args:
            pause_duration: 暂停时长（秒）
        """
        if pause_duration <= 0:
            return
        
        self._life_protection_active = True
        self._pause_start_time = time.time()
        self._current_pause_duration = pause_duration
        
        config = USB_LEVEL_CONFIG.get(self.usb_level, USB_LEVEL_CONFIG["medium"])
        
        self._log(f"⏸️ 寿命保护：正在暂停写入（连续写入 {config['time_threshold'] // 60} 分钟，停歇 {pause_duration:.0f} 秒）")
        
        if self._progress_callback:
            self._current_progress.current_phase = "paused"
            self._current_progress.speed = 0.0
            self._progress_callback(self._current_progress)
        
        remaining = pause_duration
        while remaining > 0 and not self._interrupted:
            time.sleep(0.5)
            remaining = pause_duration - (time.time() - self._pause_start_time)
            
            if self._progress_callback:
                self._current_progress.speed = 0.0
                self._progress_callback(self._current_progress)
        
        self._life_protection_active = False
        
        if not self._interrupted:
            self._log("▶️ 寿命保护：恢复写入")
            if self._progress_callback:
                self._current_progress.current_phase = "copying"
                self._progress_callback(self._current_progress)
    
    def is_life_protection_paused(self) -> bool:
        """
        检查是否正在寿命保护暂停中
        
        Returns:
            是否正在暂停
        """
        return self._life_protection_active
    
    def _check_disk_connected(self) -> bool:
        """
        检查目标磁盘是否仍连接
        
        Returns:
            磁盘是否连接
        """
        if not self._target_is_removable:
            return True
        
        try:
            return os.path.exists(self._target_root_path)
        except Exception:
            return False
    
    def get_life_protection_status(self) -> Dict[str, Any]:
        """
        获取寿命保护状态信息
        
        Returns:
            状态字典
        """
        if self._life_protection_active:
            elapsed = time.time() - self._pause_start_time
            remaining = max(0, self._current_pause_duration - elapsed)
            config = USB_LEVEL_CONFIG.get(self.usb_level, USB_LEVEL_CONFIG["medium"])
            
            return {
                "active": True,
                "remaining_time": remaining,
                "total_pause_time": self._current_pause_duration,
                "pause_count": self._pause_count,
                "usb_level": config["name"],
                "continuous_write_time": self._continuous_write_time,
                "continuous_write_size": self._continuous_write_size
            }
        else:
            return {
                "active": False,
                "remaining_time": 0,
                "total_pause_time": 0,
                "pause_count": self._pause_count,
                "usb_level": USB_LEVEL_CONFIG.get(self.usb_level, USB_LEVEL_CONFIG["medium"])["name"],
                "continuous_write_time": self._continuous_write_time,
                "continuous_write_size": self._continuous_write_size
            }
    
    def _log(self, message: str, level: str = "info"):
        """
        输出日志。

        Args:
            message: 日志内容
            level: 日志级别 info/warning/error；
                   quiet 模式下 info 级日志被抑制，警告与错误照常输出
        """
        if self.quiet and level == "info":
            return
        if self._log_callback:
            self._log_callback(message)
        else:
            print(message)

    def _log_file(self, message: str):
        """
        逐文件操作日志（复制/跳过/续传/删除）：v7.6 节流输出。

        攒够 100 条或距上次输出超过 2 秒才输出一条汇总，
        阶段结束时由 _flush_file_log() 输出剩余条数；
        quiet 模式下完全不输出。
        """
        if self.quiet:
            return
        now = time.time()
        self._file_log_pending += 1
        self._file_log_last_msg = message
        if (
            self._file_log_pending >= self._file_log_batch
            or (self._file_log_last_emit
                and now - self._file_log_last_emit >= self._file_log_interval)
        ):
            self._emit_file_log_batch()

    def _emit_file_log_batch(self):
        """输出一批节流后的逐文件日志"""
        if self._file_log_pending <= 0:
            return
        self._log(
            f"  ……已处理 {self._file_log_pending} 个文件，最近：{self._file_log_last_msg}"
        )
        self._file_log_pending = 0
        self._file_log_last_emit = time.time()
        self._file_log_last_msg = ""

    def _flush_file_log(self):
        """输出尚未刷出的逐文件日志（阶段结束时调用）"""
        self._emit_file_log_batch()
    
    def _update_progress(self, **kwargs):
        """更新进度信息"""
        for key, value in kwargs.items():
            if hasattr(self._current_progress, key):
                setattr(self._current_progress, key, value)
        
        # 计算百分比
        if self._current_progress.total_files > 0:
            self._current_progress.percentage = (
                self._current_progress.completed_files / self._current_progress.total_files * 100
            )
        
        # 计算已用时间
        if self._start_time > 0:
            self._current_progress.elapsed_time = time.time() - self._start_time
        
        # 计算预估剩余时间
        if (self._current_progress.speed > 0 and 
            self._current_progress.copied_size < self._current_progress.total_size):
            remaining_bytes = self._current_progress.total_size - self._current_progress.copied_size
            self._current_progress.estimated_remaining = remaining_bytes / self._current_progress.speed
        
        # 调用回调
        if self._progress_callback:
            self._progress_callback(self._current_progress)
    
    def interrupt(self):
        """中断同步"""
        self._interrupted = True
    
    def pause(self):
        """暂停同步"""
        self._paused = True
    
    def resume(self):
        """恢复同步"""
        self._paused = False
    
    def is_interrupted(self) -> bool:
        """检查是否已中断"""
        return self._interrupted
    
    def is_paused(self) -> bool:
        """检查是否已暂停"""
        return self._paused
    
    def _wait_if_paused(self):
        """如果暂停则等待"""
        while self._paused and not self._interrupted:
            time.sleep(0.1)
    
    def _get_strategy_for_path(self, rel_path: str) -> str:
        """
        获取指定路径的冲突策略
        
        Args:
            rel_path: 相对路径
            
        Returns:
            冲突策略名称
        """
        first_slash = rel_path.find(os.sep) if rel_path else -1
        
        if first_slash == -1:
            # 根目录文件
            if self.root_included:
                return self.root_strategy
            else:
                return self.default_strategy
        else:
            # 子目录文件
            folder_name = rel_path[:first_slash]
            if folder_name in self.folder_strategies:
                return self.folder_strategies[folder_name]
            else:
                return self.default_strategy
    
    def _get_file_info(self, filepath: Path) -> Optional[Dict]:
        """
        获取文件信息
        
        Args:
            filepath: 文件路径
            
        Returns:
            文件信息字典
        """
        try:
            stat = filepath.stat()
            return {
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'ctime': stat.st_ctime
            }
        except (OSError, PermissionError):
            return None
    
    def _copy_file_chunked(self, src: str, dst: str, start_offset: int = 0) -> int:
        """
        分块复制文件，支持寿命保护中途停歇和大文件内部断点续传
        
        Args:
            src: 源文件路径
            dst: 目标文件路径（临时文件）
            start_offset: 续传起始偏移量（字节），0 表示从头开始
            
        Returns:
            本次复制写入的字节数（不含续传前已有部分）
        """
        copied_size = 0
        # 续传时以 r+b 模式追加写入；全新复制以 wb 模式创建
        dst_mode = 'r+b' if start_offset > 0 else 'wb'

        with open(src, 'rb') as f_src:
            with open(dst, dst_mode) as f_dst:
                if start_offset > 0:
                    f_src.seek(start_offset)
                    f_dst.seek(start_offset)

                while not self._interrupted:
                    # 块级停歇检查：在写入下一块前检查寿命保护
                    if self.life_protection_enabled and self._target_is_removable:
                        pause_duration = self._check_life_protection(0)
                        if pause_duration > 0:
                            # 暂停前刷新已写入的数据，确保续传时数据完整
                            f_dst.flush()
                            self._do_life_protection_pause(pause_duration)

                    # 检查通用暂停
                    self._wait_if_paused()

                    if self._interrupted:
                        break

                    chunk = f_src.read(self.chunk_size)
                    if not chunk:
                        break

                    f_dst.write(chunk)
                    copied_size += len(chunk)

                    # 块级记录写入统计，驱动寿命保护阈值判定
                    if self.life_protection_enabled and self._target_is_removable:
                        self._continuous_write_size += len(chunk)
                        self._last_write_time = time.time()

            # 检查U盘是否脱落（写入完成后）
            if self._target_is_removable and not self._check_disk_connected():
                self._log("❌ 同步中断：U盘已断开", level="error")
                self._update_progress(
                    current_phase="error",
                    current_file="❌ 同步中断：U盘已断开",
                    speed=0.0
                )
                self._interrupted = True

        return copied_size
    
    def _copy_file(self, src: str, dst: str, strategy: str) -> bool:
        """
        事务性复制文件：先分块复制到临时文件，再原子重命名
        支持大文件内部断点续传：中断后保留临时文件，下次同步从断点继续
        
        Args:
            src: 源文件路径
            dst: 目标文件路径
            strategy: 冲突策略
            
        Returns:
            是否成功复制
        """
        # 检查中断
        if self._interrupted:
            return False
        
        # 检查暂停
        self._wait_if_paused()
        
        try:
            # 确保目标目录存在（安全网，批量预创建通常已完成）
            dst_dir = os.path.dirname(dst)
            if dst_dir and not os.path.exists(dst_dir):
                os.makedirs(dst_dir, exist_ok=True)
            
            dst_exists = os.path.exists(dst)
            
            if dst_exists:
                # 目标目录优先：保留目标文件，不覆盖
                if strategy == "target_wins":
                    self._log_file(f"  ⏭️  跳过（目标目录优先）: {src}")
                    self.stats.files_skipped += 1
                    return False

                # 保守模式：不覆盖已有文件
                if strategy == "conservative":
                    self._log_file(f"  ⏭️  跳过（保守模式）: {src}")
                    self.stats.files_skipped += 1
                    return False
                
                # 源目录优先：直接覆盖，不检查修改时间
                if strategy == "source_wins":
                    pass  # 继续执行复制
                # 时间优先模式：比较修改时间
                elif strategy == "newest_wins":
                    src_info = self._get_file_info(Path(src))
                    dst_info = self._get_file_info(Path(dst))
                    
                    if src_info and dst_info:
                        if src_info['mtime'] <= dst_info['mtime']:
                            self._log_file(f"  ⏭️  跳过（目标更新）: {src}")
                            self.stats.files_skipped += 1
                            return False
            
            # 获取源文件大小用于速度计算
            src_size = os.path.getsize(src) if os.path.exists(src) else 0
            
            # 更新进度
            self._update_progress(
                current_file=src,
                current_phase="copying"
            )
            
            # 事务性复制：先复制到临时文件
            temp_dst = dst + TEMP_FILE_SUFFIX
            
            # ===== 大文件内部断点续传 =====
            # 检查是否存在上次中断遗留的临时文件
            start_offset = 0
            if os.path.exists(temp_dst):
                temp_size = os.path.getsize(temp_dst)
                src_mtime = os.path.getmtime(src)
                temp_mtime = os.path.getmtime(temp_dst)

                if temp_size > src_size:
                    # 源文件比临时文件小（源文件已缩小），临时文件无效，重新复制
                    try:
                        os.remove(temp_dst)
                    except Exception:
                        pass
                elif temp_size == src_size:
                    # 临时文件已完整（可能是上次复制完成后重命名前的中断），直接进入重命名
                    start_offset = -1  # 标记跳过复制
                elif temp_size > 0 and src_mtime <= temp_mtime:
                    # 临时文件比源文件旧或同龄 → 源文件未修改，可安全续传
                    start_offset = temp_size
                    self._log_file(f"  📎 续传: {src}（从 {self._format_file_size(temp_size)} 继续）")
                else:
                    # 源文件比临时文件新 → 临时文件过期，重新复制
                    try:
                        os.remove(temp_dst)
                    except Exception:
                        pass
            
            # 记录复制开始时间
            copy_start_time = time.time()
            copied_size = 0

            if start_offset != -1:
                # 分块复制（支持寿命保护中途停歇 + 断点续传）
                copied_size = self._copy_file_chunked(src, temp_dst, start_offset)
            
            # 如果被中断，保留临时文件以便下次续传
            if self._interrupted:
                return False
            
            # 计算复制速度（仅基于本次实际写入量）
            copy_end_time = time.time()
            copy_duration = copy_end_time - copy_start_time
            if copy_duration > 0 and copied_size > 0:
                speed = copied_size / copy_duration
                self.actual_speeds.append(speed)
                self._current_progress.speed = speed
            
            # 原子重命名：用 os.replace() 确保重命名成功
            os.replace(temp_dst, dst)
            
            # 保留源文件元数据（权限、时间戳等），替代 shutil.copy2 的行为
            try:
                shutil.copystat(src, dst)
            except (OSError, PermissionError):
                pass  # 元数据复制失败不影响文件内容
            
            # 更新统计
            self.stats.files_copied += 1
            self.stats.total_size_copied += src_size
            self._current_progress.copied_size += src_size
            self._current_progress.completed_files += 1
            
            # 添加到已完成文件集合
            self.completed_files.add(dst)
            
            # 检查是否需要保存进度
            if self.progress_manager and self.progress_manager.should_save():
                self.progress_manager.save_progress(
                    self.completed_files,
                    self.total_files_to_sync
                )
            
            if start_offset > 0:
                self._log_file(f"  ✅ 复制（续传完成）: {src}")
            else:
                self._log_file(f"  ✅ 复制: {src}")

            # 检查U盘是否脱落
            if not self._check_disk_connected():
                self._log("❌ 同步中断：U盘已断开", level="error")
                self._update_progress(
                    current_phase="error",
                    current_file="❌ 同步中断：U盘已断开",
                    speed=0.0
                )
                self._interrupted = True
                return False
            
            return True
            
        except PermissionError as e:
            # 权限拒绝：可能是安全软件拦截（病毒）或真正的权限不足
            self.stats.permission_denied.append(src)
            if self._is_security_interception(e):
                msg = f"  ⚠️ 文件 {os.path.basename(src)} 被安全软件拦截，可能包含病毒，已跳过同步"
                self._log(msg, level="warning")
            else:
                self._log(f"  ❌ 权限拒绝: {src}", level="error")
            return False
        except OSError as e:
            # OSError（含 "Invalid argument" 等）：常见于安全软件拦截或 I/O 异常
            self.stats.errors.append((src, str(e)))
            if self._is_security_interception(e):
                msg = f"  ⚠️ 文件 {os.path.basename(src)} 被安全软件拦截，可能包含病毒，已跳过同步"
                self._log(msg, level="warning")
            else:
                self._log(f"  ❌ I/O 错误: {src} - {e}", level="error")
            return False
        except Exception as e:
            self.stats.errors.append((src, str(e)))
            self._log(f"  ❌ 错误: {src} - {e}", level="error")
            return False
    
    @staticmethod
    def _is_security_interception(exc: Exception) -> bool:
        """
        判断异常是否由安全软件拦截（病毒）引起。
        
        安全软件拦截文件读写时，在 Windows 上通常表现为：
        - PermissionError（访问被拒绝，ERROR_ACCESS_DENIED）
        - OSError: [Errno 22] Invalid argument
        - 错误信息包含 virus/malware/quarantine/blocked 等关键词
        
        Args:
            exc: 捕获的异常
            
        Returns:
            是否疑似安全软件拦截
        """
        err_msg = str(exc).lower()
        # 关键词检测
        keywords = ["virus", "malware", "quarantine", "blocked", "infected",
                    "trojan", "worm", "ransomware", "spyware"]
        if any(k in err_msg for k in keywords):
            return True
        # Windows 错误码检测
        # ERROR_ACCESS_DENIED (5) / ERROR_INVALID_PARAMETER (87) / ERROR_INVALID_FUNCTION (1)
        winerror = getattr(exc, 'winerror', None)
        if winerror in (5, 87, 1):
            return True
        # errno 检测：EACCES (13) / EINVAL (22)
        errno_val = getattr(exc, 'errno', None)
        if errno_val in (13, 22):
            return True
        # 信息中包含 "invalid argument"
        if "invalid argument" in err_msg:
            return True
        return False
    
    def _normalize_folder_filters(self, raw: Optional[Dict[str, Dict]]) -> Dict[str, Dict]:
        """
        规范化按文件夹的筛选策略配置。

        Args:
            raw: 原始 folder_filters 字典（来自任务配置）

        Returns:
            规范化后的字典 {文件夹名: {"date_start": date|None, "date_end": date|None,
             "extension_mode": "include"/"exclude", "extension_list": [".txt"]}}
            仅保留配置了日期或扩展名过滤的文件夹；未配置的文件夹不启用筛选
        """
        result: Dict[str, Dict] = {}
        if not raw or not isinstance(raw, dict):
            return result

        for folder, cfg in raw.items():
            if not isinstance(cfg, dict):
                continue

            entry: Dict = {"date_start": None, "date_end": None}

            # 日期过滤
            if cfg.get("date_filter_enabled"):
                for key, target in (("date_start", "date_start"), ("date_end", "date_end")):
                    val = str(cfg.get(key, "") or "").strip()
                    if val:
                        try:
                            entry[target] = datetime.strptime(val, "%Y-%m-%d").date()
                        except ValueError:
                            pass

            # 扩展名过滤
            if cfg.get("extension_filter_enabled"):
                ext_list = []
                for ext in (cfg.get("extension_filter_list") or []):
                    ext = str(ext).strip().lower()
                    if ext:
                        if not ext.startswith("."):
                            ext = "." + ext
                        ext_list.append(ext)
                if ext_list:
                    mode = cfg.get("extension_filter_mode", "include")
                    entry["extension_mode"] = mode if mode in ("include", "exclude") else "include"
                    entry["extension_list"] = ext_list

            # 只保留启用了任一过滤条件的文件夹
            has_date = entry["date_start"] is not None or entry["date_end"] is not None
            has_ext = "extension_list" in entry
            if has_date or has_ext:
                result[folder] = entry

        return result

    def _get_folder_filter_for_relpath(self, rel_dir: str) -> Optional[Dict]:
        """
        获取相对目录对应的筛选策略配置。

        Args:
            rel_dir: 相对于扫描根目录的目录路径（"." 表示根目录本身）

        Returns:
            该顶层文件夹的筛选配置；未配置则返回 None（不启用筛选）
        """
        if not self.folder_filters or not rel_dir or rel_dir == ".":
            return None
        top_folder = rel_dir.split(os.sep)[0]
        return self.folder_filters.get(top_folder)

    def _scan_directory(
        self,
        base_path: str,
        start_date: Optional["datetime.date"] = None,
        end_date: Optional["datetime.date"] = None
    ) -> Dict[str, Dict]:
        """
        扫描目录获取文件信息

        v7.5: 按文件夹应用筛选策略（扩展名过滤 + 日期过滤，AND 关系）。
        只有在 FolderConfigPage 中配置了筛选策略的文件夹才会被过滤；
        未配置筛选策略的文件夹同步全部文件。

        Args:
            base_path: 基础路径
            start_date: 开始日期过滤（向后兼容参数）
            end_date: 结束日期过滤（向后兼容参数）

        Returns:
            文件信息字典 {相对路径: 文件信息}
        """
        files = {}

        # v7.6: 使用 os.scandir 迭代遍历（比 os.walk 少一次目录重复列举，
        # 且 DirEntry 自带类型缓存）。显式栈替代递归，避免深层目录栈溢出。
        base = Path(base_path)
        # 栈元素：(当前目录 Path, 相对目录字符串)
        stack = [(base, ".")]

        while stack:
            # 检查中断
            if self._interrupted:
                break

            current_dir, rel_dir = stack.pop()
            folder_filter = self._get_folder_filter_for_relpath(rel_dir)

            try:
                entries = list(os.scandir(current_dir))
            except (OSError, PermissionError):
                continue

            for entry in entries:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:
                    continue

                if is_dir:
                    # 过滤隐藏目录
                    if not entry.name.startswith('.'):
                        child_rel = (
                            entry.name if rel_dir == "."
                            else os.path.join(rel_dir, entry.name)
                        )
                        stack.append((Path(entry.path), child_rel))
                    continue

                # 过滤隐藏文件
                if entry.name.startswith('.'):
                    self.stats.skipped_system_files.append(entry.name)
                    continue

                filepath = Path(entry.path)
                info = self._get_file_info(filepath)

                if not info:
                    continue

                # v7.5: 该文件夹配置了筛选策略时应用过滤（扩展名 + 日期，AND 关系）
                if folder_filter is not None and not self._file_passes_filter(
                    entry.name, info, folder_filter, start_date, end_date
                ):
                    continue

                rel_path = filepath.relative_to(base)
                files[str(rel_path)] = info
                self.stats.files_scanned += 1

        return files

    def _file_passes_filter(
        self,
        filename: str,
        file_info: Dict,
        folder_filter: Dict,
        start_date: Optional["datetime.date"] = None,
        end_date: Optional["datetime.date"] = None
    ) -> bool:
        """
        检查文件是否通过筛选（扩展名过滤 + 日期过滤，AND 关系）。

        Args:
            filename: 文件名
            file_info: 文件信息字典（含 mtime）
            folder_filter: 该文件夹的筛选配置（_normalize_folder_filters 的条目）
            start_date: 兼容参数（调用方传入的日期范围），为 None 时使用文件夹配置
            end_date: 兼容参数（调用方传入的日期范围），为 None 时使用文件夹配置

        Returns:
            是否通过筛选
        """
        # 确定日期范围：调用方显式传入时优先（向后兼容）
        if start_date or end_date:
            eff_start, eff_end = start_date, end_date
        else:
            eff_start = folder_filter.get("date_start")
            eff_end = folder_filter.get("date_end")

        # 扩展名过滤
        extension_list = folder_filter.get("extension_list")
        if extension_list:
            ext = os.path.splitext(filename)[1].lower()
            if folder_filter.get("extension_mode", "include") == "include":
                # 仅包含列表中的扩展名
                if ext not in extension_list:
                    return False
            else:
                # exclude: 排除列表中的扩展名
                if ext in extension_list:
                    return False

        # 日期过滤（按文件修改日期）
        if eff_start or eff_end:
            mtime = file_info.get('mtime')
            if mtime is None:
                return True  # 无法获取修改时间则放行
            try:
                file_date = datetime.fromtimestamp(mtime).date()
            except (OSError, ValueError):
                return True

            if eff_start and file_date < eff_start:
                return False
            if eff_end and file_date > eff_end:
                return False

        return True
    
    def _extract_date_from_filename(self, filename: str) -> Optional["datetime.date"]:
        """
        从文件名提取日期（保留用于向后兼容，v7.5 日期过滤改用文件修改时间）。
        
        Args:
            filename: 文件名
            
        Returns:
            日期对象，如果无法提取则返回 None
        """
        date_formats = [
            ("%Y%m%d", 8),
            ("%Y-%m-%d", 10),
            ("%Y.%m.%d", 10),
        ]
        
        for fmt, length in date_formats:
            if len(filename) >= length:
                date_str = filename[:length]
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue
        return None
    
    def _should_include_file(
        self, 
        filename: str, 
        start_date: Optional["datetime.date"] = None, 
        end_date: Optional["datetime.date"] = None
    ) -> bool:
        """
        [已废弃，保留向后兼容] 检查文件是否应该被包含（基于文件名日期）。
        v7.5 起请使用 _file_passes_filter（基于文件修改日期 + 扩展名）。
        """
        if not start_date and not end_date:
            return True
        
        file_date = self._extract_date_from_filename(filename)
        if not file_date:
            return True
        
        if start_date and end_date and start_date > end_date:
            start_date, end_date = end_date, start_date
        
        if start_date and file_date < start_date:
            return False
        if end_date and file_date > end_date:
            return False
        
        return True
    
    def _get_estimated_speed(self) -> float:
        """
        获取预估速度
        
        Returns:
            预估速度（bytes/秒）
        """
        # 优先使用当前会话的实测速度
        if self.actual_speeds:
            avg_speed = sum(self.actual_speeds) / len(self.actual_speeds)
            return avg_speed
        
        # 其次使用配置中的历史速度
        if self.config_manager:
            history = self.config_manager.config.get("sync_history", [])
            if history:
                # 使用最近5次同步的平均速度
                recent = history[-5:]
                speeds = [h.get("avg_speed", 0) for h in recent if h.get("avg_speed", 0) > 0]
                if speeds:
                    return sum(speeds) / len(speeds)
        
        # 从未同步过，使用保守速度 5MB/s
        return 5 * 1024 * 1024
    
    def preview_sync(
        self,
        source_dir: str,
        target_dir: str,
        direction: str = "both",
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None
    ) -> SyncPreview:
        """
        预览同步操作（不实际执行）
        
        Args:
            source_dir: 源目录
            target_dir: 目标目录
            direction: 同步方向
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            同步预览信息
        """
        # 重置统计
        self.stats = SyncStats()
        
        # 扫描目录
        scan_start = time.time()
        source_files = self._scan_directory(source_dir, start_date, end_date)
        target_files = self._scan_directory(target_dir, start_date, end_date)
        scan_time = time.time() - scan_start
        
        # 分析需要同步的文件
        preview = SyncPreview()
        
        all_files = set(source_files.keys()) | set(target_files.keys())
        
        for rel_path in all_files:
            in_source = rel_path in source_files
            in_target = rel_path in target_files
            
            if in_source and in_target:
                strategy = self._get_strategy_for_path(rel_path)
                src_mtime = source_files[rel_path]['mtime']
                dst_mtime = target_files[rel_path]['mtime']
                
                # 目标目录优先：保留目标，不做任何操作
                if strategy == "target_wins":
                    continue
                # 保守模式：不覆盖已有文件
                elif strategy == "conservative":
                    continue
                # 源目录优先：强制用源目录覆盖目标
                elif strategy == "source_wins":
                    if direction in ["both", "source_to_target"]:
                        preview.files_to_copy_source_to_target.append(rel_path)
                        preview.reasons_source_to_target.append("源目录优先")
                # 时间优先模式：比较修改时间
                elif strategy == "newest_wins":
                    if src_mtime > dst_mtime:
                        preview.files_to_copy_source_to_target.append(rel_path)
                        preview.reasons_source_to_target.append("源更新")
                    elif dst_mtime > src_mtime:
                        if direction in ["both", "target_to_source"]:
                            preview.files_to_copy_target_to_source.append(rel_path)
                            preview.reasons_target_to_source.append("目标更新")
            elif in_source and not in_target:
                if direction in ["both", "source_to_target"]:
                    preview.files_to_copy_source_to_target.append(rel_path)
                    preview.reasons_source_to_target.append("新增")
            elif in_target and not in_source:
                if direction in ["both", "target_to_source"]:
                    preview.files_to_copy_target_to_source.append(rel_path)
                    preview.reasons_target_to_source.append("新增")
        
        # 计算总大小
        total_size = 0
        all_source_files = {**source_files, **target_files}
        for rel_path in preview.files_to_copy_source_to_target:
            if rel_path in source_files:
                total_size += source_files[rel_path]['size']
        for rel_path in preview.files_to_copy_target_to_source:
            if rel_path in target_files:
                total_size += target_files[rel_path]['size']
        
        preview.total_files = len(preview.files_to_copy_source_to_target) + len(preview.files_to_copy_target_to_source)
        preview.total_size = total_size
        
        # 预估时间
        estimated_speed = self._get_estimated_speed()
        scan_speed_per_file = 0.001  # 假设每个文件扫描约1毫秒
        preview.scan_time = preview.total_files * scan_speed_per_file
        preview.copy_time = total_size / estimated_speed if total_size > 0 else 0
        preview.estimated_time = preview.scan_time + preview.copy_time
        preview.speed_mbps = estimated_speed / (1024 * 1024)
        
        return preview
    
    def sync_directories(
        self,
        source_dir: str,
        target_dir: str,
        direction: str = "both",
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        dry_run: bool = False,
        last_snapshot: Optional[Dict] = None
    ) -> bool:
        """
        同步两个目录（v7.6：全程阻止系统休眠，结束/异常/中断后必然恢复）。

        Returns:
            是否成功完成
        """
        # v7.6：同步开始即阻止系统休眠；寿命保护暂停期间不释放，
        # 在 finally 中恢复，确保成功/失败/中断/异常所有分支都能恢复
        from backend.platform_utils import prevent_sleep, allow_sleep
        sleep_prevented = False
        if getattr(self, "prevent_sleep_during_sync", True):
            sleep_prevented = prevent_sleep()
        try:
            return self._sync_directories_impl(
                source_dir=source_dir,
                target_dir=target_dir,
                direction=direction,
                start_date=start_date,
                end_date=end_date,
                dry_run=dry_run,
                last_snapshot=last_snapshot,
            )
        finally:
            if sleep_prevented:
                allow_sleep()

    def _sync_directories_impl(
        self,
        source_dir: str,
        target_dir: str,
        direction: str = "both",
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        dry_run: bool = False,
        last_snapshot: Optional[Dict] = None
    ) -> bool:
        """
        同步两个目录
        
        Args:
            source_dir: 源目录
            target_dir: 目标目录
            direction: 同步方向 ("both", "source_to_target", "target_to_source")
            start_date: 开始日期过滤
            end_date: 结束日期过滤
            dry_run: 是否为模拟运行
            last_snapshot: 上次同步时的文件快照，用于检测删除
            
        Returns:
            是否成功完成
        """
        # 重置状态
        self._interrupted = False
        self._paused = False
        self._start_time = time.time()
        self.stats = SyncStats()
        self.actual_speeds = []
        self.completed_files = set()
        
        # 检查目录是否存在
        if not os.path.exists(source_dir):
            self._log(f"❌ 同步中断：找不到目录「{source_dir}」", level="error")
            self._update_progress(
                current_phase="error",
                current_file=f"❌ 同步中断：找不到目录「{source_dir}」",
                total_files=0,
                completed_files=0
            )
            return False
        
        if not os.path.exists(target_dir):
            self._log(f"❌ 同步中断：找不到目录「{target_dir}」", level="error")
            self._update_progress(
                current_phase="error",
                current_file=f"❌ 同步中断：找不到目录「{target_dir}」",
                total_files=0,
                completed_files=0
            )
            return False
        
        # ===== v7.5: 同目录并发同步检测 =====
        # 防止多个任务同时操作同一目录导致 I/O 异常（Invalid argument 等）
        src_norm = os.path.normcase(os.path.abspath(source_dir))
        tgt_norm = os.path.normcase(os.path.abspath(target_dir))
        with FileSyncEngine._active_sync_dirs_lock:
            if src_norm in FileSyncEngine._active_sync_dirs or tgt_norm in FileSyncEngine._active_sync_dirs:
                self._log("❌ 同步中断：该目录正在被其他任务同步，禁止并发操作同一目录", level="error")
                self._update_progress(
                    current_phase="error",
                    current_file="❌ 该目录正在被其他任务同步，请等待完成后再试",
                    total_files=0,
                    completed_files=0
                )
                return False
            FileSyncEngine._active_sync_dirs.add(src_norm)
            FileSyncEngine._active_sync_dirs.add(tgt_norm)
        self._acquired_sync_dirs = (src_norm, tgt_norm)
        
        # 初始化进度管理器
        self.progress_manager = ProgressManager(target_dir)
        
        # 检测目标目录是否为可移动磁盘（用于寿命保护）
        self._target_is_removable = is_removable_disk(target_dir)
        
        # 保存目标目录根路径（用于U盘脱落检测）
        from backend.platform_utils import get_target_root_path
        self._target_root_path = get_target_root_path(target_dir)
        
        # 更新进度：开始扫描
        self._update_progress(
            current_phase="scanning",
            current_file="",
            total_files=0,
            completed_files=0
        )
        
        # 扫描目录
        scan_start = time.time()
        source_files = self._scan_directory(source_dir, start_date, end_date)
        target_files = self._scan_directory(target_dir, start_date, end_date)
        self.stats.scan_time = time.time() - scan_start
        
        # 检查中断
        if self._interrupted:
            self._log("同步已被中断")
            return False
        
        # 分析需要同步的文件
        files_to_copy = {
            "source_to_target": {"files": [], "reasons": []},
            "target_to_source": {"files": [], "reasons": []}
        }
        
        # 检测需要删除的文件（同步删除功能）
        files_to_delete = {
            "source": {"files": [], "reasons": []},
            "target": {"files": [], "reasons": []}
        }
        
        all_files = set(source_files.keys()) | set(target_files.keys())
        
        for rel_path in all_files:
            in_source = rel_path in source_files
            in_target = rel_path in target_files
            
            if in_source and in_target:
                strategy = self._get_strategy_for_path(rel_path)
                src_mtime = source_files[rel_path]['mtime']
                dst_mtime = target_files[rel_path]['mtime']
                
                # 目标目录优先：保留目标，不做任何操作
                if strategy == "target_wins":
                    continue
                # 保守模式：不覆盖已有文件
                elif strategy == "conservative":
                    continue
                # 源目录优先：强制用源目录覆盖目标
                elif strategy == "source_wins":
                    if direction in ["both", "source_to_target"]:
                        files_to_copy["source_to_target"]["files"].append(rel_path)
                        files_to_copy["source_to_target"]["reasons"].append("源目录优先")
                # 时间优先模式：比较修改时间
                elif strategy == "newest_wins":
                    if src_mtime > dst_mtime:
                        files_to_copy["source_to_target"]["files"].append(rel_path)
                        files_to_copy["source_to_target"]["reasons"].append("源更新")
                    elif dst_mtime > src_mtime:
                        if direction in ["both", "target_to_source"]:
                            files_to_copy["target_to_source"]["files"].append(rel_path)
                            files_to_copy["target_to_source"]["reasons"].append("目标更新")
            elif in_source and not in_target:
                if direction in ["both", "source_to_target"]:
                    files_to_copy["source_to_target"]["files"].append(rel_path)
                    files_to_copy["source_to_target"]["reasons"].append("新增")
            elif in_target and not in_source:
                if direction in ["both", "target_to_source"]:
                    files_to_copy["target_to_source"]["files"].append(rel_path)
                    files_to_copy["target_to_source"]["reasons"].append("新增")
        
        # 如果启用同步删除，检测删除的文件
        if self.sync_delete_enabled and last_snapshot:
            files_to_delete = self._detect_deleted_files(
                source_dir,
                target_dir,
                source_files,
                target_files,
                last_snapshot,
                direction
            )
        
        # 计算预览信息
        total_size = 0
        all_source_files = {**source_files, **target_files}
        for rel_path in files_to_copy["source_to_target"]["files"]:
            if rel_path in source_files:
                total_size += source_files[rel_path]['size']
        for rel_path in files_to_copy["target_to_source"]["files"]:
            if rel_path in target_files:
                total_size += target_files[rel_path]['size']
        
        total_files = len(files_to_copy["source_to_target"]["files"]) + len(files_to_copy["target_to_source"]["files"])
        total_deletes = len(files_to_delete["source"]["files"]) + len(files_to_delete["target"]["files"])
        self.total_files_to_sync = total_files + total_deletes
        
        # 更新进度信息
        self._update_progress(
            total_files=self.total_files_to_sync,
            total_size=total_size,
            current_phase="copying"
        )
        
        # 输出预估信息
        estimated_speed = self._get_estimated_speed()
        scan_time_est = total_files * 0.001
        copy_time_est = total_size / estimated_speed if total_size > 0 else 0
        
        self._log(f"\n📊 同步预估：")
        self._log(f"  文件数量: {total_files}")
        self._log(f"  删除数量: {total_deletes}")
        self._log(f"  总大小: {self._format_file_size(total_size)}")
        self._log(f"  预估扫描: {scan_time_est:.2f}秒")
        self._log(f"  预估复制: {copy_time_est:.2f}秒")
        self._log(f"  预估总计: {scan_time_est + copy_time_est:.2f}秒")
        self._log(f"  基于速度: {estimated_speed / (1024 * 1024):.2f} MB/s")
        
        if dry_run:
            self._log("\n⚠️  模拟运行模式，不会实际复制或删除文件", level="warning")
            self._release_sync_dirs()
            return True
        
        if total_files == 0 and total_deletes == 0:
            self._log("\n✅ 没有需要同步的文件")
            if self.progress_manager:
                self.progress_manager.clear_progress()
            self._release_sync_dirs()
            return True
        
        # 批量预创建所有需要的目录结构，减少复制阶段的逐文件创建开销
        self._create_all_directories(
            source_dir, target_dir, files_to_copy, direction
        )
        
        if self._interrupted:
            self._log("同步已被中断")
            self._release_sync_dirs()
            return False
        
        # 开始复制
        copy_start = time.time()
        
        if self.use_multithreading_copy and total_files > 1:
            # 多线程复制
            with ThreadPoolExecutor(max_workers=self.sync_workers) as executor:
                futures = []
                
                for rel_path in files_to_copy["source_to_target"]["files"]:
                    # 检查中断
                    if self._interrupted:
                        break
                    
                    src = str(Path(source_dir) / rel_path)
                    dst = str(Path(target_dir) / rel_path)
                    strategy = self._get_strategy_for_path(rel_path)
                    futures.append(executor.submit(self._copy_file, src, dst, strategy))
                
                for rel_path in files_to_copy["target_to_source"]["files"]:
                    # 检查中断
                    if self._interrupted:
                        break
                    
                    src = str(Path(target_dir) / rel_path)
                    dst = str(Path(source_dir) / rel_path)
                    strategy = self._get_strategy_for_path(rel_path)
                    futures.append(executor.submit(self._copy_file, src, dst, strategy))
                
                # 等待所有任务完成
                for future in as_completed(futures):
                    if self._interrupted:
                        break
                    future.result()
        else:
            # 单线程复制
            for rel_path in files_to_copy["source_to_target"]["files"]:
                if self._interrupted:
                    break
                
                self._wait_if_paused()
                
                src = str(Path(source_dir) / rel_path)
                dst = str(Path(target_dir) / rel_path)
                strategy = self._get_strategy_for_path(rel_path)
                self._copy_file(src, dst, strategy)
            
            for rel_path in files_to_copy["target_to_source"]["files"]:
                if self._interrupted:
                    break
                
                self._wait_if_paused()
                
                src = str(Path(target_dir) / rel_path)
                dst = str(Path(source_dir) / rel_path)
                strategy = self._get_strategy_for_path(rel_path)
                self._copy_file(src, dst, strategy)
        
        self.stats.copy_time = time.time() - copy_start
        
        # 如果启用同步删除，执行删除操作
        if self.sync_delete_enabled and total_deletes > 0:
            self._execute_deletions(
                source_dir,
                target_dir,
                files_to_delete
            )
        
        self.stats.total_time = time.time() - self._start_time
        
        # 更新进度：完成
        self._update_progress(current_phase="finishing")
        
        # 如果被中断，保存进度
        if self._interrupted:
            self._flush_file_log()
            self._log("\n⚠️ 同步已被中断", level="warning")
            if self.progress_manager:
                self.progress_manager.save_progress(
                    self.completed_files,
                    self.total_files_to_sync
                )
            self._release_sync_dirs()
            return False
        
        # 同步完成后清除进度文件
        if self.progress_manager:
            self.progress_manager.clear_progress()
        
        # 保存同步历史速度
        self._save_sync_history()
        
        # 计算速度统计
        if self.actual_speeds:
            self.stats.avg_speed = sum(self.actual_speeds) / len(self.actual_speeds)
            self.stats.max_speed = max(self.actual_speeds)
            self.stats.min_speed = min(self.actual_speeds)
            self.stats.speed_samples = len(self.actual_speeds)
        
        # 记录本次同步的文件快照
        self.last_snapshot = {
            "source": list(source_files.keys()),
            "target": list(target_files.keys()),
            "timestamp": time.time()
        }
        
        self._flush_file_log()
        self._release_sync_dirs()
        return True

    def _release_sync_dirs(self):
        """释放本次同步占用的目录（供并发检测使用）。"""
        acquired = getattr(self, "_acquired_sync_dirs", None)
        if not acquired:
            return
        with FileSyncEngine._active_sync_dirs_lock:
            for d in acquired:
                FileSyncEngine._active_sync_dirs.discard(d)
        self._acquired_sync_dirs = None
    
    def _create_all_directories(
        self,
        source_dir: str,
        target_dir: str,
        files_to_copy: Dict,
        direction: str
    ):
        """
        批量预创建所有需要同步的目录结构，减少复制阶段逐文件创建目录的开销
        
        Args:
            source_dir: 源目录
            target_dir: 目标目录
            files_to_copy: 待复制文件字典
            direction: 同步方向
        """
        dirs_to_create = set()

        # 收集源→目标方向的目录
        if direction in ["both", "source_to_target"]:
            for rel_path in files_to_copy["source_to_target"]["files"]:
                dst_dir = os.path.dirname(os.path.join(target_dir, rel_path))
                if dst_dir:
                    dirs_to_create.add(dst_dir)

        # 收集目标→源方向的目录
        if direction in ["both", "target_to_source"]:
            for rel_path in files_to_copy["target_to_source"]["files"]:
                dst_dir = os.path.dirname(os.path.join(source_dir, rel_path))
                if dst_dir:
                    dirs_to_create.add(dst_dir)

        if not dirs_to_create:
            return

        self._log(f"\n📁 预创建目录结构（{len(dirs_to_create)} 个）...")

        created_count = 0
        for dir_path in dirs_to_create:
            if self._interrupted:
                break
            try:
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                    created_count += 1
            except (OSError, PermissionError):
                pass  # 忽略创建失败，_copy_file 中有安全网

        if created_count > 0:
            self._log(f"  ✅ 已创建 {created_count} 个目录")

    def _save_sync_history(self):
        """保存同步历史速度到配置"""
        if not self.config_manager or not self.actual_speeds:
            return
        
        avg_speed = sum(self.actual_speeds) / len(self.actual_speeds)
        history_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "files_copied": self.stats.files_copied,
            "total_size": self.stats.total_size_copied,
            "avg_speed": avg_speed,
            "avg_speed_mbps": avg_speed / (1024 * 1024)
        }
        
        # 获取现有历史，保留最近10条
        history = self.config_manager.config.get("sync_history", [])
        history.append(history_entry)
        history = history[-10:]
        self.config_manager.config["sync_history"] = history
        self.config_manager.save_config()
    
    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0 or unit == 'TB':
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
    
    def get_stats(self) -> SyncStats:
        """获取统计信息"""
        return self.stats
    
    def get_progress(self) -> SyncProgress:
        """获取当前进度"""
        return self._current_progress
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """
        获取统计摘要
        
        Returns:
            统计摘要字典
        """
        summary = {
            "files_scanned": self.stats.files_scanned,
            "files_copied": self.stats.files_copied,
            "files_updated": self.stats.files_updated,
            "files_skipped": self.stats.files_skipped,
            "total_size_copied": self._format_file_size(self.stats.total_size_copied),
            "total_size_copied_bytes": self.stats.total_size_copied,
            "errors_count": len(self.stats.errors),
            "permission_denied_count": len(self.stats.permission_denied),
            "scan_time": f"{self.stats.scan_time:.3f}秒",
            "copy_time": f"{self.stats.copy_time:.3f}秒",
            "total_time": f"{self.stats.total_time:.3f}秒"
        }
        
        if self.actual_speeds:
            summary["avg_speed"] = f"{self.stats.avg_speed / (1024*1024):.2f} MB/s"
            summary["max_speed"] = f"{self.stats.max_speed / (1024*1024):.2f} MB/s"
            summary["min_speed"] = f"{self.stats.min_speed / (1024*1024):.2f} MB/s"
            summary["speed_samples"] = self.stats.speed_samples
        
        if self.stats.errors:
            summary["errors"] = self.stats.errors[:10]  # 只返回前10个错误
        
        if self.stats.permission_denied:
            summary["permission_denied"] = self.stats.permission_denied[:10]
        
        return summary
    
    def _detect_deleted_files(
        self,
        source_dir: str,
        target_dir: str,
        source_files: Dict[str, Dict],
        target_files: Dict[str, Dict],
        last_snapshot: Dict,
        direction: str
    ) -> Dict:
        """
        检测需要删除的文件
        
        Args:
            source_dir: 源目录
            target_dir: 目标目录
            source_files: 当前源目录文件列表
            target_files: 当前目标目录文件列表
            last_snapshot: 上次同步时的文件快照
            direction: 同步方向
            
        Returns:
            需要删除的文件字典
        """
        files_to_delete = {
            "source": {"files": [], "reasons": []},
            "target": {"files": [], "reasons": []}
        }
        
        last_source_files = set(last_snapshot.get("source", []))
        last_target_files = set(last_snapshot.get("target", []))
        current_source_files = set(source_files.keys())
        current_target_files = set(target_files.keys())
        
        # 检测源目录中消失但目标存在的文件（需要删除目标中的文件）
        if direction in ["both", "source_to_target"]:
            deleted_from_source = last_source_files - current_source_files
            for rel_path in deleted_from_source:
                if rel_path in current_target_files:
                    files_to_delete["target"]["files"].append(rel_path)
                    files_to_delete["target"]["reasons"].append("源目录已删除")
        
        # 检测目标目录中消失但源存在的文件（需要删除源中的文件）
        if direction in ["both", "target_to_source"]:
            deleted_from_target = last_target_files - current_target_files
            for rel_path in deleted_from_target:
                if rel_path in current_source_files:
                    files_to_delete["source"]["files"].append(rel_path)
                    files_to_delete["source"]["reasons"].append("目标目录已删除")
        
        self._log(f"\n🗑️ 检测到需要删除的文件：")
        self._log(f"  从目标删除: {len(files_to_delete['target']['files'])} 个")
        for i, rel_path in enumerate(files_to_delete['target']['files']):
            self._log_file(f"    - {rel_path} ({files_to_delete['target']['reasons'][i]})")
        self._flush_file_log()
        self._log(f"  从源删除: {len(files_to_delete['source']['files'])} 个")
        for i, rel_path in enumerate(files_to_delete['source']['files']):
            self._log_file(f"    - {rel_path} ({files_to_delete['source']['reasons'][i]})")
        self._flush_file_log()
        
        return files_to_delete
    
    def _execute_deletions(
        self,
        source_dir: str,
        target_dir: str,
        files_to_delete: Dict
    ):
        """
        执行删除操作（将文件移入回收站）
        
        Args:
            source_dir: 源目录
            target_dir: 目标目录
            files_to_delete: 需要删除的文件字典
        """
        self._log("\n📦 开始执行删除操作...")
        
        # 删除源目录中的文件
        for rel_path in files_to_delete["source"]["files"]:
            if self._interrupted:
                break
            
            self._wait_if_paused()
            
            file_path = str(Path(source_dir) / rel_path)
            if os.path.exists(file_path):
                self._update_progress(
                    current_file=f"🗑️ 删除: {rel_path}",
                    completed_files=len(self.completed_files)
                )
                
                if self.recycle_manager:
                    deleted_info = self.recycle_manager.add_deleted_file(file_path)
                    if deleted_info:
                        self._log_file(f"  ✅ 已将 {rel_path} 移入最近删除")
                    else:
                        try:
                            os.remove(file_path)
                            self._log_file(f"  ✅ 已删除 {rel_path}")
                        except Exception as e:
                            self._log(f"  ❌ 删除 {rel_path} 失败: {e}", level="error")
                else:
                    try:
                        os.remove(file_path)
                        self._log_file(f"  ✅ 已删除 {rel_path}")
                    except Exception as e:
                        self._log(f"  ❌ 删除 {rel_path} 失败: {e}", level="error")
                
                self.completed_files.add(f"delete_source_{rel_path}")
        
        # 删除目标目录中的文件
        for rel_path in files_to_delete["target"]["files"]:
            if self._interrupted:
                break
            
            self._wait_if_paused()
            
            file_path = str(Path(target_dir) / rel_path)
            if os.path.exists(file_path):
                self._update_progress(
                    current_file=f"🗑️ 删除: {rel_path}",
                    completed_files=len(self.completed_files)
                )
                
                if self.recycle_manager:
                    deleted_info = self.recycle_manager.add_deleted_file(file_path)
                    if deleted_info:
                        self._log_file(f"  ✅ 已将 {rel_path} 移入最近删除")
                    else:
                        try:
                            os.remove(file_path)
                            self._log_file(f"  ✅ 已删除 {rel_path}")
                        except Exception as e:
                            self._log(f"  ❌ 删除 {rel_path} 失败: {e}", level="error")
                else:
                    try:
                        os.remove(file_path)
                        self._log_file(f"  ✅ 已删除 {rel_path}")
                    except Exception as e:
                        self._log(f"  ❌ 删除 {rel_path} 失败: {e}", level="error")
                
                self.completed_files.add(f"delete_target_{rel_path}")
        
        self._flush_file_log()
        self._log(f"📦 删除操作完成")


def check_recovery_files(target_dir: str) -> tuple:
    """
    检查并返回未完成的同步任务文件
    
    Args:
        target_dir: 目标目录
        
    Returns:
        (临时文件列表, 进度文件列表)
    """
    temp_files = []
    progress_files = []

    if not os.path.isdir(target_dir):
        return temp_files, progress_files

    # v7.6: os.scandir 显式栈遍历，替代 os.walk
    dirs_to_visit = [target_dir]
    while dirs_to_visit:
        current = dirs_to_visit.pop()
        try:
            entries = list(os.scandir(current))
        except (OSError, PermissionError):
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    dirs_to_visit.append(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    if entry.name.endswith(TEMP_FILE_SUFFIX):
                        temp_files.append(entry.path)
                    if entry.name == PROGRESS_FILE:
                        progress_files.append(entry.path)
            except OSError:
                continue

    return temp_files, progress_files


def cleanup_temp_files(temp_files: List[str]) -> int:
    """
    清理临时文件
    
    Args:
        temp_files: 临时文件列表
        
    Returns:
        成功清理的文件数量
    """
    cleaned = 0
    for temp_file in temp_files:
        try:
            os.remove(temp_file)
            cleaned += 1
        except Exception:
            pass
    return cleaned