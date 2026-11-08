"""v7.8.0 同步事务备份与一键回滚

每次同步作为一个事务：覆盖/删除文件前先把旧内容复制到
`<config_dir>/sync_backups/<transaction_id>/`，新建文件登记到清单。
事务清单存于 `<config_dir>/sync_transactions/<transaction_id>.json`。

设计约束：
- 任何异常都不得影响同步主流程（所有磁盘操作失败均静默/仅告警）；
- 清单缺失损坏时回滚返回结构化失败，不抛异常；
- 每个任务最多保留最近 5 次事务，超出部分由 `commit()` 自动清理；
- 回滚只读取清单，绝不基于目录扫描猜测路径。
"""

import json
import os
import re
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

TRANSACTIONS_DIRNAME = "sync_transactions"
BACKUPS_DIRNAME = "sync_backups"
MAX_SNAPSHOTS_PER_TASK = 5

# 事务 ID 必须是 32 位十六进制，杜绝路径穿越
_TRANSACTION_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


class TransactionBackup:
    """同步事务备份管理器（供同步引擎逐文件登记）"""

    def __init__(self, config_dir, task_name: str = ""):
        self.config_dir = Path(config_dir).resolve()
        self.task_name = str(task_name or "")
        self.transactions_dir = self.config_dir / TRANSACTIONS_DIRNAME
        self.backups_dir = self.config_dir / BACKUPS_DIRNAME

        self.transaction_id = ""
        self.enabled = True
        self._entries: List[Dict[str, str]] = []
        self._counter = 0
        self._lock = threading.Lock()
        self._backup_warned = False
        # 清单是否已成功落盘（提交后不得再被 abort 删除）
        self._committed = False

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def start(self) -> str:
        """开启事务：建立备份目录，返回事务 ID（重复调用会重置）"""
        with self._lock:
            self.transaction_id = uuid.uuid4().hex
            self._entries = []
            self._counter = 0
            self.enabled = True
            self._committed = False
            try:
                self.transactions_dir.mkdir(parents=True, exist_ok=True)
                self.backups_dir.mkdir(parents=True, exist_ok=True)
                (self.backups_dir / self.transaction_id).mkdir(
                    parents=True, exist_ok=True
                )
            except OSError:
                self.enabled = False
            return self.transaction_id

    @property
    def active(self) -> bool:
        """是否处于可登记状态"""
        return bool(self.transaction_id) and self.enabled

    def _tx_backup_dir(self) -> Path:
        return self.backups_dir / self.transaction_id

    # ------------------------------------------------------------------
    # 逐文件登记
    # ------------------------------------------------------------------
    def backup_file(self, path, action: str) -> bool:
        """把即将被覆盖/删除的文件复制进事务备份目录。

        Args:
            path: 原文件路径
            action: "overwrite" 或 "delete"

        Returns:
            是否成功备份（失败仅告警，不阻断同步）
        """
        if not self.active:
            return False
        try:
            original = Path(path).resolve()
        except OSError:
            original = Path(path)
        if not original.is_file():
            return False

        with self._lock:
            self._counter += 1
            backup_path = self._tx_backup_dir() / f"{self._counter:04d}_{original.name}"
            try:
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(original), str(backup_path))
            except OSError as exc:
                if not self._backup_warned:
                    self._backup_warned = True
                    print(f"⚠️ 事务备份失败（回滚能力受限）：{exc}")
                return False
            self._entries.append({
                "action": action,
                "original_path": str(original),
                "backup_path": str(backup_path),
            })
            return True

    def record_created(self, path) -> None:
        """登记本次同步新建的文件（回滚时删除）"""
        if not self.active:
            return
        try:
            original = Path(path).resolve()
        except OSError:
            original = Path(path)
        with self._lock:
            self._entries.append({
                "action": "create",
                "original_path": str(original),
                "backup_path": "",
            })

    def commit(self) -> bool:
        """写入事务清单并清理该任务超出 5 次的历史事务。

        注意：提交成功后 **保留 transaction_id**，因为 GUI/CLI 是在同步
        返回之后才读取 `engine.transaction_id` 写入 recent_tasks.json；
        若在这里清空，记录里就会拿到空串（曾导致“快照缺失”的回滚失败）。

        Returns:
            清单是否写入成功
        """
        if not self.transaction_id:
            return False
        with self._lock:
            entries = list(self._entries)
            transaction_id = self.transaction_id
            self._entries = []
            # 提交后不再接收新的逐文件登记
            self.enabled = False

        payload = {
            "transaction_id": transaction_id,
            "task_name": self.task_name,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": "complete",
            "entries": entries,
        }
        ok = self._write_manifest(payload)
        if ok:
            # 清单已落盘，后续无论发生什么都不得 abort 掉这份快照
            self._committed = True
            try:
                self.prune(self.task_name)
            except Exception:  # noqa: BLE001
                # 清理旧快照失败不影响本次快照可用
                pass
        return ok

    def abort(self) -> None:
        """放弃事务：删除本次已产生的备份与清单（已提交的快照除外）"""
        if not self.transaction_id:
            return
        with self._lock:
            if self._committed:
                # 已提交的快照是回滚依赖的数据，绝不能被 abort 删除
                return
            transaction_id = self.transaction_id
            self.transaction_id = ""
            self._entries = []

        try:
            tx_dir = self.backups_dir / transaction_id
            if tx_dir.exists():
                shutil.rmtree(tx_dir, ignore_errors=True)
            manifest = self.transactions_dir / f"{transaction_id}.json"
            if manifest.exists():
                manifest.unlink()
        except OSError:
            pass

    # ------------------------------------------------------------------
    # 清单读写与清理
    # ------------------------------------------------------------------
    def _write_manifest(self, payload: Dict[str, Any]) -> bool:
        transaction_id = str(payload.get("transaction_id", ""))
        if not _TRANSACTION_ID_PATTERN.fullmatch(transaction_id):
            return False
        manifest = self.transactions_dir / f"{transaction_id}.json"
        tmp = manifest.with_name(manifest.name + ".tmp")
        try:
            manifest.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, manifest)
            return True
        except (OSError, TypeError, ValueError):
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            return False

    def prune(self, task_name: Optional[str] = None,
              keep: int = MAX_SNAPSHOTS_PER_TASK) -> int:
        """删除同一任务第 keep 次之后的事务清单与备份目录。

        Returns:
            清理掉的事务数量（失败静默）
        """
        target_task = self.task_name if task_name is None else str(task_name or "")
        keep = max(1, int(keep))
        try:
            if not self.transactions_dir.is_dir():
                return 0
            candidates = []
            for manifest in self.transactions_dir.glob("*.json"):
                if not _TRANSACTION_ID_PATTERN.fullmatch(manifest.stem):
                    continue
                data = _read_manifest_file(manifest)
                if not data:
                    continue
                if str(data.get("task_name", "")) != target_task:
                    continue
                candidates.append((str(data.get("created_at", "")), manifest.stem))
            candidates.sort(reverse=True)
            removed = 0
            for _, transaction_id in candidates[keep:]:
                self._remove_transaction(transaction_id)
                removed += 1
            return removed
        except OSError:
            return 0

    def _remove_transaction(self, transaction_id: str) -> None:
        if not _TRANSACTION_ID_PATTERN.fullmatch(transaction_id):
            return
        try:
            manifest = self.transactions_dir / f"{transaction_id}.json"
            if manifest.exists():
                manifest.unlink()
            tx_dir = self.backups_dir / transaction_id
            if tx_dir.exists():
                shutil.rmtree(tx_dir, ignore_errors=True)
        except OSError:
            pass


def _read_manifest_file(path: Path) -> Optional[Dict[str, Any]]:
    """读取事务清单；缺失/损坏/结构异常一律返回 None"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("entries", []), list):
        return None
    return data


def load_transaction(config_dir, transaction_id: str) -> Optional[Dict[str, Any]]:
    """读取指定事务清单（供 UI 判断历史版本是否仍可回滚）"""
    transaction_id = str(transaction_id or "")
    if not _TRANSACTION_ID_PATTERN.fullmatch(transaction_id):
        return None
    tx_dir = Path(config_dir).resolve() / TRANSACTIONS_DIRNAME
    return _read_manifest_file(tx_dir / f"{transaction_id}.json")


def rollback_transaction(config_dir, transaction_id: str) -> Dict[str, Any]:
    """按事务清单逆序回滚一次同步。

    Returns:
        {"success": bool, "restored": int, "removed": int,
         "failed": int, "message": str}
    """
    result = {
        "success": False,
        "restored": 0,
        "removed": 0,
        "failed": 0,
        "message": "",
    }
    transaction_id = str(transaction_id or "")
    if not _TRANSACTION_ID_PATTERN.fullmatch(transaction_id):
        result["message"] = "事务 ID 非法，无法回滚"
        return result

    manifest = load_transaction(config_dir, transaction_id)
    if not manifest:
        result["message"] = "快照缺失，无法回滚（可能已被新的同步记录顶掉）"
        return result
    if str(manifest.get("status", "")) != "complete":
        result["message"] = "该事务未正常完成，不支持回滚"
        return result

    entries = manifest.get("entries", [])
    restored = 0
    removed = 0
    failed = 0

    # 逆序撤销，先删除新建文件，再恢复被覆盖/删除的文件
    for entry in reversed(entries):
        if not isinstance(entry, dict):
            failed += 1
            continue
        action = str(entry.get("action", ""))
        raw_original = str(entry.get("original_path", "") or "")
        if not raw_original:
            failed += 1
            continue
        try:
            original = Path(raw_original).resolve()
        except (OSError, ValueError):
            failed += 1
            continue
        if action == "create":
            try:
                if original.is_file():
                    original.unlink()
                    removed += 1
            except OSError:
                failed += 1
            continue

        raw_backup = str(entry.get("backup_path", "") or "")
        if not raw_backup:
            failed += 1
            continue
        try:
            backup = Path(raw_backup).resolve()
        except (OSError, ValueError):
            failed += 1
            continue
        try:
            if not backup.is_file():
                failed += 1
                continue
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(backup), str(original))
            restored += 1
        except OSError:
            failed += 1

    result["restored"] = restored
    result["removed"] = removed
    result["failed"] = failed
    result["success"] = failed == 0
    if failed == 0:
        result["message"] = (
            f"已回滚：恢复 {restored} 个文件，删除 {removed} 个新建文件"
        )
    else:
        result["message"] = (
            f"回滚部分完成：恢复 {restored} 个，删除 {removed} 个，"
            f"{failed} 个失败（备份可能已被清理）"
        )
    return result
