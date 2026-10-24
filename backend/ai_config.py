# -*- coding: utf-8 -*-
"""AI 配置生成器：预置 Prompt、JSON 解析与预填映射。"""

import json
import re

DEFAULT_AI_PROMPT = """你是一个文件同步工具 FileSyncTool 的配置专家。请根据我的需求，生成一个合法的 JSON 任务配置。
输出要求：只输出纯 JSON 代码，不要任何 markdown 标记，不要任何解释。
JSON 格式必须严格如下：
{
  "name": "任务名称（简短英文或拼音）",
  "source": "源目录绝对路径",
  "target": "目标目录绝对路径",
  "sync_direction": "both", 
  "mode": "safe",
  "default_strategy": "conservative",
  "extensions": [],
  "extensions_mode": "include",
  "date_enabled": false,
  "date_from": "",
  "date_to": ""
}
约束条件：
- sync_direction 只能是 "both", "source_to_target", "target_to_source"。
- mode 只能是 "safe" 或 "fast"。
- default_strategy 只能是 "conservative", "newest_wins", "source_wins", "target_wins"。
- 如果没有提到扩展名，extensions 留空数组；extensions_mode 默认 "include"。
- 如果没有提到日期，date_enabled 为 false，date_from/date_to 留空字符串。

我的需求是：
[在这里输入你的需求，比如：把我的照片同步到D盘，覆盖旧文件]"""

ERROR_TEXT_KEY = "ai_json_error"
ERROR_TEXT_DEFAULT = "JSON 格式错误，请重新生成"

DIRECTIONS = ("both", "source_to_target", "target_to_source")
MODES = ("safe", "fast")
STRATEGIES = ("conservative", "newest_wins", "source_wins", "target_wins")
EXTENSION_MODES = ("include", "exclude")

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AIConfigError(Exception):
    """AI JSON 解析/校验失败。"""


def _strip_fences(text):
    value = (text or "").strip()
    if value.startswith("```"):
        value = _FENCE_RE.sub("", value).strip()
    return value


def _require_text(data, key):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AIConfigError(ERROR_TEXT_DEFAULT)
    return value.strip()


def _normalize_extensions(value):
    if value is None or value == "":
        return []
    if isinstance(value, str):
        value = [part for part in re.split(r"[,;\s]+", value) if part]
    if not isinstance(value, list):
        raise AIConfigError(ERROR_TEXT_DEFAULT)
    result = []
    for item in value:
        if not isinstance(item, str):
            raise AIConfigError(ERROR_TEXT_DEFAULT)
        ext = item.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = "." + ext
        result.append(ext)
    return result


def parse_ai_config(text):
    """解析 AI 生成的 JSON，返回规范化后的配置字典。"""
    raw = _strip_fences(text)
    if not raw:
        raise AIConfigError(ERROR_TEXT_DEFAULT)
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        raise AIConfigError(ERROR_TEXT_DEFAULT) from None
    if not isinstance(data, dict):
        raise AIConfigError(ERROR_TEXT_DEFAULT)

    direction = data.get("sync_direction", "both")
    if direction not in DIRECTIONS:
        raise AIConfigError(ERROR_TEXT_DEFAULT)
    mode = data.get("mode", "safe")
    if mode not in MODES:
        raise AIConfigError(ERROR_TEXT_DEFAULT)
    strategy = data.get("default_strategy", "conservative")
    if strategy not in STRATEGIES:
        raise AIConfigError(ERROR_TEXT_DEFAULT)
    extensions_mode = data.get("extensions_mode", "include")
    if extensions_mode not in EXTENSION_MODES:
        raise AIConfigError(ERROR_TEXT_DEFAULT)

    date_enabled = data.get("date_enabled", False)
    if not isinstance(date_enabled, bool):
        raise AIConfigError(ERROR_TEXT_DEFAULT)
    date_from = data.get("date_from", "") or ""
    date_to = data.get("date_to", "") or ""
    if not isinstance(date_from, str) or not isinstance(date_to, str):
        raise AIConfigError(ERROR_TEXT_DEFAULT)
    date_from = date_from.strip()
    date_to = date_to.strip()
    if date_from and not _DATE_RE.match(date_from):
        raise AIConfigError(ERROR_TEXT_DEFAULT)
    if date_to and not _DATE_RE.match(date_to):
        raise AIConfigError(ERROR_TEXT_DEFAULT)

    return {
        "name": _require_text(data, "name"),
        "source": _require_text(data, "source"),
        "target": _require_text(data, "target"),
        "sync_direction": direction,
        "mode": mode,
        "default_strategy": strategy,
        "extensions": _normalize_extensions(data.get("extensions")),
        "extensions_mode": extensions_mode,
        "date_enabled": date_enabled,
        "date_from": date_from,
        "date_to": date_to,
    }


def build_filter_template(cfg):
    """把 extensions/date 转换为 FolderConfigDialog 的筛选配置结构。"""
    extensions = cfg.get("extensions") or []
    date_enabled = bool(cfg.get("date_enabled"))
    if not extensions and not date_enabled:
        return {}
    return {
        "date_filter_enabled": date_enabled,
        "date_filter_start": cfg.get("date_from", "") if date_enabled else "",
        "date_filter_end": cfg.get("date_to", "") if date_enabled else "",
        "extension_filter_enabled": bool(extensions),
        "extension_filter_mode": cfg.get("extensions_mode", "include"),
        "extension_filter_list": list(extensions),
    }


def to_task_prefill(cfg):
    """转换为创建任务页的 prefill_config。"""
    prefill = {
        "name": cfg.get("name", ""),
        "source": cfg.get("source", ""),
        "target": cfg.get("target", ""),
        "sync_direction": cfg.get("sync_direction", "both"),
        "mode": cfg.get("mode", "safe"),
        "default_strategy": cfg.get("default_strategy", "conservative"),
    }
    template = build_filter_template(cfg)
    if template:
        prefill["ai_filter_template"] = template
    return prefill
