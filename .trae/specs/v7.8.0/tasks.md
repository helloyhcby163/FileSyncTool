# FileSyncTool v7.8.0 任务清单

## 阶段 0：前置任务（任务 A）
- [x] A1 `FileSyncTool.spec`：hiddenimports 补 `plyer.platforms.macosx` / `plyer.platforms.macosx.notification`；文件头 v7.8.0
- [x] A2 `backend/version.py`：`APP_VERSION = "7.8.0"`
- [x] A2 各模块文件头版本标注 → v7.8.0（保留历史 `# v7.x` 特性注释）
- [x] A2 `.github/workflows/release.yml` 产物名 → v7.8.0
- [x] A3 `CONTRIBUTORS.md` 规范化（helloyhcby163 / wang3076）
- [x] A4 新建 `PROJECT_OVERVIEW.md`（v7.6 / v7.7 / v7.7.1 / v7.8.0 演进）
- [x] A5 `AGENTS.md`：剔除 `post_sync_command`，补 v7.7 U 盘绑定与 AI 配置、v7.7.1 CLI/下载器/符号链接、v7.8.0 新特性；更正翻译键数

## 阶段 1：模块一

### 任务 B：隐藏文件同步开关
- [x] B1 `backend/task_manager.py`：`create_task(sync_hidden_files=False)` 写入字段
- [x] B2 `backend/config_manager.py`：`DEFAULT_CONFIG.settings.default_sync_hidden_files=False`；`sanitize_task_dict` 补 `sync_hidden_files`；`get_settings` 兼容旧配置补默认
- [x] B3 `backend/sync_engine.py`：`__init__(sync_hidden_files=False)`；`_scan_directory` 入口统一过滤（先豁免 PROGRESS_FILE/.sync.tmp，再跳过 `.` 开头项）
- [x] B4 `backend/cli_sync.py` / `gui/app.py`：引擎构造传 `sync_hidden_files`
- [x] B5 `gui/create_task_page.py` / `gui/settings_page.py`：开关 UI、读取/回填/保存/刷新文案

### 任务 C：最近完成任务列表
- [x] C1 新建 `backend/recent_tasks.py`（上限 20、原子写、损坏静默）
- [x] C2 `gui/app.py::_on_sync_complete` 成功分支写入；`backend/cli_sync.py::run_task_once` 成功分支写入
- [x] C3 `gui/home_page.py` 上下分栏（打断任务 weight=3 / 最近完成 weight=2 / 提示 weight=1）、搜索、清空、撤销占位
- [x] C3 `gui/app.py` 初始化 `recent_tasks_manager`

### 任务 D：系统资源防卡死
- [x] D1 `requirements.txt` 增加 `psutil>=5.9.0`
- [x] D2 新建 `backend/resource_guard.py`（后台采样线程 + `tick()` O(1) 缓存读取）
- [x] D3 `backend/sync_engine.py`：start/stop 生命周期 + 每 100 文件 tick + `sleep(0.5)` + 连续高占用通知

### 收尾
- [x] 三语翻译补齐并通过键集合一致性校验（各 482 键）
- [x] `python -m compileall -q backend gui main.py` 通过
- [x] 安全性静态检查（无 `shell=True`、无任意命令执行路径；`platform_utils.open_log_in_terminal` 已改为参数列表 PowerShell 调用）
