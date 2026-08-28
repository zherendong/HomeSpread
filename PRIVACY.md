# 개인정보 처리방침 · Privacy Policy

**제품:** HomeSpread (Mobile layout manager for iOS)
**마지막 갱신:** 2026-08-20
**문의:** forad@ujak.net

---

## 한 줄 요약

**HomeSpread 는 어떤 정보도 수집하거나 밖으로 보내지 않는다.** 이 프로그램이 다루는 것은
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

| 폴더·파일 | 내용 | 지워도 되는가 |
|-----------|------|--------------|
| `backups/` | 적용 직전의 홈화면 배치 원본 | **지우면 되돌릴 수 없다** |
| `logs/` | 실행 기록 (UDID 는 가려져 있다). **최근 20회분만 남고 오래된 것은 프로그램이 스스로 지운다** | 지워도 된다 |
| `settings.json` | 고른 언어 | 지워도 된다 |
| `HomeSpread-cache\icons\` | 아이콘 그림 | 지워도 된다. 다시 받는다 |

**어디에 만들어지는가**는 어떻게 설치했느냐에 따라 다르다.

| 설치 방법 | `backups` · `logs` · `settings.json` |
|-----------|--------------------------------------|
| 압축을 풀어 쓰는 경우 | 실행 파일이 있는 폴더 |
| 소스에서 실행하는 경우 | 프로젝트 폴더 |
| Microsoft Store 에서 설치한 경우 | `문서\HomeSpread\` |

Store 로 설치하면 프로그램이 놓이는 자리(`C:\Program Files\WindowsApps\`)에는 아무것도
쓸 수 없어서, 백업을 그 옆에 둘 수가 없다. 그래서 **문서 폴더**에 만든다 — 당신이 직접
찾아가 열어 볼 수 있는 자리여야 하기 때문이다. 어디에 만들었는지는 실행할 때마다
`logs/` 첫 줄에 그대로 적힌다.

`문서` 폴더를 OneDrive 등으로 동기화하고 있다면, **그 안에 만들어진 백업도 함께
동기화된다.** 우리가 보내는 것이 아니라 당신이 켜 둔 동기화가 하는 일이지만, 백업에는
당신의 홈화면 배치(앱 목록·폴더 이름·순서)가 들어 있으므로 알고 있어야 할 사실이다.
원하지 않으면 해당 폴더를 동기화 대상에서 제외하면 된다.

아이콘 그림만은 Windows 임시 폴더(`%TEMP%`) 안에 둔다. 다시 받으면 그만인 것이라
Windows 가 공간이 부족할 때 치워도 잃는 것이 없고, 백업이 있는 폴더가 그림 수백 개로
불어나지 않는다. **백업과 로그는 절대 임시 폴더에 두지 않는다** — 되돌릴 길을 OS 의
청소 대상으로 삼을 수는 없다.

이 파일들은 전부 당신의 것이다. 폴더째 지우면 그것으로 끝이며, 어디에도 사본은 없다.
`logs/` 만은 프로그램이 스스로 오래된 것을 지운다 — 무한정 쌓이지 않게 하기 위해서다.
`backups/` 는 **지우지 않는다.** 되돌릴 길을 우리가 임의로 없애서는 안 되기 때문이다.

## 4. 바깥으로 나가는 순간

프로그램이 인터넷에 접속하는 경우는 **당신이 눌렀을 때** 뿐이고, 그때도 브라우저를 열어
줄 뿐이다.

- **후원 버튼** — GitHub Sponsors 페이지를 브라우저로 연다. 후원하려면 GitHub 계정이
  필요하고, 결제는 전적으로 GitHub 안에서 이루어진다. 우리는 카드번호·주소 등 결제
  정보를 받지도 보지도 않으며, 누가 후원했는지는 GitHub 이 알려 주는 범위에서만 안다.
  그곳에서 일어나는 일에는 GitHub 의 개인정보 처리방침이 적용된다.
- **Apple Devices 설치 안내** — Microsoft Store 앱을 연다.

두 경우 모두 당신에 관한 정보를 함께 실어 보내지 않는다.

## 5. 아이들

이 프로그램은 아동을 대상으로 하지 않으며, 나이를 묻지도 알지도 못한다.

## 6. 방침이 바뀌면

이 문서는 소스 저장소에 함께 공개되며, 바뀐 내용은 저장소 이력에 그대로 남는다.
프로그램의 정보 창에서 현재 판과 라이선스를 확인할 수 있다.

---

# Privacy Policy (English)

**Product:** HomeSpread (Mobile layout manager for iOS)
**Last updated:** 2026-08-20
**Contact:** forad@ujak.net

## In one line

**HomeSpread collects nothing and sends nothing.** Everything it handles stays between your
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

| File / folder | Contents | Safe to delete? |
|---------------|----------|-----------------|
| `backups/` | The exact layout captured before each write | **Deleting removes your way back** |
| `logs/` | Run logs (UDIDs masked). **Only the last 20 runs are kept; older ones are deleted automatically** | Yes |
| `settings.json` | Chosen language | Yes |
| `HomeSpread-cache\icons\` | Icon images | Yes, they are fetched again |

**Where** they are created depends on how you installed the app.

| Installed as | `backups` · `logs` · `settings.json` |
|--------------|--------------------------------------|
| Unzipped folder | Next to the executable |
| Run from source | The project folder |
| Microsoft Store | `Documents\HomeSpread\` |

A Store install lives in `C:\Program Files\WindowsApps\`, which nothing may write to, so
backups cannot sit beside the program. They go to your **Documents** folder instead, because
you must be able to open them yourself. Whichever location is used is written to the first
lines of `logs/` on every run.

If your `Documents` folder is synced to OneDrive or a similar service, **the backups created
there are synced too.** That is your sync setting at work rather than anything we send, but
a backup contains your home-screen layout (app list, folder names, order), so you should
know. Exclude the folder from syncing if you would rather it stayed local.

Icon images alone are kept inside the Windows temporary folder (`%TEMP%`). They are fetched
again whenever they are missing, so nothing is lost if Windows clears them to reclaim space,
and the folder holding your backups does not grow by hundreds of images. **Backups and logs
are never placed in the temporary folder** — your way back must not be something the OS may
clean up.

These files are yours. Delete the folder and it is gone; no copy exists anywhere else.
Only `logs/` is pruned by the program itself, so it cannot grow without bound. `backups/`
is **never** pruned — removing your way back is not ours to decide.

## 4. When anything leaves your machine

Only when you click, and even then the program merely opens your browser.

- **Donate button** — opens the GitHub Sponsors page. Sponsoring requires a GitHub account,
  and payment happens entirely inside GitHub; we never receive or see card numbers, addresses,
  or any other payment detail, and we learn who sponsored only as far as GitHub tells us.
  GitHub's own privacy policy governs what happens there.
- **Apple Devices install prompt** — opens the Microsoft Store app.

Neither carries information about you.

## 5. Children

This program is not directed at children and neither asks for nor learns anyone's age.

## 6. Changes

This document is published with the source, so every change is visible in the repository's
history. The program's About window shows the current version and license.
