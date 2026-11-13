# 接口契约：device-bridge

**负责人角色：**`ios-protocol-specialist`。

**实现：**`src/ipsm/device.py`。

**当前基准：**2026-11-13 macOS 中文移植版。上游 iPhone 14 / iOS 26.1 于 2026-08-19～20 的实测属于历史证据；本机完成只读连接和备份验证，未进行真实桌面写入。

设备桥是应用与手机通信的唯一层。模型、同步引擎和界面不直接导入 pymobiledevice3，使库版本差异和替换成本集中在这一边界。

## 边界规则

| 规则 | 原因 |
|------|------|
| 应用生产代码中，仅此文件导入 `pymobiledevice3` | 库版本差异停留在设备桥内 |
| 通信失败转换为 `DeviceError(message, action)` | 上层无需理解库异常类型，用户能看到问题和下一步 |
| 日志格式化时隐藏调用栈内的完整 UDID | 防止诊断日志泄露完整设备标识；其它布局信息仍可能敏感 |
| 所有设备操作使用异步接口 | 原 v10 和当前选定版本的调用路径均为异步；不增加同步包装层 |
| 仅允许 USB 连接 | 不在连接失败后静默切换到 Wi-Fi |
| 多台 USB 设备时不默认选第一台 | 未提供明确参数时要求用户断开其它设备 |

## 接口

以下为接口概要，省略实现体：

```python
class DeviceInfo:  # 设备名称、型号、iOS、构建号、连接方式、脱敏 UDID
    def summary(self) -> str: ...

class DeviceBridge:
    device_key: str | None

    @staticmethod
    async def list_devices() -> list[dict]: ...
    async def connect(serial: str | None = None) -> DeviceInfo: ...
    async def get_icon_state(*, artifact_name: str | None = None) -> list[Any]: ...
    async def set_icon_state(state: list[Any]) -> None: ...  # 整份布局替换
    async def get_homescreen_icon_metrics() -> dict[str, Any]: ...
    async def get_icon_png(bundle_id: str) -> bytes | None: ...
    async def get_icon_pngs(ids, on_progress=None) -> dict[str, bytes]: ...
    async def list_installed_apps() -> dict[str, str]: ...  # 包标识符 → 显示名称
    async def get_orientation() -> str | None: ...
    async def close() -> None: ...

def translate(exc: BaseException) -> DeviceError: ...
```

`device_key` 是规范化 UDID 的 SHA-256，连接成功后设置，关闭后清空。它用于本地备份归属和目录隔离，不是原始 UDID，也不是加密身份认证。

macOS 通过系统 usbmuxd 服务连接；失败提示涉及 Finder、解锁与信任。库生成的配对缓存位于数据目录的 `pairing/`，目录权限 0700，不纳入诊断 ZIP 或分发制品。

## 不变量

- **上层不能直接调用 `set_icon_state`。** 应用、诊断和实机验证脚本的写入统一经过 `backup.guarded_write`；恢复也遵守备份保护，见同步引擎契约。
- `get_icon_state` 原样返回收到的 plist，不排序、不归一化、不删除未知字段。
- `get_icon_pngs` 跳过无法取得图标的条目。网页快捷方式不提供 PNG 是正常情况，不能因此终止整个批次。
- `list_installed_apps` 失败时返回空字典，它是辅助信息，不阻断读取和本地编辑。空清单不能证明没有应用会被系统放回桌面，因此通用副作用警告仍保留。
- 上游曾记录 Wi-Fi 读取能力；当前桥层策略为仅 USB，不把库支持的其它传输方式作为应用支持能力。

## 上游历史实测

环境：iPhone 14、iOS 26.1、USB，2026-08-19～20。

| 操作 | 耗时 |
|------|------|
| 连接，包括 lockdown 和配对确认 | 约 550 毫秒 |
| `getIconState`，309 个条目 | 约 280 毫秒 |
| `getHomeScreenIconMetrics` | 约 280 毫秒 |
| 获取 287 个图标 | 7.4 秒，约 26 毫秒/个 |
| `setIconState` | 少于 1 秒 |

这些数字不作为当前 Mac 或其它设备的性能保证。

## 未验证边界

- 小组件和任意内部空位的完整 plist 表示及真实回写行为。
- Wi-Fi 写入：上游未验证，当前应用禁用该路径。
- 其它设备和 iOS 版本对 `setIconState` 的接受程度。
- 当前 Mac 所连接手机的真实写入与恢复。仅凭成功读取或历史记录不能判定安全。
