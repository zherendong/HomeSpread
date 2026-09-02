# -*- coding: utf-8 -*-
"""스토어에 올릴 화면 그림용 **시연 배치**를 만든다 — `_workspace/demo-layout.json`.

**왜 사용자의 진짜 배치를 쓰지 않는가:** 스토어 페이지의 그림은 영구히 공개되고,
내린 뒤에도 캐시와 색인에 남는다. 홈화면 그림 한 장은 그 사람이 무슨 앱을 쓰는지
—은행·병원·데이팅·회사—를 통째로 알려준다. 되돌릴 수 없는 공개이므로 기본값은
"보여주지 않는다"여야 한다.

**왜 Apple 기본 앱도 쓰지 않는가(2026-08-31):** 처음에는 어느 iPhone 에나 있는
Apple 기본 앱으로 배치를 지어내고, 아이콘도 기기 캐시에서 꺼내 썼다. 그 그림이
스토어 인증에서 **10.1.1(Inaccurate Representation)** 으로 거절됐다 — "제출된 그림에
Windows 가 아닌 UI 나 기기가 보인다". 화면의 거의 전부가 Apple 의 실제 아이콘
저작물이었으니, 심사자가 그것을 iPhone 화면으로 읽은 것은 당연하다. 게다가 그
아이콘들은 우리가 만든 것도, 허락받은 것도 아니다(정책 11.2).

그래서 이제 **아무의 것도 아닌 앱**으로 배치를 짓는다. 식별자는
`com.homespread.demo.*` 이고, 아이콘은 `make_demo_icons.py` 가 그리며, 이름은 어느
회사의 제품명도 아닌 일반 낱말이다. 기기도, 백업도 필요 없다 — 저장소만 받으면
누구나 같은 그림을 다시 만들 수 있다.

    .venv/Scripts/python.exe scripts/make_demo_layout.py
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_workspace" / "demo-layout.json"

#: 시연 앱의 식별자 앞머리. 우리 것임이 이름에서 드러나야 한다 — 어느 실제 앱의
#: 번들 ID 와도 겹치지 않고, 나중에 이 배치가 어디서 왔는지 묻는 사람에게 답이 된다.
PREFIX = "com.homespread.demo"

#: 열쇠 → (한국어 이름, 영어 이름). 어느 회사의 제품명도 쓰지 않는다. 홈화면에
#: 흔히 있는 **갈래**를 가리키는 일반 낱말만 골랐다.
APPS: dict[str, tuple[str, str]] = {
    "phone": ("전화", "Phone"),
    "browser": ("브라우저", "Browser"),
    "messages": ("메시지", "Messages"),
    "music": ("음악", "Music"),
    "calendar": ("달력", "Calendar"),
    "gallery": ("갤러리", "Gallery"),
    "camera": ("카메라", "Camera"),
    "weather": ("날씨", "Weather"),
    "mail": ("메일", "Mail"),
    "notes": ("메모", "Notes"),
    "tasks": ("할 일", "Tasks"),
    "clock": ("시계", "Clock"),
    "maps": ("지도", "Maps"),
    "contacts": ("연락처", "Contacts"),
    "videocall": ("영상 통화", "Video Call"),
    "market": ("앱 마켓", "App Market"),
    "health": ("건강", "Health"),
    "workout": ("운동", "Workout"),
    "smarthome": ("스마트홈", "Smart Home"),
    "wallet": ("지갑", "Wallet"),
    "bank": ("은행", "Bank"),
    "budget": ("가계부", "Budget"),
    "settings": ("설정", "Settings"),
    "calculator": ("계산기", "Calculator"),
    "compass": ("나침반", "Compass"),
    "ruler": ("줄자", "Ruler"),
    "recorder": ("녹음", "Recorder"),
    "translate": ("번역", "Translate"),
    "automation": ("자동화", "Automation"),
    "files": ("파일", "Files"),
    "finder": ("기기 찾기", "Find Device"),
    "passwords": ("비밀번호", "Passwords"),
    "stocks": ("주식", "Stocks"),
    "video": ("동영상", "Video"),
    "podcast": ("팟캐스트", "Podcast"),
    "ebook": ("전자책", "eBooks"),
    "shop": ("쇼핑", "Shopping"),
    "games": ("게임", "Games"),
    "sketch": ("그림판", "Sketch"),
    "sheets": ("표 계산", "Spreadsheet"),
    "journal": ("일기", "Journal"),
    "help": ("도움말", "Help"),
    "watch": ("시계 연결", "Wearable"),
    "viewer": ("미리보기", "Viewer"),
}

#: 묶음 이름도 마찬가지로 일반 낱말이다. (한국어, 영어, 페이지들)
FOLDERS: dict[str, tuple[str, str, list[list[str]]]] = {
    "media": ("미디어", "Media", [["video", "podcast", "ebook", "shop", "games"]]),
    "create": ("만들기", "Create", [["sketch", "sheets", "journal"]]),
}

DOCK = ["phone", "browser", "messages", "music"]

# 페이지가 뒤로 갈수록 헐거워지는, 흔한 '늘어난 홈화면'의 모양이다 — 이 앱이
# 풀려는 문제 그 자체라 그림 한 장이 곧 설명이 된다.
PAGES: list[list[str]] = [
    [
        "calendar", "gallery", "camera", "weather",
        "mail", "notes", "tasks", "clock",
        "maps", "contacts", "videocall", "market",
        "health", "workout", "smarthome", "wallet",
        "@media", "@create",
    ],
    ["settings", "calculator", "compass", "ruler", "bank", "recorder", "translate"],
    ["automation", "files", "finder", "passwords", "stocks"],
    ["help", "watch", "viewer"],
]


def identifier(key: str) -> str:
    return f"{PREFIX}.{key}"


def all_app_keys() -> list[str]:
    """배치에 실제로 놓이는 앱 열쇠 — 아이콘을 그려야 할 목록이다."""
    keys = list(DOCK)
    for page in PAGES:
        for entry in page:
            if entry.startswith("@"):
                for folder_page in FOLDERS[entry[1:]][2]:
                    keys.extend(folder_page)
            else:
                keys.append(entry)
    return list(dict.fromkeys(keys))


def _app(key: str, language: str) -> dict:
    ko, en = APPS[key]
    ident = identifier(key)
    # `bundleIdentifier` 가 있어야 '설치된 앱'으로 그려진다. `iconModDate` 는 두지
    # 않는다 — 아이콘 캐시의 신선도 열쇠인데, 시연용 아이콘은 낡을 일이 없다.
    return {
        "displayIdentifier": ident,
        "bundleIdentifier": ident,
        "displayName": ko if language == "ko" else en,
    }


def _folder(key: str, language: str) -> dict:
    ko, en, pages = FOLDERS[key]
    return {
        "displayName": ko if language == "ko" else en,
        "listType": "folder",
        "iconLists": [[_app(child, language) for child in page] for page in pages],
    }


def _slot(entry: str, language: str) -> dict:
    return _folder(entry[1:], language) if entry.startswith("@") else _app(entry, language)


def build(language: str = "ko") -> list:
    return [[_slot(e, language) for e in DOCK]] + [
        [_slot(e, language) for e in page] for page in PAGES
    ]


# 앱 이름은 원래 기기의 언어를 따라온다. 영어 스토어 목록에 한국어 이름이 박힌
# 그림을 올리면 그 나라 사람에게는 읽히지 않는 그림이 된다. 식별자는 그대로라
# 아이콘은 같은 것이 나온다.
_EN_BY_KO: dict[str, str] = {ko: en for ko, en in APPS.values()}
_EN_BY_KO.update({ko: en for ko, en, _ in FOLDERS.values()})


def englishify(state: list) -> list:
    """시연 배치의 이름만 영어로 바꾼 사본을 돌려준다."""

    def walk(items: list) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            name = _EN_BY_KO.get(item.get("displayName", ""))
            if name:
                item["displayName"] = name
            for page in item.get("iconLists") or []:
                walk(page if isinstance(page, list) else [])

    copied = copy.deepcopy(state)
    for page in copied:
        walk(page if isinstance(page, list) else [])
    return copied


if __name__ == "__main__":
    state = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = [len(page) for page in state]
    print(f"{OUT} — 독 {counts[0]}개, 페이지 {counts[1:]}, 아이콘 {len(all_app_keys())}개")
