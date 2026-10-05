# 项目交接概况

## 1. 基本信息
- 项目名称：文件同步工具（FileSyncTool），当前版本号 7.5.1（多语言架构重构版）
- 项目根目录：`e:\杨昊宸\python文件夹\文件同步工具7.5.1`
- 技术栈：Python 3、CustomTkinter（GUI）、plyer（系统通知）、watchdog、darkdetect、PyInstaller（打包）
- 入口：`main.py`（开发环境优先使用根目录 `.venv\Scripts\python.exe` 重启自身）；另有 `run.bat`
- v7.5.1 变更主线：多语言架构重构（语言文件 meta/texts 升级、字体配置提取、语言选择改下拉框、损坏文件处理、两级 fallback、界面硬编码文本清零）

## 2. 目录结构
- `backend/`：后端逻辑（配置、任务、同步引擎、回收站、多语言、通知、主题、平台工具、文件工具）
- `gui/`：全部界面页面与主窗口（共 10 个页面 + app.py 主窗口）
- `translations/`：`zh.json`、`en.json`、`zh_tw.json`（三语言，当前各 259 个键）。v7.5.1 起格式升级为 `{"meta":{name,code,font,font_size}, "texts":{...}}`，旧扁平格式仍可加载（自动补 meta）
- `data/`：旧版配置文件与备份（`sync_config_v7.json`、`sync_config_v7_1.json.bak`、`sync_config_v7_2.json.bak`、`sync_config_v7_3.json`），新版本首次启动会从此处复制迁移
- 根目录：`main.py`、`FileSyncTool.spec`（PyInstaller）、`requirements.txt`、`run.bat`、`LICENSE`、`sync_config_v6.json.bak`、`test_fix.py`、`test_platform_compat.py`、`test_sync_delete.py`
- `__pycache__/` 中存在 3.6/3.7/3.12/3.13 多版本字节码

## 3. 核心文件职责
- `main.py`：启动入口；全局异常捕获（excepthook + Tkinter 回调）、信号处理（SIGINT/SIGTERM/SIGBREAK）、PyInstaller 路径处理、日志写入。文件头注释版本标注为 v7.3
- `backend/config_manager.py`：配置文件读写、旧版本升级（v6→v7.5 多档迁移）、任务与设置存取、自定义配置目录（指针文件 `config_path.json`）。配置文件名 `sync_config_v7_5.json`
- `backend/sync_engine.py`：同步核心。含枚举 ConflictStrategy/SyncDirection/SyncMode，FileSyncEngine 主类，SyncStats/SyncProgress/SyncPreview/ProgressManager；扫描与预览、冲突策略、分块复制、断点续传、写入寿命保护、同步删除、同目录并发检测、按文件夹筛选
- `backend/task_manager.py`：任务增删改查、复制、重命名、运行中任务（内存态）、导入/导出（单任务、多选 `export_tasks`、全部）、目录占用检测
- `backend/recycle_manager.py`：最近删除（回收站）管理，含容量上限
- `backend/language_manager.py`：v7.5.1 重写。动态扫描 `translations/*.json`；支持新 `{meta,texts}` 格式与旧扁平格式（自动补 meta）；损坏文件标注（JSON 解析失败/缺 texts/键值非字符串）；两级文本 fallback（当前→zh→en→default→键名）；初始语言回退（精确→主语言码→en→zh→首个可用）；字体 API `get_font/get_font_family/get_default_font_size/get_meta`，按平台实际安装字体（`tkinter.font.families()`）解析候选；模块级 `get_font()` 供启动早期使用；`get_language_options()` 返回 `(code, display, broken)` 三元组列表
- `backend/platform_utils.py`：资源路径（兼容 `sys._MEIPASS`）、跨平台默认配置/回收站/数据目录、系统语言检测（v7.5.1 重写：去除硬编码 supported 列表，中文繁体归 zh_tw、C/POSIX 归 en，locale 失败回退环境变量）、可移动磁盘识别、日志路径（默认配置目录下 `filesynctool.log`）
- `backend/notification_manager.py`、`backend/theme_manager.py`、`backend/file_utils.py`：系统通知、主题、通用文件工具函数
- `gui/app.py`：`FileSyncApp(ctk.CTk)` 主窗口；页面工厂 `show_page(page_name, **kwargs)`，页面名：home、sync、create_task、folder_config、sync_confirm、sync_progress、running_tasks、task_manage、recycle、settings；其中 sync_confirm/sync_progress/folder_config/create_task 每次切换重建实例。v7.5.1：`change_language(code)` 通用切换入口，`_apply_language_change()` 销毁并重建全部缓存页面（含非当前页）+ 刷新状态栏字体；`switch_language()` 保留为循环切换（自动跳过损坏语言）；状态栏字体改用 `get_font(size=12)`
- `gui/home_page.py`：首页，功能入口与最近打断任务列表。v7.5.1：左侧语言按钮改为只读 `CTkComboBox`（动态扫描语言文件，显示 meta 名称，损坏项带后缀且禁选弹警告复位）
- `gui/sync_page.py`：已保存任务选择页（列表、搜索、使用/新建任务）
- `gui/create_task_page.py`：创建/编辑任务页（源、目标、方向、模式、线程等）
- `gui/folder_config_page.py`：文件夹配置页；`FolderConfigPage` 配置各文件夹冲突策略与筛选策略；含 `StrategySelectDialog`、`FilterConfigDialog`；右栏为可滚动容器
- `gui/sync_confirm_page.py`：同步确认页；任务摘要、文件夹策略、筛选策略展示、预估、同步删除开关；含 `FastModeWarningDialog`
- `gui/sync_progress_page.py`：同步进度页（进度、速度、暂停/中断/恢复）
- `gui/running_tasks_page.py`：运行中任务页
- `gui/task_manage_page.py`：任务管理页；复制、重命名、删除、编辑、导出（Ctrl/Shift 多选；选中导出所选，未选询问是否全部导出）；含 `ConfirmDialog`
- `gui/recycle_page.py`：最近删除页
- `gui/settings_page.py`：设置页；分区为语言设置（v7.5.1 新增：只读下拉框 + 提示）、主题、线程、寿命保护、同步删除与回收站上限、配置存储路径、任务导入导出（含「导出所有任务」「导入任务」）。全局筛选策略区已移除

## 4. 已实现功能
- 双向/单向同步、快速与安全模式、可配置线程数
- 五种冲突策略：conservative、newest_wins、source_wins、target_wins、skip；支持根目录文件与每个顶层子文件夹独立配置
- 大文件分块复制、断点续传、进度持久化（`.sync_progress.json`）、中断恢复
- 面向可移动磁盘的写入寿命保护（档位/强度/分块大小可配）
- 同步删除（任务级开关，删除进入最近删除，容量上限可配）
- 任务级筛选策略：按顶层文件夹配置日期过滤（按文件修改时间，YYYY-MM-DD）与扩展名过滤（白名单 include / 黑名单 exclude），二者 AND；未配置的文件夹不筛选；根目录文件不参与文件夹筛选；配置随任务持久化、参与导出导入
- 任务导入导出 JSON（跨电脑迁移，导入时重新生成任务 ID，同名自动加 `_importedN` 后缀）
- 三语言界面（中文/英文/繁体）；v7.5.1 多语言架构重构：语言文件 `{meta,texts}` 格式、字体配置从 meta 读取、语言选择改下拉框（首页+设置页）、损坏文件标注禁选、两级 fallback（文本缺 key → zh → en；缺 meta → 文件名+en 字体；系统语言不支持 → en → zh）、GUI 硬编码中文文本全部清零
- 系统语言自动检测、明暗主题、系统通知、全局异常日志

## 5. 代码约定与数据格式
- GUI 页面均继承 `ctk.CTkFrame`，对话框继承 `ctk.CTkToplevel`（模态 `transient`+`grab_set`+`wait_window`）
- 界面文案统一 `language_manager.get_text(key, "中文默认")` 或 `app.get_text(...)`，第二参数为中文兜底；页面内通常有 `update_language`/`refresh` 方法
- v7.5.1：GUI 字体统一用 `from backend.language_manager import get_font` 后 `get_font(size=..., weight=...)`，不再硬编码 `ctk.CTkFont`；字体按当前语言 meta 的 `font` 候选列表 + 平台已安装字体解析
- 占位符替换用 `format_text(key, **kwargs)`，模板中形如 `{name}`；损坏警告模板用 `{filename}`，在调用处 `.replace("{filename}", ...)` 而非 format_text（保留模板原样展示）
- 包内相对导入（`from .xxx import`），外部以 `backend.`/`gui.` 顶级包导入
- 配置 JSON 顶层键：`version`、`tasks`、`settings`、`recent_paths`、`interrupted_tasks`、`deleted_files`、`sync_history`
- settings 主要键：language、scan_workers、sync_workers、recycle_limit_mb、recycle_limit_gb、sync_delete_default、theme、auto_check_updates、life_protection_enabled、usb_level、protection_strength、chunk_size_mb
- 任务对象字段：id（uuid4）、name、source、target、mode、sync_direction、folders[]、default_strategy、folder_strategies{}、folder_filters{}、root_included、root_strategy、use_multithreading_scan、use_multithreading_copy、last_snapshot、created_at、last_used（格式 `%Y-%m-%dT%H:%M:%S`）、status
- `folder_strategies`：`{顶层文件夹名: 策略键}`；`folder_filters`：`{文件夹名: {date_filter_enabled, date_filter_start, date_filter_end, extension_filter_enabled, extension_filter_mode, extension_filter_list[]}}`，扩展名统一小写带点
- 导出文件结构：`{version:"7.5", exported_at, task_count, tasks:[...]}`；自定义配置目录指针：`config_path.json` 内容 `{"config_dir": "..."}`
- 翻译文件为 `{meta, texts}` 双层 JSON（v7.5.1 升级，旧扁平格式仍兼容）；占位符使用 `{name}` 形式

## 6. 已知问题与注意事项
- 2026-09-26 报告的问题，v7.5.1 处理结果：
  1. ✅ 多语言不完整：多数按钮缺失翻译 —— 已补齐至 259 键，GUI 硬编码中文文本全部清零
  2. ✅ 设置界面「同步删除」「最近删除上限」相关文案缺失翻译 —— 已补齐
  3. ✅ 切换到繁体中文后点击其他按钮界面跳回英文 —— 根因：语言切换只重建当前页，缓存页保留旧语言；已改为切换时销毁并重建全部缓存页面 + 刷新状态栏字体
  4. ⏳ 同步确认页任务详情未显示筛选策略（注：当前 sync_confirm_page.py 已存在筛选展示区 `_create_filter_section`，待实际运行确认是否正常展示）
  5. ⏳ 任务导出只能全选，无法选几个任务导出（注：task_manage_page.py 已支持多选导出，设置页仍只有「导出所有任务」）
- v7.5.1：语言切换后销毁并重建**全部**缓存页面（含非当前页），下次打开任意页面均以新语言+新字体重建；状态栏字体同步刷新
- 翻译文件 v7.5.1 起为 `{meta,texts}` 格式，旧扁平格式仍可加载（自动补 meta）；损坏文件（JSON 解析失败/缺必要字段）标注「损坏」并禁止在下拉框选择
- 首次运行若默认配置目录无配置文件，会从项目 `data/` 目录复制旧版配置（复制而非移动）
- 测试脚本位于项目根目录，无独立 tests 目录；无 CI 配置
- 无 requirements 锁定版本以外的依赖管理文件；`.venv` 目录不在仓库清单内（不确定是否存在于本机）

## 核心特性
- **性能优先**：多线程扫描与复制、大文件分块传输、断点续传、块级寿命保护
- **跨平台**：完整支持 Windows / macOS / Linux
- **U 盘优化**：写入寿命保护、可移动磁盘检测、U 盘脱落处理
- ** GUI美观好用
