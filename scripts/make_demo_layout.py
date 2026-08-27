# -*- coding: utf-8 -*-
"""스토어에 올릴 화면 그림용 **시연 배치**를 만든다 — `_workspace/demo-layout.json`.

**왜 사용자의 진짜 배치를 쓰지 않는가:** 스토어 페이지의 그림은 영구히 공개되고,
내린 뒤에도 캐시와 색인에 남는다. 홈화면 그림 한 장은 그 사람이 무슨 앱을 쓰는지
—은행·병원·데이팅·회사—를 통째로 알려준다. 되돌릴 수 없는 공개이므로 기본값은
"보여주지 않는다"여야 한다.

그래서 **Apple 기본 앱만으로** 배치를 지어낸다. 어느 iPhone 에나 있는 앱이라
사적인 것을 드러내지 않으면서도 화면은 진짜처럼 보인다.

항목의 raw 는 지어내지 않고 **기기 백업에서 그대로 꺼내 쓴다.** `iconModDate` 가
아이콘 캐시의 신선도 열쇠라, 손으로 지으면 아이콘을 못 받는다.

    .venv/Scripts/python.exe scripts/make_demo_layout.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "_workspace" / "demo-layout.json"

DOCK = ["com.apple.mobilephone", "com.apple.mobilesafari", "com.apple.MobileSMS", "com.apple.Music"]

# 페이지가 뒤로 갈수록 헐거워지는, 흔한 '늘어난 홈화면'의 모양이다 — 이 앱이
# 풀려는 문제 그 자체라 그림 한 장이 곧 설명이 된다.
PAGES = [
    [
        "com.apple.mobilecal",
        "com.apple.mobileslideshow",
        "com.apple.camera",
        "com.apple.weather",
        "com.apple.mobilemail",
        "com.apple.mobilenotes",
        "com.apple.reminders",
        "com.apple.mobiletimer",
        "com.apple.Maps",
        "com.apple.MobileAddressBook",
        "com.apple.facetime",
        "com.apple.AppStore",
        "com.apple.Health",
        "com.apple.Fitness",
        "com.apple.Home",
        "com.apple.Passbook",
        ("Apple 미디어", [["com.apple.tv", "com.apple.podcasts", "com.apple.iBooks",
                          "com.apple.MobileStore", "com.apple.games"]]),
        ("만들기", [["com.apple.freeform", "com.apple.Numbers", "com.apple.journal"]]),
    ],
    [
        "com.apple.Preferences",
        "com.apple.calculator",
        "com.apple.compass",
        "com.apple.measure",
        "com.apple.Magnifier",
        "com.apple.VoiceMemos",
        "com.apple.Translate",
    ],
    [
        "com.apple.shortcuts",
        "com.apple.DocumentsApp",
        "com.apple.findmy",
        "com.apple.Passwords",
        "com.apple.stocks",
    ],
    [
        "com.apple.tips",
        "com.apple.Bridge",
        "com.apple.Preview",
    ],
]


def _catalog() -> dict[str, dict]:
    """기기 백업에서 항목 raw 를 모은다 (Apple 기본 앱만)."""
    backups = sorted((ROOT / "backups").glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not backups:
        raise SystemExit("backups/*.json 이 없다 — 기기에서 한 번 읽어야 한다")

    found: dict[str, dict] = {}

    def walk(items: list) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            if "iconLists" in item:
                for page in item["iconLists"]:
                    walk(page if isinstance(page, list) else [])
                continue
            ident = item.get("displayIdentifier", "")
            if ident.startswith("com.apple.") and ident not in found:
                found[ident] = item

    for page in json.loads(backups[-1].read_text(encoding="utf-8")):
        walk(page if isinstance(page, list) else [])
    return found


def _slot(entry, catalog: dict[str, dict]) -> dict:
    if isinstance(entry, tuple):
        name, pages = entry
        return {
            "displayName": name,
            "listType": "folder",
            "iconLists": [[_slot(child, catalog) for child in page] for page in pages],
        }
    item = catalog.get(entry)
    if item is None:
        raise SystemExit(f"백업에 없는 앱이다: {entry}")
    return item


# 앱 이름은 기기의 언어를 따라온다 — 우리가 가진 기기가 한국어라 이름도 한국어로
# 온다. 영어 스토어 목록에 한국어 이름이 박힌 그림을 올리면 그 나라 사람에게는
# 읽히지 않는 그림이 된다. 그래서 **시연 배치에 한해** 이름만 영어로 갈아 끼운다
# (식별자와 `iconModDate` 는 그대로라 아이콘은 같은 것이 나온다).
EN_NAMES = {
    "com.apple.mobilephone": "Phone",
    "com.apple.mobilesafari": "Safari",
    "com.apple.MobileSMS": "Messages",
    "com.apple.Music": "Music",
    "com.apple.mobilecal": "Calendar",
    "com.apple.mobileslideshow": "Photos",
    "com.apple.camera": "Camera",
    "com.apple.weather": "Weather",
    "com.apple.mobilemail": "Mail",
    "com.apple.mobilenotes": "Notes",
    "com.apple.reminders": "Reminders",
    "com.apple.mobiletimer": "Clock",
    "com.apple.Maps": "Maps",
    "com.apple.MobileAddressBook": "Contacts",
    "com.apple.facetime": "FaceTime",
    "com.apple.AppStore": "App Store",
    "com.apple.Health": "Health",
    "com.apple.Fitness": "Fitness",
    "com.apple.Home": "Home",
    "com.apple.Passbook": "Wallet",
    "com.apple.tv": "TV",
    "com.apple.podcasts": "Podcasts",
    "com.apple.iBooks": "Books",
    "com.apple.MobileStore": "iTunes Store",
    "com.apple.games": "Games",
    "com.apple.freeform": "Freeform",
    "com.apple.Numbers": "Numbers",
    "com.apple.journal": "Journal",
    "com.apple.Preferences": "Settings",
    "com.apple.calculator": "Calculator",
    "com.apple.compass": "Compass",
    "com.apple.measure": "Measure",
    "com.apple.Magnifier": "Magnifier",
    "com.apple.VoiceMemos": "Voice Memos",
    "com.apple.Translate": "Translate",
    "com.apple.shortcuts": "Shortcuts",
    "com.apple.DocumentsApp": "Files",
    "com.apple.findmy": "Find My",
    "com.apple.Passwords": "Passwords",
    "com.apple.stocks": "Stocks",
    "com.apple.tips": "Tips",
    "com.apple.Bridge": "Watch",
    "com.apple.Preview": "Preview",
    "Apple 미디어": "Apple Media",
    "만들기": "Create",
}


def englishify(state: list) -> list:
    """시연 배치의 이름만 영어로 바꾼 사본을 돌려준다."""
    import copy

    def walk(items: list) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            if "iconLists" in item:
                name = EN_NAMES.get(item.get("displayName", ""))
                if name:
                    item["displayName"] = name
                for page in item["iconLists"]:
                    walk(page if isinstance(page, list) else [])
                continue
            name = EN_NAMES.get(item.get("displayIdentifier", ""))
            if name:
                item["displayName"] = name

    copied = copy.deepcopy(state)
    for page in copied:
        walk(page if isinstance(page, list) else [])
    return copied


def build() -> list:
    catalog = _catalog()
    return [[_slot(e, catalog) for e in DOCK]] + [
        [_slot(e, catalog) for e in page] for page in PAGES
    ]


if __name__ == "__main__":
    state = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = [len(page) for page in state]
    print(f"{OUT} — 독 {counts[0]}개, 페이지 {counts[1:]}")
