# HomeSpread

*iOS 主屏幕布局管理工具*

在电脑上同时展开 iPhone 的多页主屏幕，用拖放整理应用和文件夹，再将确认过的布局写回手机。本仓库是 [humanlyj/HomeSpread](https://github.com/humanlyj/HomeSpread) 的中文 macOS 分支，保留原作者提交历史和 GPL-3.0-or-later 许可。

- **Mac 使用与构建：** [macOS 中文使用指南](README.zh-CN.md)
- **安全与隐私：** [安全审计](SECURITY_AUDIT.zh-CN.md)、[隐私说明](PRIVACY.md)
- **项目来源：** [来源核查](PROVENANCE.zh-CN.md)
- **开发资料：** [文档索引](DOCUMENTATION.zh-CN.md)、[开发规范](CLAUDE.md)

## 当前状态与验证范围

**iPhone Duo 与小组件布局仅支持只读预览。** 小组件按跨格面积绘制，Duo 显示两个逻辑页和右侧程序坞。点击“打开备份文件”后选择 Duo 预览即可离线查看；不会自动读取手机。此类布局的拖放、应用修改、恢复和原样写回校验均禁用，详见 [使用指南](README.zh-CN.md)。


中文 macOS 版 `1.0.22-mac.zh.2` 已完成 Apple Silicon 应用打包、启动和签名校验。自动测试覆盖编辑模型、中文界面、设备工作线程、备份完整性和写入保护；结果见[验收记录](_workspace/04_macos-qa_final-report.md)。macOS 使用系统自带的 iPhone 连接服务，不需要安装 Apple Devices 或 iTunes。

本分支在获授权的 iOS 27.3 设备上完成了 USB 连接、布局读取、网格读取和本地备份校验，**没有执行真实的原样写回、编辑应用或恢复**。对于通过设备与布局能力检查的普通布局，编辑流程须先通过用户明确确认的“原样写回校验”，再启用“应用修改”。能力检查通过但会话校验失败时，仍保留单独确认的同设备备份恢复入口；恢复后读回核对通过，也会建立当前会话的编辑写入许可。

上游 Windows 版曾在 iPhone 14 / iOS 26.1 上验证读取、展示、拖放编辑、备份和写入。两次应用均记录丢失 0 项、系统追加 0 项，第二次发出与读回的内容完全相同。这些是上游 2026 年 8 月的历史结果，不能代替本分支或其它设备的写入验收。

## 工作原理

非越狱 iPhone 的 lockdown 服务 `com.apple.springboardservices` 提供 `getIconState` / `setIconState`。程序通过它读取和写入表示整份主屏幕布局的 plist，不依赖越狱、开发者模式、Xcode 或 WebDriverAgent。具体设备和系统版本是否接受写入，需要单独验证。

**`setIconState` 替换整份布局，不是局部修改。** 如果遗漏未知元素，例如小组件或新系统功能，写回可能丢失它们。程序因此遵守以下规则：

- 统一能力检查拒绝 Duo、小组件、未知项及空位布局的所有写入；恢复同样检查手机现状和目标备份。
- 保留原始数据，只在其上建立解析和编辑视图，见 `iconstate.py`、`layout.py`。
- 写入前重新读取设备，编辑应用必须与最初读入的布局一致，防止旧快照覆盖手机上的新变化。
- 所有写入先保存、同步并读回验证备份；失败即停止，见 `backup.py`。
- 备份按设备指纹隔离；恢复检查设备归属和文件摘要。
- 原样写回校验、应用修改和恢复都需要明确确认，并重新读取结果进行核对。

备份提供布局恢复点，**不保证完整撤销所有系统副作用**。iOS 可能把仅位于 App 资源库的应用重新放回主屏幕，恢复旧备份也可能再次触发这一行为。布局备份不包含应用数据、照片、壁纸或完整系统状态。读与写之间没有原子比较交换，操作时应避免同时在手机上整理桌面。

## macOS 快速开始

1. 双击构建产物 `dist/HomeSpread.app`，或已安装到个人应用程序文件夹的 `~/Applications/HomeSpread.app`。
2. 若要读取设备，用数据线连接一台 iPhone，解锁并在手机上选择“信任此电脑”。
3. 点击“从设备读取”，再按需点击“获取图标”。读取、查看和本地编辑不会写入手机。
4. 仅对能力检查通过的普通布局，若要应用编辑，在开始编辑前点击“原样写回校验”。阅读确认框并勾选确认后才会真实写回；这不是只读测试。
5. 整理布局，检查右侧修改列表，再点击“应用修改”并确认。

安装、源码运行、Apple Silicon 构建要求、命令和数据路径详见 [macOS 中文使用指南](README.zh-CN.md)。尚未连接手机时显示“未连接”是正常状态。

## Windows 准备与运行

本节保留上游 Windows 使用方式的中文说明。Windows 安装和打包脚本没有在本次 Mac 验收中重新运行，不将历史依赖安装方式视为当前 macOS 的安装流程。

1. 安装 **Apple Devices 或 iTunes**。上游推荐 Microsoft Store 的 Apple Devices；这些组件负责 Windows 与 iPhone 的 USB 通信。
2. 双击 `install.bat`，或在命令提示符中运行：

   ```bat
   install.bat
   ```

   在 PowerShell 中也可运行 `.\install.ps1`。在 cmd 中直接输入 `.\install.ps1` 可能只打开文件关联程序，不能当作成功执行脚本。

上游安装脚本为当时的依赖环境避开了部分需要本地编译、且主屏幕操作未用到的包。其记录中的 `lzfse` 构建会要求 Visual C++ 工具；这不代表当前所有版本在所有平台上都有同样限制。Mac 使用独立的锁定文件和安装脚本。

启动时的引导面板每 3 秒检查一次本机 `127.0.0.1:27015` 是否可连接。安装目录只用于选择提示语：区分“已安装但服务未启动”和“尚未安装”。服务可用并不表示手机已经连接或已授予信任。

将 iPhone 用数据线连接、保持解锁，然后运行：

```bat
run_app.bat
```

首次建立配对需要在手机上确认“信任此电脑”，并按系统要求输入密码。若出现设备锁定或未信任提示，解锁后重连再试；重置信任或配对信息后可能需要再次确认。

没有 Python 的 Windows 电脑可以接收完整的 `HomeSpread\` 分发文件夹，双击其中的 `HomeSpread.exe`，无需运行源码安装脚本。普通文件夹分发会在程序旁创建 `logs\`、`backups\` 等数据，因此需要可写目录。不能写入备份时，程序会提示并停止相关操作。

重新构建 Windows 分发文件夹的入口为：

```bat
build_exe.bat
```

输出位置为 `dist\HomeSpread\`，打包配置见 `HomeSpread.spec`。上游选择文件夹而非单文件 exe，是为避免每次启动解压内置文件：2026-08-21 的记录中，单文件启动约 21 秒，其中解压约 16.5 秒；文件夹版约 2.3 秒。上游 Windows 启动画面由 PyInstaller 引导程序显示，记录约 0.3 秒出现。以上是当时的测量，不是本机性能承诺；macOS 包不使用该 Windows 启动画面。

## 编辑操作

本节适用于通过能力检查的普通布局；Duo、小组件和未知结构的布局只能预览。

读取后，各页主屏幕会同时展开。未获取图标时显示文字替代图块；点击“获取图标”会从已连接设备读取并缓存图像。上游记录约 300 个图标需要 8 秒，再次打开可使用缓存。

拖动应用可调整位置，双击文件夹可展开内容。拖到文件夹中央表示放入文件夹，放到边缘表示插入旁边。右侧持续显示修改列表；尚未确认应用前，手机上的布局不变。

### 创建文件夹与重命名

有两种分组方式：

- 把一个应用拖到另一个应用的中央；拖到边缘仍是普通插入。
- 按住 Ctrl 多选应用，再按 Ctrl+G 分组；macOS 对应 ⌘ Command 和 ⌘G。可以跨页面多选，文件夹按屏幕顺序收纳应用，而非点击顺序，并放在第一项原来的位置。

创建后会询问名称。已有文件夹和新文件夹都可通过“重命名”按钮改名；上游快捷键为 F2。

把应用插入已满页面的具体位置，会将后续条目逐个后移，溢出的末项进入下一页开头；必要时继续后移或新增页面。拖到末尾空白区域表示追加，会寻找可用空间，而不会无故把未指向的项目推到下一页。主屏幕页面与文件夹内页共用这套布局规则。

清空的文件夹页会被清理；移出最后一个应用时，空文件夹会从原位置移除。上游曾观察到 iOS 自动删除空文件夹后使后续图标移位，因此编辑模型先做清理，避免把预期的系统整理误报成大量丢失或移动。页面增减和文件夹清理包含在同一个撤销操作中。

无法分组时，界面会说明原因：iOS 不支持文件夹嵌套；已经位于文件夹中的应用需先移出才能参与顶层分组；不能理解的元素不允许直接移动，写入保护也会拒绝其间接位移。

## 诊断与原样写回校验

只读诊断会读取布局并创建本地备份，不会写入手机：

```sh
# macOS
./run_probe_macos.command
```

```bat
REM Windows
run_probe.bat
```

设备与布局能力检查通过时，`--roundtrip` 才会在明确确认后把读到的布局原样写回，再次读取并核对。它是真实写入，也可能触发 App 资源库回填：

```sh
./run_probe_macos.command --roundtrip
```

```bat
run_probe.bat --roundtrip
```

| 结果 | 含义 |
|---|---|
| 通过 | 此次读回未发现原有项目丢失、意外移动或内容变更；不能据此保证所有后续编辑或其它系统版本安全。 |
| 失败 | 读回与预期存在差异，停止普通编辑写入；检查结果；设备、现状和备份都通过能力检查时，可单独确认恢复同设备的完整备份。 |

界面的校验标记属于当前应用会话，命令行校验不会自动赋予界面写入许可。重新读取或操作失败会撤销界面的编辑写入许可。

系统额外追加的应用单独列出。上游曾观察到原本只位于 App 资源库的应用重新出现在末页；这些应用可以在手机上手动“从主屏幕移除”，但不能靠再次写入旧备份消除这种系统行为。

### 上游历史真机记录

2026-08-19，iPhone 14 / iOS 26.1 原样写回通过：309 项的顺序、文件夹内容和 `iconModDate` 得以保留，丢失 0 项、移动 0 项，另有 4 个 App 资源库应用被系统追加。记录中的写入耗时约 820 毫秒，读回约 100 毫秒。

| 参数 | 说明 |
|---|---|
| `--roundtrip` | 原样写回校验，真实写入，执行前确认。 |
| `--icons` | 同时获取应用图标；图形界面也提供“获取图标”。 |
| `--icon-limit <数量>` | 诊断获取图标的数量上限，默认 30。 |
| `--udid <标识>` | 指定一台 USB 设备；没有明确指定且连接多台 USB 设备时拒绝任意选择。 |

## 数据、日志与恢复

`src/ipsm/paths.py` 统一决定数据位置，将需要保留的备份、日志、设置，与可以重新获取的图标缓存分开。

| 平台及运行方式 | 备份、日志和设置 | 图标缓存 |
|---|---|---|
| macOS，源码或 `.app` | `~/Library/Application Support/HomeSpread/` | `~/Library/Caches/HomeSpread/` |
| Windows，源码 | 项目目录 | `%TEMP%\HomeSpread-cache\` |
| Windows，普通分发文件夹 | exe 所在目录 | `%TEMP%\HomeSpread-cache\` |
| Windows，MSIX / Microsoft Store | 系统返回的文档文件夹中的 `HomeSpread\` | `%TEMP%\HomeSpread-cache\` |

如果通过 `HOMESPREAD_DATA_DIR` 或 `HOMESPREAD_CACHE_DIR` 明确指定目录，以配置为准。Windows 文档目录通过系统接口查询，以支持用户移动文档目录的情况。实际采用的路径会写入会话日志。

每次运行创建唯一会话，仅自动清理最近 20 次以外、符合应用命名规则的日志与诊断文件，不删除备份。当前命名包含微秒和随机标记，避免同秒运行互相覆盖。以下是结构示意，不是实际设备数据：

```text
logs/probe_<时间与随机标记>.log             会话日志
logs/probe_<时间与随机标记>/                有诊断产物时才创建
    icon_state_before.plist                 原始布局
    icon_state_before_readable.json         可读布局
    icon_metrics.json                       网格尺寸
    device_info.json                        诊断用设备信息
    unknown_items.json                      未识别元素原文
logs/probe_<时间与随机标记>_report.zip       本地诊断压缩包
backups/<设备指纹>/<时间与随机标记>_probe.plist
backups/<设备指纹>/<时间与随机标记>_probe.json
backups/<设备指纹>/<时间与随机标记>_probe.meta.json
pairing/                                   敏感配对凭据，不用于报告或分发
```

日志会遮盖常见格式 UDID 的完整值，只保留前四字符。设备名称、应用清单、文件夹名和布局仍可能出现在诊断文件中，所以报告不是匿名数据。程序不主动读取电话簿、照片、聊天消息或应用内容；保存的布局、诊断和配对信息仍应当作为个人数据保护。

恢复受同一写入能力检查约束，Duo 或现状/备份包含小组件时拒绝。通过检查后使用 `backup.py` 的 `restore()`，并先保存恢复前的状态。恢复时保留 `.plist`、`.json`、`.meta.json` 三份文件及原设备目录。缺少归属与完整性记录的旧版备份可以预览，不能直接恢复到手机。

`_report.zip` 汇总本地诊断信息，便于定位失败阶段和原因；分享前检查内容，不会自动上传。完整说明见 [隐私说明](PRIVACY.md)，也可在程序的“关于 → 隐私政策”中离线阅读。

## 项目结构

| 文件或目录 | 职责 |
|---|---|
| `src/ipsm/logging_setup.py` | 会话日志、诊断产物和保留规则。 |
| `src/ipsm/device.py` | 唯一直接使用 pymobiledevice3 的设备桥，负责 USB 连接和错误翻译。 |
| `src/ipsm/iconstate.py` | 原始布局解析与写后比较。 |
| `src/ipsm/placement.py`、`write_policy.py` | 只读跨格排布和所有写入路径的能力限制。 |
| `src/ipsm/layout.py` | 编辑文档、移动规则、分组、撤销及修改列表。 |
| `src/ipsm/backup.py`、`safeio.py` | 按设备备份、完整性核验、私有文件写入和统一写入保护。 |
| `src/ipsm/icons.py` | 图标缓存。 |
| `src/ipsm/apple_devices.py` | Windows 本地端口或 macOS Unix socket 的连接服务检查。 |
| `src/ipsm/i18n.py`、`translations_*.py` | 中文、英语、韩语界面；原有韩文字符串作为翻译键，内部日志保留诊断语言。 |
| `src/ipsm/ui/` | 窗口、画布、文件夹、启动引导和设备工作线程。 |
| `src/ipsm/app.py`、`probe.py` | 图形界面与诊断命令行入口。 |
| `src/ipsm/product.py`、`version.py` | 产品名、上游来源、赞助地址与版本。 |
| `src/ipsm/paths.py` | 持久数据、缓存及只读打包资源的路径。 |
| `tests/` | 不需要真实手机的模型、平台、界面和安全测试。 |
| `install_macos.command`、`requirements-macos.lock` | macOS 安装与锁定依赖。 |
| `build_macos.command`、`HomeSpread-macos.spec` | macOS `.app` 打包。 |
| `install.bat`、`install.ps1`、`requirements.txt` | 上游 Windows 依赖安装入口及记录。 |
| `run_app.bat`、`run_probe.bat` | Windows 图形界面与诊断启动入口。 |
| `build_exe.bat`、`HomeSpread.spec` | Windows 分发文件夹打包。 |
| `scripts/gen_notices.py` | 从 Windows 构建环境生成第三方许可清单。 |
| `scripts/prepare_macos.py` | 从 macOS 锁定环境生成许可材料和对应源码包。 |
| `_workspace/` | 需求、设计、契约、验证及上游发布历史。 |
| `.claude/` | 代理职责、技能流程和参考资料。 |

## 名称与赞助

上游将产品名 `HomeSpread` 和兼容性副标题 `Mobile layout manager for iOS` 分开，并统一定义在 `product.py`。开发记录说明，这一命名方式是为了区分产品名称与 Apple 平台兼容性描述；原名 `HomeBoard` 在上游提交商店时已被占用，因此于 2026-08-26 更名。历史商标和商店政策判断不能代替后续发行时的规则核查。

“设置”中的赞助按钮由用户主动点击后才打开 GitHub Sponsors，单纯打开设置不会访问赞助页面。收款账号仍为上游作者 `humanlyj`，由 `DONATE_ACCOUNT` 定义，`.github/FUNDING.yml` 指向同一账号。本 fork 保留上游署名和赞助归属。

上游 2026-08-28 的记录称，韩国账户无法使用当时的 PayPal 捐赠路径，因此改用 GitHub Sponsors。其记录中的 Sponsors 付款流程由 GitHub/Stripe 处理，需要 GitHub 账户；应用不接收银行卡信息，也不通过赞助解锁功能。

上游选择自愿无回报赞助，是依据当时 Microsoft Store 政策 10.8.2 和开发者协议作出的发布决定。其提交说明要求披露外部支付服务，并区分捐赠与有功能回报的购买。若重新提交商店，需针对实际发行版本和当时规则重新核查；本分支没有安排新的商店提交。

## 许可与第三方组件

HomeSpread 按 **GPL-3.0-or-later** 发布，法律原文见 [LICENSE](LICENSE)，中文阅读说明见 [LICENSE.zh-CN.md](LICENSE.zh-CN.md)。上游在选用 GPL 的 pymobiledevice3 后采用该许可，并公开了设备读写实现。使用、研究、修改和再分发的权利及条件以许可原文为准；软件不提供担保。

仓库的 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) 和 `third_party_licenses/` 保存上游 Windows 构建环境的依赖及许可快照，版本不能冒充本机 macOS 依赖。Windows 构建环境重新生成清单的入口为：

```powershell
.\.venv\Scripts\python.exe scripts\gen_notices.py
```

macOS 使用 `requirements-macos.lock` 和 `scripts/prepare_macos.py` 生成自己的依赖清单、许可原文及 `HomeSpread-source.zip`，随 `.app` 提供。许可证原文保留原语言，不用中文说明替换它们。

上游源码位于 [humanlyj/HomeSpread](https://github.com/humanlyj/HomeSpread)，本修改版位于 [zherendong/HomeSpread](https://github.com/zherendong/HomeSpread)。程序“关于”同时提供上游链接与包内对应修改源码；分发修改版时应一并提供相应源码和许可材料。

## 发布记录

上游 MSIX 安装、商店审核及公开状态见[商店提交清单](_workspace/05_store-submission-checklist.md)。早期 README 中“MSIX 的本地端口和备份写入尚未验证”的结论，已被上游 2026-08-26 的验证记录更新；2026-09-01 的商店上架结果属于 Windows 版历史。本分支的 macOS 本地签名不等于 Apple Developer ID 签名或公证。
