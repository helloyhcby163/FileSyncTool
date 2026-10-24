# FileSyncTool v7.7 验收清单

## 基础与版本
- [x] `backend/downloader.py` 在包内导入时不再抛 `ImportError`（已改为相对导入 + 顶层回退）
- [x] `backend/version.py` 提供 `APP_VERSION="7.7"`、`is_newer()`、`parse_version()`
- [x] `main.py` 文件头与 `--help` 描述均为 v7.7

## U 盘自动同步
- [x] `backend/usb_monitor.py` 后台线程实现，无任何 Tk/GUI 调用；首次扫描仅建立基线
- [x] 插入后等待 3 秒再读取并发出事件（防抖），拔出立即发出 removed
- [x] Windows 读取卷序列号 + 卷标 + BusType==USB；macOS/Linux 使用挂载点与 UUID
- [x] `snapshot_devices()` 在无设备时返回 `[]` 且不抛异常（已实测）
- [x] 创建任务页 row=9 存在「当插入特定 U 盘时自动同步」复选框、设备下拉与刷新按钮
- [x] 勾选后任务 JSON 写入 `usb_auto_sync` 与 `usb_binding`（serial/label/mount/子路径）
- [x] 设置页 row=8 存在「插入 U 盘时自动同步」总开关，切换即时启停监听
- [x] 无绑定任务插入 U 盘时弹窗引导创建（同设备每次插入只提示一次）
- [x] 已绑定任务插入时按新挂载点重写路径副本，不回写任务配置
- [x] 程序退出（`_on_closing` / `safe_exit`）时停止监听线程

## 自动版本更新
- [x] 启动 3 秒后自动检查，`auto_check_updates` + 24 小时节流生效
- [x] GitHub Releases 解析 `tag_name`/`published_at`/`body`/exe asset
- [x] 新版本发布不足 24 小时返回 `too_new`，不弹更新提示（已用 mock 验证四种场景）
- [x] 下载复用 `downloader.download()`（内部调用 `accelerator.rewrite_url()`）
- [x] `.bat` 含 5 次 `move` 重试、每次 `timeout /t 2`（已实测生成内容）
- [x] `.bat` 失败时写 `%TEMP%\FileSyncTool_update_failed.txt` 并用 `mshta` 弹出系统级提示
- [x] `.bat` 成功分支启动新程序并 `del "%~f0"` 自删除
- [x] `launch_update_script` 使用 `CREATE_NO_WINDOW | DETACHED_PROCESS` 隐藏窗口
- [x] 非 frozen / 非 Windows / 目录不可写时引导手动替换并打开发布页

## AI 配置生成器
- [x] 工具包页 row=6 存在「AI 帮我配置」入口与说明
- [x] 弹窗包含只读 Prompt 文本框、一键复制按钮（1.5 秒恢复文案）
- [x] JSON 输入框 + 「解析并创建任务」按钮，成功后关闭弹窗并预填创建任务页
- [x] 缺字段 / 非法枚举 / 非 JSON / 代码围栏四种输入行为正确（已实测）
- [x] 解析失败提示「JSON 格式错误，请重新生成」
- [x] `ai_filter_template` 在文件夹配置页套用到全部子文件夹且不覆盖已有配置

## 多语言与打包
- [x] 三份翻译均为 391 个键、键集合完全一致、无空值（已实测）
- [x] `app_title` 更新为 v7.7（中/英/繁）
- [x] en / zh_tw 的 `ai_prompt_template` 仅翻译自然语言，JSON 键名与枚举值保持英文原样（已实测）
- [x] `FileSyncTool.spec` datas 增加 `tools/aria2/aria2c.exe`，文件头更新 v7.7

## 回归
- [x] `python -m compileall backend gui main.py` 通过
- [x] GUI 冒烟：`FileSyncApp` 可创建、页面可加载、退出时后台监听被停止
