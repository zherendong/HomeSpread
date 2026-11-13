"""영어 사전. 열쇠는 소스에 적힌 **한국어 원문 그대로**다.

여기 없는 문구는 한국어가 그대로 보인다 — 앱이 말을 잃지는 않는다. 빠뜨림은
`tests/test_core.py` 의 `test_every_translatable_string_has_an_english_entry`
가 잡는다. 값이 들어가는 자리(`{n}`, `{name}` …)는 **이름과 개수가 원문과 같아야**
하고, 그것도 시험이 본다.
"""

TRANSLATIONS: dict[str, str] = {
    # ----------------------------------------------------------------- 시작
    "시작할 수 없습니다": "Cannot start",
    "PySide6 가 설치되어 있지 않습니다. install.bat 을 먼저 실행해 주세요.":
        "PySide6 is not installed. Run install.bat first.",
    "'{where}' 에 폴더를 만들 수 없습니다 ({why}).\n"
    "쓰기 권한이 있는 폴더(예: 바탕화면, 문서)로 프로그램을 옮긴 뒤 다시 실행해 주세요.":
        "Cannot create folders in '{where}' ({why}).\n"
        "Move the program to a folder you can write to (Desktop or Documents) and run it again.",
    "'{where}' 에 파일을 쓸 수 없습니다.\n"
    "이 앱은 홈화면을 바꾸기 전에 반드시 백업을 남깁니다. 백업을 쓸 수 없으면\n"
    "적용도 하지 않습니다. 쓰기 권한이 있는 폴더로 프로그램을 옮겨 주세요.":
        "Cannot write files to '{where}'.\n"
        "This app always saves a backup before changing your Home Screen. If the backup\n"
        "cannot be written, nothing is applied. Move the program to a writable folder.",
    # 권한은 멀쩡한데 막히는 경우가 하나 있다 — 그 한 줄을 네 갈래 모두에 붙인다.
    "폴더 권한과 별개로, Windows 보안의 '제어된 폴더 액세스'가 막고 있을 수도\n"
    "있습니다. Windows 보안 › 바이러스 및 위협 방지 › 랜섬웨어 방지 에서\n"
    "이 앱을 허용해 주세요.":
        "Apart from folder permissions, Windows Security's Controlled Folder Access\n"
        "may be blocking it. Allow this app under Windows Security > Virus & threat\n"
        "protection > Ransomware protection.",
    # Store 로 설치한 앱은 사용자가 옮길 수 없다 — 그때는 옮기라고 말하지 않는다.
    "'{where}' 에 폴더를 만들 수 없습니다 ({why}).\n"
    "이 폴더의 쓰기 권한을 확인해 주세요.":
        "Cannot create folders in '{where}' ({why}).\n"
        "Please check that you have permission to write to this folder.",
    "'{where}' 에 파일을 쓸 수 없습니다.\n"
    "이 앱은 홈화면을 바꾸기 전에 반드시 백업을 남깁니다. 백업을 쓸 수 없으면\n"
    "적용도 하지 않습니다. 이 폴더의 쓰기 권한을 확인해 주세요.":
        "Cannot write files to '{where}'.\n"
        "This app always saves a backup before changing your Home Screen. If the backup\n"
        "cannot be written, nothing is applied. Please check that you have permission to\n"
        "write to this folder.",

    # ------------------------------------------------------------------ 백업
    "{stamp} {dash} {reason} {dash} {pages}페이지 {items}개 항목":
        "{stamp} {dash} {reason} {dash} {pages} pages, {items} items",
    "백업 파일의 형식이 올바르지 않습니다.": "This backup file is not in the expected format.",
    "백업 파일을 다시 읽었을 때 원본과 달랐습니다. 백업을 신뢰할 수 없습니다.":
        "The backup did not match the original when read back. It cannot be trusted.",
    "백업을 저장하지 못했습니다: {why}": "Could not save the backup: {why}",
    "백업 파일을 읽지 못했습니다: {why}": "Could not read the backup file: {why}",
    " (예: {sample})": " (for example: {sample})",

    # ------------------------------------------------------------------ 기기
    "iPhone과 통신하는 Windows 구성요소를 찾을 수 없습니다.":
        "The Windows component that talks to iPhone was not found.",
    "Apple 기기(Apple Devices) 앱 또는 iTunes를 설치한 뒤 PC를 다시 시작해 주세요.":
        "Install the Apple Devices app (or iTunes), then restart your PC.",
    "연결된 iPhone이 없습니다.": "No iPhone is connected.",
    "USB 케이블로 iPhone을 연결해 주세요. 충전 전용 케이블은 동작하지 않습니다.":
        "Connect your iPhone with a USB cable. Charge-only cables will not work.",
    "지정한 iPhone을 찾을 수 없습니다.": "That iPhone could not be found.",
    "케이블을 다시 연결하고 시도해 주세요.": "Reconnect the cable and try again.",
    "iPhone에서 아직 신뢰 여부를 선택하지 않았습니다.":
        "You have not answered the trust prompt on the iPhone yet.",
    "iPhone 화면의 '이 컴퓨터를 신뢰하시겠습니까?'에서 '신뢰'를 눌러 주세요.":
        "On the iPhone, tap 'Trust' in the 'Trust This Computer?' prompt.",
    "iPhone에서 이 PC를 신뢰하지 않도록 선택했습니다.":
        "The iPhone was set not to trust this PC.",
    "케이블을 다시 연결한 뒤 '신뢰'를 선택해 주세요.":
        "Reconnect the cable and choose 'Trust'.",
    "iPhone이 잠겨 있어 연결할 수 없습니다.": "The iPhone is locked, so it cannot be reached.",
    "iPhone 잠금을 해제한 상태로 두고 다시 시도해 주세요.":
        "Unlock the iPhone, leave it unlocked, and try again.",
    "이 PC가 iPhone과 아직 연결 설정되지 않았습니다.":
        "This PC has not been paired with the iPhone yet.",
    "iPhone 잠금을 해제하고, 화면에 나타나는 '신뢰'를 눌러 주세요.":
        "Unlock the iPhone and tap 'Trust' when it appears.",
    "iPhone이 이 PC를 신뢰하지 않습니다.": "The iPhone does not trust this PC.",
    "iPhone 잠금을 해제하고 '신뢰'를 눌러 주세요.": "Unlock the iPhone and tap 'Trust'.",
    "iPhone이 홈화면 변경 요청을 거부했습니다.":
        "The iPhone refused the Home Screen change.",
    "iPhone 잠금을 해제한 상태로 다시 시도해 주세요. 계속 실패하면 진단 보고서를 저장해 주세요.":
        "Unlock the iPhone and try again. If it keeps failing, save a diagnostic report.",
    "iPhone의 홈화면 서비스를 시작하지 못했습니다.":
        "The iPhone's Home Screen service could not be started.",
    "iPhone 잠금을 해제하고 다시 시도해 주세요. 계속 실패하면 iPhone을 재시동해 주세요.":
        "Unlock the iPhone and try again. If it keeps failing, restart the iPhone.",
    "이 iPhone에서는 홈화면 서비스를 사용할 수 없습니다.":
        "The Home Screen service is not available on this iPhone.",
    "진단 보고서를 저장해 주세요. iOS 버전에 따라 지원되지 않을 수 있습니다.":
        "Save a diagnostic report. Some iOS versions do not support this.",
    "iPhone과 통신하는 중 예상치 못한 문제가 발생했습니다.":
        "Something unexpected went wrong while talking to the iPhone.",
    "iPhone 잠금을 해제하고 케이블을 다시 연결해 주세요. 반복되면 진단 보고서를 저장해 주세요.":
        "Unlock the iPhone and reconnect the cable. If it repeats, save a diagnostic report.",
    "iPhone에 연결되지 않았습니다.": "Not connected to an iPhone.",
    "먼저 iPhone을 연결해 주세요.": "Connect an iPhone first.",
    "알 수 없음": "Unknown",

    # ------------------------------------------------------------- 항목 이름
    "(이름 없음)": "(no name)",
    "(빈칸)": "(empty slot)",
    "(알 수 없는 항목)": "(unrecognized item)",
    "(사라진 페이지)": "(page is gone)",

    # ------------------------------------------------------------------ 자리
    "독": "Dock",
    "독 {n}번째": "Dock slot {n}",
    "{page}페이지 {n}번째": "Page {page}, slot {n}",
    " 폴더 안": ", inside a folder",
    "{n}페이지": "page {n}",
    "폴더 “{name}” {n}페이지": "folder “{name}”, page {n}",
    "{where} {n}번째": "{where}, slot {n}",

    # ------------------------------------------------------------- 편집 판정
    "항목을 찾을 수 없습니다.": "That item could not be found.",
    "항목을 찾을 수 없습니다 ({uid}).": "That item could not be found ({uid}).",
    "묶음 안에서 항목을 찾을 수 없습니다 ({uid}).":
        "That item could not be found inside the folder ({uid}).",
    "자리를 찾을 수 없습니다 ({uid}).": "That location could not be found ({uid}).",
    "자리를 찾을 수 없습니다.": "That location could not be found.",
    "이 항목은 우리가 해석하지 못한 것이라, 안전을 위해 옮기지 않습니다.":
        "This item is one we could not interpret, so it is left where it is for safety.",
    "폴더 안에 폴더를 넣을 수 없습니다.": "A folder cannot go inside another folder.",
    "폴더를 자기 자신 안에 넣을 수 없습니다.": "A folder cannot go inside itself.",
    "이 페이지가 가득 찼습니다 (최대 {n}칸).": "This page is full (up to {n} slots).",
    "독이 가득 찼습니다 (최대 {n}칸).": "The Dock is full (up to {n} slots).",
    "이 묶음이 가득 찼습니다 (최대 {n}개).": "This folder is full (up to {n} items).",
    "이 묶음이 가득 차서 밀어낼 자리가 없습니다.":
        "This folder is full and there is nowhere left to push items.",
    "홈화면이 가득 차서 밀어낼 자리가 없습니다.":
        "The Home Screen is full and there is nowhere left to push items.",
    "페이지는 최대 {n}개까지입니다.": "There can be at most {n} pages.",
    "페이지 번호가 범위를 벗어났습니다.": "That page number is out of range.",
    "비어 있는 페이지만 지울 수 있습니다. 먼저 항목을 옮겨 주세요.":
        "Only an empty page can be removed. Move its items away first.",
    "페이지를 모두 지울 수는 없습니다.": "You cannot remove every page.",

    # ------------------------------------------------------------------ 묶기
    "묶으려면 항목을 두 개 이상 골라야 합니다.": "Pick at least two items to group.",
    "묶음 하나에는 최대 {limit}개까지 들어갑니다 ({picked}개를 고르셨습니다).":
        "A folder holds at most {limit} items (you picked {picked}).",
    "“{name}”은(는) 우리가 해석하지 못한 항목이라, 안전을 위해 묶지 않습니다.":
        "“{name}” is an item we could not interpret, so it is not grouped, for safety.",
    "“{name}”은(는) 이미 묶음입니다. 묶음끼리는 묶을 수 없습니다.":
        "“{name}” is already a folder. Folders cannot be grouped together.",
    "“{name}”은(는) 이미 묶음 안에 있습니다. 먼저 묶음 밖으로 꺼내 주세요.":
        "“{name}” is already inside a folder. Take it out first.",
    "새 묶음": "New folder",
    "묶음의 이름만 바꿀 수 있습니다.": "Only folders can be renamed.",
    "이름을 비워 둘 수 없습니다.": "The name cannot be empty.",
    "이름이 너무 깁니다 (64자까지).": "That name is too long (up to 64 characters).",

    # -------------------------------------------------------------- 명령 이름
    "{name} 이동": "Move {name}",
    "묶음 “{name}” 만들기 ({n}개)": "Create folder “{name}” ({n} items)",
    "묶음 이름 “{before}” → “{after}”": "Rename folder “{before}” → “{after}”",
    "{n}페이지를 {to}번째로 이동": "Move page {n} to position {to}",
    "{n}페이지 추가": "Add page {n}",
    "{n}페이지 삭제": "Remove page {n}",

    # ------------------------------------------------------------- 변경 목록
    "{n}페이지 → {to}번째": "page {n} → position {to}",
    "페이지 순서: {list}": "Page order: {list}",
    " 외 {n}개": " and {n} more",
    "새 묶음 “{name}” 만듦 ({n}개: {members})":
        "Created folder “{name}” ({n} items: {members})",
    "빈 묶음 “{name}” 없어짐 ({where})": "Empty folder “{name}” removed ({where})",
    "묶음 이름: “{before}” → “{after}”": "Folder name: “{before}” → “{after}”",
    "{name}: {where} 안에서 {before}번째 → {after}번째":
        "{name}: within {where}, slot {before} → slot {after}",
    "페이지 {n}개": "{n} pages",
    "앱 {n}개": "{n} apps",
    "폴더 {n}개": "{n} folders",
    "알 수 없는 항목 {n}개": "{n} unrecognized items",

    # ------------------------------------------------------------------ 캔버스
    "이 페이지를 앞으로": "Move this page earlier",
    "이 페이지를 뒤로": "Move this page later",
    "빈 페이지 삭제": "Remove empty page",
    "이름 바꾸기": "Rename",
    "닫기": "Close",
    "{n}페이지 · {count}/{capacity}": "Page {n} · {count}/{capacity}",
    "독 · {count}/{capacity}": "Dock · {count}/{capacity}",
    "폴더 “{name}” · {n}개": "Folder “{name}” · {n} items",
    " · {n}개": " · {n} items",
    "{name} — {where} {n}번째{extra}": "{name} — {where}, slot {n}{extra}",
    "이 묶음에는 넣을 수 없습니다.": "It cannot go into this folder.",
    "여기에는 놓을 수 없습니다.": "It cannot be dropped here.",
    "놓으면 “{name}” 와(과) 새 묶음이 됩니다.":
        "Drop to make a new folder with “{name}”.",

    # ------------------------------------------------------------------- 도구
    "연결되지 않음": "Not connected",
    "연결됨": "Connected",
    "기기에서 읽기": "Read from device",
    "백업 파일 열기": "Open backup file",
    "아이콘 받기": "Fetch icons",
    "실행 취소": "Undo",
    "다시 실행": "Redo",
    "페이지 추가": "Add page",
    "묶기": "Group",
    "고른 앱들을 새 묶음(폴더)으로 (Ctrl 을 누른 채 눌러 여러 개 고름)":
        "Put the selected apps into a new folder (hold Ctrl to select several)",
    "고른 묶음의 이름을 바꾼다": "Rename the selected folder",
    "적용": "Apply",
    "백업으로 복원": "Restore from backup",
    "모두 보이게": "Fit all",
    " 크기 ": " Size ",

    # ----------------------------------------------------------------- 안내판
    "iPhone 홈화면을 PC 한 화면에 펼쳐 정리합니다":
        "Lay out every iPhone home screen page on one PC screen",
    "탈옥도, 개발자 모드도 필요 없습니다. USB 케이블과 ‘신뢰’ 한 번이면 됩니다.":
        "No jailbreak, no developer mode. A USB cable and one “Trust” is all it takes.",
    "① Apple 이 만든 구성요소가 USB 를 맡습니다 — Apple Devices 앱 또는 iTunes":
        "① Apple's own software handles the USB link — the Apple Devices app, or iTunes",
    "② iPhone 을 케이블로 연결하고, 잠금을 푼 뒤 ‘신뢰’ 를 눌러 주세요":
        "② Connect the iPhone by cable, unlock it, and tap “Trust”",
    "③ 위쪽 ‘기기에서 읽기’ 를 누르면 홈화면이 펼쳐집니다":
        "③ Press “Read from device” above and your home screens appear",
    "적용할 때는 홈화면 전체가 한 번에 덮어써집니다. 그래서 쓰기 직전에 늘 백업을\n"
    "먼저 뜨고, 백업에 실패하면 쓰지 않습니다. 언제든 백업으로 되돌릴 수 있습니다.":
        "Applying overwrites the whole home screen at once. That is why a backup is\n"
        "always taken first, and nothing is written if it fails. You can always go back.",
    "✓ 준비됐습니다. iPhone 을 케이블로 연결하고 잠금을 풀어 주세요.":
        "✓ Ready. Connect your iPhone by cable and unlock it.",
    "Apple Devices 는 설치되어 있지만 아직 동작하지 않습니다.\n"
    "한 번 실행하거나 PC 를 다시 시작하면 준비됩니다.":
        "Apple Devices is installed but not running yet.\n"
        "Start it once, or restart the PC, and you are set.",
    "iPhone 과 통신하는 Apple 구성요소가 없습니다.\n"
    "Microsoft Store 의 무료 앱 ‘Apple Devices’ 를 설치해 주세요. (iTunes 도 됩니다)":
        "The Apple software that talks to an iPhone is missing.\n"
        "Install the free “Apple Devices” app from the Microsoft Store. (iTunes works too)",
    "Microsoft Store 에서 Apple Devices 받기": "Get Apple Devices from the Microsoft Store",
    "Microsoft Store 에서 열기": "Open in the Microsoft Store",
    "다시 확인": "Check again",

    # ------------------------------------------------------------------- 설정
    "설정": "Settings",
    "프로그램": "Program",
    "도움말": "Help",
    "언어를 고릅니다": "Choose the language",
    "언어": "Language",
    "바꾸면 곧바로 화면에 적용되고, 다음에 켤 때도 그대로입니다.":
        "The change takes effect right away and is remembered next time.",
    "확인": "OK",

    # ------------------------------------------------------------------- 본문
    "변경 없음": "No changes",
    "(변경 없음)": "(no changes)",
    "미적용 변경 {n}건": "{n} unapplied changes",
    "아이콘을 끌어 옮기고, 폴더는 두 번 눌러 엽니다.\n"
    "폴더 한가운데에 놓으면 폴더 안으로, 옆에 놓으면 그 자리에 끼웁니다.":
        "Drag icons to move them; double-click a folder to open it.\n"
        "Drop on the middle of a folder to put an app inside, or beside it to insert there.",
    "미배치 앱": "Apps not on the Home Screen",
    "미배치 앱 {n}개": "{n} apps not on the Home Screen",
    "적용하면 마지막 페이지 끝에 붙습니다 (iOS 동작).":
        "Applying will append these to the end of the last page (this is iOS behavior).",
    "iPhone 을 연결하고 ‘기기에서 읽기’를 눌러 주세요.":
        "Connect an iPhone and press ‘Read from device’.",
    " · 아이콘이 없습니다. ‘아이콘 받기’를 눌러 주세요.":
        " · No icons yet. Press ‘Fetch icons’.",
    "이 홈화면은 편집할 수 없습니다": "This Home Screen cannot be edited",
    "읽어 들인 홈화면을 그대로 되돌려 쓸 수 없는 구조가 섞여 있습니다.\n"
    "안전을 위해 쓰기를 막습니다. logs/ 의 기록을 확인해 주세요.":
        "The layout we read contains something we cannot write back unchanged.\n"
        "Writing is blocked for safety. Check the records under logs/.",
    "이 앱은 무료이고 소스가 공개되어 있습니다. 마음이 내키면 개발을 응원해 주세요.":
        "This app is free and open source. If you feel like it, you can support the work.",
    "♥ GitHub 으로 후원하기": "♥ Sponsor on GitHub",
    "파일: {name}": "File: {name}",
    "페이지 {n}장을 한 화면에 폈습니다.": "Laid out all {n} pages on one screen.",
    "페이지 {n}장은 이 창 크기에 다 들어가지 않습니다. 창을 키우면 더 보입니다.":
        "{n} pages do not all fit at this window size. Enlarge the window to see more.",
    "{n}개 골랐습니다 — 묶기(Ctrl+G)로 하나로 묶을 수 있습니다.":
        "{n} selected — press Group (Ctrl+G) to put them in one folder.",
    "{n}개를 묶습니다. 묶음 이름:": "Grouping {n} items. Folder name:",
    "묶음 “{name}” 을(를) 만들었습니다. 두 번 누르면 열립니다.":
        "Created folder “{name}”. Double-click to open it.",
    "이름을 바꿀 묶음을 하나 골라 주세요.": "Select one folder to rename.",
    "묶음 이름 바꾸기": "Rename folder",
    "새 이름:": "New name:",

    # ------------------------------------------------------------- 적용 · 복원
    "iPhone 홈화면에 적용": "Apply to the iPhone Home Screen",
    "아래 {n}건을 iPhone 홈화면에 적용합니다.":
        "The {n} changes below will be applied to the iPhone Home Screen.",
    "• 적용 전에 현재 홈화면을 자동으로 백업합니다. 백업에 실패하면 쓰지 않습니다.":
        "• The current Home Screen is backed up first. If the backup fails, nothing is written.",
    "• 홈화면은 부분 수정이 아니라 전체가 한 번에 덮어써집니다.":
        "• The Home Screen is overwritten as a whole, not patched in part.",
    "• 앱 라이브러리에만 있던 앱이 마지막 페이지 끝에 붙을 수 있습니다. iOS 의 동작이며\n"
    "   백업 복원으로도 되돌아가지 않습니다.":
        "• Apps that lived only in the App Library may be appended to the last page. That is\n"
        "   iOS behavior, and restoring the backup does not undo it.",
    "• 지금 홈화면에 없는 앱 {n}개가 마지막 페이지 끝에 붙습니다:\n"
    "   {names}{more}\n"
    "   iOS 의 동작이라 백업 복원으로도 되돌아가지 않습니다. 적용 후 직접 정리해 주세요.":
        "• {n} apps that are not on the Home Screen will be appended to the last page:\n"
        "   {names}{more}\n"
        "   That is iOS behavior and restoring the backup does not undo it. Tidy up afterwards.",
    "• 적용 중에는 케이블을 뽑지 마세요. 1초 남짓 걸립니다.":
        "• Do not unplug the cable while applying. It takes about a second.",
    "위 내용을 확인했습니다.": "I have read the above.",
    "백업하고 적용": "Back up and apply",
    "취소": "Cancel",
    "적용할 변경이 없습니다.": "There are no changes to apply.",
    "적용하지 않은 변경이 있습니다": "You have unapplied changes",
    "기기에서 다시 읽으면 지금까지의 편집이 사라집니다. 계속할까요?":
        "Reading from the device again discards your edits so far. Continue?",
    "편집한 내용은 iPhone 에 반영되지 않았습니다. 그대로 닫을까요?":
        "Your edits were never sent to the iPhone. Close anyway?",
    "열 수 없습니다": "Cannot open",
    "홈화면 백업 (*.plist)": "Home Screen backup (*.plist)",
    "백업 없음": "No backups",
    "아직 만들어진 백업이 없습니다.": "No backup has been made yet.",
    "복원할 백업 선택": "Choose a backup to restore",
    "{name} 시점으로 홈화면을 되돌립니다.\n"
    "복원도 쓰기이므로, 복원 직전 상태를 먼저 백업합니다. 계속할까요?":
        "This restores the Home Screen to {name}.\n"
        "Restoring is also a write, so the current state is backed up first. Continue?",
    "아이콘이 모두 준비되어 있습니다.": "All icons are already here.",
    "아이콘 {done}/{total}개를 받았습니다.": "Fetched {done} of {total} icons.",
    " (받지 못한 {n}개는 웹 클립처럼 원래 이미지가 없는 항목일 수 있습니다)":
        " ({n} could not be fetched — web clips and the like have no icon image)",
    "백업: {name}": "Backup: {name}",
    "사용자 배치가 그대로 반영되었습니다. 손실·이동 없음.":
        "Your arrangement was applied exactly. Nothing lost, nothing moved.",
    "⚠ 손실 {lost}건 · 의도치 않은 이동 {moved}건":
        "⚠ {lost} lost · {moved} moved unintentionally",
    "iOS 가 앱 {n}개를 마지막 페이지 끝에 되붙였습니다 (앱 라이브러리에만 있던 앱).":
        "iOS appended {n} apps to the end of the last page (they lived only in the App Library).",
    "적용 완료": "Applied",
    "적용했지만 확인이 필요합니다": "Applied, but please check",
    "복원 완료": "Restored",
    "복원 직전 상태를 {name} 로 백업했습니다.":
        "The state just before restoring was backed up as {name}.",
    "문제가 생겼습니다": "Something went wrong",

    # ------------------------------------------------------------------ 작업
    "홈화면 읽기": "Reading the Home Screen",
    "아이콘 내려받기": "Fetching icons",
    "홈화면 적용": "Applying the Home Screen",
    "백업 복원": "Restoring a backup",
    "이미 다른 작업이 진행 중입니다.": "Another task is already running.",
    "끝날 때까지 기다려 주세요.": "Please wait for it to finish.",
    "작업 스레드가 시작되지 않았습니다.": "The worker thread did not start.",
    "앱을 다시 실행해 주세요.": "Please restart the app.",
    "iPhone 을 찾는 중…": "Looking for an iPhone…",
    "홈화면을 읽는 중…": "Reading the Home Screen…",
    "백업을 만드는 중…": "Making a backup…",
    "홈화면을 쓰는 중…": "Writing the Home Screen…",
    "결과를 확인하는 중…": "Checking the result…",
    "복원하는 중…": "Restoring…",
    "아이콘 받는 중 ({done}/{total})": "Fetching icons ({done}/{total})",
    "로그 파일(logs/)을 확인해 주세요.": "Check the log files under logs/.",
    "{what} 중 문제가 생겼습니다: {why}": "Something went wrong during {what}: {why}",

    # ------------------------------------------------------------------ 정보
    "정보": "About",
    "판·라이선스·소스": "Version, license, source",
    "라이선스 전문": "License text",
    "함께 실려 오는 것들": "What ships with it",
    "개인정보 처리방침": "Privacy policy",
    "이 프로그램은 자유 소프트웨어입니다. {license} 아래에서 누구나 자유롭게 "
    "쓰고, 뜯어보고, 고쳐서 다시 나눠 줄 수 있습니다. 보증은 없습니다.":
        "This program is free software. Under {license} anyone may use it, take it "
        "apart, change it, and pass it on. It comes with no warranty.",
    "소스: {url}": "Source: {url}",
    "소스 전체를 요구할 권리가 있습니다. 배포한 사람에게 요청하세요.":
        "You have the right to the complete source. Ask whoever gave you this copy.",
    "'{name}' 을(를) 찾을 수 없습니다.": "'{name}' could not be found.",
    "'{name}' 을(를) 읽을 수 없습니다 ({why}).": "'{name}' could not be read ({why}).",
}


# Diagnostic CLI messages.
TRANSLATIONS.update({
    "대화형 입력이 불가능하여 쓰기를 건너뜁니다.": "No interactive input is available; device writing was skipped.",
    "사용자가 입력을 취소했습니다.": "Input was cancelled.",
    "2. 홈화면 레이아웃 읽기": "2. Read the Home Screen layout",
    "   %s 해석하지 못한 항목이 %d개 있습니다 (위젯 등일 수 있습니다).": "   %s There are %d unrecognized items (possibly widgets).",
    "     원본 표본을 산출물로 저장합니다 — 형식을 보완하는 근거가 됩니다.": "     Original samples are saved locally for format analysis.",
    "3. 그리드 메트릭 읽기": "3. Read grid dimensions",
    "   (이 기기에서는 메트릭을 제공하지 않습니다 — 치명적이지 않습니다)": "   (This device does not provide grid dimensions.)",
    "   화면 방향: %s": "   Orientation: %s",
    "조회 불가": "Unavailable",
    "   성공 %d개 / 실패 %d개": "   Fetched %d / failed %d",
    "5. 항등 왕복 안전 시험 (기기에 씁니다)": "5. Unchanged layout round-trip test (writes to the device)",
    "   읽은 레이아웃을 그대로 다시 써서, 아무것도 변하지 않는지 확인합니다.": "   Write the layout back unchanged, then read it again to check the result.",
    "   값이 바뀌지 않는 쓰기지만, 실제로 기기에 전송됩니다.": "   This sends a real write request to the iPhone, even though the layout is unchanged.",
    "   직전 상태는 이미 백업되어 있으므로 되돌릴 수 있습니다.": "   A verified backup is required immediately before writing.",
    "   진행할까요?": "   Back up and write the unchanged layout?",
    "   -> 건너뜁니다. 기기에 아무것도 쓰지 않았습니다.": "   -> Skipped. Nothing was written to the device.",
    "   %s 시험이 끝날 때까지 iPhone을 분리하지 말고 잠금 해제 상태로 두세요.": "   %s Keep the iPhone connected and unlocked until verification finishes.",
    "6. 결과 대조": "6. Verify the result",
    "   %s 실패 %s 사용자의 배치가 보존되지 않았습니다.": "   %s FAILED %s The layout was not preserved.",
    "     사라짐: %s": "     Lost: %s",
    "     이동:   %s": "     Moved: %s",
    "   이 기기에서는 홈화면 쓰기 기능을 활성화하면 안 됩니다.": "   Do not continue editing this device until the mismatch is understood.",
    "   되돌리려면 backups/ 의 가장 최근 파일로 복원하세요.": "   The latest backup in backups/ can be selected for recovery.",
    "   %s 통과 %s 쓰기 전후가 완전히 동일합니다.": "   %s PASSED %s The layouts before and after writing are identical.",
    "     이 기기에서 홈화면 편집 기능을 만들어도 안전합니다.": "     This result covers this layout and device; it does not guarantee all future edits.",
    "   %s 통과 %s 사라지거나 움직인 항목이 없습니다 (%d개 항목 보존).": "   %s PASSED %s No lost or moved items (%d items preserved).",
    "   %s 다만 iPhone이 앱 %d개를 홈화면 끝에 새로 붙였습니다:": "   %s iOS appended %d apps to the end of the Home Screen:",
    "     홈화면에 없던 앱(앱 라이브러리에만 있던 앱)입니다. iOS 는 홈화면 배치를": "     These apps were only in the App Library. After receiving a complete layout,",
    "     통째로 받으면, 그 안에 없는 설치된 앱을 끝에 되붙입니다. 우리가 빠뜨린 것이": "     iOS can append installed apps that were absent from the Home Screen.",
    "     아니라 iOS 의 동작이며, 쓰기를 할 때마다 일어납니다.": "     Restoring a backup also writes the layout and cannot reverse this behavior.",
    "     원치 않으면 iPhone에서 해당 아이콘을 길게 눌러 '홈 화면에서 제거'를 선택하세요": "     To hide them again, long-press each icon and choose 'Remove from Home Screen'.",
    "     (앱은 지워지지 않고 앱 라이브러리에 남습니다).": "     (This keeps the apps installed and available in the App Library.)",
    "iPhone 홈화면 진단 (%s)": "iPhone Home Screen diagnostics (%s)",
    "모든 기록: %s": "Session log: %s",
    "1. 기기 연결": "1. Connect to the device",
    "   연결된 iPhone이 없습니다.": "   No iPhone is connected.",
    "   USB 케이블로 연결하고, iPhone 화면에서 '신뢰'를 눌러 주세요.": "   Connect with a USB data cable and tap 'Trust' on the iPhone.",
    "   (충전 전용 케이블은 데이터 통신이 되지 않습니다)": "   (Charge-only cables cannot transfer data.)",
    "   같은 기기가 %s 로 잡힙니다. USB 를 사용합니다.": "   Available transports: %s. USB will be used.",
    "   기기가 %d대 있습니다. 첫 번째 기기를 사용합니다.": "   %d devices found. Specify --udid or leave only one iPhone connected by USB.",
    "4. 백업": "4. Save a backup",
    "   파일: %s": "   File: %s",
    "5. 항등 왕복 안전 시험": "5. Unchanged layout round-trip test",
    "   건너뜀 (읽기 전용 실행).": "   Skipped (read-only run).",
    "   위 결과가 정상으로 보이면 --roundtrip 을 붙여 다시 실행하세요.": "   --roundtrip requests a real write and asks for confirmation before continuing.",
    "원인": "Cause",
    "%s 백업을 만들지 못해 중단했습니다: %s": "%s Stopped because the backup could not be created: %s",
    "  -> 백업 없이는 기기에 아무것도 쓰지 않습니다.": "  -> Nothing is written without a verified backup.",
    "사용자가 중단했습니다.": "Interrupted by the user.",
    "예상치 못한 오류로 중단했습니다.": "Stopped because of an unexpected error.",
    "진단 보고서": "Diagnostic report",
    "   문제가 있었다면 이 파일 하나만 전달하면 됩니다:": "   This local report contains device and app-layout information. Review it before sharing:",
    "보고서를 만들지 못했습니다. 로그 파일은 그대로 남아 있습니다.": "Could not create the report. The log file is still available.",
    "iPhone 홈화면 진단 프로브 — 기본은 읽기 전용입니다.": "iPhone Home Screen diagnostics. Read-only unless --roundtrip is requested.",
    "특정 기기를 지정 (생략하면 첫 번째 기기)": "Select a device by UDID; otherwise exactly one USB iPhone must be connected.",
    "항등 왕복 안전 시험을 수행한다 (기기에 씁니다 · 확인 질문 있음)": "Write the unchanged layout back for verification (writes to the device; asks for confirmation).",
    "앱 아이콘 이미지도 내려받는다": "Also fetch app icons from the device.",
    "내려받을 아이콘 수 (기본 30)": "Maximum number of icons to fetch (default: 30).",
})


# macOS port and write-safety messages.
TRANSLATIONS.update({
    "   Apps kept only in the App Library may reappear on the Home Screen. Restoring a backup cannot undo this iOS behavior.": "   Apps kept only in the App Library may reappear on the Home Screen. Restoring a backup cannot undo this iOS behavior.",
    "3b. Fetch app icons (up to {limit})": "3b. Fetch app icons (up to {limit})",
    "A device operation is running. Wait for it to finish before closing.": "A device operation is running. Wait for it to finish before closing.",
    "Applying replaces the entire Home Screen after a verified backup. Apps kept only in the App Library may reappear; restoring a backup cannot undo that iOS behavior.": "Applying replaces the entire Home Screen after a verified backup. Apps kept only in the App Library may reappear; restoring a backup cannot undo that iOS behavior.",
    "Cannot create the data folder '{where}' ({why}). Check folder permissions and disk space in Finder.": "Cannot create the data folder '{where}' ({why}). Check folder permissions and disk space in Finder.",
    "Cannot identify the connected iPhone safely. Reconnect and read it again.": "Cannot identify the connected iPhone safely. Reconnect and read it again.",
    "Cannot load the device connection library.": "Cannot load the device connection library.",
    "Cannot write to '{where}'. A verified backup is required before changing the Home Screen. Check this folder's permissions in Finder.": "Cannot write to '{where}'. A verified backup is required before changing the Home Screen. Check this folder's permissions in Finder.",
    "Check the folder permissions and available disk space in Finder.": "Check the folder permissions and available disk space in Finder.",
    "Connect the intended iPhone with a data cable and try again.": "Connect the intended iPhone with a data cable and try again.",
    "Demo layout (fictional apps)": "Demo layout (fictional apps)",
    "Disconnect the other devices before reading or changing a layout.": "Disconnect the other devices before reading or changing a layout.",
    "More than one iPhone is connected by USB.": "More than one iPhone is connected by USB.",
    "No iPhone is connected by USB.": "No iPhone is connected by USB.",
    "Reconnect your iPhone, unlock it and select Trust in Finder and on the iPhone. Restart the Mac if needed.": "Reconnect your iPhone, unlock it and select Trust in Finder and on the iPhone. Restart the Mac if needed.",
    "Reinstall the application dependencies and restart the app.": "Reinstall the application dependencies and restart the app.",
    "Restore the Home Screen from backup: {name}": "Restore the Home Screen from backup: {name}",
    "The Mac cannot reach Apple's iPhone connection service.": "The Mac cannot reach Apple's iPhone connection service.",
    "The Mac's iPhone connection service is unavailable. Reconnect the cable, open Finder, and restart your Mac if needed.": "The Mac's iPhone connection service is unavailable. Reconnect the cable, open Finder, and restart your Mac if needed.",
    "The application is already running. Switch to its existing window.": "The application is already running. Switch to its existing window.",
    "The backup integrity record is invalid. Restoration was stopped.": "The backup integrity record is invalid. Restoration was stopped.",
    "The edit would lose, duplicate, change or move an unsupported item. No changes were written.": "The edit would lose, duplicate, change or move an unsupported item. No changes were written.",
    "The iPhone layout changed after it was read. Read it again before applying edits.": "The iPhone layout changed after it was read. Read it again before applying edits.",
    "The layout has an unsupported structure. No changes were written.": "The layout has an unsupported structure. No changes were written.",
    "The selected iPhone is not connected by USB.": "The selected iPhone is not connected by USB.",
    "This backup does not belong to the connected iPhone.": "This backup does not belong to the connected iPhone.",
    "① macOS includes iPhone connectivity. No Apple Devices app or iTunes installation is needed.": "① macOS includes iPhone connectivity. No Apple Devices app or iTunes installation is needed.",
    "도구": "Tools",
    "Mobile layout manager for iOS": "Mobile layout manager for iOS",
    "     Changed content: %s": "     Changed content: %s",
    "Unexpected item content changes: {n}": "Unexpected item content changes: {n}",
})


# Layout summaries and backup comparison details.
TRANSLATIONS.update({
    "{name} ({model}), iOS {ios} [{build}], {connection} connection, UDID {udid}": "{name} ({model}), iOS {ios} [{build}], {connection} connection, UDID {udid}",
    "페이지 {pages}개, 독 {dock}칸": "{pages} pages, {dock} Dock slots",
    "앱 {apps}개 · 폴더 {folders}개 · 빈칸 {empty}개 · 알 수 없는 항목 {unknown}개": "{apps} apps · {folders} folders · {empty} empty slots · {unknown} unrecognized items",
    "(그 중 오프로드된 앱 {offloaded}개 · 웹 클립 {clips}개)": "(including {offloaded} offloaded apps · {clips} web clips)",
    "  독: {items}": "  Dock: {items}",
    ", … (총 {count}칸)": ", … ({count} slots in total)",
    "  {index}페이지 ({count}칸): {preview}": "  Page {index} ({count} slots): {preview}",
    "페이지 수: {before} → {after}": "Page count: {before} → {after}",
    "독 항목 수: {before} → {after}": "Dock item count: {before} → {after}",
    "사라진 앱 {count}개: {items}": "{count} apps lost: {items}",
    "새로 나타난 앱 {count}개: {items}": "{count} apps added: {items}",
    "알 수 없는 항목 수: {before} → {after}": "Unrecognized item count: {before} → {after}",
    "구조적 차이 없음": "No structural differences",
    "{path}: 타입 {before} -> {after}": "{path}: type {before} -> {after}",
    "{path}.{key}: (없음) -> {after!r}": "{path}.{key}: (absent) -> {after!r}",
    "{path}.{key}: {before!r} -> (없음)": "{path}.{key}: {before!r} -> (absent)",
    "{path}: 항목 수 {before} -> {after}": "{path}: item count {before} -> {after}",
})


# Explicit write-compatibility gate and included modified source.
TRANSLATIONS.update({
    "Checking write compatibility… Keep the iPhone connected.": "Checking write compatibility… Keep the iPhone connected.",
    "Compatibility test failed. Applying edits and restoring backups are disabled.": "Compatibility test failed. Applying edits and restoring backups are disabled.",
    "Compatibility test passed. You can now edit and apply changes.": "Compatibility test passed. You can now edit and apply changes.",
    "Modified source included in this app: {url}": "Modified source included in this app: {url}",
    "Read complete. Before editing, run the write compatibility test; it requires confirmation and writes to the iPhone.": "Read complete. Before editing, run the write compatibility test; it requires confirmation and writes to the iPhone.",
    "Run the write compatibility test before applying edits or restoring a backup.": "Run the write compatibility test before applying edits or restoring a backup.",
    "Upstream source: {url}": "Upstream source: {url}",
    "Write compatibility test": "Write compatibility test",
    "Write the current layout back unchanged, then read it again to verify compatibility. This is a real write to the iPhone.": "Write the current layout back unchanged, then read it again to verify compatibility. This is a real write to the iPhone.",
})


# Recovery remains available when the compatibility gate fails.
TRANSLATIONS.update({
    "Compatibility test failed. Applying edits is disabled. You may explicitly restore a verified backup for recovery.": "Compatibility test failed. Applying edits is disabled. You may explicitly restore a verified backup for recovery.",
    "Run the write compatibility test before applying edits.": "Run the write compatibility test before applying edits.",
    "Write compatibility is unverified or failed. Recovery remains available, but restoration is another full write and may fail.": "Write compatibility is unverified or failed. Recovery remains available, but restoration is another full write and may fail.",
})

# Widget-aware read-only preview and central write capability policy.
TRANSLATIONS.update({
    'Duo preview is read-only. Device writes are disabled.': 'Duo preview is read-only. Device writes are disabled.',
    'Individual pages': 'Individual pages',
    'Keep this layout in read-only preview. No device changes were sent.': 'Keep this layout in read-only preview. No device changes were sent.',
    'Layout placeholder · no live content': 'Layout placeholder · no live content',
    'No next page': 'No next page',
    'Offline preview never connects to or writes to an iPhone.': 'Offline preview never connects to or writes to an iPhone.',
    'Offline preview uses a local backup only. No iPhone connection is made.': 'Offline preview uses a local backup only. No iPhone connection is made.',
    'Offline preview: no phone access or layout changes.': 'Offline preview: no phone access or layout changes.',
    'Page {n} · {count} items · {cells}/{capacity} cells': 'Page {n} · {count} items · {cells}/{capacity} cells',
    'Positions unverified; not placed on the grid: {items}': 'Positions unverified; not placed on the grid: {items}',
    'Preview layout': 'Preview layout',
    'This layout contains an unsupported structure. It can be previewed, but device writes are disabled.': 'This layout contains an unsupported structure. It can be previewed, but device writes are disabled.',
    'This layout contains widgets or widget stacks. Preview is read-only; applying, restoring and write compatibility tests are disabled.': 'This layout contains widgets or widget stacks. Preview is read-only; applying, restoring and write compatibility tests are disabled.',
    'This preview is read-only; layout changes are disabled.': 'This preview is read-only; layout changes are disabled.',
    'Unknown size': 'Unknown size',
    'Widget': 'Widget',
    'Widget stack ({n})': 'Widget stack ({n})',
    'Widgets: {blocks} positions, {members} including stack members': 'Widgets: {blocks} positions, {members} including stack members',
    'iPhone Duo is available for read-only preview. Applying, restoring and write compatibility tests are disabled for this device.': 'iPhone Duo is available for read-only preview. Applying, restoring and write compatibility tests are disabled for this device.',
    'iPhone Duo preview is read-only. Device writing is not supported.': 'iPhone Duo preview is read-only. Device writing is not supported.',
    'iPhone Duo · two-page preview': 'iPhone Duo · two-page preview',
    'item {n}: {name}': 'item {n}: {name}',
    '{columns} × {rows} cells': '{columns} × {rows} cells',
})

TRANSLATIONS.update({
    'Double-click folders to inspect them. Dragging, edits, compatibility tests, and restoration are disabled.': 'Double-click folders to inspect them. Dragging, edits, compatibility tests, and restoration are disabled.',
    'Read-only preview': 'Read-only preview',
    'Read-only preview — {reason}\nWidget cards show size and stack membership, not live content.': 'Read-only preview — {reason}\nWidget cards show size and stack membership, not live content.',
    'The layout exceeds the reported grid capacity. Preview only; editing is disabled.': 'The layout exceeds the reported grid capacity. Preview only; editing is disabled.',
    'This layout contains unknown items or empty placeholders. Preview only; editing is disabled.': 'This layout contains unknown items or empty placeholders. Preview only; editing is disabled.',
    'This layout contains widgets. Preview only; editing is disabled.': 'This layout contains widgets. Preview only; editing is disabled.',
    'This layout has an unsupported structure. Preview only; editing is disabled.': 'This layout has an unsupported structure. Preview only; editing is disabled.',
    'Cannot open the preview file: {why}': 'Cannot open the preview file: {why}',
})

TRANSLATIONS['Some icons are not cached. Offline preview shows text placeholders.'] = 'Some icons are not cached. Offline preview shows text placeholders.'
