# 타당성 조사 — iPhone 홈화면 읽기/쓰기 경로

**조사일**: 2026-08-19
**결론**: **쓰기 경로가 존재한다.** 프로젝트의 초기 전제("비탈옥 iPhone에는 레이아웃 쓰기 API가 없다")는 **틀렸다.**

## 표기 규약

| 표기 | 의미 |
|------|------|
| `[확인됨]` | 소스 코드/문서를 직접 확인함 |
| `[문헌]` | 2차 자료에서 확인, 출처 병기 |
| `[미검증]` | 실기기 확인 필요 |

---

## 1. 핵심 발견 — `com.apple.springboardservices`

iOS에는 **`com.apple.springboardservices`** 라는 일반 lockdown 서비스가 있고, 여기에 홈화면 레이아웃을 **읽고 쓰는 명령이 모두 존재한다.**

| 명령 | 기능 | 확인 |
|------|------|------|
| `getIconState` | 홈화면 전체 레이아웃(페이지·폴더·독) 반환 | `[확인됨]` |
| `setIconState` | **홈화면 레이아웃 전체를 덮어씀** | `[확인됨]` |
| `getHomeScreenIconMetrics` | 그리드 행·열·간격 등 배치 수치 반환 | `[확인됨]` |
| `getIconPNGData` | 앱 아이콘 PNG | `[확인됨]` |
| `getInterfaceOrientation` | 화면 방향 | `[확인됨]` |

근거: `pymobiledevice3/services/springboard.py` (master) 원본 코드 직접 확인.

```python
async def set_icon_state(self, newstate=None) -> None:
    state = {} if newstate is None else newstate
    await self.service.send_recv_prefixed(
        build_plist({"command": "setIconState", "iconState": state}))
```

### 이것이 바꾸는 것

| 항목 | 초기 전제 | 실제 |
|------|----------|------|
| 쓰기 방법 | 드래그 제스처 재생 | **plist 한 번 전송** |
| 아이콘 1개 이동 비용 | 수 초 | 전체 레이아웃이 **1회 호출** |
| 사전 요구사항 | 개발자 모드 + DDI + WDA 서명 | **페어링(신뢰)만** |
| 되돌리기 | 불가능 | **이전 iconState를 다시 setIconState → 완전 복원** |
| 부분 실패 | 상시 발생 | 전부 적용 또는 전부 미적용 |
| 그리드 수치 | 실측·추정 필요 | `getHomeScreenIconMetrics`가 제공 |
| 앱 식별 | 접근성 트리 + OCR + 아이콘 매칭 | **번들 ID가 그대로 들어 있음** |

**제스처 재생, 접근성 트리 파싱, 아이콘 이미지 인식, 밀어내기 시뮬레이터, 체크포인트/재개 — 전부 불필요해진다.**

### 선례

`libimobiledevice/sbmanager`는 이 서비스로 데스크톱에서 홈화면을 편집하는 GUI를 이미 구현했다 `[문헌]`. 다만 iOS 3~6 시대 프로젝트로 현재는 유지보수되지 않는다.

---

## 2. 남은 불확실성 `[미검증]`

**실기기 검증 전까지 아래를 사실로 취급하지 않는다.**

| 질문 | 왜 중요한가 | 검증 방법 |
|------|-----------|----------|
| 최신 iOS(18/26)에서 `setIconState`가 실제로 반영되는가 | 이것이 거짓이면 제스처 경로로 회귀해야 한다 | 항등 왕복(현재 상태를 그대로 재전송) 후 오류 여부 |
| 변경된 상태도 반영되는가 (항등이 아니라 실제 변경) | 항등만 통과하고 변경이 무시될 수 있다 | 아이콘 1개 이동 후 재조회 대조 |
| 기기 잠금 해제가 필요한가 | UX 안내 문구가 달라진다 | 잠금 상태에서 호출 |
| 위젯을 iconState가 어떻게 표현하는가 | 위젯이 포함되지 않으면 setIconState가 위젯을 지울 위험 | 위젯이 있는 페이지에서 조회 |
| 빈칸(iOS 18+ 자유 배치)이 어떻게 표현되는가 | 편집 모델의 핵심 | 빈칸이 있는 페이지 조회 |
| App Library / 숨긴 페이지 / 포커스별 페이지 | 덮어쓸 때 손실 위험 | 조회 결과 확인 |
| 잘못된 iconState를 보내면 어떻게 되는가 | 안전장치 설계의 근거 | **의도적으로 시험하지 않는다** |

**항등 왕복이 통과하지 않으면 이 경로는 폐기하고 제스처 경로로 되돌아간다.**

`reload_icon_state()`(get → set 왕복)가 pymobiledevice3의 `wallpaper-preview-image --reload` 기능에 실제로 쓰이고 있다는 점은 `setIconState`가 현행 iOS에서 동작한다는 **정황 증거**다 `[확인됨-코드]`. 그러나 정황일 뿐이다.

---

## 3. 도구 선정

### pymobiledevice3

| 항목 | 내용 | 확인 |
|------|------|------|
| 언어 | 순수 Python 3 (외부 실행 파일 불필요) | `[확인됨]` |
| 라이선스 | **GPL-3.0-or-later** | `[확인됨]` |
| iOS 17+ | RemoteXPC 터널 지원 | `[확인됨]` |
| 연결 | USB / Wi-Fi / RemoteXPC | `[확인됨]` |
| SpringBoard | 일반 lockdown 서비스 — DDI 불필요 | `[확인됨]` |
| Windows | pyusb 기반, Apple Devices(iTunes) 드라이버 필요 | `[문헌]` `[미검증]` |

**대체 후보**: `libimobiledevice`(C, LGPL-2.1, `sbservices` 동일 기능 제공). Python에서 쓰려면 별도 바인딩·바이너리 번들이 필요해 마찰이 크다. pymobiledevice3가 불가할 때의 폴백으로 둔다.

### 라이선스 판단

GPL-3.0 라이브러리를 **import** 하면 배포 시 전체가 GPL-3.0이 된다. 이 앱은 사용자 개인 도구이며 상용 폐쇄 배포 계획이 없으므로 **수용한다.** 향후 폐쇄 배포가 필요해지면 이 결정을 재검토한다 (→ ADR 재검토 조건).

---

## 4. 사전 요구사항 (사용자가 해야 할 것)

| 항목 | 필요 여부 | 비고 |
|------|----------|------|
| USB 케이블 연결 | 필수 | |
| iPhone에서 "이 컴퓨터를 신뢰" | 필수 | 최초 1회 |
| Apple Devices 앱 또는 iTunes (Windows 드라이버) | 필요 추정 `[미검증]` | 드라이버 제공 목적 |
| 개발자 모드 | **불필요** | springboardservices는 DDI를 요구하지 않음 |
| WebDriverAgent / Xcode / Apple 개발자 계정 | **불필요** | |
| 탈옥 | **불필요** | |

---

## 5. 권고

1. **제스처 경로 개발을 중단하고 springboardservices 경로로 전환한다.**
2. 최초 산출물은 **기기 프로브 도구**여야 한다 — 연결, `getIconState` 덤프, 메트릭 덤프, **항등 왕복 안전 시험**, 전 과정 로그 파일 기록. 위 `[미검증]` 항목이 전부 여기서 판정된다.
3. 프로브가 항등 왕복에 실패하면 제스처 경로로 되돌아간다. 그때를 위해 `layout-diff-planner` 스킬은 **삭제하지 않고 보존한다.**
4. 되돌리기가 가능해졌으므로(이전 iconState 저장 → 복원) 안전 설계의 축이 "중단 안전성"에서 **"백업 무결성"**으로 이동한다.

## 출처

- pymobiledevice3 `services/springboard.py`, `cli/springboard.py`, `pyproject.toml`, `LICENSE` (master, 직접 확인)
- libimobiledevice `sbservices.h`, `sbmanager/src/iconstate.c`
- Appium XCUITest driver — Run Preinstalled WDA (제스처 경로 비교용)
