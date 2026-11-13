# HomeSpread 中文 macOS 版隐私说明

更新日期：2026-11-13。

HomeSpread 通过 macOS 本地 iPhone 连接服务 `/var/run/usbmuxd` 与 USB 连接、已获信任的 iPhone 通信。它读取主屏幕布局、应用名称和标识、文件夹、图标、布局尺寸，以及连接诊断所需的设备名称、型号、系统版本等。读取安装列表用于提醒哪些 App 资源库中的应用可能在写入后重新出现。它不主动读取照片、通讯录、聊天消息、密码或应用数据。

应用没有分析追踪、广告、自动更新、云端同步或自动上传功能。赞助和上游源码链接只在用户主动点击后由默认浏览器打开。源码安装、构建依赖安装及手动漏洞扫描会访问 Python 包索引或漏洞数据库，这些开发工具不在日常使用时运行。

## 本地保存

- `~/Library/Application Support/HomeSpread/backups/`：布局原文、可读副本、校验记录。以设备 UDID 的 SHA-256 分目录；不把完整 UDID 用作目录名。备份不自动清理。
- `~/Library/Application Support/HomeSpread/logs/`：会话日志、设备与布局诊断文件，以及手动诊断生成的报告 ZIP。只保留最近 20 个符合本应用会话命名规则的会话。
- `~/Library/Application Support/HomeSpread/settings.json`：界面语言选择。
- `~/Library/Caches/HomeSpread/icons/`：应用图标和缓存索引；可删除后重新读取。

设备连接的信任和配对由 macOS 与 pymobiledevice3 管理。HomeSpread 新建的配对缓存位于 `~/Library/Application Support/HomeSpread/pairing/`，包含敏感信任凭据，目录权限为 0700；应用不会将其加入日志报告或分发包。现有 macOS 系统配对记录仍由系统管理。开发环境可通过 `HOMESPREAD_DATA_DIR` 和 `HOMESPREAD_CACHE_DIR` 明确覆盖数据位置。

HomeSpread 创建的备份、诊断文件和目录设置为当前用户可访问的私有权限。数据未由应用单独加密；能够访问当前 macOS 账户或磁盘的程序仍可能读取它们。日志会遮盖常见格式的完整 UDID，但设备名称、应用列表和文件夹名仍可能包含个人信息，不能将报告视为匿名数据。

## 写入与恢复

只有用户在界面确认“原样写回校验”“应用”或“恢复”，或在诊断命令中明确确认写入测试后，程序才会发送主屏幕写入请求。写入前会保存、同步并读回验证备份；备份失败则停止。恢复同样先备份当前状态。

写入替换整份主屏幕。仅在 App 资源库中的应用可能被 iOS 重新放回桌面，旧备份不能撤销该系统行为。布局备份不是 iPhone 整机备份。

## 删除与分享

删除缓存不会删除布局备份。卸载 `.app` 不会删除上述用户资料目录；可在 Finder 中打开目录并自行删除。删除备份会失去对应恢复点。诊断报告只保存在本机，分享前应检查设备名称、应用列表和文件夹内容。
