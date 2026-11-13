# 接口契约：ui-viewmodel

**负责人角色：**`ui-engineer`。

**实现：**`src/ipsm/ui/` 下的 `worker.py`、`tiles.py`、`canvas.py`、`main_window.py`，以及入口 `src/ipsm/app.py`。

**当前基准：**2026-11-13 macOS 中文移植版。上游 2026-08-20 两次编辑应用、丢失 0 的结果属于历史实机证据，本机未执行真实写入。

## 边界规则

| 规则 | 原因 |
|------|------|
| Qt 仅用于界面层及应用入口 | `layout.py`、`iconstate.py`、`device.py`、`backup.py`、`icons.py` 必须可以不依赖 Qt 测试 |
| 编辑规则由 `LayoutDocument` 判断 | 避免界面与模型各自判断后不一致 |
| 设备操作只在工作线程执行 | 保持写入期间界面可响应，降低用户误拔线的可能 |
| 结果通过信号跨线程传递 | 不在两个线程同时操作设备对象 |

ADR-001 选择 PySide6 的重要理由是减少界面与设备层之间的序列化边界。相同进程共享 Python 结构降低未知字段丢失风险，但不能替代复制输入和写入前验证。

## 工作线程 `DeviceWorker(QThread)`

```python
# 成功信号
loaded(state, metrics, DeviceInfo)
installedListed(dict)             # 包标识符 → 名称
iconsUpdated(fetched, requested)
applied(dict)                     # backup、comparison、state
compatibilityChecked(dict)        # backup、comparison、state
restoredFrom(dict)                # backup、comparison、state
backupsListed(list)

# 状态信号
progressed(message, done, total)
busyChanged(bool)
failed(what_went_wrong, what_to_do)
```

- 一次只运行一个设备任务，不建立写入队列；用户不会在忘记操作后遭遇排队中的覆盖。
- `failed` 提供问题描述和下一步两部分。
- `load()` 先展示主屏幕，再取得安装清单，辅助信息不能延迟主要结果。
- 建立连接后绑定设备备份目录；普通加载重置 `write_verified`，不会自动发起写入兼容性测试。
- `apply(state, reason="before-edit", *, expected_state)` 必须接收 `document.origin`。工作线程在调度前复制输入，写入入口重新读取手机并对照。
- `check_compatibility(expected_state)` 会真实写回未编辑布局，备份后重新读取比较。只有明确确认的界面入口才能发起，不能附带在普通读取中。
- 普通编辑的应用要求本次会话 `write_verified` 为真；原样回写测试成功，或明确确认的恢复成功且读回比较安全，均可建立或刷新该标记。加载、异常或不安全的写后比较使其失效。界面和后台同时检查，不能仅禁用按钮。
- `restore_backup(path)` 不受兼容性门禁阻断，但必须验证同设备备份，恢复前再次备份，并在明确确认后执行。失败后的恢复是独立路径，不自动执行。
- `shutdown()` 必须能重复调用；设备操作进行时界面拒绝关闭，避免销毁仍在工作的线程。

## 画布交互

| 约定 | 原因 |
|------|------|
| 每个页面由一个控件绘制全部格子 | 大量图标不需要大量单格控件（REQ-012） |
| 重绘通过 `QTimer.singleShot(0, …)` 延后 | 避免在拖放事件处理期间删除接收事件的控件 |
| 图标中央 62% 为进入文件夹，边缘为插入旁边 | 同一动作表达两种位置，边框反馈其区别 |
| 文件夹在同一窗口下方展开 | 内外目标同时可见，便于拖动 |
| 在 `dragMoveEvent` 拒绝不合法落点 | 松手前通过禁止指针反馈 |
| 页面排序使用 `◀`、`▶` 按钮 | 避免把页面拖动与图标拖动混淆 |
| 应用叠放到另一应用中央 62% 区域时创建文件夹 | 与移入文件夹使用相同的落点语义 |
| 画布仅发送 `grouped(拖动项 uid, 目标项 uid)` | 询问名称前不能先修改文档，取消应保持原状 |
| 唯一选择集是 `MainWindow.selection` | 支持跨页多选；Windows 使用 Ctrl，macOS 使用 Command |
| 重绘时移除已不存在的 uid | 避免分组按钮启用但没有有效目标 |
| 样式的文字色和背景色成对指定 | 防止默认系统颜色造成黑底黑字或白底白字 |

## 确认界面 `ApplyDialog`

普通编辑流程：读取 → 展开 → 明确确认后的原样回写兼容性测试 → 编辑 → 查看变更 → 明确确认 → 备份 → 写入 → 比较结果。

对话框必须说明：

1. 写前自动备份，失败不写入。
2. 操作替换整份主屏幕布局。
3. App 资源库中的应用可能被放回最后一页；可取得安装清单时显示数量和名称。恢复不能消除该副作用；不能把未知数量描述为没有风险。
4. 操作期间保持 USB 连接和手机解锁。

用户勾选“我已了解上述内容”之前，执行按钮禁用。潜在回填应用还应在侧栏持续可见，不能直到最后确认才第一次告知。

恢复复用明确确认流程，兼容性未验证或失败时另行提示。**恢复不要求 `write_verified` 为真**，否则真实测试失败后会使用户无法使用备份；同设备归属、完整性和恢复前备份仍不可省略。

## 普通编辑应用的禁用条件

- `LayoutDocument.verify_identity()` 为假。该检查只证明内存解析保真，不等于 iOS 接受真实写入。
- 本次会话 `write_verified` 为假。原样回写测试或明确恢复后的安全读回均可建立该标记。
- 没有编辑变化。
- 来源是文件预览，而非当前设备读取结果。
- 工作线程忙碌或没有有效设备。

从文件打开的布局只供离线预览，不能作为其它手机的编辑来源。恢复入口只接受当前设备目录内通过归属和内容摘要验证的备份。

应用和恢复结果都检查 `lost`、`moved`、`changed`，单独报告 `added`。条目内容损坏也使 `.safe` 为假，不能只看标识符与位置后报告成功。

## 国际化 `i18n`

`ipsm.i18n` 统一选择语言。已有韩文源键和新增英文源键是代码查找键，不以文档译文替换。`translations_zh.TRANSLATIONS`、`translations_en.TRANSLATIONS` 提供映射；找不到时回退源键，覆盖测试用于发现遗漏。

以下示例保留实际代码中的英文查找键，中文界面显示其译文：

```python
tr("Unexpected item content changes: {n}").format(n=count)
# 中文结果示例：意外的项目内容变化：3
```

| 约定 | 原因 |
|------|------|
| 内部诊断日志可保留原语言；面向用户的界面和 CLI 输出需翻译 | 兼顾诊断检索和用户可理解性；不把内部日志等同于全部用户消息 |
| 参数通过 `.format(...)` 等占位符传入 | 不为每个数量生成不同查找键 |
| 翻译完整句子，不拆成带语法依赖的片段 | 其它语言的词序和语法不同 |
| `LANGUAGES` 中语言名称以各自语言显示，不再翻译 | 用户能从陌生界面找到自己的语言 |
| 静态控件文案在 `MainWindow.retranslate()` 中有对应更新 | Qt 不会自动替换已设置文字 |
| 窗口标题的设备信息保留类型和值，而非固定已译句子 | 切换语言时可重新组合 |
| 画布重建时恢复展开的文件夹 | 避免逐个追踪所有临时图标文案而遗漏 |
| 窗口关闭时调用 `off_language_changed` | 防止回调访问已销毁的 Qt 控件 |

语言保存到数据目录的 `settings.json`。`app.py` 在 `ensure_ready()` 前调用 `i18n.start()`，使启动错误也采用用户语言。当前中文版默认 `zh_CN`；显式参数或已保存选择优先。原“韩文系统用韩文，其余系统用英文”的启动策略属于上游历史实现。

翻译检查包括 `test_every_translatable_string_has_an_english_entry`、`test_translations_keep_the_same_placeholders`、`test_the_window_changes_its_words_when_the_language_changes`，以及 `tests/test_chinese.py` 的中文覆盖、占位符和默认语言检查。

## 启动引导 `GuideBoard`

读取前，引导页占用画布区域，说明已具备的条件和下一步；读取成功后通过 `_show_guide` 把位置交给画布。

| 约定 | 原因 |
|------|------|
| macOS 检查 `/var/run/usbmuxd` 本地 Unix socket | 使用系统 Apple 连接服务；提示 Finder、解锁和信任，不跳转 Windows 商店 |
| Windows 检查 `127.0.0.1:27015` | 这是 Apple 连接组件常用的本机端口；连通只证明服务可达，不证明特定手机已配对 |
| Windows 安装目录只用于选择提示 | 目录命名可能变化，不能作为硬性阻断依据 |
| Windows 端口可达时不再靠目录猜测否定就绪 | 可达性优先于安装位置猜测 |
| Windows 区分已就绪、已安装未运行、未发现组件 | 每种状态对应不同操作 |
| 每 3 秒重查 | 用户完成旁边的准备工作后能看到状态更新 |
| 单次检测超时 0.4 秒 | 防止在界面线程长时间阻塞 |

Windows 商店入口使用 `ms-windows-store://pdp/?PFN=…`，失败时回退到商店搜索；只适用于 Windows。检查包含 `test_the_open_port_decides_readiness_not_the_folder`、`test_the_guide_tells_the_user_what_to_do_next`、`test_the_guide_hands_its_place_to_the_canvas`，macOS 路径另由平台测试覆盖。

## 颜色与可读性

顶层 `QWidget { color: … }` 会影响所有文字，因此局部控件若未设置背景，仍可能出现默认白底白字。上游曾在工具栏、重命名输入框和语言列表出现这类问题。

`QComboBox` 的下拉列表是内部 `QAbstractItemView`，必须为 `QComboBox QAbstractItemView` 单独指定颜色；只看收起的控件不够。

`test_dialog_text_is_readable_on_its_own_background` 和 `test_the_dropdown_list_is_readable_too` 实际渲染并测量亮度差，后一项在列表展开后测量。

## 产品名称和赞助入口

| 规则 | 原因与验证 |
|------|------|
| 从 `product.NAME` 读取产品名 | 修改名称只有一个声明点；`test_the_name_is_declared_once` 检查源字符串 |
| 名称保持 HomeSpread，兼容性副标题使用 `TAGLINE` | 保留上游名称/商标策略；`test_the_store_name_carries_no_apple_trademark` 检查名称，不代表替代最新商标审核 |
| 赞助 URL 由 `product.donate_url()` 生成 | 窗口不重复拼接账户地址 |
| 只有点击才打开浏览器 | 设置窗口本身不联网；`test_the_settings_offers_support_without_going_anywhere_by_itself` 使用替代 `QDesktopServices` 验证 |
| 赞助不解锁功能或移除广告 | 保留上游无回报赞助模式；历史 Store 政策依据见商店清单，后续提交需核对当时政策 |
| 当前提供 GitHub Sponsors 入口 | 旧文中的 `no_recurring=1` 是已移除 PayPal 方案的参数，不能用于描述 GitHub 付款行为；`test_the_donate_link_reaches_the_right_account` 检查当前账户 |

## 诊断

`app.py` 在常规 Qt 窗口初始化前建立 `logs/` 会话，便于排查无法启动的问题。诊断文件仍包含应用清单等本地敏感数据，不能因 UDID 脱敏就当成匿名资料。

## 历史验证与未验证范围

- 上游完成 11 步离屏冒烟检查，以及 6 页、287 个图标和程序坞的实机展示。
- 应用确认框锁定和非法拖放不改文档有 `tests/test_core.py` 记录。
- 上游实际拖动后应用两次，丢失均为 0；第二次发送与读回完全相同。原文将两次都写为完全相同，已按界面规格中的原始表格纠正。
- 专门的 HiDPI 200% 交互、未知 iOS 功能和当前手机真实写入未验证。
- 当前 macOS 模拟测试、打包启动和只读证据见 [macOS 独立验收记录](../04_macos-qa_final-report.md)，不与上游实机写入记录混用。
