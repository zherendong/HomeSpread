# Duo 编辑与写回：公开协议证据

核查日期：2026-11-13。研究对象是 HomeSpread 的 Duo 编辑与写回路径，不是本次开放写入的实施许可。本轮只阅读本地源码与公开资料；没有连接手机、查询设备、写入布局或运行原样写回。

## 研究结论

有第三方在 **iPhone Duo / iOS 27.2 / USB** 上完成读取及两次写入后读回的报告，说明这条协议路径值得继续研究，不能据此认定 HomeSpread 在 iOS 27.3 上已经安全可写。主要缺口不仅是小组件占位，还包括写入载荷、未显示应用清单、小组件配置标识、自由空位与隐藏页面，以及写入后的完整性判断。

**保留原始小组件字典是必要条件，但未必足以保留设备上的配置和位置。** 公开项目报告了原样写入后组件选择/设置重置，以及未修改页面上的空隙消失；部分项目的读回比较有意忽略这些差异。因此“序列化无损”“API 返回”“第三方读回通过”必须分别记录，不能当作等价证据。

## 固定版本的证据表

下列“实机报告”均指来源作者自述，本研究没有复现；源码行为则按固定提交核对。

| 问题 | 公开证据及明确范围 | 对 HomeSpread 的意义 |
|---|---|---|
| Duo 是否有写入成功先例 | [ios-homescreen PR #3](https://github.com/YakupEmreYerli/ios-homescreen/pull/3)，2026-10-31 创建，研究时 API 返回已合并；PR head `6d973c634d349eabac658d3e1d03118cdc1a4bbb`。作者说明使用 Rejig 0.1.0、引擎 `97649547dbc4`，在 Duo/iOS 27.2/USB 上读取并完成两次写入后读回。PR 本身只新增型号名称，不是 Duo 写入实现。 | 这是直接 Duo 设备线索，但没有每次修改内容、组件设置、折叠姿态、隐藏页或空位的完整验收矩阵。不能替代本机 iOS 27.3 验证。 |
| 读取和写入是否应使用同一根结构 | [unjiggle PR #4](https://github.com/chungty/unjiggle/pull/4)，head `8780b35be3f75272490ee1ba33bc1ccc01a1c9a8`，2026-07-14，研究时仍未合并。作者报告 iOS 27.0 读回为 list，写回 dict `{buttonBar, iconLists, ignored}` 后可保留 App 资源库中的应用；未注明 Duo。后续 [ios-homescreen 实现](https://github.com/YakupEmreYerli/ios-homescreen/blob/97649547dbc44295e451c6bf130a87404481e10c/src/ios_homescreen/state.py#L175-L291) 采用该结构。 | 必须区分“原始读取快照”和“待评估的协议载荷”。不能把 plist 顶层 list 原样发送视为唯一正确路径，也不能将 `ignored=[]` 视为无副作用默认值。 |
| `ignored` 从哪里来 | PR #4 报告 `getIconState` 不返回该清单；只枚举 User 应用仍会使部分 System 应用回填。ios-homescreen 从当前 User + System 安装列表减去桌面应用生成清单。 | 现有布局备份不足以证明未放置应用清单完整。不能从“备份没有某应用”推断它未安装或可以忽略。需要独立的、明确范围的清单证据。 |
| 已卸载但保留图标的应用 | Rejig 固定提交 `a0b6a97d132e151bf8a53e0cb3d016f8caf15ab0` 的 [offloaded-apps.patch](https://github.com/rejig-app/rejig/blob/a0b6a97d132e151bf8a53e0cb3d016f8caf15ab0/patches/offloaded-apps.patch) 为安装查询加入 `ShowPlaceholders=True` 和 `IsDemotedApp`，避免漏掉仅在资源库中的卸载占位应用。 | 完整清单不能等同于普通的 `get_apps(User)`。离线用合成清单测试这一边界，本轮不额外查询手机安装信息。 |
| `ignored` 的剩余分歧 | [ios-homescreen 的 `counts_for_home_screen`](https://github.com/YakupEmreYerli/ios-homescreen/blob/97649547dbc44295e451c6bf130a87404481e10c/src/ios_homescreen/state.py#L234-L291) 包括隐藏 System 服务；[homescreen-mcp](https://github.com/kats1123/homescreen-mcp/blob/1bf46f6304a3b7b04a07a86c63ce86b647b04e2f/homescreen/device.py#L280-L300) 过滤隐藏及永不显示的应用。后者的 [README](https://github.com/kats1123/homescreen-mcp/blob/1bf46f6304a3b7b04a07a86c63ce86b647b04e2f/README.md#L89-L100) 还说明隐藏网页快捷方式不在安装列表、也不由 USB 布局返回。 | 候选实现存在差异，不能未经证据就选择其中一种并宣传“完整保持资源库”。未知/不完整清单应阻止生成可执行写入计划。 |
| 格式版本是否能补齐缺失状态 | [ios-homescreen 读取接口](https://github.com/YakupEmreYerli/ios-homescreen/blob/97649547dbc44295e451c6bf130a87404481e10c/src/ios_homescreen/device.py#L145-L167) 将 formatVersion 2 作为 `[Dock, page1, ...]` 工作视图，formatVersion 3 仅保存参考快照。homescreen-mcp 的限制说明表示 USB 各版本导出均不包含 gaps/隐藏页。 | 不能假设改用 formatVersion 3 就能获得完整页面状态；它可作为后续只读研究候选，但本轮没有请求设备。 |
| 当前 SDK 是否等待写入回复 | HomeSpread 固定 `pymobiledevice3==11.54.0`，Git tag 对应提交 `48f0215836ee1349b75464ddb08ad6aebb1e74f4`。[SpringBoard setter](https://github.com/doronz88/pymobiledevice3/blob/48f0215836ee1349b75464ddb08ad6aebb1e74f4/pymobiledevice3/services/springboard.py#L29-L49) 调用 `send_recv_prefixed`；[底层实现](https://github.com/doronz88/pymobiledevice3/blob/48f0215836ee1349b75464ddb08ad6aebb1e74f4/pymobiledevice3/service_connection.py#L434-L467) 发出后等待长度前缀回复，没有此调用自身的超时。 | 不能把“函数尚未返回”解释成尚未写入，也不能超时后直接重试。后续适配需有发送、回复、独立读回的状态区别。 |
| 无可靠回复如何处理 | [ios-homescreen `write_state`](https://github.com/YakupEmreYerli/ios-homescreen/blob/97649547dbc44295e451c6bf130a87404481e10c/src/ios_homescreen/device.py#L202-L241) 有限时发送、有限时等待回复；无回复返回不确定状态，再用新服务连接读回确认。 | 这是可借鉴的通信设计，不是本轮可调用的写入工具。发送超时或断线后的状态应为“可能已写入，未确认”，不能自动重发。 |
| 组件选择被忽略的问题 | ios-homescreen 的 [README 限制](https://github.com/YakupEmreYerli/ios-homescreen/blob/97649547dbc44295e451c6bf130a87404481e10c/README.md#L415-L435) 报告 iOS 27 写入会丢失组件选择；[比较器](https://github.com/YakupEmreYerli/ios-homescreen/blob/97649547dbc44295e451c6bf130a87404481e10c/src/ios_homescreen/state.py#L311-L346) 明确不比较 `userSelectedElementIdentifier`，源码注释指出 iOS 27.0.1。[测试](https://github.com/YakupEmreYerli/ios-homescreen/blob/97649547dbc44295e451c6bf130a87404481e10c/tests/test_state.py#L253-L266) 断言缺少该字段也算相同。 | 第三方的“读回相同”不代表完整组件配置相同。HomeSpread 不应为了让校验通过就静默忽略该差异；应报告确切变化和无法验证的状态。该重置报告不是 Duo 专属实测。 |
| 组件配置的候选修复 | [Rejig widget-ids.patch](https://github.com/rejig-app/rejig/blob/a0b6a97d132e151bf8a53e0cb3d016f8caf15ab0/patches/widget-ids.patch) 对缺少 `uniqueIdentifier` 的独立组件，将已有 `userSelectedElementIdentifier` 复制为 `uniqueIdentifier`；堆叠保持原状。方法来源 [homescreen-mcp](https://github.com/kats1123/homescreen-mcp/blob/1bf46f6304a3b7b04a07a86c63ce86b647b04e2f/homescreen/device.py#L87-L119)。 | 这属于有依据的候选协议转换，不能偷偷修改原始备份。必须单独记录转换、原值和理由，离线测试别名冲突、缺失 ID、堆叠不能套用独立组件规则。 |
| 上述组件修复验证到了哪里 | [Rejig 测试和限制](https://github.com/rejig-app/rejig/blob/a0b6a97d132e151bf8a53e0cb3d016f8caf15ab0/README.md#L237-L296) 报告 iPhone 16 Pro/iOS 27.0.1 的 Weather 城市设置三次应用后保持；iPhone 15 Pro/iOS 26.7.1 的一个堆叠保留大小、成员和当前顶部。堆叠内部配置仍未检查。其补丁还允许读回缺失组件 ID 时匹配任意 ID。 | 不能将别名匹配或缺失值通配当作配置完整性证明。普通组件和堆叠必须分别验收；Duo/iOS 27.3 仍缺具体证据。 |
| 自由空位和隐藏页 | [Rejig 限制](https://github.com/rejig-app/rejig/blob/a0b6a97d132e151bf8a53e0cb3d016f8caf15ab0/README.md#L278-L296) 报告仅修改 Dock 时，未修改页面上的手机原生空隙仍消失；USB 只给顺序，读回检查看不见这个变化。[homescreen-mcp](https://github.com/kats1123/homescreen-mcp/blob/1bf46f6304a3b7b04a07a86c63ce86b647b04e2f/README.md#L120-L135) 描述写入 `listMetadata.fixedLocations` 与页面 ID，可保留应用自己记录的空位，但 USB 读不到手机原有的 pins/隐藏页。 | 即使只交换两个同页 App，整体写入也可能影响其它页面的未导出状态。界面预览的 first-fit 排布不能成为真实坐标证据；不能声称原始布局备份覆盖了所有桌面状态。 |
| 其它项目的恢复策略 | [ios-homescreen 工作流](https://github.com/YakupEmreYerli/ios-homescreen/blob/97649547dbc44295e451c6bf130a87404481e10c/src/ios_homescreen/workflow.py#L149-L189) 在校验失败后自动再写备份；README 还提供 force 绕过检查。 | 不照搬：这会引入额外真实写入，且被省略的状态仍无法恢复。HomeSpread 保持不自动重试、不自动恢复和不开放当前 Duo 写入的约束。 |

## 对下一阶段方案的具体要求

### 可以在本轮离线完成

- 针对已有原始备份，用独立的纯函数生成极小编辑候选，例如同一逻辑页上的两个普通 1×1 App 互换。
- 固定 Dock、页面数量和顺序、文件夹全部原文、所有组件及堆叠原文。不得把双页视觉展示合成一个 8 列的写入页面。
- 对候选做强约束比较：只有两个指定位置的对象互换；条目多重集、其它所有位置和全部未知字段不变；序列化后再解析保持类型和值；组件几何不因 App 交换改变。
- 单独研究 list → dict 的候选载荷构造，以及 `ignored`、组件 ID 别名、pins 证据缺失时的拒绝行为。没有完整证据时，候选只能标记为草稿，不产生“可发送”状态。
- 对虚构设备响应模拟“无回复”“部分变化”“配置标识丢失”“隐藏内容回填”等故障。测试对象不能导入 SDK、打开 USB/socket 或调用应用写入入口。

### 仍需后续独立证据，不能由离线测试替代

1. **目标设备范围**：Duo/iOS 27.3 的只读格式与实际屏幕关系；不同折叠姿态、布局配置和隐藏页范围是否变化。
2. **读入信息完整性**：`ignored` 的完整来源、卸载占位应用及隐藏网页快捷方式的处理；对无法观测的信息如何明确拒绝或限定范围。
3. **组件配置与身份**：独立组件是否需要 ID 别名转换，堆叠顶部选择和每个成员的参数是否保留；不能使用“缺失字段匹配任何值”的比较证明成功。
4. **几何与页面可见性**：仅靠顺序读回无法证明空位、真实坐标、隐藏页可见性或折叠布局未变。需要能对照设备画面的证据，不可由模拟排布自证。
5. **传输及故障状态**：发送、可能已写入、回复、读回不一致必须分别表达；不因无回复自动重发，也不自动恢复。

真实写入仍要求在上述设计和离线验证结果可评审后，另外取得明确的、针对具体实验与副作用的授权。本轮的公开资料和模拟结果不会修改现有 Duo 写入拒绝策略。
