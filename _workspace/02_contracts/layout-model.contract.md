# 接口契约：layout-model

**负责人角色：**`homescreen-model-analyst`。

**实现：**`src/ipsm/iconstate.py`（解析）、`src/ipsm/layout.py`（编辑文档）、`src/ipsm/placement.py`（只读跨格预览）。

**证据范围：**上游曾使用实机 309 个条目验证无小组件模型；2026-11-13 的原始布局核查发现小组件被误认成文件夹，本次已增加独立分类、只读预览与禁止编辑规则。本机真实写入未验证。

模型定义应用如何表达一份主屏幕，其它契约建立在这个数据边界上。

## 两层模型

| 层 | 文件 | 职责 |
|----|------|--------------|
| 解析 | `iconstate.py` | 读取 plist 并分类，不编辑原始内容 |
| 编辑 | `layout.py` | 管理页面、位置、移动、撤销；用 `raw` 保存原始结构 |

分层用于保留原始数据。`Node.raw` 保存设备提供的对象，非文件夹的 `to_raw()` 原样返回它；文件夹重建 `iconLists` 时保留其它原始键。只用已理解字段重建条目会丢失未知字段，因此禁止这种做法。

## 条目标识

优先使用 **`displayIdentifier`**，没有该字段时才回退到 `bundleIdentifier`。

2026-08-19 的首份上游实机数据中，79 个条目，约 26%，曾被误判为未知项：已卸载但保留图标的应用没有包标识符，只有 `displayIdentifier`。仅使用 `bundleIdentifier` 会使这些条目无法移动。

`placed_identifiers()` 同时收集两个字段。安装清单按包标识符返回，若只比较其中一个字段，会错误提示“已安装但不在主屏幕”。

## 条目类型 `ItemKind`

| 类型 | 判断 | 能否移动 |
|------|------|-----------------|
| `APP` | 排除小组件、文件夹及未知自定义结构后，含显示/包标识符；旧格式字符串也视为应用 | 只在整份文档可编辑时允许 |
| `FOLDER` | 明确的 `listType == "folder"`，且 `iconLists` 是有效二维数组 | 只在整份文档可编辑时允许，不能嵌套进入另一文件夹 |
| `WIDGET` | 明确的 `elementType: widget`、`widgetIdentifier`，或全为组件条目的 `elements` 堆叠 | 不可以 |
| `EMPTY` | 原始值为 `None` | 不可以 |
| `UNKNOWN` | 其余未知结构，包括仅有 `iconLists` 而没有明确文件夹类型的对象、未理解的自定义图标 | 不可以 |

网页快捷方式由 `is_web_clip` 标记识别，属于应用条目，不是独立的 `WEB_CLIP` 枚举成员；旧文中的枚举描述已按代码修正。它可以移动，但设备未必提供图标 PNG。

小组件也可能包含空的 `iconLists`，因此不能按该字段的存在与否判断文件夹。必须先识别组件，再检查明确的文件夹标记。组件的 `elements`、所选成员、尺寸、建议设置及未知字段全部保留，不能把堆叠成员作为独立 App 或文件夹计算。

只要原始文档包含 `WIDGET`、`UNKNOWN` 或 `EMPTY`，整份文档即为只读：相邻 App 移动、分组、文件夹重命名、增删页、调页和撤销重做均不能改变它。格式不支持或条目超出已报告容量的文档同样只读。`readonly_reason` 根据读入基准产生，调用方不能通过删掉预览节点来解除限制。只读文档的 `to_state()` 返回原始快照的深拷贝，不重新构造设备载荷。保留返回数据不代表系统未返回的状态已经受到保护。

## 容器 `Container` 与网格

```python
@dataclass
class Grid:
    columns: int
    rows: int
    dock_capacity: int
    folder_columns: int
    folder_rows: int
    max_pages: int
    folder_max_pages: int

    @property
    def page_capacity(self) -> int: ...
    @property
    def folder_page_capacity(self) -> int: ...
    @classmethod
    def from_metrics(cls, metrics) -> Grid: ...  # 设备值优先，否则用声明的回退值
```

- `state[0]` 是程序坞，`state[1:]` 是主屏幕页面，不能交换顺序。
- 文件夹通过 `iconLists` 包含自己的页面。`containers()` 遍历程序坞、主屏幕页面和文件夹页面。
- `page_capacity`、`folder_page_capacity` 是属性，不是调用方法；回退值来自上游 iPhone 样本，不能当作当前设备实测。

## 跨格只读预览

`place_items(items, columns, rows)` 接受原始项目、解析 `Item` 或编辑 `Node`，返回不可变的 `PagePlacement`：

- `cells`：`Placement(index, row, column, width, height)` 元组，`index` 始终是输入数组原始索引。
- `occupied_cells`：已知内容占用的格子总数；明确空占位会保留位置，但不计为已占内容。
- `unsupported_indices`、`overflow_indices`：无法定位或放不下的原始索引，界面必须仍展示这些条目，不能丢弃。
- `complete`：仅在没有未定位条目、溢出或非法网格时为真。

已知尺寸为 `small = 2×2`、`medium = 4×2`、`large = 4×4`，按行优先寻找可容纳的空矩形。尺寸未知时不猜为单格，其后的条目也不再推断坐标。4 列、6 行的样例中，中号组件加 8 个普通图标占 16 格，加 16 个普通图标占 24 格。

这是根据尺寸和数组次序生成的离线预览，不是系统截图，也不作为 iOS 写入兼容性证据。Duo 的双页展示必须保留两个逻辑页面，不能把原始数组合并成一个 8 列页面后写回。

## 编辑文档 `LayoutDocument`

以下是使用概要：

```python
LayoutDocument(origin: list, grid: Grid)
    .origin                                  # 不可修改的读入基准
    .readonly_reason                         # str | None；组件/未知/空占位等整页禁改原因
    .can_move(node_uid, dst_uid, dst_index=None) -> str | None
    .move(node_uid, dst_uid, dst_index)
    .can_group(node_uids) -> str | None       # 返回不能分组的原因，或 None
    .group(node_uids, name) -> str            # 新文件夹节点 uid
    .suggest_group_name(node_uids) -> str     # 默认取首项名称
    .can_rename(node_uid, name) -> str | None
    .rename_folder(node_uid, name)
    .add_page() / .remove_page(index) / .reorder_pages(from_index, to_index)
    .undo() / .redo() / .can_undo / .can_redo
    .to_state() -> list                      # 待写入的 plist 结构
    .verify_identity() -> bool               # 从 origin 重新构建后是否原样一致
    .changes() -> list[str]                  # 用户可读的变更清单
    .placed_identifiers() -> set[str]
    .unplaced_apps(installed) -> list[tuple[str, str]]
```

## 编辑不变量

- **`can_move` 是移动规则的统一判定者。**它先检查整份文档的只读限制。界面传入实际目标位置，不自行复制模型规则；写入层的设备和数据完整性检查是另一道保护。
- 拒绝原因是一句可直接展示给用户的话，界面无需重新拼接。
- 变更清单对照原始快照生成，不回放命令历史来推断，避免撤销/重做后的偏差。
- 页面排序变化只报告一行，不把页内每个应用都列成单独移动。
- `verify_identity()` 为假时禁用普通应用。它证明的是内存解析/重建保真，**不是设备实际回写兼容性**；后者由会话测试判断。
- 新文件夹只构造 `displayName`、`listType`、`iconLists` 三个键。这与上游观察到的 26 个文件夹一致，是已采用的模型，不保证所有 iOS 都接受新建结果。
- 重命名先记录到 `Node.renamed_to`，不改原始 `raw`。`to_raw()` 导出时只替换 `displayName`，保留其它字段（REQ-017）。
- 分组按屏幕展示顺序收纳，而非点击选择顺序；新文件夹放在第一个条目原来的位置。
- 一个文件夹页面已满不等于整个文件夹已满。优先找有空间的页面，没有则在 `folder_max_pages` 上限内新增；由模型统一判断。
- 拖到满页内某个明确位置，即 `dst_index < len(items)`，会使后续项顺移，溢出项进入下一页最前面。拖到尾部追加区域不会把未瞄准的条目跨页推出，而是寻找可容纳位置。
- 主屏幕和文件夹共用 `_plan_spill`，由 `_page_family` 提供各自容量及页数上限，避免维护两套规则。
- `can_move` 必须接收目标索引。不提供 `dst_index` 时，无法确认具体插入方案，满页会被拒绝；界面必须传入 `_resolve_target` 计算的位置。
- 同一文件夹内跨页移动不增加总条目数量，不能仅因整个文件夹已满就拒绝。
- 页面变空时清理该页，但同一页面组的最后一页可保留为空；文件夹消失后，其所在主屏幕页若变空，也一起处理。
- 最后一个条目移出文件夹后，由模型删除空文件夹。上游 2026-08-20 实测显示 iOS 会自行删除空文件夹，并使后续项前移，旧比较器因此误报丢失和位移。
- 新增页、删除空页和空文件夹等连带变化，与移动一起放在同一个 `MoveCommand` 中；用户一次撤销即可回到操作前状态（REQ-014）。
- 仅重命名也必须出现在 `changes()` 中，并使 `dirty` 为真，不能因为没有移动就关闭应用入口。

## 上游验证记录与当前边界

- 上游 309 个条目原样回写通过 REQ-003，丢失和意外位移均为 0；设备和系统信息见设备桥契约。
- 当时 `tests/test_core.py` 71 项无设备测试通过，覆盖分组、重命名、页数变化和顺移。
- 当时主屏幕跨页顺移和空主屏幕页清理尚未实机写入验证。后续纯模型测试不将这一状态自动改为已验证。
- `tests/test_widgets.py` 使用虚构的组件与 App 结构覆盖组件/堆叠分类、占位、完整原始数据保留、整份文档禁改、未知尺寸和内容损坏检查，不包含私人设备数据。
- 当前移植版的模拟回归结果见 [macOS 独立验收记录](../04_macos-qa_final-report.md)；未知 iOS 功能、当前手机实际编辑应用和恢复仍未验证。跨格预览不解除写入限制。
