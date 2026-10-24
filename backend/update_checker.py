# -*- coding: utf-8 -*-
"""GitHub Releases 更新检查。

规则：
- 只读取 /releases/latest；
- 最新版本发布时间距今不足 24 小时 → 暂不提示（reason="too_new"）；
- 自动检查最多每 24 小时一次（settings.last_update_check）；
- 网络/解析异常静默返回 None，不打扰用户。
"""

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from .version import APP_VERSION, RELEASES_LATEST_API, is_newer

TOO_NEW_HOURS = 24
AUTO_CHECK_INTERVAL = timedelta(hours=24)

_SHA256_RE = re.compile(r"(?i)sha-?256[^0-9a-f]{0,16}([0-9a-f]{64})")
_HEX64_RE = re.compile(r"(?i)\b([0-9a-f]{64})\b")


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _pick_asset(assets):
    if not isinstance(assets, list):
        return {}
    for asset in assets:
        name = str(asset.get("name") or "")
        if name.lower().endswith(".exe"):
            return asset
    return {}


def _fetch_checksum_asset(assets, timeout=10):
    """从 Release 关联的 .sha256 / checksums 文件读取哈希。"""
    if not isinstance(assets, list):
        return ""
    for asset in assets:
        name = str(asset.get("name") or "").lower()
        if not (name.endswith(".sha256") or "checksum" in name):
            continue
        url = str(asset.get("browser_download_url") or "")
        if not url:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FileSyncTool"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
        except (urllib.error.URLError, OSError, ValueError):
            continue
        match = _HEX64_RE.search(text)
        if match:
            return match.group(1).lower()
    return ""


def _extract_sha256(payload, timeout=10):
    """
    获取官方 SHA-256（v7.7.1）。

    优先级：
    1. GitHub Assets API 的 digest 字段（sha256:...）；
    2. Release 正文中的 sha256 哈希；
    3. Release 关联的 .sha256 / checksums 文件。

    未找到时返回空字符串，由上层中止自动更新。
    """
    assets = payload.get("assets") if isinstance(payload, dict) else None

    if isinstance(assets, list):
        for asset in assets:
            digest = str(asset.get("digest") or "").strip()
            if digest.lower().startswith("sha256:"):
                value = digest.split(":", 1)[1].strip().lower()
                if _HEX64_RE.fullmatch(value):
                    return value

    body = str((payload or {}).get("body") or "")
    match = _SHA256_RE.search(body)
    if match:
        return match.group(1).lower()

    return _fetch_checksum_asset(assets, timeout=timeout)


def check_for_update(current=APP_VERSION, timeout=10, now=None):
    """检查更新。

    Returns:
        None：网络/解析失败；
        {"reason": "up_to_date", ...}：无新版本；
        {"reason": "too_new", ...}：有新版本但发布不足 24 小时；
        其余为可直接下载的更新信息字典。
    """
    try:
        req = urllib.request.Request(
            RELEASES_LATEST_API,
            headers={
                "User-Agent": f"FileSyncTool/{current}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"检查更新失败: {exc}")
        return None

    tag = str(payload.get("tag_name") or "").strip()
    version = tag.lstrip("vV") or str(payload.get("name") or "")
    published = _parse_time(payload.get("published_at"))
    asset = _pick_asset(payload.get("assets"))
    info = {
        "version": version,
        "tag": tag,
        "published_at": published.isoformat() if published else "",
        "notes": str(payload.get("body") or "").strip(),
        "page_url": str(payload.get("html_url") or ""),
        "asset_url": str(asset.get("browser_download_url") or ""),
        "asset_name": str(asset.get("name") or ""),
        "asset_size": int(asset.get("size") or 0),
        # v7.7.1：官方 SHA-256（未提供时为空，下载层将中止更新）
        "sha256": _extract_sha256(payload, timeout=timeout),
    }

    if not is_newer(version, current):
        info["reason"] = "up_to_date"
        return info

    reference = now or datetime.now(timezone.utc)
    if published is not None:
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if reference - published < timedelta(hours=TOO_NEW_HOURS):
            info["reason"] = "too_new"
            return info

    info["reason"] = "available"
    return info


def should_auto_check(config_manager, now=None):
    """是否应执行启动自动检查（开关开启且距上次检查 ≥ 24 小时）。"""
    try:
        settings = config_manager.get_settings()
    except Exception:
        return False
    if not settings.get("auto_check_updates", True):
        return False
    last = _parse_time(settings.get("last_update_check"))
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    reference = now or datetime.now(timezone.utc)
    return reference - last >= AUTO_CHECK_INTERVAL


def record_check_time(config_manager, now=None):
    """记录本次检查时间（UTC ISO），用于 24 小时节流。"""
    try:
        settings = config_manager.get_settings()
        settings["last_update_check"] = (now or datetime.now(timezone.utc)).isoformat()
        config_manager.update_settings(settings)
    except Exception as exc:  # noqa: BLE001
        print(f"记录更新检查时间失败: {exc}")
