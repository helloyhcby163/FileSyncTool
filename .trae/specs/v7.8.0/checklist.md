# FileSyncTool v7.8.0 验收清单

## 安全红线
- [x] 无 `shell=True`，所有进程调用使用参数列表
- [x] 无“执行任意用户命令”的接口；旧 `post_sync_command` 仅丢弃并警告
- [x] 新增路径均经 `Path(...).resolve()`

## 任务 A
- [x] `FileSyncTool.spec` hiddenimports 含 `plyer.platforms.macosx` 与 `plyer.platforms.macosx.notification`
- [x] `APP_VERSION == "7.8.0"`，窗口标题/系统信息自动读取
- [x] `CONTRIBUTORS.md` 含 helloyhcby163、wang3076
- [x] `PROJECT_OVERVIEW.md` 存在且覆盖 v7.7 / v7.7.1 / v7.8.0
- [x] `AGENTS.md` 不再有 `post_sync_command` 功能描述

## 任务 B
- [x] 新建任务默认 `sync_hidden_files=False`；旧任务静默补 False
- [x] 设置项 `default_sync_hidden_files` 默认 False，且有 UI
- [x] `_scan_directory` 在 `os.scandir` entry 入口 `continue` 过滤 `.` 开头项
- [x] `.sync.tmp` / `.sync_progress.json` 始终忽略（不受开关影响）

## 任务 C
- [x] `recent_tasks.json` 结构正确、上限 20、FIFO
- [x] 仅成功写入；失败/中断不写
- [x] 首页上下两栏，下栏约 40% 高，`CTkScrollableFrame`
- [x] 搜索实时过滤；“清空列表”可用；“撤销同步”弹占位提示

## 任务 D
- [x] `psutil` 在 `requirements.txt`
- [x] 后台监控线程采样；主循环每 100 文件 `tick()`
- [x] CPU > 90% 或可用内存 < 500MB → `sleep(0.5)`
- [x] 连续触发时通知最高占用进程名（`{process}` 占位符）

## 收尾
- [x] `python -m compileall -q backend gui main.py` 通过
- [x] zh / en / zh_tw `texts` 键集合完全一致（各 482 键）
