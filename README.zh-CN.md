# HomeSpread 中文 macOS 版

在 Mac 上展开 iPhone 的多页主屏幕，拖动应用、整理文件夹，再把确认过的布局写回手机。

本分支基于 [humanlyj/HomeSpread](https://github.com/humanlyj/HomeSpread) 的提交 `0cfbc6866e9748105cbc3c9e743ad0b1788e6775`。这是中文 macOS 移植版，版本 `1.0.22-mac.zh.1`，保留 GPL-3.0-or-later 许可和原作者历史。来源核查见 [PROVENANCE.zh-CN.md](PROVENANCE.zh-CN.md)，原仓库的 Windows 说明见 [README.md](README.md)。

## 启动与使用

1. 在 Finder（访达）中双击 `dist/HomeSpread.app`。程序包含 Python 和 Qt，不需要另装 Python、iTunes 或 Apple Devices。
2. 用数据线连接一台 iPhone，解锁，在手机上确认“信任此电脑”。保持连接与解锁。
3. 点击“从设备读取”。点击“获取图标”即可显示应用图标。
4. 若要写回，在开始编辑前点击“原样写回校验”。它会在明确确认后备份、真实写回当前布局并核对读回结果；也可能触发下述 App 资源库回填。未通过校验时禁止应用编辑。为便于故障恢复，仍可在单独确认风险后恢复同设备的校验备份；恢复后读回核对通过也会建立当前会话的编辑写入许可。每次重新读取或操作失败后需重新校验。
5. 拖动应用调整位置；双击文件夹查看内容。按住 **⌘ Command** 点选多个应用，按 **⌘G** 新建文件夹；**⌘Z** 撤销，**⇧⌘Z** 重做。文件夹名称也可用工具栏“重命名”修改。
6. 查看右侧修改列表，点击“应用修改”，阅读影响并勾选确认后，程序才会备份并写入。

读取、获取图标、编辑和撤销都不会修改 iPhone。确认后的“原样写回校验”“应用修改”或“从备份恢复”会写入。导入备份文件只供预览，不能直接写到另一台手机；恢复必须先读取对应设备，再选该设备自己的完整备份。

**应用和恢复都会替换整份主屏幕布局。** iOS 可能把仅留在 App 资源库的应用重新加入主屏幕；恢复旧备份也不能撤销这一系统行为。主屏幕备份不包含应用数据、照片、壁纸或整机系统状态。

如果手机上的布局在读取之后发生了变化，应用会停止写入，要求重新读取。无法理解的布局结构会被拒绝；未知内容必须保持原样。写入失败或读回结果不符时，不自动重试或自动恢复，先检查提示和备份。

## 本机数据

| 内容 | 位置 |
|---|---|
| 备份、日志和设置 | `~/Library/Application Support/HomeSpread/` |
| 每台设备的备份 | `backups/<设备标识的 SHA-256>/` |
| 新建的本地设备配对凭据 | `~/Library/Application Support/HomeSpread/pairing/` |
| 可重新下载的图标 | `~/Library/Caches/HomeSpread/icons/` |
| 对应修改源码与依赖清单 | `.app/Contents/Resources/` 中的 `HomeSpread-source.zip` 与 `dependency-inventory.json` |

每份备份由 `.plist`、可读 `.json`、校验用 `.meta.json` 组成，移动或存档时保留三者和原设备目录。恢复时会检查设备归属与 SHA-256。旧版没有归属记录的备份可预览，不能用于恢复。

数据文件使用当前用户私有权限；它们没有单独加密。诊断报告含应用清单、文件夹名和设备信息，分享前应检查内容。应用不自动上传数据、不自动更新，也不会自动打开赞助链接。详见 [中文隐私说明](PRIVACY.zh-CN.md)。

## 从源码运行或重新构建

构建环境为 Apple Silicon Mac（macOS 14 或更新）和 Python 3.12。macOS 包为 arm64，不是 Intel 通用包；仅本机 macOS 27.3 已实际验证。

```sh
./install_macos.command
./run_macos.command
./run_probe_macos.command          # 只读诊断并备份，不写手机
./build_macos.command             # 生成 dist/HomeSpread.app
```

`install_macos.command` 安装 `requirements-macos.lock` 中锁定的 93 个运行时依赖；`requirements-build.txt` 是打包、测试和审计工具。首次创建虚拟环境时可用 `HOMESPREAD_PYTHON=/路径/python3.12` 指定解释器。安装脚本遇到任何失败会停止。

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
./run_macos.command --demo             # 虚构布局，无法写入手机
./run_macos.command --language zh_CN   # 也支持 en、ko
.venv/bin/python -m pip_audit --progress-spinner off
```

测试可用 `HOMESPREAD_DATA_DIR` 和 `HOMESPREAD_CACHE_DIR` 指定隔离目录。依赖升级须重新审计、运行测试，再运行 `scripts/lock_macos.py` 更新版本快照。构建过程不修改锁文件。锁文件固定版本，未固定下载文件哈希。

`.app` 使用本地临时签名（ad-hoc），未经过 Apple Developer ID 签名或公证。它用于这台电脑上的本地运行；向其他电脑分发前需另行处理签名、公证及适配验证。无需关闭 Gatekeeper 或 SIP。

## 验证边界

源码全量测试通过：173 项测试、351 项子测试，包含 25 项 macOS/UI/工作线程检查和 24 项安全回归。Apple Silicon `.app` 打包及本地签名校验通过。独立检查记录见 [_workspace/04_macos-qa_final-report.md](_workspace/04_macos-qa_final-report.md)。

已在获授权的 iOS 27.3 设备上验证 USB 发现、连接、读取主屏幕、读取网格尺寸和创建校验备份。设备清单和原始布局保留在本地，不随源码公开。尚未执行真实 `setIconState`、原样写回或恢复；软件测试不能代替对应 iOS 版本的真实写入验证。

详细审计发现、修复与残余风险见 [安全审计报告](SECURITY_AUDIT.zh-CN.md)。上游文档中的 iPhone 14 / iOS 26.1 写入结果是上游历史记录，不能作为此 macOS 修改版的写入验收。

## 许可与源码

许可证原文见 [LICENSE](LICENSE)，中文阅读说明见 [LICENSE.zh-CN.md](LICENSE.zh-CN.md)，全部文档入口见 [文档索引](DOCUMENTATION.zh-CN.md)。macOS 包包含本次修改的对应源码、依赖清单及第三方许可，不将上游仓库链接冒充本地修改版源码。重新分发时请一并提供这些材料，并遵守相应许可证。
