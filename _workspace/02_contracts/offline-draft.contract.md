# 接口契约：离线草稿

实现：`src/ipsm/draft_rules.py`（纯数据规则）、`src/ipsm/drafts.py`（草稿历史与本地文件）。设备写入策略不变；本模块没有设备桥、工作线程、SDK 或 GUI 依赖。

## 与设备布局分离

`draft_rules.py` 从已验证的研究规划器提升，成为单一规则来源。`research/duo_planner.py` 只重新导出兼容接口，研究测试和离线界面复用同一份纯数据规则。该规则仍将 `device_write_supported` 标记为假，不能作为手机发送许可。

只允许同一逻辑主屏幕页内两个可区分的普通 1×1 App 交换。Dock、文件夹、小组件、堆叠、分页与所有其它原始字段均不变。未知结构、未知尺寸、空位和模型容量超限会拒绝建立可编辑草稿。所有手机写入仍须遵守原来的能力拒绝，草稿不能改变该判断。

## 内存 API

```python
OfflineDraft(origin)
    .origin / .current_state / .current     # 每次返回独立的 plist 快照
    .swap(page, index_a, index_b)           # page 从 1 开始，条目索引从 0 开始
    .undo() / .redo() -> bool
    .can_undo / .can_redo -> bool
    .operations -> tuple[Swap, ...]         # 当前已应用的交换历史
    .diff() -> tuple[DraftChange, ...]      # 最终状态相对基线的差异
    .dirty / .has_changes -> bool
    .path -> Path | None
    .device_write_allowed -> False
    .save(path, replace=False) -> Path
    .load(path) -> OfflineDraft             # 类方法
```

`Swap` 与 `DraftChange` 是不可变的数据类。`Swap` 字段为 `page`、`index_a`、`index_b`。`DraftChange` 字段为 `page`、`index`、`before_label`、`after_label`；索引表示原始数组条目，不把含小组件的条目索引冒充实际网格坐标。

基线和历史状态以二进制 plist 字节保存；界面拿到的列表不能修改内部快照。新交换完整验证后才提交；失败不会改变当前状态或删除重做历史。成功的新分支会替换未执行的重做尾部。

`has_changes` 比较当前状态与最初基线。`dirty` 比较当前状态与最近一次成功保存的状态，新草稿的保存基准是原始布局。两次互逆交换可能仍有撤销历史，但最终内容没有改变，因此不标为未保存。保存记录当前已应用历史，不保存已撤销的重做尾部；内存中的重做尾部不因保存而删除。加载后可以撤销已保存交换。

## 专用文件格式

草稿使用 `.hsdraft` 扩展名、二进制 plist 根字典。根字段必须恰好为：

```text
format = "ipsm.offline-draft"
schema_version = 1
purpose = "offline-only"
device_write_allowed = false
origin                     原始布局 list
current                    当前草稿 list
origin_sha256              规范化二进制 plist 的基线摘要
current_sha256             规范化二进制 plist 的当前摘要
operations                 page / index_a / index_b 三整数的交换序列
```

这些摘要用于发现损坏，不是签名或设备身份验证。草稿不保存原文件的绝对路径，不伪装为设备归属备份，也不声称包含当前手机全部状态。文件中包含应用与布局信息，应作为本地个人数据保存。

加载必须验证魔数、格式版本、用途及字面布尔值 `False`，从基线重新执行每一步受限交换，并与保存的当前状态进行类型敏感的完整比较。只改哈希不能绕过操作范围；`True` 与 `1` 不能被当成相同值。草稿根字典不能通过只接受布局 list 的备份/恢复读取器，即使重命名为 `.plist` 也不能变为恢复备份。

文件读取限制 32 MiB，最多 1000 步操作，保留的历史快照总量限制 128 MiB，以避免小文件内的大量操作导致无界内存放大。超限时拒绝操作，不截断历史来伪造成功。

## 本地保存约束

- 父目录必须已存在。界面可创建应用专用的私有草稿目录；模型不会修改任意父目录的权限。
- 文件以 0600 权限写入同目录临时文件，落盘后原子发布，并读回核对全部字节。
- 默认拒绝覆盖。界面已取得用户对目标草稿的覆盖确认时，才可传入 `replace=True`。
- 即使允许覆盖，也拒绝 `.plist` 后缀、符号链接和不是有效草稿的现有目标；把原始布局改名成 `.hsdraft` 不能使其被覆盖。
- 保存或读回失败不更新 `dirty` 的保存基准，也不更新成功路径。源布局备份不作为保存目标。

文件或规则错误统一使用 `DraftError`，携带 `.code` 与可显示的信息。调用方不能把加载失败当作空草稿，不能在错误后接通设备或回退到实时编辑。
