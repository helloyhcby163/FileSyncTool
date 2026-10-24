🚨 紧急安全声明 (Security Advisory)

⚠️ 废弃版本警告：由于早期设计的不完善，v7.6.0 至 v7.7.0 版本中的「同步后执行命令」功能存在潜在的安全滥用风险。为了防止恶意脚本借此功能损害用户设备，开发者正式宣布废弃上述所有旧版本。

🛡️ 补救措施：我们正在紧急重构该功能，新版本（v7.7.1 及以后）将彻底移除执行任意命令的接口，改为严格的内置安全动作。

👉 用户操作建议：请所有用户立即停止使用 v7.6.0 - v7.7.0 版本，并暂缓使用“执行命令”功能。请密切关注我们的最新 Release，在安全重构版发布后尽快升级。感谢您的理解与配合！

# FileSyncTool / 文件同步工具

一个专注 U 盘与文件夹同步的跨平台文件同步工具，注重性能与跨平台兼容。具有自动化。同时也擅长通用文件同步。

A cross-platform file synchronization tool that focuses on U-disk and folder synchronization, emphasizing performance and cross-platform compatibility. It features automation and excels in general file synchronization.

## 🚀 v7.7.1 Security & Hardening Release

This release fixes critical security vulnerabilities present in v7.6 - v7.7 and brings major updates:

- 🛡️ **Security Refactoring**: Completely removed the "execute arbitrary command" feature and replaced it with built-in safe actions. Added SHA-256 hash verification for auto-updates. Filtered system symlinks to prevent path traversal attacks.
- 🤖 **Brand New CLI Support**: Added `--config`, `--source`, `--target`, and `--silent` parameters, perfectly supporting script orchestration and automated pipelines.
- ⚡ **Pure Python Multi-threaded Download**: Completely removed external dependencies (aria2c/FastGithub), natively supporting multi-threaded chunked downloading with a 3-tier fallback (GitHub/Gitee/Mirror).
- 🎨 **Experience Optimization**: Path log sanitization, and network acceleration status display.

**⚠️ It is strongly recommended that all users of older versions upgrade to this version immediately!**

---

## 🚀 v7.7.1 安全加固版发布

本版本修复了 v7.6 - v7.7 中的高危安全问题，并带来了重大更新：

- 🛡️ **安全重构**：彻底移除“任意命令执行”功能，改为内置安全动作。加入自动更新 SHA-256 哈希校验。过滤系统软链接，防止路径穿越。
- 🤖 **全新 CLI 支持**：新增 `--config`、`--source`、`--target`、`--silent` 参数，完美支持脚本编排与自动化流水线。
- ⚡ **纯 Python 多线程下载**：彻底移除外部依赖（aria2c/FastGithub），原生支持多线程分块下载与 GitHub/Gitee/镜像三层降级。
- 🎨 **体验优化**：路径日志脱敏、网络加速状态显示。

**⚠️ 强烈建议所有旧版本用户立即升级至此版本！**
