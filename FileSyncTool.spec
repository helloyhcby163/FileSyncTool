# -*- mode: python ; coding: utf-8 -*-
"""
文件同步工具 v7.6 - PyInstaller 打包配置文件

修复要点：
- hiddenimports 包含 plyer 各平台通知模块，防止打包后通知功能失效
- datas 包含 translations 目录、docs 目录、图标文件
- 使用 sys._MEIPASS 处理资源路径
- v7.6: onefile 模式，输出 main.exe，方便 release.yml 重命名
"""

import sys
from pathlib import Path

block_cipher = None

# 程序根目录
project_root = Path(SPECPATH).resolve()

# 收集 plyer 跨平台通知模块的 hiddenimports
plyer_notification_imports = [
    'plyer.platforms.win.notification',
    'plyer.platforms.linux.notification',
    'plyer.platforms.macos.notification',
]

# plyer 其他常用模块（防止打包后 plyer 子模块缺失）
plyer_extra_imports = [
    'plyer.facades',
    'plyer.platforms',
    'plyer.platforms.win',
    'plyer.platforms.linux',
    'plyer.platforms.macos',
]

# 数据文件：多语言、帮助文档、图标
ctk_datas = [
    (str(project_root / 'translations'), 'translations'),
    (str(project_root / 'docs'), 'docs'),
    (str(project_root / 'FileSyncTool.ico'), '.'),
]

# 尝试收集 CustomTkinter 的主题数据
try:
    import customtkinter
    ctk_install_dir = Path(customtkinter.__file__).parent
    ctk_themes_dir = ctk_install_dir / 'assets' / 'themes'
    if ctk_themes_dir.exists():
        ctk_datas.append((str(ctk_themes_dir), 'customtkinter/assets/themes'))
    ctk_assets = ctk_install_dir / 'assets'
    if ctk_assets.exists():
        for item in ctk_assets.rglob('*'):
            if item.is_file():
                rel = item.relative_to(ctk_install_dir)
                ctk_datas.append((str(item), str(rel.parent)))
except Exception:
    pass

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=ctk_datas,
    hiddenimports=plyer_notification_imports + plyer_extra_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'FileSyncTool.ico'),
)