# FileSyncTool v7.8.0 规格说明

基线：v7.7.1　应用版本常量：`7.8.0`（`backend/version.py: APP_VERSION`）
配置 schema 版本：保持 `ConfigManager.CURRENT_VERSION = "7.7"`（新增设置键依靠默认值合并，不触发数据迁移）

## 0. 安全红线（本规格所有实现必须满足）

1. 所有外部路径（CLI 参数、配置、任务、下载目标）先 `Path(...).resolve()`，禁止未规范化拼接。
2. 禁止 `shell=True`；任何进程调用使用参数列表。同步后动作仅保留内置枚举 `none / notify / shutdown`。
3. 旧字段（`post_sync_command`）加载/导入时静默丢弃并记录警告，绝不执行、绝不导致异常。
4. 新增字段缺失时静默补默认值，不抛异常。

## 1. 任务 A：前置任务与打包修复

### A1 `FileSyncTool.spec`
- `plyer_notification_imports` 增加 `'plyer.platforms.macosx.notification'`（保留 win/linux；`macos` 保留用于旧版 plyer 兼容）。
- `plyer_extra_imports` 增加 `'plyer.platforms.macosx'`（保留 `plyer.platforms.macos`）。
- 文件头版本标注改为 `v7.8.0`。

### A2 全局版本号
- `backend/version.py`：`APP_VERSION = "7.8.0"`；`parse_version` 文档字符串示例改为 `"v7.8.0"`。
- 模块头注释 `文件同步工具 v7.x - ...` 统一改为 `v7.8.0`：`main.py`、`FileSyncTool.spec`、`gui/app.py`、`gui/toolkit_page.py`、`gui/watch_task_select_page.py`、`backend/cli_sync.py`、`backend/watch_manager.py`、`backend/watch_process.py`、`backend/system_menu.py`、`gui/home_page.py`（头部为 v7.0，仅改版本标注）。
- **不改**历史功能注释中的 `# v7.7:` / `# v7.7.1:` 标记（它们记录特性引入版本）。
- **不改** `README.md` / `SECURITY.md` 中关于 v7.6.0–v7.7.0 废弃版本的历史说明。
- `.github/workflows/release.yml` 产物名 `FileSyncTool_v7.7.1_*` → `FileSyncTool_v7.8.0_*`。
- `translations/*.json` 的 `app_title` 已为 `{version}` 占位符，无需改字面版本；确认 `format_app_title()` 生效即可。
- **不改** `ConfigManager.CURRENT_VERSION` / `DEFAULT_CONFIG["version"]`（配置 schema 版本，与应用版本独立）。

### A3 `CONTRIBUTORS.md`
已存在且含 `helloyhcby163`、`wang3076`。规范化：去掉“（待确认）”，保留贡献说明与加入方式。

### A4 `PROJECT_OVERVIEW.md`（新建，根目录）
内容结构：
1. 项目简介与技术栈（Python 3 / CustomTkinter / watchdog / plyer / psutil / PyInstaller）。
2. 目录结构（backend、gui、translations、docs、tools）。
3. 版本演进：
   - v7.6：后台监听子进程、工具包、外挂语言目录、配置路径迁移、U 盘缺失提示、Defender 拦截提示。
   - v7.7：U 盘插入自动同步与任务-U 盘绑定（`usb_auto_sync` / `usb_binding`）、AI 配置导入（预置 Prompt + JSON 粘贴）、场景预设、自动更新检查。
   - v7.7.1：CLI 编排扩展（`--config`、即时传参 `--source/--target/--mode/--direction`、`--silent`、退出码 0/1/2）、纯 Python 多线程分块下载（HTTP Range + GitHub→Gitee→镜像三层降级）、符号链接过滤、安全红线（移除任意命令执行）。
   - v7.8.0：隐藏文件同步开关、最近完成任务列表（含撤销占位）、系统资源防卡死降速、打包 macosx 通知修复、贡献者与项目总览文档。
4. 安全约束摘要（引用 AGENTS.md 第 0 节）。
5. 运行与打包命令。

### A5 `AGENTS.md`
- 删除所有 `post_sync_command` 字段描述、“同步后命令”功能描述、`create_task_page` 命令输入框描述；统一表述为“同步后内置安全动作（none/notify/shutdown）”。
- 版本号 v7.6 → v7.8.0；翻译键数 `344` 更正为实际三语一致键数（以 `zh.json` 为准，新增键后校验）。
- 新增 v7.7 章节：U 盘绑定（`usb_auto_sync`/`usb_binding`、`usb_monitor`、`apply_usb_auto_sync_setting`）、AI 配置（工具包 Prompt 复制 + JSON 粘贴预填）。
- 新增 v7.7.1 章节：CLI 扩展、纯 Python 多线程下载器（`backend/downloader.py`）、符号链接过滤、退出码约定。
- 新增 v7.8.0 章节：任务 B/C/D 的新字段、新模块、新设置键与新增翻译键。

## 2. 任务 B：隐藏文件同步开关

### B1 `backend/task_manager.py`
- `create_task(...)` 新增关键字参数 `sync_hidden_files: bool = False`，写入任务字典字段 `"sync_hidden_files": bool(sync_hidden_files)`。
- `update_task(...)`（若存在字段白名单/逐字段更新）同步支持该字段。
- 读取旧任务缺失该字段时静默补 `False`（统一在 `config_manager.sanitize_task_dict` 内 `task.setdefault(...)`，覆盖 load/import/CLI/监听路径）。
- 不改变 `sanitize_task_dict` 对 `post_sync_command` 的静默丢弃逻辑。

### B2 `backend/config_manager.py`
- `DEFAULT_CONFIG["settings"]` 新增 `"default_sync_hidden_files": False`。
- `get_settings()` 返回的 settings 必须包含该键（依赖现有默认值合并；若无合并则显式 `setdefault`）。
- `sanitize_task_dict` 增加 `task.setdefault("sync_hidden_files", False)` 并强制 `bool()`。
- 迁移分支 `elif version in ("7.4","7.5","7.6","7.7")` 内补 `settings.setdefault("default_sync_hidden_files", False)`。

### B3 `backend/sync_engine.py`
- `FileSyncEngine.__init__` 新增 `sync_hidden_files: bool = False`，保存 `self.sync_hidden_files`。
- `_scan_directory()` 的 `os.scandir` entry 入口统一过滤，顺序如下（**先豁免内置文件，再判断隐藏**）：
  1. `entry.is_symlink()` → 跳过并 warning（现状保留）。
  2. `entry.name == PROGRESS_FILE` → 跳过。
  3. `entry.name.endswith(TEMP_FILE_SUFFIX)` → 跳过。
  4. `if not self.sync_hidden_files and entry.name.startswith('.'): continue`（文件与目录统一在此处 continue，**禁止进入目录后再判断**）。
- 移除原目录分支与文件分支中分散的 `entry.name.startswith('.')` 判断（避免逻辑重复/冲突）；若为隐藏且开启同步，隐藏**文件**不再加入 `stats.skipped_system_files`（改为静默同步）。
- 内置临时文件豁免不受 `sync_hidden_files` 影响。

### B4 引擎传参
- `backend/cli_sync.py::build_engine_for_task`：`sync_hidden_files=bool(task.get("sync_hidden_files", settings.get("default_sync_hidden_files", False)))`。
- `gui/app.py::_start_sync`：预览引擎与正式引擎两处 `SyncEngine(...)` 同样传参；来源优先 `task_config["sync_hidden_files"]`，缺失回落 `settings["default_sync_hidden_files"]`，再回落 `False`。

### B5 UI
- `gui/create_task_page.py`：在“高级选项/同步模式”区域新增 `CTkSwitch`（默认值：新建页面时取 `settings["default_sync_hidden_files"]`；编辑任务时取 `task["sync_hidden_files"]`），`_get_task_config()` 输出 `sync_hidden_files`，`_apply_prefill_config()` 识别该键，`_load_task_config()` 回填，`update_language()` 刷新文案。
- `gui/settings_page.py`：“同步行为”区在“同步时阻止休眠”下方新增 `default_sync_hidden_files` 开关，切换即写 `self.config_manager.update_settings(...)`；`update_language()` 刷新文案。

## 3. 任务 C：最近完成任务列表

### C1 新模块 `backend/recent_tasks.py`
- `MAX_RECENT_TASKS = 20`；文件名 `recent_tasks.json`，位置 `<config_dir>/recent_tasks.json`（`Path(...).resolve()`）。
- `class RecentTasksManager`：
  - `__init__(config_manager)`
  - `add_record(task_name, file_count, transaction_id=None) -> dict`：追加 `{"task_name","time","file_count","transaction_id"}`，`time = datetime.now().astimezone().isoformat(timespec="seconds")`，`transaction_id` 缺省 `uuid4().hex`；FIFO 截断到 20；原子写（临时文件 + `os.replace`）。
  - `get_records() -> list[dict]`：文件缺失/损坏/JSON 非列表 → 返回 `[]`（静默），逐条校验字段类型。
  - `clear() -> bool`：写入 `[]`；失败返回 False 并静默。
- 全程 try/except，不影响同步主流程。

### C2 写入时机（仅成功）
- GUI：`gui/app.py::_on_sync_complete` 在 `final_success`（`sync_success` 且无错误）分支调用 `self.recent_tasks_manager.add_record(...)`，`file_count = stats.files_copied + stats.files_updated`（从 `sync_engine.get_stats()` 取，使用 `current_file` 是错误的）。
- CLI/监听：`backend/cli_sync.py::run_task_once` 成功且无拦截错误时同样写一条。
- 失败/中断/用户取消不写。

### C3 `gui/home_page.py` 上下分栏
- `_create_right_panel()` 改为三行：`row0`（被打断的任务）weight=3、`row1`（最近完成的任务）weight=2（约占 40%）、`row2`（提示轮播/提示信息）weight=1。
- 新面板 `_create_recent_tasks_panel()`：
  - 标题标签（翻译键 `home_recent_tasks_title`）。
  - 顶部搜索框 `CTkEntry`（`home_recent_search_placeholder`），`<KeyRelease>` 实时过滤 `task_name`（大小写不敏感）。
  - “清空列表”按钮（`home_recent_clear_btn`）→ 二次确认后 `recent_tasks_manager.clear()` 并刷新。
  - `CTkScrollableFrame` 列表；每行：任务名、时间（本地可读格式）、文件数、`撤销同步` 按钮（`home_recent_undo_btn`）。
  - 空状态标签（`home_recent_empty`）。
- 撤销按钮点击 → 信息弹窗 `home_recent_undo_tip`：“该功能将在后续版本接入事务回滚”。
- `_load_data()` 增加 `_load_recent_tasks()`；`show_page`/页面重建时刷新。
- `update_language()` 刷新标题、搜索占位、清空按钮、撤销按钮、空状态文案。

## 4. 任务 D：系统资源防卡死

### D1 依赖
- `requirements.txt` 增加 `psutil>=5.9.0`。

### D2 新模块 `backend/resource_guard.py`
- `class ResourceGuard`：
  - 参数：`enabled=True, cpu_threshold=90.0, memory_threshold_mb=500, sample_interval=2.0, max_consecutive=3, notify_cooldown=60.0`。
  - 软导入 `psutil`；缺失 → `enabled=False`，所有方法安全 no-op。
  - `start()`：启动 daemon 线程，周期性（`sample_interval`）采样 `psutil.cpu_percent(interval=None)` 与 `psutil.virtual_memory().available`，更新原子状态 `_throttle_active`、`_consecutive`。
  - `registry` 线程在连续 `max_consecutive` 次超阈值时，用 `psutil.process_iter(["pid","name","cpu_percent","memory_percent"])` 找**非本进程**中占用最高者（优先 CPU，其次内存），记录 `_top_offender_name`。
  - `tick()`（主扫描/复制线程调用，O(1)）：仅读取缓存状态；若 `_throttle_active` 为真，返回 `True`（由调用方 `time.sleep(0.5)`），并每 `notify_cooldown` 秒触发一次通知（通知在线程内委托 `notification_manager.send_notification`，标题/内容使用翻译键）。
  - `stop()`：置停止事件并 join（超时 2s）。
- 主线程**不直接调用 psutil**，避免拖慢扫描。

### D3 `backend/sync_engine.py` 接入
- `FileSyncEngine.__init__` 新增 `resource_guard_enabled: bool = True`（默认开启），构造 `ResourceGuard(notification_manager=None)`；通知器由调用方注入（可选 `notification_manager` 参数）。
- `sync_directories()` 薄包装：`guard.start()`，`try/finally` 中 `guard.stop()`（与 `prevent_sleep/allow_sleep` 并列，异常/中断均恢复）。
- `_scan_directory()` 与复制主循环（多线程与单线程两支）中，每处理 100 个文件调用 `guard.tick()`；返回 True 则 `time.sleep(0.5)`（仅调用线程降速）。
- 通知文案：`resource_guard_slowdown_title` / `resource_guard_slowdown_message`（`{process}` 占位符）。

## 5. 新增翻译键（zh / en / zh_tw 三语一致）

| 键 | zh 默认 |
| --- | --- |
| `home_recent_tasks_title` | 最近完成的任务 |
| `home_recent_search_placeholder` | 搜索任务名… |
| `home_recent_clear_btn` | 清空列表 |
| `home_recent_empty` | 暂无最近完成的任务 |
| `home_recent_undo_btn` | 撤销同步 |
| `home_recent_undo_tip` | 该功能将在后续版本接入事务回滚 |
| `home_recent_clear_confirm` | 确定清空最近完成任务列表？ |
| `task_sync_hidden_files` | 同步隐藏文件（以 . 开头的文件和文件夹） |
| `task_sync_hidden_files_desc` | 默认关闭。开启后会同步 . 开头的隐藏项，内置临时文件始终忽略。 |
| `settings_default_sync_hidden_files` | 新建任务默认同步隐藏文件 |
| `resource_guard_slowdown_title` | 同步已自动降速 |
| `resource_guard_slowdown_message` | 由于 {process} 占用过高，同步已自动降速 |

## 6. 变更文件清单

新增：`.trae/specs/v7.8.0/*`、`PROJECT_OVERVIEW.md`、`backend/recent_tasks.py`、`backend/resource_guard.py`
修改：`FileSyncTool.spec`、`backend/version.py`、`backend/config_manager.py`、`backend/task_manager.py`、`backend/sync_engine.py`、`backend/cli_sync.py`、`gui/app.py`、`gui/home_page.py`、`gui/create_task_page.py`、`gui/settings_page.py`、`translations/zh.json`、`translations/en.json`、`translations/zh_tw.json`、`requirements.txt`、`AGENTS.md`、`CONTRIBUTORS.md`、`.github/workflows/release.yml`、各模块文件头（仅版本标注）

## 7. 验证步骤
1. `python -m compileall -q backend gui main.py` 无输出（退出码 0）。
2. 三份翻译 JSON 可解析，键集合完全一致（以 `zh.json` 的 `texts` 键为准）。
3. `python main.py --help` 显示 v7.8.0。
4. 关键路径静态检查：`grep` 确认无 `shell=True`；`sync_engine` 入口隐藏过滤在 `os.scandir` 循环内且豁免 `.sync.tmp`/`.sync_progress.json`。
5. 无 `post_sync_command` 可执行路径（仅保留“丢弃并警告”）。

## 8. 明确不做
- 不实现真正的同步事务回滚（撤销按钮只弹占位提示）。
- 不改配置 schema 版本，不重写历史 `# v7.7` 特性注释。
- 不引入新的系统命令执行接口。
