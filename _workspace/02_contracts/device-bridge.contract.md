# 계약: device-bridge

## macOS 中文移植版接口补充（2026-11-13）

本节描述当前本地移植版，优先于下方保留的上游历史实现记录。

- `DeviceBridge.device_key: str | None` 为规范化 UDID 的 SHA-256。连接成功后设置，关闭后清空；仅用于本地备份设备隔离，不将原始 UDID 写进报告。
- `connect()` 只使用 USB。未指定设备且发现多部 USB 设备时拒绝连接，不默认选第一部，不静默回退到 Wi-Fi。
- macOS 通过系统 usbmuxd 服务连接；连接失败给出 Finder、解锁和信任提示。库创建的配对缓存存入数据目录下 `pairing/`，目录权限 0700，不进入诊断压缩包或分发制品。
- 应用、诊断和实机验证脚本均不得直接调用 `set_icon_state`；唯一上层写入入口是 `backup.guarded_write`。
- 当前 Mac/iPhone 已完成只读连接和备份验证，未进行实际桌面写入。下方其它型号/系统的实测属于上游历史证据。

## 上游历史约定与验证记录

**소유자:** ios-protocol-specialist
**구현:** `src/ipsm/device.py`
**상태:** 실기기 확인됨 (iPhone 14 / iOS 26.1, 2026-08-19~20)

기기와 이야기하는 유일한 층. 위쪽(모델·엔진·화면)은 pymobiledevice3 를 직접 import 하지
않는다. 라이브러리를 갈아 끼울 때 고칠 곳을 한 파일로 묶어 두기 위해서다.

## 경계 규칙

| 규칙 | 이유 |
|------|------|
| `pymobiledevice3` import 는 이 파일에만 | 라이브러리 교체·버전 차이가 여기서 멎는다 |
| 모든 실패는 `DeviceError(message, action)` 으로 번역해 던진다 | 위층은 라이브러리 예외 종류를 알지 못하고, 사용자에게는 "무엇을 하면 되는가"가 필요하다 |
| 원본 트레이스백에서 UDID 를 지운다 | 로그를 공유해도 기기 식별자가 새지 않게 |
| 전면 async | pymobiledevice3 v10 이 async 전용. 동기 래퍼를 두지 않는다 |

## 제공하는 것

```python
class DeviceInfo:                      # 이름, 모델, iOS, 빌드, 연결 방식, 마스킹된 UDID
    def summary(self) -> str

class DeviceBridge:
    async def list_devices() -> list[dict]                     # 정적 메서드
    async def connect(serial: str | None = None) -> DeviceInfo
    async def get_icon_state(*, artifact_name: str | None = None) -> list[Any]
    async def set_icon_state(state: list[Any]) -> None          # ← 전체 덮어쓰기
    async def get_homescreen_icon_metrics() -> dict[str, Any]
    async def get_icon_png(bundle_id: str) -> bytes | None
    async def get_icon_pngs(ids, *, on_progress=None) -> dict[str, bytes]
    async def list_installed_apps() -> dict[str, str]           # 번들 ID → 표시 이름
    async def get_orientation() -> str | None
    async def close() -> None

def translate(exc: BaseException) -> DeviceError
```

## 지키기로 한 것

- **`set_icon_state` 는 직접 부르지 않는다.** 쓰기는 `backup.guarded_write` 를 통해서만
  나간다. 이 계약을 어기면 백업 없는 쓰기가 생긴다 (sync-engine 계약 참조).
- `get_icon_state` 는 받은 plist 를 **손대지 않은 그대로** 돌려준다. 정규화·정렬·필드
  제거를 하지 않는다 — 우리가 모르는 필드가 사라지는 첫 번째 경로가 여기다.
- `get_icon_pngs` 는 받지 못한 항목을 **조용히 건너뛴다.** 웹 클립은 PNG 를 주지
  않는 것이 정상이며, 이것을 오류로 다루면 아이콘 수집 전체가 멎는다.
- `list_installed_apps` 는 실패해도 빈 dict 를 돌려준다. 부가 정보이므로 없다고
  편집을 막을 이유가 없다.

## 실측 (iPhone 14, iOS 26.1, USB)

| 작업 | 시간 |
|------|------|
| 연결 (lockdown + 페어링 확인) | 약 550 ms |
| `getIconState` (309개 항목) | 약 280 ms |
| `getHomeScreenIconMetrics` | 약 280 ms |
| 아이콘 287개 내려받기 | 7.4 초 (약 26 ms/개) |
| `setIconState` | 1 초 미만 |

## 미검증

- 위젯이 놓인 홈화면, 빈칸이 남은 홈화면의 plist 모양 `[미검증]`
- 네트워크(Wi-Fi) 연결에서의 쓰기 `[미검증]` — 읽기는 확인됨
- 다른 기기·iOS 버전에서의 `setIconState` 수용 여부 `[미검증]`
