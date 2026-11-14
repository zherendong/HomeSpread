# 接口契约：只读证据与草稿预检

实现：`ipsm.evidence`、`ipsm.evidence_collect`、设备层的 `ReadOnlyEvidenceAdapter`、`ipsm.preflight` 和 `ui/preflight_dialog.py`。本契约不改变现有设备写入能力，所有结果的 `can_write` 恒为 `False`。

## 证据包

`EvidenceBundle.from_backup(raw, source_file_sha256=None)` 只导入已有布局，不补造设备身份、安装清单、第二次读取或新鲜度。`source=imported_backup`，仅 `layout_v2_before` 为已观测，其余为缺失。

`collect_evidence(adapter, source='synthetic', timeout=10, include_layout_v3=True)` 仅调用适配器 `read(part)` 与 `close()`。顺序为：

```text
identity_before → layout_v2_before → metrics → apps_user → apps_system
→ layout_v2_after → identity_after → layout_v3（可选）
```

第一项失败、超时或响应不合格后停止，不重试；后续查询保留未采集状态。关闭失败单独记录，不能把已有观测误报成完整采集。每项查询最多 60 秒，关闭最多 5 秒。已收集数据受总大小上限约束。

每项收据恰含 `status/data/started_at/finished_at/error_code/options`。状态为 `observed`、`failed`、`missing`、`not_collected`。只有 observed 可以包含数据；成功返回空字典不等于失败，而查询完成也不等于资源库全覆盖。

机型身份仅含设备标识摘要、机型、iOS、构建号及 USB 传输标记，不保存设备名称、完整 UDID 或信任凭据。User/System 查询均明确请求占位应用及白名单属性。布局原文保留；几何、隐藏页、组件配置和隐藏网页快捷方式始终记录为 unknown，不能伪造为已验证。

文件为 `.hsevidence` 二进制 plist，根格式为 `ipsm.readonly-evidence`、版本 1、`can_write=False`、record 与类型敏感的 record SHA-256。加载校验模式、状态、时间、查询选项及内容；摘要不是来源签名或身份认证。文件上限 64 MiB，原子写入、私有权限、读回核对；不能覆盖其它格式文件。

## 真实只读适配器的边界

应用界面不调用真实采集器。源码 CLI 只有同时提供明确的 USB 模式及范围确认后，才延迟导入适配器；默认、本地导入和帮助均不访问设备。工具的初始实现验收仅使用假对象；真实采集须独立取得范围授权，个人结果仅保留本地。

- 只查询本地 usbmux 端点，不接受环境变量重定向到远端。
- 仅接受一台已经信任的 USB 设备，`autopair=False`，不新建配对。
- 前后身份通过逐字段请求重新读取，不使用连接时缓存充当第二次观测。
- 应用清单使用 Lookup 的 User/System、ShowPlaceholders 和属性白名单，不复用界面中经过过滤的未放置 App 清单。
- 没有布局写入、图标/壁纸获取、安装卸载或任意命令入口。
- SDK 连接初始化仍读取系统元数据；只保存上述白名单。照片、联系人、聊天和应用内容不属于此采集范围。

## 预检 API

```python
build_preflight_report(draft, evidence=None, *, now=None, max_age_seconds=300) -> dict
render_preflight_report(report) -> str
save_preflight_report(path, report, *, replace=False) -> Path
```

先独立重放草稿操作，并对照实际当前草稿，不能通过重新生成一个正确版本掩盖当前状态损坏。证据即使在内存中也再次经过记录模式校验。

检查项包括：本地草稿完整性、改动、证据来源、采集是否完成、基线一致、前后布局稳定、设备/系统身份、时效、User/System 查询、重复标识冲突、桌面 App 清单覆盖、占位请求范围、网格、格式 3 参考、无法观测的状态、生产写入策略和协议编码。

时效是最多 300 秒的工程检查，不是当前设备状态证明；发送前仍需要重新读取。超过 5 秒的未来时间、时间次序错误和过期记录都不通过。导入备份不会刷新设备观测时间，模拟来源也不能冒充当前手机。

普通 App 的显示标识符和包标识符均可参与清单核对；组件扩展不充当桌面 App。User/System 空查询可以是已完成查询，但若缺少基线中明确存在的 App，覆盖检查仍失败。隐藏内容完整性不能由此推导。

报告格式为 `ipsm.preflight-report`、版本 1、`status=blocked`、`can_write=False`，含 checks、blockers、明确的草稿差异、摘要、来源和可得的设备型号/系统信息。任何局部核对通过都不能变为写入许可。保存使用 `.hspreflight` UTF-8 JSON，上限 16 MiB，私有权限并读回检查；拒绝覆盖不同格式文件和符号链接。

## 界面与模拟器隔离

活动离线草稿提供“草稿预检报告”。弹窗只使用分离的草稿快照和用户导入的本地证据文件；导出前刷新时间检查。应用名称以纯文本展示，不能触发 HTML 或外部资源加载。界面没有 USB 采集按钮，也不调用工作线程。

`research.duo_simulator` 仅构造封闭的内存假传输，不能接收真实适配器或发送回调。24 个内置场景覆盖阻塞、不确定、内容不一致和仅导出字段匹配。一次尝试最多一个模拟发送，没有自动重试或恢复；读回次数有上限，使用新的虚构连接标识。模拟匹配仍不是完整设备验证。

`.hsevidence`、`.hspreflight`、evidence/、preflight_reports/ 均是私人运行资料，不提交源码、不进入分发源码包；它们也不能作为恢复备份使用。

## 已保存证据的研究分析

`scripts/analyze_duo_evidence.py` 使用同一证据加载器，要求采集已完成、来源为 USB 只读且前后身份/格式 2 布局精确一致；否则拒绝生成报告。它不会连接设备补充缺失项。`research.duo_evidence_analysis.analyze_observations` 只接收内存数据，输出固定字段的聚合统计和明确的未知项，无原始标识或请求载荷；`can_write=False`、`device_requests=0`、`payload_generated=False`。

格式 3 压缩投影须逐值、逐类型匹配整个观察值才成立；不能据此推断真实空隙。安装清单保留“未返回标签”“明确返回空标签”“含 hidden 标签”的区别。研究报告不授权写入，也不会回填预检中的 geometry、hidden_pages、widget_settings、hidden_webclips 或 wire_protocol。详细算法、输出与后续证据见[研究说明](../../research/DUO_EVIDENCE_ANALYSIS.zh-CN.md)。
