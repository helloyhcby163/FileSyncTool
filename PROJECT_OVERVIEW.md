# FileSyncTool 项目总览

文件同步工具（FileSyncTool）是一个基于 Python 3 + CustomTkinter 的跨平台文件同步应用，面向 U 盘/移动硬盘场景优化，支持图形界面、命令行与后台监听三种运行方式。

## 技术栈

| 组件 | 用途 |
| :--- | :--- |
| Python 3 | 运行时 |
| CustomTkinter | 桌面 GUI |
| watchdog | 目录变更监听（空闲触发式同步） |
| plyer | 跨平台系统通知 |
| psutil | 系统资源监控（CPU / 内存） |
| darkdetect / theme_manager | 主题跟随系统 |
| pywin32 / pyshortcuts | Windows / macOS 快捷方式 |
| Pillow | 帮助文档图片渲染 |
| PyInstaller | 单文件打包 |

## 目录结构

```
main.py                  程序入口（GUI / CLI / --watch 监听子进程）
FileSyncTool.spec        PyInstaller 打包配置
backend/
  config_manager.py      配置读写、默认值合并、配置目录指针、旧字段清洗
  task_manager.py        任务 CRUD、导入导出、任务字段默认值
  sync_engine.py         同步核心（os.scandir 扫描、多线程复制、分块与断点续传）
  cli_sync.py            无界面同步执行（CLI / 监听子进程共用）
  downloader.py          纯 Python 多线程分块下载器（更新包）
  usb_monitor.py         U 盘插拔监听与任务-U 盘绑定
  watch_manager.py       watchdog 空闲触发监听
  watch_process.py       后台监听子进程管理（watchers.json / watch_logs）
  recent_tasks.py        最近完成任务列表（recent_tasks.json）
  resource_guard.py      系统资源守护（高占用自动降速）
  language_manager.py    多语言（支持外挂 translations 目录、按键合并）
  notification_manager.py / theme_manager.py / platform_utils.py / system_menu.py
  recycle_manager.py / file_utils.py / update_checker.py / updater.py / version.py
gui/                     主窗口与各页面（home / sync / create_task / settings / toolkit ...）
translations/            zh.json、en.json、zh_tw.json
docs/                    HELP.md、TRANSLATING.md、images/
tools/                   网络加速辅助工具（不随版本逻辑调用）
```

## 版本演进

### v7.6
- 命令行基础自动化（`--task` / `--watch` / `--silent` / `--idle` / `--list-tasks`）。
- 工具包页面：后台监听子进程、系统菜单与桌面快捷方式、任务导入导出、系统信息、反馈、帮助文档。
- 外挂语言目录初始化与独立迁移；配置存储路径完整迁移（复制/验证/回滚/删旧）。
- 崩溃详情弹窗、U 盘缺失区分源/目标提示、Defender 拦截文件列表。
- 同步时阻止系统休眠；`os.scandir` 扫描与日志降频。

### v7.7
- **U 盘绑定**：任务级 `usb_auto_sync` / `usb_binding`（序列号 + 卷标 + 相对子路径）；插入已绑定 U 盘自动同步，未绑定 U 盘引导创建任务并在成功后询问绑定；`usb_monitor` 后台线程监听插拔，同一设备一次插入仅提示一次。
- **AI 配置**：工具包「AI 帮我配置」弹窗复制环境感知 Prompt（OS + 脱敏主目录），要求 AI 按【需求分析】【安全风险提示】【配置 JSON】【导入操作指南】四段输出；粘贴后解析 JSON 代码块，进入审核预览弹窗，确认后才创建任务；命中系统高危路径时红色警告并禁用创建。
- 场景预设（U 盘极速备份、双向工作同步）；自动更新检查（24 小时节流 + 镜像加速）。
- 安全重构：移除「同步后执行任意命令」，改为内置动作 `none / notify / shutdown`。

### v7.7.1
- **CLI 扩展**：`--config` 外部任务文件；即时传参 `--source/--target/--mode/--direction`；`--silent`；退出码约定（0 成功 / 1 同步失败 / 2 参数或配置错误）。
- **纯 Python 多线程下载**：`backend/downloader.py` 使用 ThreadPoolExecutor + HTTP Range 分块下载，GitHub → Gitee → 镜像三层降级，UI 显示当前下载策略。
- **符号链接过滤**：扫描阶段跳过符号链接（不读取、不复制、不删除），防止路径穿越。
- 更新包 SHA-256 校验；日志与控制台绝对路径脱敏。

### v7.8.0
- **隐藏文件同步开关**：任务级 `sync_hidden_files`（默认 False）与全局默认 `default_sync_hidden_files`（默认 False）；关闭时在 `os.scandir` 入口直接跳过 `.` 开头的文件与文件夹，内置 `.sync.tmp` / `.sync_progress.json` 始终忽略。
- **最近完成任务列表**：`<config_dir>/recent_tasks.json` 最多 20 条（FIFO），仅同步成功写入；首页上下分栏，下栏支持搜索、清空与「撤销同步」占位入口。
- **系统资源防卡死**：引入 psutil，后台线程采样 CPU/内存；CPU > 90% 或可用内存 < 500MB 时同步自动 `sleep(0.5)` 降速；连续高占用时通知占用最高的外部进程名。
- 打包修复：`FileSyncTool.spec` 增加 `plyer.platforms.macosx` / `plyer.platforms.macosx.notification` hiddenimports。

## 安全约束

完整约束见 `AGENTS.md` 第 0 节，核心三条：

1. 不提供任何执行用户自定义命令的接口。
2. 禁止 `shell=True`，进程调用一律使用参数列表。
3. 所有外部路径先 `Path(...).resolve()`；废弃字段加载时静默丢弃。

## 运行与打包

```bash
python main.py                     # 启动 GUI
python main.py --list-tasks        # 列出任务
python main.py --task "任务名"      # 单次无界面同步
python main.py --watch "任务名" --idle 10   # 空闲触发监听
pip install -r requirements.txt
pyinstaller FileSyncTool.spec      # 打包
```
