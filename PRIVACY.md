# 개인정보 처리방침 · Privacy Policy

**제품:** HomeBoard (Mobile layout manager for iOS)
**마지막 갱신:** 2026-08-20
**문의:** forad@ujak.net

---

## 한 줄 요약

**HomeBoard 는 어떤 정보도 수집하거나 밖으로 보내지 않는다.** 이 프로그램이 다루는 것은
전부 당신의 PC 와 USB 로 연결된 당신의 기기 사이에서만 오간다.

## 1. 우리가 수집하는 것

없다. 계정도, 로그인도, 사용 통계도, 오류 보고도 없다. 프로그램은 우리에게 아무것도
보내지 않으며, 우리를 향한 서버 자체가 존재하지 않는다.

## 2. 프로그램이 당신의 기기에서 읽는 것

USB 로 연결한 기기에서 다음을 읽는다. 모두 당신의 PC 안에서만 쓰인다.

| 읽는 것 | 쓰는 곳 |
|---------|---------|
| 홈화면 배치 정보 (`iconState`) | 화면에 페이지를 펼쳐 보이고, 편집한 결과를 되쓰기 위해 |
| 설치된 앱 목록 | 홈화면에 없는 앱이 적용 후 끝에 붙는다는 사실을 미리 알리기 위해 |
| 앱 아이콘 그림 | 타일에 그리기 위해 |
| 기기 식별자(UDID) | 어느 기기의 백업인지 구분하기 위해. **로그에는 앞 4글자만 남긴다** |

기기와의 통신은 Apple 이 만든 구성요소가 여는 `127.0.0.1:27015` 를 통한다. 이 주소는
당신의 PC 를 벗어나지 않는다.

## 3. 당신의 PC 에 남는 것

실행 파일 옆(또는 소스에서 실행한 경우 프로젝트 폴더)에 다음이 만들어진다.

| 폴더·파일 | 내용 | 지워도 되는가 |
|-----------|------|--------------|
| `backups/` | 적용 직전의 홈화면 배치 원본 | **지우면 되돌릴 수 없다** |
| `logs/` | 실행 기록 (UDID 는 가려져 있다). **최근 20회분만 남고 오래된 것은 프로그램이 스스로 지운다** | 지워도 된다 |
| `cache/icons/` | 아이콘 그림 | 지워도 된다. 다시 받는다 |
| `settings.json` | 고른 언어 | 지워도 된다 |

이 파일들은 전부 당신의 것이다. 폴더째 지우면 그것으로 끝이며, 어디에도 사본은 없다.
`logs/` 만은 프로그램이 스스로 오래된 것을 지운다 — 무한정 쌓이지 않게 하기 위해서다.
`backups/` 는 **지우지 않는다.** 되돌릴 길을 우리가 임의로 없애서는 안 되기 때문이다.

## 4. 바깥으로 나가는 순간

프로그램이 인터넷에 접속하는 경우는 **당신이 눌렀을 때** 뿐이고, 그때도 브라우저를 열어
줄 뿐이다.

- **후원 버튼** — PayPal 후원 페이지를 브라우저로 연다. 결제는 전적으로 PayPal 안에서
  이루어지며, 우리는 카드번호·주소 등 결제 정보를 받지도 보지도 않는다. PayPal 에서
  일어나는 일에는 PayPal 의 개인정보 처리방침이 적용된다.
- **Apple Devices 설치 안내** — Microsoft Store 앱을 연다.

두 경우 모두 당신에 관한 정보를 함께 실어 보내지 않는다.

## 5. 아이들

이 프로그램은 아동을 대상으로 하지 않으며, 나이를 묻지도 알지도 못한다.

## 6. 방침이 바뀌면

이 문서는 소스 저장소에 함께 공개되며, 바뀐 내용은 저장소 이력에 그대로 남는다.
프로그램의 정보 창에서 현재 판과 라이선스를 확인할 수 있다.

---

# Privacy Policy (English)

**Product:** HomeBoard (Mobile layout manager for iOS)
**Last updated:** 2026-08-20
**Contact:** forad@ujak.net

## In one line

**HomeBoard collects nothing and sends nothing.** Everything it handles stays between your
PC and the device you connected over USB.

## 1. What we collect

Nothing. No account, no sign-in, no usage statistics, no crash reports. The program sends us
nothing, and there is no server of ours for it to send anything to.

## 2. What the program reads from your device

Over USB, and used only on your PC:

| Read | Used for |
|------|----------|
| Home screen layout (`iconState`) | Showing your pages on screen and writing your edits back |
| List of installed apps | Warning you, before applying, that apps missing from the home screen will be appended |
| App icon images | Drawing the tiles |
| Device identifier (UDID) | Telling one device's backups from another. **Logs keep only the first 4 characters** |

Device communication goes through `127.0.0.1:27015`, opened by Apple's own component. That
address never leaves your PC.

## 3. What stays on your PC

Next to the executable (or in the project folder when run from source):

| File / folder | Contents | Safe to delete? |
|---------------|----------|-----------------|
| `backups/` | The exact layout captured before each write | **Deleting removes your way back** |
| `logs/` | Run logs (UDIDs masked). **Only the last 20 runs are kept; older ones are deleted automatically** | Yes |
| `cache/icons/` | Icon images | Yes, they are fetched again |
| `settings.json` | Chosen language | Yes |

These files are yours. Delete the folder and it is gone; no copy exists anywhere else.
Only `logs/` is pruned by the program itself, so it cannot grow without bound. `backups/`
is **never** pruned — removing your way back is not ours to decide.

## 4. When anything leaves your machine

Only when you click, and even then the program merely opens your browser.

- **Donate button** — opens PayPal's donation page. Payment happens entirely inside PayPal;
  we never receive or see card numbers, addresses, or any other payment detail. PayPal's own
  privacy policy governs what happens there.
- **Apple Devices install prompt** — opens the Microsoft Store app.

Neither carries information about you.

## 5. Children

This program is not directed at children and neither asks for nor learns anyone's age.

## 6. Changes

This document is published with the source, so every change is visible in the repository's
history. The program's About window shows the current version and license.
