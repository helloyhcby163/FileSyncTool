
"""
文件同步工具 v7.6 - 无界面同步执行

供命令行模式使用：
- --task "任务名" --silent：执行一次同步后退出
- --watch "任务名" --idle N：监听触发时复用同一份执行逻辑

不依赖 GUI，不修改手动同步路径；与 GUI 使用同一个 FileSyncEngine。
"""

import os
import subprocess
from typing import Callable, Dict, Optional

from .config_manager import ConfigManager
from .recycle_manager import RecycleManager
from .sync_engine import FileSyncEngine as SyncEngine
from .task_manager import TaskManager


def run_post_sync_command(
    command: str,
    task_name: str = "",
    cwd: Optional[str] = None,
    log: Callable[[str], None] = print,
) -> Optional[int]:
    """
    同步成功后执行用户在任务中配置的命令（可选，留空不执行）。

    非阻塞启动，命令的退出结果不影响同步本身；返回启动的子进程 PID，
    启动失败返回 None。

    Args:
        command: 用户配置的命令行字符串
        task_name: 任务名（仅用于日志）
        cwd: 命令工作目录（默认取任务源目录）
        log: 日志函数
    """
    command = (command or "").strip()
    if not command:
        return None

    try:
        process = subprocess.Popen(command, shell=True, cwd=cwd)
    except Exception as e:
        log(f"⚠️ 同步后命令启动失败（任务「{task_name}」）：{e}")
        return None

    log(f"▶️ 已启动同步后命令（任务「{task_name}」，PID {process.pid}）：{command}")
    return process.pid


def _format_size(num_bytes: float) -> str:
    """字节数格式化为易读单位"""
    try:
        size = float(num_bytes)
    except (TypeError, ValueError):
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def build_engine_for_task(
    task: Dict,
    config_manager: ConfigManager,
    recycle_manager: RecycleManager,
    quiet: bool = False,
) -> SyncEngine:
    """
    根据任务配置与全局设置构造同步引擎（参数口径与 GUI 手动同步一致）。
    """
    settings = config_manager.get_settings()
    scan_workers = settings.get("scan_workers", settings.get("max_workers", 4))
    sync_workers = settings.get(
        "sync_workers", max(2, settings.get("max_workers", 4) // 2)
    )

    engine = SyncEngine(
        mode=task.get("mode", task.get("run_mode", "safe")),
        use_multithreading_scan=task.get("use_multithreading_scan", False),
        use_multithreading_copy=task.get("use_multithreading_copy", False),
        scan_workers=scan_workers,
        sync_workers=sync_workers,
        default_strategy=task.get("default_strategy", "conservative"),
        folder_strategies=task.get("folder_strategies", {}),
        root_included=task.get("root_included", False),
        root_strategy=task.get("root_strategy", "conservative"),
        life_protection_enabled=settings.get("life_protection_enabled", True),
        usb_level=settings.get("usb_level", "medium"),
        protection_strength=settings.get("protection_strength", "balanced"),
        sync_delete_enabled=task.get("sync_delete_enabled", False),
        recycle_manager=recycle_manager,
        chunk_size=int(settings.get("chunk_size_mb", 8)) * 1024 * 1024,
        folder_filters=task.get("folder_filters", {}),
        quiet=quiet,
        prevent_sleep_during_sync=settings.get("prevent_sleep_during_sync", True),
    )
    engine.config_manager = config_manager
    return engine


def run_task_once(
    task: Dict,
    config_manager: ConfigManager,
    task_manager: TaskManager,
    recycle_manager: Optional[RecycleManager] = None,
    silent: bool = False,
    log: Callable[[str], None] = print,
    watch_mode: bool = False,
) -> bool:
    """
    无界面执行一次任务同步。

    Args:
        task: 任务配置字典
        config_manager: 配置管理器
        task_manager: 任务管理器（用于持久化快照）
        recycle_manager: 回收站管理器，为 None 时新建
        silent: 静默模式（只输出摘要、错误与警告）
        log: 日志输出函数
        watch_mode: 是否为监听触发模式（True 时将进度写入共享状态文件，
                    供 GUI「正在进行的任务」页显示）

    Returns:
        是否成功完成（目录缺失或引擎异常返回 False）
    """
    task_name = task.get("name", "未命名任务")
    source_dir = task.get("source", "")
    target_dir = task.get("target", "")
    direction = task.get("sync_direction", "both")

    config_dir = config_manager.get_config_dir()

    # 监听模式：注册进度回调，把同步进度写入跨进程状态文件
    if watch_mode:
        from . import watch_process

        def _progress_callback(progress):
            try:
                watch_process.update_watch_sync_status(config_dir, task_name, {
                    "source": source_dir,
                    "target": target_dir,
                    "current_file": progress.current_file,
                    "current_phase": progress.current_phase,
                    "total_files": progress.total_files,
                    "completed_files": progress.completed_files,
                    "percentage": progress.percentage,
                    "elapsed_time": progress.elapsed_time,
                    "estimated_remaining": progress.estimated_remaining,
                    "speed": progress.speed,
                })
            except Exception:
                pass

    # 目录检查：给出具体原因（未插 U 盘时常见于目标目录）
    missing = []
    if not source_dir or not os.path.isdir(source_dir):
        missing.append(f"源目录不存在：{source_dir or '（未配置）'}")
    if not target_dir or not os.path.isdir(target_dir):
        missing.append(f"目标目录不存在：{target_dir or '（未配置）'}，请检查 U 盘是否已插入")
    if missing:
        for reason in missing:
            log(f"❌ 任务「{task_name}」无法同步：{reason}")
        return False

    if recycle_manager is None:
        recycle_manager = RecycleManager(config_manager)

    engine = build_engine_for_task(task, config_manager, recycle_manager, quiet=silent)
    if watch_mode:
        engine.set_progress_callback(_progress_callback)
    if silent:
        # 静默模式：只保留错误与警告级别的日志
        engine.set_log_callback(
            lambda msg: log(msg) if (
                "❌" in msg or "⚠️" in msg or "错误" in msg or "拦截" in msg
            ) else None
        )

    log(f"===== 开始同步任务「{task_name}」 =====")
    log(f"源目录：{source_dir}")
    log(f"目标目录：{target_dir}")

    try:
        engine.sync_directories(
            source_dir=source_dir,
            target_dir=target_dir,
            direction=direction,
            last_snapshot=task.get("last_snapshot"),
        )
    except Exception as e:
        log(f"❌ 任务「{task_name}」同步异常：{e}")
        if watch_mode:
            watch_process.clear_watch_sync_status(config_dir, task_name)
        return False

    stats = engine.get_stats()

    # 持久化本次快照（与 GUI 行为一致）
    if engine.last_snapshot and task.get("id"):
        try:
            task_manager.update_task(task["id"], {"last_snapshot": engine.last_snapshot})
        except Exception as e:
            log(f"⚠️ 保存快照失败：{e}")

    # 结果摘要
    blocked = len(stats.permission_denied)
    log(
        f"✅ 任务「{task_name}」同步完成："
        f"复制 {stats.files_copied} 个、更新 {stats.files_updated} 个、"
        f"跳过 {stats.files_skipped} 个、共 {_format_size(stats.total_size_copied)}、"
        f"耗时 {stats.total_time:.1f} 秒、错误 {len(stats.errors)} 个"
        + (f"、被安全软件拦截 {blocked} 个" if blocked else "")
    )
    if blocked:
        for path in stats.permission_denied[:10]:
            log(f"  ⚠️ 被拦截：{path}")
        if blocked > 10:
            log(f"  ……另有 {blocked - 10} 个文件被拦截")

    # 同步成功后执行用户配置的命令（失败不影响同步结果）
    run_post_sync_command(
        task.get("post_sync_command", ""),
        task_name=task_name,
        cwd=source_dir,
        log=log,
    )

    # 监听模式：同步结束后清除进度记录
    if watch_mode:
        watch_process.clear_watch_sync_status(config_dir, task_name)

    return len(stats.errors) == 0
