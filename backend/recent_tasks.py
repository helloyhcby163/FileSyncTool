"""文件名同步工具 v7.8.0 - 最近完成任务持久化

记录同步成功结束的任务，供首页「最近完成的任务」栏展示。
失败/中断不写入；文件损坏或缺失时静默返回空列表，绝不影响同步主流程。
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

MAX_RECENT_TASKS = 50
MAX_RECORDS_PER_TASK = 5
RECENT_TASKS_FILE = "recent_tasks.json"


def _trim_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """同一任务最多保留最近 5 条（记录本身已按时间倒序），并做全局上限保护。"""
    per_task: Dict[str, int] = {}
    result = []
    for item in records:
        name = str(item.get("task_name", ""))
        if per_task.get(name, 0) >= MAX_RECORDS_PER_TASK:
            continue
        per_task[name] = per_task.get(name, 0) + 1
        result.append(item)
        if len(result) >= MAX_RECENT_TASKS:
            break
    return result


class RecentTasksManager:
    """最近完成任务管理器（每任务保留最近 5 次，FIFO）"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self._lock = threading.Lock()

    def _get_file_path(self) -> Path:
        """返回 recent_tasks.json 的绝对路径（强制 resolve）"""
        config_dir = Path(self.config_manager.get_config_dir()).resolve()
        return (config_dir / RECENT_TASKS_FILE).resolve()

    def get_records(self) -> List[Dict[str, Any]]:
        """读取全部记录；文件缺失/损坏/非列表时返回空列表"""
        path = self._get_file_path()
        try:
            if not path.exists():
                return []
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return []
            records = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                records.append({
                    "task_name": str(item.get("task_name", "")),
                    "time": str(item.get("time", "")),
                    "file_count": int(item.get("file_count", 0) or 0),
                    "transaction_id": str(item.get("transaction_id", "")),
                })
            return _trim_records(records)
        except (OSError, ValueError, TypeError):
            return []

    def add_record(self, task_name: str, file_count: int,
                   transaction_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """追加一条成功记录（每任务保留最近 5 条），失败时静默返回 None"""
        record = {
            "task_name": str(task_name or ""),
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "file_count": int(file_count or 0),
            "transaction_id": str(transaction_id or ""),
        }
        # 注意：这里绝不伪造 transaction_id。空值表示本次同步没有可回滚的快照，
        # 由 UI 提示“快照缺失”；伪造随机 UUID 会指向不存在的清单，掩盖真实问题。

        with self._lock:
            records = self.get_records()
            records.insert(0, record)
            records = _trim_records(records)
            if not self._write(records):
                return None
        return record

    def clear(self) -> bool:
        """清空记录"""
        with self._lock:
            return self._write([])

    def _write(self, records: List[Dict[str, Any]]) -> bool:
        """原子写入（临时文件 + os.replace），失败静默"""
        path = self._get_file_path()
        tmp_path = path.with_name(path.name + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
            return True
        except OSError:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            return False
