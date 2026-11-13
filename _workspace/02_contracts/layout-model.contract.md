# 接口契约：layout-model

**负责人角色：**`homescreen-model-analyst`。

**实现：**`src/ipsm/iconstate.py`（解析）、`src/ipsm/layout.py`（编辑文档）。

**证据范围：**上游曾使用实机 309 个条目验证模型；2026-11-13 移植版增加独立写入保护。本机真实写入未验证。

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
| `APP` | 非文件夹，含显示/包标识符；旧格式字符串也视为应用 | 可以 |
| `FOLDER` | `listType == "folder"` 或含 `iconLists` | 可以，但不能嵌套进入另一文件夹 |
| `EMPTY` | 原始值为 `None` | 不可以 |
| `UNKNOWN` | 其余未知结构，如尚未理解的小组件 | 不可以 |

网页快捷方式由 `is_web_clip` 标记识别，属于应用条目，不是独立的 `WEB_CLIP` 枚举成员；旧文中的枚举描述已按代码修正。它可以移动，但设备未必提供图标 PNG。

未知项保留原始值和位置。模型禁止直接移动；写入入口还会拒绝因其它条目的插入、删除或页面变化而造成的未知项/空占位间接位移。保留返回数据不代表系统未返回的状态已经受到保护。

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

## 编辑文档 `LayoutDocument`

以下是使用概要：

```python
LayoutDocument(origin: list, grid: Grid)
    .origin                                  # 不可修改的读入基准
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

- **`can_move` 是移动规则的统一判定者。**界面传入实际目标位置，不自行复制模型规则；写入层的设备和数据完整性检查是另一道保护。
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
- 当前移植版的模拟回归结果见 [macOS 独立验收记录](../04_macos-qa_final-report.md)；未知 iOS 功能、当前手机实际编辑应用和恢复仍未验证。
