# 中文文档索引

本仓库的说明、操作步骤、设计资料、接口契约、开发流程和代理职责统一使用简体中文。文件名、API、命令、配置标识和许可证名称保留原值，便于与代码核对。许可证法律原文及上游历史截图保留原样，中文说明会明确其用途和验证范围。

## 使用、隐私与来源

| 文档 | 内容 |
|---|---|
| [项目首页](README.md) | 项目状态、工作原理、编辑操作、诊断、Windows 说明和历史结果。 |
| [macOS 使用指南](README.zh-CN.md) | Mac 安装、构建、快捷键、数据目录和实际验证边界。 |
| [完整隐私说明](PRIVACY.md) | 读取的数据、保存位置、网络边界、删除和分享规则。 |
| [macOS 隐私说明](PRIVACY.zh-CN.md) | macOS 用户的简明本地数据说明。 |
| [安全审计](SECURITY_AUDIT.zh-CN.md) | 发现、修复、测试证据和残余风险。 |
| [来源核查](PROVENANCE.zh-CN.md) | 上游历史、同类项目比对、证据与局限。 |
| [许可证中文阅读说明](LICENSE.zh-CN.md) | 项目许可、第三方许可和保留法律原文的原因。 |
| [第三方组件清单](THIRD-PARTY-NOTICES.md) | 上游 Windows 依赖快照与许可文件索引。 |
| [开发规范](CLAUDE.md) | 当前实现原则、项目约定与有日期的上游开发历史。 |

## 需求、设计和验收

| 文档 | 内容 |
|---|---|
| [协议可行性](_workspace/01_ios-protocol-specialist_feasibility.md) | 读取与写入路径、前提、历史观测和未验证范围。 |
| [产品需求](_workspace/01_product-strategist_requirements.md) | 需求编号、范围、优先级和验收标准。 |
| [技术栈决策](_workspace/02_desktop-app-architect_adr-001-stack.md) | Python、Qt、工作线程及依赖边界。 |
| [布局与同步实现](_workspace/02_layout-sync-engineer_implementation.md) | 原始布局保留、备份和同步实现说明。 |
| [界面规格](_workspace/02_ui-engineer_screen-spec.md) | 页面、文件夹、拖放、状态和确认交互。 |
| [macOS 独立验收](_workspace/04_macos-qa_final-report.md) | 自动测试、平台检查和未进行的真机写入验证。 |

## 接口契约

| 文档 | 内容 |
|---|---|
| [设备桥](_workspace/02_contracts/device-bridge.contract.md) | USB 选择、连接、设备信息、布局与图标接口。 |
| [布局模型](_workspace/02_contracts/layout-model.contract.md) | 条目标识、网格、容器、移动、分组与撤销。 |
| [同步与备份](_workspace/02_contracts/sync-engine.contract.md) | 写入保护、设备归属、完整性和恢复。 |
| [界面与工作线程](_workspace/02_contracts/ui-viewmodel.contract.md) | 异步结果、应用前确认、校验许可和恢复入口。 |

## 上游 Windows 发布记录

| 文档 | 内容 |
|---|---|
| [商店提交清单](_workspace/05_store-submission-checklist.md) | MSIX、Microsoft Store 审核与上架的历史证据。 |
| [商店介绍材料](_workspace/06_store-listing.md) | 商店文案、截图说明、分类和提交字段的中文阅读版。 |

这些记录不表示本 fork 已重新提交 Microsoft Store，也不代表 macOS 版已获得 Apple 公证。`_workspace/screenshots/` 的 `ko`、`en` 文件是上游历史画面，不能当作本次中文版界面截图。

## 开发技能与参考资料

| 技能 | 参考资料 |
|---|---|
| [项目协作流程](.claude/skills/iphone-homescreen-orchestrator/SKILL.md) | 任务阶段、职责协调、验证与交付。 |
| [设备协议](.claude/skills/ios-device-protocol/SKILL.md) | [采集与结构化](.claude/skills/ios-device-protocol/references/capture-and-structure.md)、[连接排障](.claude/skills/ios-device-protocol/references/connection-troubleshooting.md)、[工具选择](.claude/skills/ios-device-protocol/references/tooling.md)。 |
| [主屏幕布局模型](.claude/skills/homescreen-layout-model/SKILL.md) | [提取流程](.claude/skills/homescreen-layout-model/references/extraction-pipeline.md)、[网格约束](.claude/skills/homescreen-layout-model/references/grid-constraints.md)。 |
| [主屏幕画布](.claude/skills/homescreen-canvas-ui/SKILL.md) | 页面、拖放、缩放、文件夹与状态展示。 |
| [接口契约](.claude/skills/interface-contract/SKILL.md) | 数据、错误、事件和职责边界。 |
| [布局差异规划](.claude/skills/layout-diff-planner/SKILL.md) | [重排与手势](.claude/skills/layout-diff-planner/references/reflow-and-gestures.md)，属于有条件启用的历史替代方案。 |
| [原生集成验收](.claude/skills/native-integration-qa/SKILL.md) | [验收清单](.claude/skills/native-integration-qa/references/checklists.md)。 |
| [技术栈决策记录](.claude/skills/stack-decision-adr/SKILL.md) | 方案比较、约束和决策记录方法。 |

## 代理职责

[产品策略](.claude/agents/product-strategist.md)、[设备协议](.claude/agents/ios-protocol-specialist.md)、[布局模型](.claude/agents/homescreen-model-analyst.md)、[桌面架构](.claude/agents/desktop-app-architect.md)、[布局同步](.claude/agents/layout-sync-engineer.md)、[界面工程](.claude/agents/ui-engineer.md)、[验收检查](.claude/agents/qa-inspector.md)。

## 文档维护规则

先区分“当前实现”“有日期的历史结果”“满足条件才考虑的扩展”和“尚未验证的研究”，再修改正文与范例。涉及相同接口、路径或安全行为时，同步核对使用指南、契约、技能和验收说明。翻译不改 API 名、路径或命令语义；更新文档生成模板，防止重新构建后恢复成旧语言。

发布时保留原作者与上游来源，不提交个人设备数据。随应用提供的隐私说明、许可清单和源码包必须与该构建对应。仓库中的相对链接以各文档所在目录为起点；技能中的产物路径按仓库根目录解释，未生成的预期产物需明确标为预期，不冒充现有文件。
