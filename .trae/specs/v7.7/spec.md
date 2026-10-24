# FileSyncTool v7.7 规格说明

分支：`dev-v7.7`　基线：v7.6.2　版本常量：`7.7`

## 1. 目标与范围

1. **插 U 盘自动同步**：后台独立线程监听移动设备，插入后防抖 3 秒，按任务绑定的设备唯一标识匹配并自动触发同步；无匹配任务时引导创建任务；设置页提供全局总开关。
2. **自动版本更新**：启动时 / 每 24 小时检查 GitHub Releases；最新 Release 发布时间不足 24 小时则不提示；复用 `backend/downloader.py` 下载（内部已调用 `backend/accelerator.py`）；Windows 使用临时 `.bat` 延迟替换并重启。
3. **AI 配置生成器**：工具包页新增入口，弹窗内置完整预置 Prompt（可一键复制）+ JSON 输入框，解析成功后跳转新建任务表单并预填。

不在范围：签名校验、增量补丁更新、非 Windows 的 exe 自替换、AI 联网调用。

## 2. 已确认的关键决策

### 2.1 硬件监听方案（Windows 优先，macOS/Linux 轮询）

新建 `backend/usb_monitor.py`，**纯后台守护线程 + 轮询**，不调用任何 Tk API，也不 hook Windows 窗口消息：

- 基类 `class UsbMonitor(threading.Thread)`：
  - 构造：`UsbMonitor(on_event=None, poll_interval=2.0, debounce=3.0)`
  - `on_event(event)` 在**工作线程**中回调；App 侧传入 `lambda ev: self.post_ui(lambda: self._handle_usb_event(ev))`，复用 v7.6.2 已有的主线程事件泵，杜绝跨线程 UI。
  - `start()` 启动线程；`stop()` 置 `threading.Event`，线程最多一个轮询周期内退出。
  - 首次扫描只建立基线，**不产生 inserted 事件**，避免程序启动时已插着 U 盘就自动同步。
  - 去重键：`serial`；`_known: Dict[serial, info]`，拔出后移除。
  - 新增设备时在工作线程内 `self._stop_event.wait(debounce)`（3 秒），随后重新读取一次硬件信息再入事件；等待期间设备消失则丢弃。
  - 事件结构：
    ```python
    {"type": "inserted" | "removed",
     "serial": str,        # Windows 卷序列号(8位十六进制) / macOS VolumeUUID / Linux UUID
     "label": str,         # 卷标 / 卷名
     "mount": str,         # 挂载点，如 "D:\\" 或 "/Volumes/KINGSTON"
     "volumes": [info, ...]}  # 该设备所有可访问挂载点（Windows 多分区）
    ```
- 也导出同步快照函数 `snapshot_devices() -> list[dict]`，供“绑定当前 U 盘”时立即读取。
- 平台实现：
  - **Windows**：`kernel32.GetLogicalDrives()` 枚举盘符；`GetDriveTypeW` 取 `DRIVE_REMOVABLE(2)` 与 `DRIVE_FIXED(3)`。对 `DRIVE_FIXED` 用 `CreateFileW("\\\\.\\X:")` + `DeviceIoControl(IOCTL_STORAGE_QUERY_PROPERTY / StorageDeviceProperty)` 读取 `STORAGE_DEVICE_DESCRIPTOR.BusType`，`BusType == 7 (BusTypeUsb)` 视为 U 盘/移动硬盘。序列号取 `GetVolumeInformationW` 的卷序列号，格式化为 8 位大写十六进制；卷标取同函数的卷名。设备打开失败时跳过，不误判为 U 盘。
  - **macOS**：枚举 `/Volumes/*`，对每个挂载点执行 `diskutil info -plist <mount>` 并用 `plistlib` 解析，取 `VolumeUUID`（缺失时用 `VolumeName`）、`VolumeName`，`Internal=True` 或 `RemovableMedia=False` 的跳过。
  - **Linux**：解析 `/proc/mounts`，取 `/media/`、`/run/media/`、`/mnt/` 下的挂载；UUID 由 `/dev/disk/by-uuid` 反查 `realpath` 匹配；无 UUID 时用挂载点作为 serial。
  - 所有平台异常均 `print` 后继续，绝不抛出到线程外。
- 任务匹配后重写路径（见 3.2），在**主线程**调用 `app._start_sync(task_config)`（该函数内部做主线程预扫描 + 后台同步线程，符合现有架构）。

### 2.2 Windows 自更新替换方案（已确认：临时 .bat）

新建 `backend/updater.py`：

- `download_update(info, progress_cb=None, on_status=None) -> Path`：`downloader.download(info["asset_url"], temp_dir, ...)`，临时目录 `tempfile.gettempdir()/FileSyncTool_update`。
- `write_windows_update_script(new_exe: Path, current_exe: Path) -> Path`：在临时目录生成 `update.bat`（UTF-8 无 BOM，`\r\n` 换行），内容为：

  ```bat
  @echo off
  chcp 65001 >nul
  set "NEW=新exe绝对路径"
  set "OLD=旧exe绝对路径"
  set "FAILFILE=%TEMP%\FileSyncTool_update_failed.txt"
  set /a TRIES=0
  timeout /t 2 /nobreak >nul

  :retry
  move /y "%NEW%" "%OLD%" >nul 2>&1
  if not errorlevel 1 goto success
  set /a TRIES+=1
  if %TRIES% lss 5 (
      timeout /t 2 /nobreak >nul
      goto retry
  )
  goto failed

  :success
  start "" "%OLD%"
  del "%~f0"
  exit /b 0

  :failed
  > "%FAILFILE%" echo 更新失败，请手动替换。
  >> "%FAILFILE%" echo 新文件: %NEW%
  >> "%FAILFILE%" echo 旧文件: %OLD%
  >> "%FAILFILE%" echo 时间: %DATE% %TIME%
  mshta "javascript:alert('更新失败，请手动替换。\\\\n\\\\n新文件: %NEW%\\\\n旧文件: %OLD%');close()"
  del "%~f0"
  exit /b 1
  ```

  失败兜底行为：`move` 共重试 **5 次**（每次间隔 2 秒，总计约 10 秒）；仍失败则：
  1. 写入 `%TEMP%\FileSyncTool_update_failed.txt`（含中文说明、新旧文件绝对路径、时间戳）；
  2. 通过 `mshta` 弹出系统级提示框“更新失败，请手动替换。”（不依赖主程序存活）；
  3. 脚本自删除，退出码 1。

  另外**启动前**做可写性预检（`os.access(current_exe.parent, os.W_OK)` 且旧 exe 存在），不可写则直接走手动替换引导，不启动脚本。
- `launch_update_script(bat_path)`：`subprocess.Popen(["cmd", "/c", str(bat_path)], creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS, close_fds=True)`。
- 启动脚本后 App 弹窗“更新准备就绪，即将重启应用。如果您的安全软件弹出拦截提示，请选择‘允许’。”，用户确认后调用 `app.safe_exit()`。
- 非 frozen（开发环境）/ 非 Windows / 预检失败：不替换，弹窗给出下载文件路径，并提供「打开发布页」「打开下载目录」按钮。

### 2.3 AI 配置生成器

- Prompt 全文按语言硬编码进 `translations/{zh,en,zh_tw}.json` 的 `ai_prompt_template` 键（zh 与用户原文逐字一致）；`backend/ai_config.py` 导出 `DEFAULT_AI_PROMPT` 作为 `get_text` 的兜底默认值。
- **翻译硬约束**：`en` / `zh_tw` 的 `ai_prompt_template` 只翻译自然语言描述（角色说明、输出要求、约束条件的文字、需求示例），以下内容必须与 zh 版本**逐字保持英文原样**：
  - JSON 模板整体结构与所有键名（`name`、`source`、`target`、`sync_direction`、`mode`、`default_strategy`、`extensions`、`extensions_mode`、`date_enabled`、`date_from`、`date_to`）；
  - 全部枚举值与字符串字面量（`"both"`、`"source_to_target"`、`"target_to_source"`、`"safe"`、`"fast"`、`"conservative"`、`"newest_wins"`、`"source_wins"`、`"target_wins"`、`"include"`、`false`、`""`、`[]`）；
  - 产品名 `FileSyncTool`、markdown 标记禁令与“只输出纯 JSON”的语义不得弱化为本地化键名。
  - 保留 `[在这里输入你的需求…]` 占位符的对应本地化版本，但不得改动任何 JSON 片段。
- 解析宽松处理：允许首尾空白与 ```json 代码围栏；其余严格按白名单校验（枚举、类型、必填），失败统一抛 `AIConfigError("JSON 格式错误，请重新生成")`。
- 筛选条件映射：`extensions` / `date_*` 转为任务级模板 `ai_filter_template`（结构同 FolderConfigDialog 的 `result`），由 `folder_config_page` 在扫描出子文件夹后套用到**全部**子文件夹，避免改动同步引擎。

## 3. 数据模型

### 3.1 任务新增字段（写入 `TaskManager.create_task`，均有默认值，兼容旧任务）

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `usb_auto_sync` | bool | `False` | 是否插 U 盘自动同步 |
| `usb_binding` | dict | `{}` | 绑定信息 |

`usb_binding`：
```json
{
  "serial": "1A2B3C4D",
  "label": "KINGSTON",
  "mount": "E:\\",
  "source_on_usb": true,
  "source_subpath": "Photos",
  "target_on_usb": false,
  "target_subpath": ""
}
```

### 3.2 触发时的路径重写规则

- 匹配：`binding.serial` 与事件 `serial` 大小写不敏感相等；`serial` 为空时退化为 `label` 相等；两者都为空则永不自动触发。
- `source = os.path.join(event.mount, source_subpath)`，`source_subpath == ""` 时即 `event.mount`；`source_on_usb == False` 时保留任务原 `source`。
- `target` 同理，依据 `target_on_usb` / `target_subpath`。
- 重写仅作用于本次运行的任务副本，**不回写**任务配置（盘符变化不影响已保存任务）。
- 若同目录任务正在同步，`is_directory_in_use` 已能拦截，捕获警告后跳过本次触发并写日志。

### 3.3 settings 新增键（`ConfigManager.DEFAULT_CONFIG["settings"]`）

| 键 | 默认 | 说明 |
|---|---|---|
| `usb_auto_sync_enabled` | `True` | 全局总开关 |
| `last_update_check` | `""` | 上次检查更新时间（ISO8601），用于 24h 节流 |

`CURRENT_VERSION` 保持 `"7.6"` 不变（配置 schema 未破坏，避免触发旧配置升级弹窗）。

### 3.4 版本常量

新建 `backend/version.py`：`APP_VERSION = "7.7"`、`GITHUB_REPO = "helloyhcby163/FileSyncTool"`、`RELEASES_LATEST_API`、`parse_version()`、`is_newer()`。不复用 `ConfigManager.CURRENT_VERSION`。

## 4. 新模块 API 契约

### 4.1 `backend/update_checker.py`

- `check_for_update(current=APP_VERSION, timeout=10) -> Optional[dict]`
  - GET `RELEASES_LATEST_API`（`User-Agent: FileSyncTool/<ver>`，`Accept: application/vnd.github+json`）。
  - 字段：`version`(去 `v` 前缀)、`tag`、`published_at`、`notes`、`page_url`、`asset_url`、`asset_name`、`asset_size`。
  - 资产选择：优先 `.exe`；无 `.exe` 返回 `asset_url=""`（只提示、不下载）。
  - `now - published_at < 24h` → 返回 `{"reason": "too_new", ...}` 由调用方忽略（不弹窗）。
  - 网络/解析异常 → 返回 `None` 并 `print`。
- `should_auto_check(config_manager) -> bool`：`auto_check_updates` 为真且 `last_update_check` 距今 ≥ 24h。
- `record_check_time(config_manager)`：写 `last_update_check`（UTC ISO）。

### 4.2 `backend/usb_monitor.py`

见 2.1。另导出 `snapshot_devices()`、`UsbMonitor`、`EVENT_INSERTED`、`EVENT_REMOVED`。

### 4.3 `backend/ai_config.py`

- `DEFAULT_AI_PROMPT: str`（中文全文）
- `class AIConfigError(Exception)`
- `parse_ai_config(text: str) -> dict`：返回规范化字段（缺失可选字段补默认）。
- `to_task_prefill(cfg: dict) -> dict`：输出含 `source`、`target`、`sync_direction`、`mode`、`default_strategy`，以及可选 `ai_filter_template`。
- 扩展名规范化：确保以 `.` 开头、小写。

## 5. 逐文件改动清单

### 5.1 新增

| 文件 | 内容 |
|---|---|
| `backend/usb_monitor.py` | 2.1 |
| `backend/version.py` | 3.4 |
| `backend/update_checker.py` | 4.1 |
| `backend/updater.py` | 2.2 |
| `backend/ai_config.py` | 4.3 |

### 5.2 修改

| 文件 | 改动 |
|---|---|
| `backend/downloader.py` | 第 29 行 `import accelerator` → `try: from . import accelerator  except ImportError: import accelerator`（修复包内导入崩溃） |
| `backend/config_manager.py` | `DEFAULT_CONFIG["settings"]` 增加 `usb_auto_sync_enabled`、`last_update_check` |
| `backend/task_manager.py` | `create_task` 增加 `usb_auto_sync=False, usb_binding=None` 形参并写入任务字典 |
| `gui/app.py` | ① `_init_backend_modules` 末尾创建 `self.usb_monitor` 并按设置启动，新增 `apply_usb_auto_sync_setting()`；② 新增 `_handle_usb_event`、`_match_usb_tasks`、`_rewrite_usb_paths`、`_prompt_usb_task_creation`；③ `_create_page` 的 `create_task` 分支透传 `prefill_config=kwargs.get("prefill_config")`；④ `_on_save_and_start_sync` 透传 `usb_auto_sync` / `usb_binding`；⑤ `_on_closing`/`safe_exit` 中 `usb_monitor.stop()`；⑥ 启动后 `after(3000, self._auto_check_update)`，后台检查，结果 `post_ui` 弹更新对话框 |
| `gui/create_task_page.py` | ① 构造新增 `prefill_config: Optional[Dict] = None`，创建控件与加载编辑数据后应用预填；② 新增 `_create_usb_bind_section()`（content_frame row=9）：复选框「当插入特定 U 盘时自动同步」+ 当前设备下拉（`snapshot_devices()`）+ 刷新按钮 + 状态提示；③ `usb_auto_sync`/`usb_binding`/`ai_filter_template` 状态字段；④ `get_task_config`、`_on_next_step_click`、`_on_skip_config_click` 三个构建点统一补齐这三个键；⑤ `_load_task_data` 读取绑定并回填；⑥ 勾选时若无可用 U 盘，取消勾选并提示 |
| `gui/folder_config_page.py` | 扫描出 `self.subfolders` 后，若 `task_config.get("ai_filter_template")` 非空，则为每个子文件夹写入 `folder_filters[name] = dict(template)`（已有配置不覆盖） |
| `gui/settings_page.py` | 新增 row=8「U 盘自动同步」区：总开关 + 说明；切换后写 `usb_auto_sync_enabled` 并调用 `app.apply_usb_auto_sync_setting()` |
| `gui/toolkit_page.py` | ① `_create_content` 增加 `_create_ai_config_section()`（row=6）与 `_create_update_section()`（row=7），「反馈与问题」由 row=5 不变；② AI 按钮打开 `AIConfigDialog`；③ 更新区显示当前版本、`auto_check_updates` 复选框、立即检查按钮、状态标签；④ 新增 `AIConfigDialog`（`CTkToplevel`，模态；Prompt 只读 `CTkTextbox` + 复制按钮；JSON 输入 `CTkTextbox`；解析按钮；错误红色标签；成功后 `app.show_page("create_task", prefill_config=...)`） |
| `main.py` | 文件头注释更新为 v7.7；`--help` 描述保持 |
| `FileSyncTool.spec` | datas 增加 `('tools/aria2/aria2c.exe', 'tools/aria2')`（不打包 fastgithub 大目录） |
| `translations/zh.json`、`en.json`、`zh_tw.json` | 新增键见第 6 节；`app_title` 更新为 v7.7 |

## 6. 新增翻译键（zh 基准，en / zh_tw 同步翻译）

```
app_title                        文件同步工具 v7.7
usb_auto_sync_section            插入 U 盘时自动同步
usb_auto_sync_switch             插入 U 盘时自动同步
usb_auto_sync_hint               检测到已绑定的 U 盘插入后自动运行对应同步任务；关闭后不再监听。
usb_bind_section                 自动同步（U 盘）
usb_bind_checkbox                当插入特定 U 盘时自动同步
usb_bind_current_device          当前 U 盘
usb_bind_no_device               未检测到 U 盘，请插入后刷新
usb_bind_refresh                 刷新设备列表
usb_bind_hint                    绑定当前 U 盘的唯一标识；之后插入同一 U 盘时自动同步本任务。
usb_bind_need_usb                当前没有检测到 U 盘，无法绑定
usb_inserted_title               检测到 U 盘
usb_inserted_message             检测到 U 盘「{label}」插入，但没有任何任务绑定它。是否创建自动同步任务？
usb_create_task_now              创建自动同步任务
usb_not_now                      暂不
usb_sync_started                 已检测到 U 盘「{label}」，正在自动同步：{name}
usb_sync_skipped                 任务「{name}」正在同步中，本次自动触发已跳过
update_section                   软件更新
update_current_version           当前版本：v{version}
update_check_now                 检查更新
update_checking                  正在检查更新…
update_up_to_date                已是最新版本
update_auto_check                启动时自动检查更新（每 24 小时最多一次）
update_available_title           发现新版本 v{version}
update_available_message         发布时间：{date}
                                 更新内容：
                                 {notes}
update_too_new                   新版本发布不足 24 小时，稍后再提示
update_download                  下载并更新
update_downloading               正在下载更新：{percent}%（{speed} KB/s）
update_download_done_title       下载完成
update_download_ready            更新准备就绪，即将重启应用。如果您的安全软件弹出拦截提示，请选择“允许”。
update_restart_now               立即重启并应用
update_manual_title              请手动完成更新
update_manual_message            新的程序文件已下载到：
                                 {path}
                                 请关闭本程序后，用该文件替换当前程序。
update_open_page                 打开发布页
update_open_folder               打开下载目录
update_failed                    检查更新失败，请稍后重试
ai_config_section                AI 帮我配置
ai_config_button                 AI 帮我配置
ai_config_hint                   复制预置 Prompt 给 AI，把生成的 JSON 粘贴回来即可创建任务。
ai_dialog_title                  AI 帮我配置
ai_prompt_label                  第 1 步：复制下面的 Prompt 给任意 AI
ai_copy_prompt                   复制 Prompt
ai_copied                        已复制
ai_json_label                    第 2 步：粘贴 AI 生成的 JSON
ai_json_placeholder              在此粘贴纯 JSON 配置
ai_import_button                 解析并创建任务
ai_json_error                    JSON 格式错误，请重新生成
ai_prompt_template               （用户给定 Prompt 全文，中/英/繁三份；
                                  en/zh_tw 仅翻译自然语言，JSON 键名/枚举/字面量保持英文原样，见 2.3）
```

## 7. 验证计划

1. `python -m compileall backend gui main.py`
2. 导入修复：`python -c "from backend import downloader; print(downloader._aria2_exe())"`
3. 翻译完整性：三个 JSON 均可 `json.load`，且键集合与 zh 完全一致、无空值
4. `backend.ai_config`：合法样例 → 预填字典；代码围栏包裹样例 → 成功；缺 `source` / 非法 `mode` / 非 JSON → 均抛 `AIConfigError`
5. `backend.usb_monitor.snapshot_devices()`：本机无 U 盘时返回 `[]` 且不报错；插入 U 盘后可读到 `serial/label/mount`
6. `backend.update_checker.parse` 用本地假 JSON（monkeypatch `urlopen`）验证：新版可用、同版无更新、不足 24h 返回 `too_new`、网络异常返回 `None`
7. `backend.updater.write_windows_update_script` 生成内容逐行比对（含 `:retry`、`TRIES lss 5`、`:failed`、`update_failed.txt`、`mshta` 五个要素）；`launch_update_script` 仅在 frozen 时可达（开发环境走手动分支）
8. 三语 `ai_prompt_template` 均能通过 `parse_ai_config` 中的 JSON 模板片段提取校验：键名与枚举值在 en/zh_tw 中与 zh 完全一致，仅自然语言不同
9. GUI 冒烟：启动无异常；设置开关即时启停监听；创建任务勾选绑定后 `usb_binding` 正确落盘；工具包 AI 弹窗可复制 Prompt、错误 JSON 提示、正确 JSON 跳转并预填；工具包更新区可手动检查

## 8. 风险与约束

- 轮询开销：仅 2 秒一次枚举盘符/挂载点，IO 极轻；不做 ctypes 窗口消息 hook。
- 后台线程严禁触碰 Tk：监听事件、下载进度、更新检查结果全部经 `app.post_ui` 回主线程。
- `.bat` 依赖外部进程存活：先预检目录可写，失败则明确走手动替换；安全软件拦截时用“允许”文案提示。
- `tools/` 为未跟踪目录，打包体积需权衡，故仅打包 aria2c。
- 绑定的 U 盘若格式化导致序列号变化需重新绑定（提示文案已说明唯一标识）。
