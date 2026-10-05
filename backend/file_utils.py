"""
文件同步工具 v7.0 - 文件工具函数
提供文件大小格式化、路径处理等通用功能
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 文件大小（字节）
        
    Returns:
        格式化后的字符串（如 "1.23 MB"）
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0 or unit == 'TB':
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0


def format_time(seconds: float) -> str:
    """
    格式化时间
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化后的字符串（如 "1分23秒"）
    """
    if seconds < 60:
        return f"{int(seconds)}秒"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}分{secs}秒"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}时{minutes}分"


def get_file_info(filepath: str) -> Optional[Dict]:
    """
    获取文件信息
    
    Args:
        filepath: 文件路径
        
    Returns:
        文件信息字典，如果失败则返回 None
    """
    try:
        path = Path(filepath)
        if not path.exists():
            return None
        
        stat = path.stat()
        return {
            'size': stat.st_size,
            'mtime': stat.st_mtime,
            'ctime': stat.st_ctime,
            'is_file': path.is_file(),
            'is_dir': path.is_dir()
        }
    except Exception:
        return None


def get_directory_size(directory: str) -> int:
    """
    获取目录大小
    
    Args:
        directory: 目录路径
        
    Returns:
        目录总大小（字节）
    """
    total_size = 0
    
    try:
        for root, dirs, files in os.walk(directory):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(filepath)
                except Exception:
                    pass
    except Exception:
        pass
    
    return total_size


def get_file_count(directory: str, include_hidden: bool = False) -> int:
    """
    获取目录中的文件数量
    
    Args:
        directory: 目录路径
        include_hidden: 是否包含隐藏文件
        
    Returns:
        文件数量
    """
    count = 0
    
    try:
        for root, dirs, files in os.walk(directory):
            # 过滤隐藏目录
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            # 过滤隐藏文件
            if include_hidden:
                count += len(files)
            else:
                count += len([f for f in files if not f.startswith('.')])
    except Exception:
        pass
    
    return count


def get_subfolders(directory: str, include_hidden: bool = False) -> List[str]:
    """
    获取目录中的子文件夹列表
    
    Args:
        directory: 目录路径
        include_hidden: 是否包含隐藏文件夹
        
    Returns:
        子文件夹名称列表
    """
    folders = []
    
    try:
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            return folders
        
        for item in path.iterdir():
            if item.is_dir():
                if include_hidden or not item.name.startswith('.'):
                    folders.append(item.name)
    except Exception:
        pass
    
    return sorted(folders)


def is_valid_directory(path: str) -> bool:
    """
    检查路径是否为有效目录
    
    Args:
        path: 路径
        
    Returns:
        是否为有效目录
    """
    try:
        p = Path(path)
        return p.exists() and p.is_dir()
    except Exception:
        return False


def normalize_path(path: str) -> str:
    """
    规范化路径
    
    Args:
        path: 路径
        
    Returns:
        规范化后的路径
    """
    try:
        return str(Path(path).resolve())
    except Exception:
        return path


def get_relative_path(base_path: str, full_path: str) -> str:
    """
    获取相对路径
    
    Args:
        base_path: 基础路径
        full_path: 完整路径
        
    Returns:
        相对路径
    """
    try:
        base = Path(base_path)
        full = Path(full_path)
        return str(full.relative_to(base))
    except Exception:
        return full_path


def ensure_directory_exists(directory: str) -> bool:
    """
    确保目录存在
    
    Args:
        directory: 目录路径
        
    Returns:
        是否成功创建或目录已存在
    """
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


def copy_file_with_metadata(src: str, dst: str) -> bool:
    """
    复制文件并保留元数据
    
    Args:
        src: 源文件路径
        dst: 目标文件路径
        
    Returns:
        是否成功复制
    """
    try:
        import shutil
        # 确保目标目录存在
        ensure_directory_exists(str(Path(dst).parent))
        # 复制文件
        shutil.copy2(src, dst)
        return True
    except Exception:
        return False


def move_file(src: str, dst: str) -> bool:
    """
    移动文件
    
    Args:
        src: 源文件路径
        dst: 目标文件路径
        
    Returns:
        是否成功移动
    """
    try:
        import shutil
        # 确保目标目录存在
        ensure_directory_exists(str(Path(dst).parent))
        # 移动文件
        shutil.move(src, dst)
        return True
    except Exception:
        return False


def delete_file(filepath: str) -> bool:
    """
    删除文件
    
    Args:
        filepath: 文件路径
        
    Returns:
        是否成功删除
    """
    try:
        os.remove(filepath)
        return True
    except Exception:
        return False


def get_file_extension(filepath: str) -> str:
    """
    获取文件扩展名
    
    Args:
        filepath: 文件路径
        
    Returns:
        文件扩展名（包含点，如 ".txt"）
    """
    try:
        return Path(filepath).suffix
    except Exception:
        return ""


def get_filename(filepath: str) -> str:
    """
    获取文件名（不含路径）
    
    Args:
        filepath: 文件路径
        
    Returns:
        文件名
    """
    try:
        return Path(filepath).name
    except Exception:
        return filepath


# ===================== v7.6: 配置/语言目录迁移辅助 =====================


def rollback_copied_files(
    new_dir: Path,
    copied_files: List[str],
    preexisting_files: Set[str],
    preexisting_dirs: Set[str],
    created_new_dir: bool,
):
    """
    迁移失败回滚：删除本次复制的文件；若目录为本次新建则整目录删除；
    否则仅清理本次新建的空子目录。不留"一半迁移"状态。
    """
    try:
        for path_str in copied_files:
            try:
                os.remove(path_str)
            except Exception:
                pass
        if created_new_dir:
            shutil.rmtree(str(new_dir), ignore_errors=True)
        else:
            # 自底向上删除本次新建的空子目录（迁移前已存在的目录不动）
            try:
                all_dirs = sorted(
                    (p for p in new_dir.rglob("*") if p.is_dir()),
                    key=lambda x: len(str(x)),
                    reverse=True,
                )
                for d in all_dirs:
                    if str(d) in preexisting_dirs:
                        continue
                    try:
                        d.rmdir()
                    except Exception:
                        pass
            except Exception:
                pass
    finally:
        print("迁移失败，已回滚")


def delete_dir_contents(dir_path: Path, exclude_names: tuple = ()) -> Tuple[bool, str]:
    """
    删除目录下的全部文件与空子目录，exclude_names 中的文件名（仅顶层）保留。

    Returns:
        (是否完全成功, 失败摘要)
    """
    if not dir_path.is_dir():
        return (False, "目录不存在")
    errors: List[str] = []
    for p in dir_path.rglob("*"):
        if not p.is_file():
            continue
        # 仅顶层文件按名称排除（如默认目录下的 config_path.json 指针）
        if p.parent == dir_path and p.name in exclude_names:
            continue
        try:
            p.unlink()
        except Exception as e:
            errors.append(f"{p.name}: {e}")
    for d in sorted(
        (p for p in dir_path.rglob("*") if p.is_dir()),
        key=lambda x: len(str(x)),
        reverse=True,
    ):
        try:
            d.rmdir()
        except Exception:
            pass
    if errors:
        return (False, "; ".join(errors[:5]))
    return (True, "")