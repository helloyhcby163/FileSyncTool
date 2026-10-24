# -*- coding: utf-8 -*-
"""U 盘 / 移动设备监听（后台独立线程，不涉及任何 GUI 调用）。

设计：
- 纯轮询，不使用 ctypes 拦截 Windows 窗口消息，避免与 Tkinter 主循环冲突；
- Windows 枚举盘符 + 卷序列号；macOS 枚举 /Volumes；Linux 解析 /proc/mounts；
- 首次扫描只建立基线，不产生 inserted 事件（启动时已插着的设备不自动触发）；
- 新设备插入后等待 debounce（默认 3 秒）再读取硬件信息，防止系统挂载未完成；
- 事件回调在工作线程内执行，调用方必须自行转投主线程（GUI 使用 app.post_ui）。
"""

import ctypes
import os
import plistlib
import subprocess
import sys
import threading
from pathlib import Path

EVENT_INSERTED = "inserted"
EVENT_REMOVED = "removed"

_DEFAULT_POLL_INTERVAL = 2.0
_DEFAULT_DEBOUNCE = 3.0

_WIN_DRIVE_REMOVABLE = 2
_WIN_DRIVE_FIXED = 3
_WIN_BUS_TYPE_USB = 7
_IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
_STORAGE_DEVICE_PROPERTY = 0
_STORAGE_QUERY_TYPE_STANDARD = 0


def _device_info(serial, label, mount):
    return {
        "serial": serial or "",
        "label": label or "",
        "mount": mount or "",
    }


# ===================== Windows =====================

if sys.platform == "win32":
    from ctypes import wintypes

    class _STORAGE_PROPERTY_QUERY(ctypes.Structure):
        _fields_ = [
            ("PropertyId", wintypes.DWORD),
            ("QueryType", wintypes.DWORD),
            ("AdditionalParameters", wintypes.BYTE * 1),
        ]

    class _STORAGE_DEVICE_DESCRIPTOR(ctypes.Structure):
        _fields_ = [
            ("Version", wintypes.DWORD),
            ("Size", wintypes.DWORD),
            ("DeviceType", wintypes.BYTE),
            ("DeviceTypeModifier", wintypes.BYTE),
            ("RemovableMedia", wintypes.BOOLEAN),
            ("CommandQueueing", wintypes.BOOLEAN),
            ("VendorIdOffset", wintypes.DWORD),
            ("ProductIdOffset", wintypes.DWORD),
            ("ProductRevisionOffset", wintypes.DWORD),
            ("SerialNumberOffset", wintypes.DWORD),
            ("BusType", wintypes.DWORD),
            ("RawPropertiesLength", wintypes.DWORD),
            ("RawDeviceProperties", wintypes.BYTE * 1),
        ]


def _windows_is_usb(root):
    """对 DRIVE_FIXED 的盘符读取 BusType，判断是否为 USB 移动硬盘。"""
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateFileW(
            "\\\\.\\" + root.rstrip("\\"),
            0,
            0x00000001 | 0x00000002,  # FILE_SHARE_READ | FILE_SHARE_WRITE
            None,
            3,  # OPEN_EXISTING
            0,
            None,
        )
        if handle is None or handle == -1:
            return False
        try:
            query = _STORAGE_PROPERTY_QUERY()
            query.PropertyId = _STORAGE_DEVICE_PROPERTY
            query.QueryType = _STORAGE_QUERY_TYPE_STANDARD
            buffer = ctypes.create_string_buffer(1024)
            returned = wintypes.DWORD(0)
            ok = kernel32.DeviceIoControl(
                handle,
                _IOCTL_STORAGE_QUERY_PROPERTY,
                ctypes.byref(query),
                ctypes.sizeof(query),
                buffer,
                ctypes.sizeof(buffer),
                ctypes.byref(returned),
                None,
            )
            if not ok:
                return False
            desc = ctypes.cast(buffer, ctypes.POINTER(_STORAGE_DEVICE_DESCRIPTOR)).contents
            return int(desc.BusType) == _WIN_BUS_TYPE_USB
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return False


def _windows_volume_info(root):
    """返回 (serial, label)；取不到序列号返回 (\"\", label)。"""
    try:
        kernel32 = ctypes.windll.kernel32
        name_buf = ctypes.create_unicode_buffer(261)
        fs_buf = ctypes.create_unicode_buffer(261)
        serial = wintypes.DWORD(0)
        max_len = wintypes.DWORD(0)
        flags = wintypes.DWORD(0)
        ok = kernel32.GetVolumeInformationW(
            root,
            name_buf,
            261,
            ctypes.byref(serial),
            ctypes.byref(max_len),
            ctypes.byref(flags),
            fs_buf,
            261,
        )
        if not ok:
            return "", ""
        return f"{serial.value:08X}", name_buf.value
    except Exception:
        return "", ""


def _scan_windows():
    devices = {}
    try:
        mask = ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        return devices
    for index in range(26):
        if not (mask & (1 << index)):
            continue
        root = f"{chr(ord('A') + index)}:\\"
        try:
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(root)
        except Exception:
            continue
        if drive_type == _WIN_DRIVE_REMOVABLE:
            is_usb = True
        elif drive_type == _WIN_DRIVE_FIXED:
            is_usb = _windows_is_usb(root)
        else:
            continue
        if not is_usb:
            continue
        serial, label = _windows_volume_info(root)
        key = serial or f"mount:{root}"
        devices[key] = _device_info(serial, label, root)
    return devices


# ===================== macOS =====================

def _scan_macos():
    devices = {}
    volumes = Path("/Volumes")
    if not volumes.is_dir():
        return devices
    for mount in volumes.iterdir():
        try:
            if not mount.is_dir() or mount.is_symlink():
                continue
            output = subprocess.run(
                ["diskutil", "info", "-plist", str(mount)],
                capture_output=True, timeout=6, check=False,
            ).stdout
            info = plistlib.loads(output) if output else {}
        except Exception:
            continue
        if info.get("Internal") or info.get("RemovableMedia") is False:
            continue
        serial = info.get("VolumeUUID") or ""
        label = info.get("VolumeName") or mount.name
        key = serial or f"mount:{mount}"
        devices[key] = _device_info(serial, label, str(mount))
    return devices


# ===================== Linux =====================

_LINUX_MOUNT_ROOTS = ("/media/", "/run/media/", "/mnt/")


def _linux_uuid_map():
    mapping = {}
    by_uuid = Path("/dev/disk/by-uuid")
    if not by_uuid.is_dir():
        return mapping
    for entry in by_uuid.iterdir():
        try:
            mapping[str(entry.resolve())] = entry.name
        except OSError:
            continue
    return mapping


def _scan_linux():
    devices = {}
    uuid_map = _linux_uuid_map()
    try:
        with open("/proc/mounts", "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return devices
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        device, mount = parts[0], parts[1].replace("\\040", " ")
        if not any(mount.startswith(root) for root in _LINUX_MOUNT_ROOTS):
            continue
        serial = uuid_map.get(device, "")
        label = os.path.basename(mount.rstrip("/")) or mount
        key = serial or f"mount:{mount}"
        devices[key] = _device_info(serial, label, mount)
    return devices


# ===================== 统一入口 =====================

def _scan_devices():
    if sys.platform == "win32":
        return _scan_windows()
    if sys.platform == "darwin":
        return _scan_macos()
    return _scan_linux()


def snapshot_devices():
    """同步读取当前已插入的移动设备列表（供“绑定当前 U 盘”立即使用）。"""
    try:
        return list(_scan_devices().values())
    except Exception as exc:  # noqa: BLE001
        print(f"读取 U 盘信息失败: {exc}")
        return []


class UsbMonitor(threading.Thread):
    """后台轮询监听移动设备插拔。"""

    def __init__(self, on_event=None, poll_interval=_DEFAULT_POLL_INTERVAL,
                 debounce=_DEFAULT_DEBOUNCE, name="UsbMonitor"):
        super().__init__(name=name, daemon=True)
        self.on_event = on_event
        self.poll_interval = max(0.5, float(poll_interval))
        self.debounce = max(0.0, float(debounce))
        self._stop_event = threading.Event()
        self._known = {}
        self._started_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def wait_ready(self, timeout=5.0):
        """等待首次基线扫描完成（最长 timeout 秒）。"""
        return self._started_event.wait(timeout)

    def run(self):
        # 首次扫描：只建立基线，不触发事件
        self._known = _scan_devices()
        self._started_event.set()

        while not self._stop_event.is_set():
            if self._stop_event.wait(self.poll_interval):
                break

            current = _scan_devices()
            new_keys = [key for key in current if key not in self._known]
            removed_keys = [key for key in self._known if key not in current]

            if new_keys and self.debounce:
                # 等待系统完全挂载后再读取硬件信息
                if self._stop_event.wait(self.debounce):
                    break
                current = _scan_devices()
                new_keys = [key for key in new_keys if key in current]

            for key in removed_keys:
                info = self._known[key]
                self._emit(EVENT_REMOVED, info)

            for key in new_keys:
                self._emit(EVENT_INSERTED, current[key])

            self._known = current

    def _emit(self, event_type, info):
        event = dict(info)
        event["type"] = event_type
        event["volumes"] = [dict(info)]
        if not self.on_event:
            return
        try:
            self.on_event(event)
        except Exception as exc:  # noqa: BLE001
            print(f"U 盘事件回调失败: {exc}")


def parse_relative_subpath(path, mount):
    """把挂载点下的绝对路径转换为相对子路径；不在挂载点内返回 None。"""
    if not path or not mount:
        return None
    try:
        path_abs = os.path.abspath(path)
        mount_abs = os.path.abspath(mount)
    except (OSError, ValueError):
        return None
    if os.name == "nt":
        path_abs = path_abs.lower()
        mount_abs = mount_abs.lower()
    if path_abs == mount_abs:
        return ""
    prefix = mount_abs if mount_abs.endswith(os.sep) else mount_abs + os.sep
    if not path_abs.startswith(prefix):
        return None
    return os.path.abspath(path)[len(os.path.abspath(mount)):].lstrip("\\/")


def join_subpath(mount, subpath):
    """把挂载点与相对子路径拼为绝对路径。"""
    if not subpath:
        return mount
    return os.path.join(mount, subpath.replace("/", os.sep).replace("\\", os.sep))
