# Partner Center 제출 문안 — HomeSpread

**작성:** 2026-08-27 · **대상 패키지:** `HomeSpread_1.0.21.0_x64.msix` · **태그:** `v1.0.21`
**쓰는 법:** 아래 코드 블록 안의 글자를 **그대로** Partner Center 의 같은 이름 칸에 붙여
넣는다. 블록 밖의 글은 왜 그렇게 썼는지를 남긴 것이니 붙여 넣지 않는다.

---

## 0. 제품 신원 — 이미 정해진 것

| 칸 | 값 |
|---|---|
| Store ID | `9NT54QJ7XQNL` |
| Package/Identity/Name | `YOUNGJONGLEE.HomeSpread` |
| Package/Identity/Publisher | `CN=D68EF2DF-56B8-44DF-BCF5-B40E38E8607A` |
| Package/Properties/PublisherDisplayName | `YOUNGJONG, LEE` |
| PFN | `YOUNGJONGLEE.HomeSpread_ea89tz3tby8xy` |
| 제품 유형 | **MSIX 또는 PWA 앱** |

`packaging/identity.json` 이 이 셋을 그대로 담고 있고, `scripts/make_msix.py` 가 그것을
매니페스트에 싣는다. 손으로 옮겨 적는 자리가 없으므로 어긋날 자리도 없다.

---

## 1. 이름과 부제

```
HomeSpread
```

부제(스토어의 이름 칸이 **아닌** 자리에만 쓴다):

```
Mobile layout manager for iOS
```

> **이름 칸에 `iPhone`·`iOS` 를 넣지 않는다.** Apple 상표 지침은 제품 이름 **안에**
> Apple 상표를 넣는 것을 금지하고 호환성 표기는 이름 **아래**로만 허용한다. 스토어
> 심사가 보는 칸이 정확히 이름 칸이다.

**선점·상표 확인(2026-08-27):**
- 선점 — Partner Center 가 `HomeSpread` 로 제품을 만들어 주었고 Store ID 를 발급했다.
  이름은 확보된 것이다 `[확인됨]`
- 상표 — 웹에서 `HomeSpread` 를 쓰는 등록 상표나 같은 이름의 소프트웨어를 찾지 못했다.
  USPTO 데이터베이스를 직접 조회한 것은 아니므로 `[확인됨(2차)]` 로 남긴다. 앞서
  걸렀던 다섯(`PageDeck`·`IconDesk`·`Screenlay`·`Iconlay`·`Screenboard`)과 달리
  임자가 보이지 않는다

---

## 2. 범주와 검색어

| 칸 | 값 |
|---|---|
| 범주 | `유틸리티 및 도구` (Utilities & tools) |
| 하위 범주 | `백업 및 관리` (Backup & manage) |

검색어(최대 7개, 각 30자 이내):

```
iPhone home screen
home screen layout
app icon organizer
iOS device manager
아이폰 홈화면
홈화면 정리
아이콘 정리
```

---

## 3. 짧은 설명 (Short description)

한국어:

```
여러 장으로 늘어난 iPhone 홈화면을 PC 한 화면에 펼쳐 놓고, 마우스로 끌어 정리한 뒤
기기에 그대로 반영합니다. 적용 전에 항상 백업을 남깁니다.
```

English:

```
Spread every iPhone home screen page across one PC window, rearrange icons by dragging,
and write the result back to the device. A full backup is taken before every write.
```

---

## 4. 설명 (Description)

> **첫 문단이 준비물을 말한다.** 준비물을 모르고 받은 사람이 첫 화면에서 막히면 그대로
> 별 하나가 된다. 두 번째로 말하는 것이 **부작용**이다 — 앱 라이브러리에만 있던 앱이
> 마지막 페이지 끝에 되붙는 것은 우리가 막을 수 없고, 백업으로도 되돌려지지 않는다.
> 프로그램도 적용 직전에 알리지만, 받기 **전에** 아는 편이 낫다.

### 한국어

```
■ 시작하기 전에 (필수)

이 프로그램은 Apple 의 "Apple Devices"(또는 iTunes)가 설치된 Windows PC 에서
동작합니다. 두 가지 모두 Microsoft Store 에서 무료로 받을 수 있습니다. iPhone 을
USB 로 연결하고 기기에서 "이 컴퓨터를 신뢰하시겠습니까?"에 [신뢰]를 눌러 주세요.
탈옥, 개발자 모드, Xcode 는 필요하지 않습니다.

■ 무엇을 하는 프로그램인가

iPhone 의 홈화면이 여러 장으로 늘어나면, 3페이지의 앱을 1페이지로 옮기는 일조차
손가락으로 끌면서 화면이 넘어가기를 기다려야 합니다. HomeSpread 는 그 페이지들을
PC 화면 하나에 나란히 펼쳐 놓습니다. 전체를 한눈에 보면서 마우스로 끌어 옮기고,
다 됐을 때 한 번에 기기로 보냅니다.

■ 할 수 있는 일

· 모든 홈화면 페이지와 독, 폴더 안까지 한 화면에 펼쳐 보기
· 마우스 드래그로 앱 옮기기 — 페이지 사이, 폴더 안팎 모두
· 앱을 앱 위에 겹쳐 새 폴더 만들기, 폴더 이름 바꾸기
· 꽉 찬 페이지에 끼워 넣으면 iPhone 과 똑같이 뒤로 밀려납니다
· 빈 폴더와 빈 페이지는 스스로 사라집니다
· 되돌리기 / 다시 하기
· 적용 전 자동 백업, 그리고 언제든 백업으로 복원
· 한국어 · English

■ 반드시 알아 두실 것 (되돌릴 수 없는 한 가지)

iPhone 에 배치를 쓰는 방법은 "일부만 고치기"가 아니라 "전체 덮어쓰기" 하나뿐입니다.
그래서 홈화면에는 없고 앱 라이브러리에만 있던 앱이 있으면, iOS 가 그 앱들을 마지막
페이지 끝에 다시 붙입니다. 이것은 프로그램이 막을 수 있는 일이 아니며 백업으로
복원해도(복원 역시 쓰기이므로) 되돌아가지 않습니다.

HomeSpread 는 적용을 누르기 전에 그런 앱이 몇 개이고 무엇인지 이름까지 보여 드립니다.
알고 누르는 것과 모르고 누르는 것은 다르기 때문입니다.

■ 안전에 대해

· 적용 직전에 기기의 현재 배치를 통째로 백업합니다. 백업에 실패하면 쓰지 않습니다
· 백업은 자동으로 지우지 않습니다
· 프로그램이 해석하지 못한 항목(위젯 등)은 손대지 않고 원본 그대로 다시 싣습니다
· 쓴 뒤에 기기에서 다시 읽어, 보낸 것과 같은지 대조해 알려 드립니다

■ 개인정보

아무것도 수집하지 않고 아무 데도 보내지 않습니다. 계정도, 로그인도 없습니다.
백업 · 로그 · 아이콘 그림은 모두 이 PC 안에만 남습니다. 통신은 Apple 구성요소가 여는
같은 PC 안의 주소(127.0.0.1:27015) 하나뿐입니다.

■ 라이선스

HomeSpread 는 GPL-3.0-or-later 자유 소프트웨어입니다. 전체 소스는
https://github.com/humanlyj/HomeSpread 에서 받을 수 있습니다.

■ 확인된 환경

iPhone 14 / iOS 26.1 에서 읽기 · 편집 · 쓰기 · 되돌리기 전 구간을 실기기로
확인했습니다. 다른 기기와 iOS 판에서도 같은 경로를 쓰지만, 처음 쓸 때는 백업이
남는지 먼저 확인해 보시기를 권합니다.
```

### English

```
■ Before you start (required)

HomeSpread needs Apple's "Apple Devices" app (or iTunes) installed on your Windows PC —
both are free in the Microsoft Store. Connect your iPhone over USB and tap "Trust" when
the device asks whether to trust this computer. No jailbreak, no developer mode, and no
Xcode are required.

■ What it does

Once your iPhone home screen grows to several pages, moving an app from page 3 to page 1
means dragging with a fingertip and waiting for each page to slide past. HomeSpread lays
those pages side by side in a single PC window. See the whole layout at once, rearrange
it with the mouse, and send it to the device when you are done.

■ Features

· Every home screen page, the dock, and the inside of every folder on one canvas
· Drag apps with the mouse — across pages and in and out of folders
· Drop one app onto another to create a folder; rename folders
· Drop into a full page and the rest shifts along, exactly as iPhone does
· Empty folders and empty pages remove themselves
· Undo / redo
· Automatic backup before every write, and restore from any backup at any time
· Korean and English

■ One thing you cannot undo

The only way to write a layout to an iPhone is a full overwrite — there is no partial
edit. As a result, any app that was installed but kept only in the App Library (not on
a home screen) is re-added by iOS at the end of the last page. No program can prevent
this, and restoring a backup does not undo it, because restoring is itself a write.

HomeSpread counts those apps and lists them by name before you press Apply. Knowing
before you press is not the same as finding out afterwards.

■ About safety

· The device's current layout is backed up in full immediately before every write.
  If the backup fails, nothing is written
· Backups are never deleted automatically
· Items the program does not understand (widgets and the like) are carried through
  untouched, exactly as they were read
· After writing, the layout is read back and compared with what was sent

■ Privacy

Nothing is collected and nothing is sent anywhere. There is no account and no sign-in.
Backups, logs, and cached icons stay on this PC. The only network traffic is to an
address on this same PC (127.0.0.1:27015) opened by Apple's own components.

■ License

HomeSpread is free software under GPL-3.0-or-later. The complete source is at
https://github.com/humanlyj/HomeSpread

■ Verified on

Reading, editing, writing, and restoring were all verified end to end on a real device
(iPhone 14 / iOS 26.1). Other devices and iOS versions use the same path, but on a first
run we recommend confirming that a backup file is created before you apply.
```

---

## 5. 제품 기능 (Product features) — 최대 20개, 각 200자

```
여러 홈화면 페이지와 독을 PC 한 화면에 펼쳐 봅니다
마우스 드래그로 페이지 사이·폴더 안팎으로 앱을 옮깁니다
앱을 겹쳐 새 폴더를 만들고 이름을 바꿉니다
꽉 찬 페이지에 끼우면 iPhone 과 똑같이 뒤가 밀려납니다
적용 전 자동 백업 — 백업에 실패하면 쓰지 않습니다
언제든 백업으로 되돌립니다
쓴 뒤 기기에서 되읽어 보낸 것과 대조합니다
아무것도 수집하지 않고 아무 데도 보내지 않습니다
GPL-3.0-or-later 자유 소프트웨어 · 소스 전체 공개
한국어 · English
```

---

## 6. 시스템 요구 사항

| 칸 | 값 |
|---|---|
| 아키텍처 | x64 |
| 최소 OS | Windows 10 버전 1809 (10.0.17763) 이상 |

**추가 하드웨어/소프트웨어 안내(Notes):**

```
Apple Devices 또는 iTunes 가 설치되어 있어야 합니다(Microsoft Store 에서 무료).
iPhone 과 USB 케이블이 필요하며, 기기에서 이 PC 를 "신뢰"해야 합니다.
```

---

## 7. 개인정보·연락처·라이선스 약관

| 칸 | 값 |
|---|---|
| 개인정보 처리방침 URL | `https://github.com/humanlyj/HomeSpread/blob/main/PRIVACY.md` |
| 지원 연락처 | `forad@ujak.net` |
| 웹사이트 | `https://github.com/humanlyj/HomeSpread` |

2026-08-27 에 로그인하지 않은 상태로 세 주소가 모두 열리는 것을 확인했다(HTTP 200).
로그인해야 읽을 수 있는 주소는 없는 주소와 같다.

**라이선스 약관 — 표준 약관 대신 우리 것을 낸다.**
개발자 계약은 개발자가 자기 라이선스 약관을 대신 제출하는 것을 허용하고, FOSS 가
요구하는 범위에서 표준 약관의 역공학·복제·재배포 금지를 넘어서도록 명시적으로 허락한다.
`라이선스 약관` 칸에 URL 을 넣는다:

```
https://github.com/humanlyj/HomeSpread/blob/main/LICENSE
```

---

## 8. 제3자 결제 API 신고 (정책 10.8.2)

Partner Center 가 "제품이 제3자 결제 API 를 사용합니까?"를 물으면 **예**로 답한다.
설명 칸에 넣을 말:

```
설정 창에 PayPal 후원 버튼이 하나 있습니다. 자발적 후원만 받으며 후원자에게
디지털 재화, 추가 기능, 광고 제거 등 어떤 대가도 제공하지 않습니다(정책 10.8.2).
버튼을 누르면 기본 브라우저에서 PayPal 페이지가 열리고, 앱 안에서 결제를 받거나
결제 정보를 다루지 않습니다.
```

> 이 선을 넘는 순간 — 후원자에게 무엇이든 돌려주는 순간 — Microsoft 인앱 결제 API 로
> 넘어가야 한다. 단추를 만들 때부터 아무것도 주지 않도록 지어 둔 이유다.

---

## 9. 연령 등급 (IARC 설문)

수집·공유·사용자 간 소통이 전혀 없으므로 대부분 **아니오**다. 걸릴 만한 문항의 답:

| 문항 | 답 | 근거 |
|---|---|---|
| 폭력·성적 표현·비속어·약물 | 아니오 | 없다 |
| 사용자 간 소통(채팅·메시지) | 아니오 | 없다 |
| 사용자 위치 공유 | 아니오 | 없다 |
| 개인정보 수집·제3자 공유 | 아니오 | 아무것도 수집하지 않는다(`PRIVACY.md`) |
| 디지털 재화 구매 | 아니오 | 후원은 대가 없는 기부이고 앱 밖 브라우저에서 일어난다 |
| 사용자 생성 콘텐츠 공유 | 아니오 | 없다 |
| 앱에서 웹으로 나가는 링크 | 예 | PayPal, 저장소, Microsoft Store(Apple 구성요소 안내) |

---

## 10. 인증 담당자에게 남기는 메모 (Notes for certification)

> **이 칸을 비우면 떨어질 가능성이 크다.** 인증 담당자의 PC 에는 iPhone 이 꽂혀 있지
> 않다. 그 상태에서 프로그램을 켜면 편집 화면이 아니라 준비물 안내판이 뜬다 — 미리
> 말해 두지 않으면 "동작하지 않는 앱"으로 읽힌다.

```
이 앱은 USB 로 연결된 iPhone 의 홈화면 배치를 읽고 편집해 다시 쓰는 도구입니다.
검토용 계정이나 로그인은 없습니다.

iPhone 이 연결되어 있지 않은 PC 에서 실행하면, 앱은 오류 없이 시작한 뒤 준비물
안내 화면을 보여줍니다. 이 화면은 (1) Apple Devices 또는 iTunes 설치 여부와
(2) Apple 구성요소가 127.0.0.1:27015 를 열고 있는지를 3초마다 다시 확인하고,
설치가 필요하면 Microsoft Store 의 해당 페이지로 안내합니다. 이것이 기기 없이
확인할 수 있는 정상 동작입니다.

기기를 연결해 전체 기능을 확인하시려면:
1. Microsoft Store 에서 "Apple Devices" 를 설치하고 한 번 실행합니다
2. iPhone 을 USB 로 연결하고 기기 화면에서 [신뢰] 를 누릅니다
3. 앱의 [기기에서 읽기] 를 누르면 홈화면 페이지들이 펼쳐집니다
탈옥, 개발자 모드, Xcode, 별도 드라이버는 필요하지 않습니다.

네트워크: 인터넷으로 나가는 통신이 없습니다. 유일한 소켓 연결은 같은 PC 안의
127.0.0.1:27015 이며, 이는 Apple 이 설치한 구성요소가 여는 기기 통신 창구입니다.
사용자가 버튼을 눌렀을 때만 기본 브라우저로 외부 주소(PayPal 후원, GitHub 저장소,
Microsoft Store)를 엽니다.

파일: 백업·로그는 문서 폴더의 HomeSpread 아래에, 아이콘 캐시는 %TEMP% 아래에
만듭니다. 설치 폴더에는 아무것도 쓰지 않습니다.

라이선스: GPL-3.0-or-later 입니다. 표준 라이선스 약관 대신 제출한 약관을 확인해
주십시오. 전체 소스: https://github.com/humanlyj/HomeSpread
```

---

## 11. 그림

| 칸 | 요건 | 상태 |
|---|---|---|
| 스토어 로고 | 300x300 이상 | `assets/store-listing-300.png` **있음** |
| 앱 타일 로고 한 벌 | MSIX 매니페스트가 가리킨다 | `assets/logo/` 14장 **있음** (`scripts/make_logos.py` 가 그린다) |
| 스크린샷 | 최소 1장, 1366x768 이상 | `_workspace/screenshots/` **8장 있음** (1760x880, 언어별 4장) |

### 무엇을 찍었는가

핵심 장면은 "여러 페이지가 한 화면에 펼쳐진 모습" 하나다. 그런데 그 장면을 만들려면
실제 배치와 아이콘 그림이 있어야 하고, 아이콘은 기기에서 받아 온다. 여기서 갈린다:

- **실기기 배치 그대로** — 가장 진짜 같지만 사용자의 앱 목록이 그대로 공개된다
- **시연용 배치** — Apple 기본 앱만으로 배치를 지어내면 개인적인 것이 하나도 드러나지
  않으면서 아이콘은 진짜 그림이 쓰인다

**시연용 배치를 택했다.** 스토어 페이지는 영구히 공개되는 자리이고, 내린 뒤에도 캐시와
색인에 남는다. 홈화면 그림 한 장은 그 사람이 무슨 앱을 쓰는지 — 은행·병원·회사 — 를
통째로 알려준다. 되돌릴 수 없는 공개이므로 기본값은 "보여주지 않는다"여야 한다.

배치는 `scripts/make_demo_layout.py` 가 짓고(항목 raw 는 기기 백업에서 그대로 꺼내
쓴다 — `iconModDate` 를 손으로 지으면 아이콘을 못 받는다), 그림은
`scripts/make_screenshots.py` 가 찍는다. 기기 없이도 다시 찍을 수 있다(아이콘 캐시만
있으면 된다). 이름을 다시 바꾸는 날에도 손으로 찍을 일이 없다.

영어 그림에서는 앱 이름만 영어로 갈아 끼운다. 이름은 기기의 언어를 따라오는데 우리
기기가 한국어라, 그대로 두면 en-US 목록에 읽히지 않는 그림이 올라간다.

### 올릴 순서 (같은 순서로 두 언어 모두)

| 순서 | 파일 | 캡션(ko) | 캡션(en) |
|---|---|---|---|
| 1 | `01_spread_*.png` | 홈화면 4장을 PC 한 화면에 펼쳐 놓은 모습 | All your home screen pages, side by side on one screen |
| 2 | `03_changes_*.png` | 편집하면 무엇이 바뀌는지 오른쪽에 줄줄이 선다. 그때서야 '적용'이 켜진다 | Every pending change is listed before anything is written |
| 3 | `02_folder_*.png` | 폴더를 열어 안까지 편집한다 | Open a folder and edit what is inside |
| 4 | `04_guide_*.png` | 기기를 붙이기 전 첫 화면 — 준비물을 스스로 보고 알려 준다 | The first screen checks the prerequisites for you |

크기는 모두 1760x880 으로, 스토어 최소치(1366x768)를 넘는다.
