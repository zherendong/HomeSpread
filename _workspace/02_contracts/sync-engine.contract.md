# 接口契约：sync-engine

**负责人角色：**`layout-sync-engineer`。

**实现：**`src/ipsm/backup.py`、`src/ipsm/safeio.py`、`src/ipsm/iconstate.py`（写后比较）。

**当前基准：**2026-11-13 macOS 中文移植版。上游 2026-08-19 的原样回写通过是历史设备证据；本机只验证读取和本地备份。

这一层将编辑结果提交给设备。主实现直接发送完整布局，不执行设备手势序列；界面的变更清单和本地顺移计算仍然需要。`layout-diff-planner` 只保留为条件性研究方案。

## 单一写入入口

```python
async def guarded_write(
    bridge, store: BackupStore, new_state: list, reason: str,
    *, expected_state: list | None = None,
) -> Backup: ...
```

```text
设备归属 → 容器结构 → 读取当前状态 → 核对 expected_state → 条目完整性
                                                        ↓
       setIconState ← 重新读取并验证备份 ← 持久化布局与归属/完整性记录
                       任一步失败：停止，不写手机
```

普通编辑必须传入读入时的 `document.origin`。手机端已有变化时停止，不合并或覆盖。普通编辑还检查叶项多重集及未知项/空占位位置，拒绝丢失、重复、原始内容改写和未知项位移。

设备桥的 `device_key` 必须有效并与备份存储绑定一致。上层直接调用 `DeviceBridge.set_icon_state` 违反契约；应用、诊断 CLI、实机验证脚本均受此约束。

**备份失败不写入（REQ-010）。**备份完整性、原始数据保留、设备隔离、快照时效和写后比较共同提供保护。备份不是全部安全保证，也不能保证系统副作用完全可逆。

## 备份

```python
class BackupStore:
    def __init__(self, root, device_key: str | None = None): ...
    def bind_device(self, device_key: str) -> None: ...
    def save(self, state, reason="auto") -> Backup: ...
    def list_backups(self) -> list[Backup]: ...
    def latest(self) -> Backup | None: ...
    def load(self, path, *, for_restore: bool = False) -> list: ...
```

- 使用**二进制 plist**。上游 2026-08-19 发现 XML plist 会截掉 `iconModDate` 秒以下精度，导致备份与原始值比较正确地失败。
- 保存后重新读取并对照原始值，**不使用忽略易变时间字段的 `deep_equal` 作为备份保真标准**。失败文件不作为有效备份展示。
- 目录为 `backups/<device_key>/`。设备键是规范化 UDID 的 SHA-256；原始 UDID 不用于报告文件名。
- 文件名使用 `YYYYMMDD_HHMMSS_<微秒>_<随机后缀>_<原因>.plist`，并生成可读 `.json` 与 `.meta.json`。原秒级命名已被替换，避免同一秒覆盖。
- 临时文件完整写入并 `fsync` 后，在同目录发布且拒绝覆盖现有目标。文件权限 0600，目录权限 0700。元数据成功写入后才算完整备份。
- 元数据记录格式版本、设备键、SHA-256 内容摘要、创建时间和原因。摘要用于发现损坏，不是对同一用户权限下恶意进程的数字签名。
- `load(path)` 可预览旧文件；`load(path, for_restore=True)` 必须验证所属目录、当前设备、元数据和内容摘要，拒绝无归属旧文件、跨设备文件及损坏备份。读取同时限制文件大小和基本容器形状。

## 写后比较

```python
def compare_after_write(before: list, after: list) -> WriteComparison: ...

# WriteComparison 字段与属性：
# lost       丢失条目
# moved      意外位移
# changed    同一条目的内容变化
# added      请求中没有、返回结果中新出现的条目
# safe       lost、moved、changed 均为空
# identical  safe 为真且 added 为空
```

旧文中的 `appended` 已按实际字段名修正为 `added`。未知项使用完整内容摘要，不能截短后比较；同 ID 条目也必须检查原始内容。比较可忽略已知易变时间字段，因此 `identical` 是该比较器下的一致性，不能宣传为未经任何归一化的逐字节相同。

上游 2026-08-19 观察到，`setIconState` 可能将仅在 App 资源库中的应用放回最后一页，因此新增项单独报告，不作为丢失或意外移动。**恢复本身也是写入，不能撤销这一资源库回填副作用。**界面提前展示可能回填的应用名称并保留通用提示；安装清单为空不证明没有回填风险。

## 恢复

```python
async def restore(bridge, store, backup_path) -> Backup: ...
```

恢复只接受当前设备的有效备份，先备份手机现状，再发送选定布局。用户可能选择了错误备份，因此恢复前状态同样必须可追溯。

恢复是明确确认的独立恢复入口：**即使本次会话兼容性测试失败，也不因此禁用恢复。**普通编辑的“应用”仍要求本次会话 `write_verified` 为真。原样回写测试成功，或明确恢复成功且读回比较安全，均可建立或刷新此标记；加载或失败使标记失效。恢复不自动执行，不盲目连续重试；用户需了解它是另一轮完整写入及其系统副作用。

## 重新读取前的等待

界面工作线程在写后等待 **1.5 秒**，常量为 `ui/worker.py` 的 `_SETTLE_SECONDS`，再读取结果。目的是让 SpringBoard 完成布局更新，避免将尚未稳定的结果误报为损失。应用、兼容性测试和恢复均进行结果比较；这个等待值不是所有设备都能在该时限内完成的保证。

## 安全边界与明确不做的事

- 不故意向用户实机发送损坏 iconState 来探索失败模式；该项保持“有意未验证”。
- 不实现部分布局写入、自动写入重试或自动恢复。
- **不声称整份替换是事务，或在断线/掉电时必然全成全败。**接口调用粒度不能证明系统原子性。
- 重新读取与写入之间没有系统级 compare-and-swap，仍存在短暂竞争窗口；用户应避免同时在手机或其它工具编辑。
- 上游其它设备的成功、当前只读成功和模拟测试都不能代替本机真实写入兼容性验证。
