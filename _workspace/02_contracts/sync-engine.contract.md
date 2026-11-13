# 계약: sync-engine

## macOS 中文移植版安全约定（2026-11-13）

本节描述当前本地移植版，优先于下方保留的上游历史实现记录。

```python
BackupStore(root, device_key: str | None = None)
BackupStore.bind_device(device_key: str) -> None
BackupStore.load(path, *, for_restore: bool = False) -> list
async guarded_write(bridge, store, new_state, reason, *, expected_state=None) -> Backup
async restore(bridge, store, backup_path) -> Backup
```

写入顺序：设备归属校验 → 容器结构校验 → 读取最新桌面 → 对照 `expected_state` → 编辑条目完整性校验 → 持久化备份及归属/完整性记录 → 再次读取校验备份 → 一次 `setIconState`。普通编辑必须传入读入时的 `document.origin`；手机端发生变化时停止，不合并或覆盖。缺失、复制、改写原始叶项或移动未知项/占位均拒绝写入。

备份目录为 `backups/<device_key>/`。新文件名含微秒和随机后缀，不覆盖同名文件；临时文件完整写入并 `fsync` 后发布，权限 0600，目录权限 0700。`.meta.json` 记录设备键、内容摘要、创建时间和原因，元数据成功写入后才算完整备份。文件摘要检测损坏，不是对同一账户恶意进程的真实性认证。

`load(path)` 可预览旧备份；`load(path, for_restore=True)` 必须验证所属目录、当前设备、元数据和内容摘要。恢复前仍备份当前状态。应用和恢复均等待系统稳定后重新读取，`WriteComparison` 包含 `lost`、`moved`、`changed`、`added`；`safe` 要求前三者为空，`identical` 还要求无新增项。

**备份并不保证所有系统效果可逆。** App 资源库回填不能通过恢复撤销；Apple 未承诺该接口在所有系统和布局上兼容。整份替换也不构成经过验证的事务/掉电原子性保证。读取和写入之间没有系统 compare-and-swap，用户应避免同时在手机或其它工具中编辑。

当前 Mac/iPhone 仅验证了读取与本地备份。下方实际写入结果是上游历史证据，不能作为本机写入兼容性证明。

## 上游历史约定与验证记录

**소유자:** layout-sync-engineer
**구현:** `src/ipsm/backup.py`, `src/ipsm/iconstate.py` (쓰기 후 대조)
**상태:** 실기기 항등 왕복 통과 (2026-08-19)

편집 결과를 기기에 반영하는 층. 항등 왕복 시험이 통과했으므로 **diff·계획·제스처는
필요 없다.** `layout-diff-planner` 는 폴백으로만 남아 있다.

## 쓰기는 한 길로만 나간다

```python
async def guarded_write(bridge, store: BackupStore, new_state: list, reason: str) -> Backup
```

```
현재 상태 읽기 → 백업 저장 → 백업 다시 읽어 대조 → (같을 때만) setIconState
                     ↓ 실패                ↓ 다르면
                  쓰지 않는다           쓰지 않는다
```

**백업이 실패하면 쓰지 않는다 (REQ-010).** 이 앱에서 안전성의 축은 "중단 안전성"이 아니라
백업 무결성이다. `setIconState` 는 부분 수정이 아니라 전체 덮어쓰기이고, 직전 상태를 그대로
다시 쓰면 완전히 복구된다. 그러므로 되돌릴 수 있는 백업이 있는지가 전부다.

`DeviceBridge.set_icon_state` 를 다른 곳에서 직접 부르는 것은 이 계약 위반이다.

## 백업

```python
class BackupStore:
    save(state, reason="auto") -> Backup    # 저장 후 다시 읽어 원본과 대조한다
    list_backups() -> list[Backup]
    latest() -> Backup | None
    load(path) -> list
```

- **이진 plist 로 저장한다.** XML plist 는 `iconModDate` 의 소수점 이하를 잘라내
  저장-재읽기 대조가 정상적으로 실패한다 (2026-08-19 발견).
- 저장 직후 다시 읽어 `deep_equal` 로 대조한다. 통과하지 못한 백업 파일은 지운다 —
  되돌릴 수 없는 백업은 없느니만 못하다.
- 파일 이름: `YYYYMMDD_HHMMSS_reason.plist`

## 쓰기 후 대조

```python
def compare_after_write(before: list, after: list) -> WriteComparison
    .lost      # 사라진 항목
    .moved     # 자리가 달라진 항목
    .appended  # 우리가 쓰지 않았는데 생긴 항목
    .safe      # 손실도 이동도 없는가
    .identical # 완전히 같은가
```

판정 기준은 **"완전 동일"이 아니라 "손실·이동 없음"**이다 (2026-08-19 정정).

이유: iOS 는 `setIconState` 를 받은 뒤 **앱 라이브러리에만 있던 앱을 마지막 페이지 끝에
되붙인다.** `setIconState` 에는 "설치됐지만 홈화면에 없음"을 표현할 방법이 없기 때문이다.
이것은 우리 쪽 손실이 아니므로 `appended` 로 따로 세고, 실패로 보지 않는다.

**이 부작용만은 백업 복원으로 되돌아가지 않는다.** 복원도 쓰기이기 때문이다. 그래서
적용 전에 어떤 앱이 붙을지 이름까지 대어 알린다 (ui-viewmodel 계약 참조).

## 복원

```python
async def restore(bridge, store, backup_path) -> Backup
```

복원도 쓰기다. 그러므로 복원 직전에도 현재 상태를 백업한다 — 잘못 고른 백업으로
복원했을 때 되돌아갈 자리가 있어야 한다.

## 쓰기 후 정착 시간

되읽기까지 **1.5초** 기다린다 (`ui/worker.py: _SETTLE_SECONDS`). SpringBoard 가 배치를
반영하는 데 잠깐 걸리고, 너무 짧으면 '아직 반영 안 된 상태'를 손실로 오해한다.

## 하지 않기로 한 것

- **깨진 iconState 로 기기의 반응을 시험하지 않는다.** 사용자의 실기기밖에 없고,
  실패 모드를 알아내는 값보다 홈화면을 망가뜨릴 위험이 크다. `[의도적 미검증]`
- 부분 쓰기·재시도 루프를 두지 않는다. 전체 덮어쓰기는 원자적이므로 중간 상태가 없다.
