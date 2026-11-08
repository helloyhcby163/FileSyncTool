# -*- coding: utf-8 -*-
"""AI 配置生成器：预置 Prompt、分段响应解析、高危路径检测与预填映射。

v7.8.0 阶段 2：
- Prompt 注入运行环境（操作系统 + 脱敏后的主目录），并要求 AI 按四段输出；
- 从 AI 回复中提取 ```json ... ``` 代码块，损坏/缺失时抛出 AIConfigError；
- 源/目标路径强制 Path.resolve()，并检测系统高危目录，命中时标记 is_dangerous。
"""

import json
import os
import platform
import re
from pathlib import Path

DEFAULT_AI_PROMPT = """你是一个文件同步工具 FileSyncTool 的配置专家。请先理解我的需求，再给出可导入的任务配置。

当前运行环境：
- 操作系统：{os_name}
- 用户主目录（已脱敏，仅保留父级目录）：{user_home_dir}

请严格按以下四段输出，顺序不可变，不要输出四段之外的任何内容：

【需求分析】：
用 2-4 句话说明你对需求的理解，以及你为源目录、目标目录、同步方向做出的判断。

【安全风险提示】：
指出该配置可能造成的数据覆盖、误删除或误同步风险，并给出规避建议。

【配置 JSON】：
请用 ```json 代码块包裹严格 JSON，格式如下：
{
  "name": "任务名称（简短英文或拼音）",
  "source": "源目录绝对路径",
  "target": "目标目录绝对路径",
  "sync_direction": "both",
  "mode": "safe",
  "default_strategy": "conservative",
  "sync_hidden_files": false,
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
- sync_hidden_files 为布尔值；用户未提及时为 false。
- 如果没有提到扩展名，extensions 留空数组；extensions_mode 默认 "include"。
- 如果没有提到日期，date_enabled 为 false，date_from/date_to 留空字符串。

【导入操作指南】：
说明用户应如何把 JSON 复制到 FileSyncTool 的「AI 帮我配置」窗口并完成创建。

我的需求是：
[在这里输入你的需求，比如：把我的照片同步到D盘，覆盖旧文件]"""

ERROR_TEXT_KEY = "ai_json_error"
ERROR_TEXT_DEFAULT = "AI 返回格式错误，请重试"

DIRECTIONS = ("both", "source_to_target", "target_to_source")
MODES = ("safe", "fast")
STRATEGIES = ("conservative", "newest_wins", "source_wins", "target_wins")
EXTENSION_MODES = ("include", "exclude")

_SECTION_HEADERS = ("【需求分析】", "【安全风险提示】", "【配置 JSON】", "【导入操作指南】")
# 优先匹配 ```json 代码块；兼容 AI 输出 ```JSON 或仅 ``` 包裹的情况
_JSON_BLOCK_RE = re.compile(r"```[ \t]*json[ \t]*\r?\n?(.*?)```", re.DOTALL | re.IGNORECASE)
_ANY_FENCE_RE = re.compile(r"```[a-zA-Z0-9_-]*\s*(.*?)```", re.DOTALL)
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AIConfigError(Exception):
    """AI JSON 解析/校验失败。"""


def mask_home_dir(home_path=None) -> str:
    """
    脱敏用户主目录：保留父级目录，最后一级（通常是用户名）替换为 ***。

    说明：把完整家目录发给第三方 AI 存在泄露用户名的隐私风险，因此这里只保留
    盘符/上级目录（例如 C:\\Users\\***、/home/***），足以让 AI 推断路径风格，
    但不会暴露真实账户名。
    """
    try:
        home = Path(home_path or Path.home()).expanduser()
        parts = home.parts
        if len(parts) <= 1:
            return str(home)
        return str(Path(*parts[:-1]) / "***")
    except (OSError, RuntimeError, ValueError):
        return "***"


def build_ai_prompt(template: str = None) -> str:
    """把运行环境注入 Prompt（使用 replace 而非 format，避免 JSON 花括号冲突）。

    若用户外挂翻译里的旧 Prompt 没有环境占位符，则在开头补一段环境上下文，
    保证发给 AI 的 Prompt 始终包含操作系统与脱敏主目录。
    """
    base = str(template or DEFAULT_AI_PROMPT)
    try:
        os_name = platform.system() or "Unknown"
    except Exception:  # noqa: BLE001
        os_name = "Unknown"
    home = mask_home_dir()
    if "{os_name}" in base or "{user_home_dir}" in base:
        return base.replace("{os_name}", os_name).replace("{user_home_dir}", home)
    return (
        "当前运行环境：\n"
        f"- 操作系统：{os_name}\n"
        f"- 用户主目录（已脱敏，仅保留父级目录）：{home}\n\n"
        + base
    )


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


def _norm_path(path) -> str:
    """归一化路径用于比较（Windows 忽略大小写与分隔符差异）。"""
    if not path:
        return ""
    try:
        return os.path.normcase(os.path.abspath(str(path)))
    except (OSError, ValueError, TypeError):
        return ""


def _dangerous_roots() -> list:
    """返回当前系统的高危目录列表（均会在判定时做存在与否无关的字符串比较）。"""
    if os.name == "nt":
        system_drive = (os.environ.get("SystemDrive") or "C:") + os.sep
        candidates = [
            os.environ.get("SystemRoot") or r"C:\Windows",
            os.environ.get("ProgramFiles") or r"C:\Program Files",
            os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)",
            os.environ.get("ProgramData") or r"C:\ProgramData",
            system_drive,
            str(Path.home() / ".ssh"),
        ]
    else:
        candidates = [
            "/",
            "/System",
            "/usr",
            "/etc",
            "/bin",
            "/sbin",
            "/var",
            str(Path.home() / ".ssh"),
        ]
    return [item for item in candidates if item]


def _root_only_paths() -> set:
    """只能精确匹配、不能按“位于其内部”判断的根目录（否则所有路径都会命中）。"""
    roots = {_norm_path("/")}
    if os.name == "nt":
        roots.add(_norm_path((os.environ.get("SystemDrive") or "C:") + os.sep))
    roots.discard("")
    return roots


def is_dangerous_path(path) -> tuple:
    """
    判断路径是否命中系统高危目录。

    Returns:
        (是否高危, 命中的高危目录字符串)
    """
    value = _norm_path(path)
    if not value:
        return False, ""
    root_only = _root_only_paths()
    for root in _dangerous_roots():
        root_value = _norm_path(root)
        if not root_value:
            continue
        if value == root_value:
            return True, str(root)
        if root_value in root_only:
            continue
        prefix = root_value if root_value.endswith(os.sep) else root_value + os.sep
        if value.startswith(prefix):
            return True, str(root)
    return False, ""


def resolve_user_path(value) -> str:
    """强制把用户/AI 给出的路径解析为绝对路径（失败时退化为 absolute）。"""
    raw = str(value or "").strip()
    if not raw:
        return raw
    try:
        return str(Path(raw).expanduser().resolve())
    except (OSError, RuntimeError, ValueError):
        try:
            return str(Path(raw).expanduser().absolute())
        except (OSError, RuntimeError, ValueError):
            return raw


def extract_json_block(text) -> str:
    """从 AI 分段回复中提取 JSON 文本；找不到时返回空字符串。"""
    raw = str(text or "")
    match = _JSON_BLOCK_RE.search(raw)
    if match:
        return match.group(1).strip()
    match = _ANY_FENCE_RE.search(raw)
    if match:
        return match.group(1).strip()
    # 兼容没有代码块的纯 JSON / 夹杂解释的情况
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        return raw[start:end + 1].strip()
    return ""


def _extract_section(text, header) -> str:
    """提取某个【段名】到下一个段名之间的内容（缺失时返回空字符串）。"""
    raw = str(text or "")
    index = raw.find(header)
    if index < 0:
        return ""
    rest = raw[index + len(header):]
    ends = []
    for other in _SECTION_HEADERS:
        if other == header:
            continue
        pos = rest.find(other)
        if pos >= 0:
            ends.append(pos)
    end = min(ends) if ends else len(rest)
    value = rest[:end].strip()
    if value.startswith("："):
        value = value[1:].strip()
    return value


def parse_ai_config(text):
    """解析 AI 生成的 JSON，返回规范化后的配置字典（含 is_dangerous 标记）。"""
    raw = extract_json_block(text)
    if not raw:
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

    sync_hidden_files = data.get("sync_hidden_files", False)
    if not isinstance(sync_hidden_files, bool):
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

    # v7.8.0：源/目标路径强制解析为绝对路径，并检测系统高危目录
    source = resolve_user_path(_require_text(data, "source"))
    target = resolve_user_path(_require_text(data, "target"))
    dangerous_paths = []
    for path in (source, target):
        hit, _root = is_dangerous_path(path)
        if hit:
            dangerous_paths.append(path)

    return {
        "name": _require_text(data, "name"),
        "source": source,
        "target": target,
        "sync_direction": direction,
        "mode": mode,
        "default_strategy": strategy,
        "sync_hidden_files": sync_hidden_files,
        "extensions": _normalize_extensions(data.get("extensions")),
        "extensions_mode": extensions_mode,
        "date_enabled": date_enabled,
        "date_from": date_from,
        "date_to": date_to,
        "is_dangerous": bool(dangerous_paths),
        "dangerous_paths": dangerous_paths,
    }


def parse_ai_response(text) -> dict:
    """
    解析 AI 的分段回复，返回 {config, analysis, risk, guide}。

    JSON 缺失或损坏时抛出 AIConfigError，调用方应提示“AI 返回格式错误，请重试”。
    """
    raw = str(text or "")
    config = parse_ai_config(raw)
    return {
        "config": config,
        "analysis": _extract_section(raw, "【需求分析】"),
        "risk": _extract_section(raw, "【安全风险提示】"),
        "guide": _extract_section(raw, "【导入操作指南】"),
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
        "sync_hidden_files": bool(cfg.get("sync_hidden_files", False)),
    }
    template = build_filter_template(cfg)
    if template:
        prefill["ai_filter_template"] = template
    return prefill
