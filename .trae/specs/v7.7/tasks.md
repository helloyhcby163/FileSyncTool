# FileSyncTool v7.7 任务清单

依赖顺序：T1 → T2/T3 → T4 → T5 → T6 → T7 → T8；T9、T10 可与 T5 并行。

## T1 基础修复与版本常量
- [x] `backend/downloader.py`：`import accelerator` 改为包内相对导入 + 顶层回退
- [x] 新建 `backend/version.py`：`APP_VERSION="7.7"`、`GITHUB_REPO`、`RELEASES_LATEST_API`、`parse_version()`、`is_newer()`
- [x] `main.py` 文件头注释更新为 v7.7
- 验收：`python -c "from backend import downloader, version; print(version.APP_VERSION)"`

## T2 U 盘监听模块
- [x] 新建 `backend/usb_monitor.py`（2.1 全部逻辑：Windows / macOS / Linux、防抖 3 秒、静默基线、去重、`snapshot_devices()`）
- 验收：无 U 盘 `snapshot_devices()` 返回 `[]`；插入后可读 serial/label/mount；`stop()` 1 个周期内退出

## T3 更新检查与自更新
- [x] 新建 `backend/update_checker.py`（GitHub API、24h published_at 门限、24h 节流、异常静默）
- [x] 新建 `backend/updater.py`（download_update / write_windows_update_script（含 5 次重试 + update_failed.txt + mshta 兜底）/ launch_update_script / 可写性预检）
- 验收：monkeypatch `urlopen` 的四种场景；`update.bat` 含 `:retry`、`TRIES lss 5`、`:failed`、`update_failed.txt`、`mshta` 五个要素

## T4 AI 配置解析
- [x] 新建 `backend/ai_config.py`（`DEFAULT_AI_PROMPT`、`parse_ai_config`、`to_task_prefill`、白名单校验、扩展名规范化）
- 验收：合法 / 代码围栏 / 缺字段 / 非法枚举 / 非 JSON 五种输入行为正确

## T5 数据层接入
- [x] `backend/config_manager.py`：settings 增加 `usb_auto_sync_enabled=True`、`last_update_check=""`（`CURRENT_VERSION` 不动）
- [x] `backend/task_manager.py`：`create_task` 增加 `usb_auto_sync`、`usb_binding` 并写入任务
- 验收：新建任务 JSON 中出现两字段，旧任务读取不报错

## T6 创建任务页：U 盘绑定 + 预填
- [x] 构造新增 `prefill_config`，控件创建后应用预填（目录、方向、模式、策略、绑定、`ai_filter_template`）
- [x] 新增 `_create_usb_bind_section()`（row=9）：复选框 + 当前设备下拉 + 刷新 + 无设备提示
- [x] 三个配置构建点（`get_task_config`、`_on_next_step_click`、`_on_skip_config_click`）补齐 `usb_auto_sync` / `usb_binding` / `ai_filter_template`
- [x] `_load_task_data` 回填绑定状态
- 验收：勾选后进入确认页保存，任务 JSON 的 `usb_binding.serial` 与当前 U 盘一致；不插 U 盘时勾选被拒绝并提示

## T7 App 接线：监听生命周期与触发
- [x] `_init_backend_modules`：创建 `UsbMonitor` 并按总开关启动
- [x] `apply_usb_auto_sync_setting()`：开关即时启停
- [x] `_handle_usb_event` / `_match_usb_tasks` / `_rewrite_usb_paths` / `_prompt_usb_task_creation`（主线程，路径重写按 3.2）
- [x] `_create_page` 透传 `prefill_config`；`_on_save_and_start_sync` 透传 usb 字段
- [x] `_on_closing` / `safe_exit` 停止监听线程
- 验收：插入绑定的 U 盘 → 自动进入同步进度页；无绑定 → 弹引导窗；关闭程序后线程退出

## T8 设置页与工具包页
- [x] `gui/settings_page.py`：row=8「U 盘自动同步」总开关区
- [x] `gui/toolkit_page.py`：row=6「AI 帮我配置」区 + `AIConfigDialog`；row=7「软件更新」区（版本、自动检查、立即检查、状态）
- [x] `gui/app.py`：启动 3 秒后自动检查更新（24h 节流），发现新版本弹窗；下载→frozen 走 .bat/非 frozen 走手动提示
- 验收：总开关即时生效；AI 弹窗可复制 Prompt、错误提示、成功预填；更新区可手动检查并展示结果

## T9 筛选模板落地
- [x] `gui/folder_config_page.py`：扫描出子文件夹后把 `ai_filter_template` 套用到全部子文件夹（不覆盖已有）
- 验收：AI JSON 带扩展名/日期时，文件夹配置页所有子文件夹均显示对应筛选

## T10 多语言与打包
- [x] 三个翻译文件补齐第 6 节全部键（`ai_prompt_template` 中文逐字一致；en/zh_tw 只翻译自然语言，JSON 键名与枚举值保持英文原样）
- [x] `app_title` 更新为 v7.7
- [x] `FileSyncTool.spec` datas 增加 `tools/aria2/aria2c.exe`
- 验收：三 JSON 键集合一致且可加载；打包配置无语法错误

## T11 回归验证
- [x] `python -m compileall backend gui main.py`
- [x] 按 spec 第 7 节逐项执行
- [x] GUI 冒烟：启动、创建任务、绑定、工具包三新功能、设置开关
