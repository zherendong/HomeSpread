# -*- coding: utf-8 -*-
"""스토어 목록에 올릴 화면 그림을 찍는다 — `_workspace/screenshots/`.

**왜 손으로 찍지 않는가:** 스토어 그림은 1366×768 이상이어야 하고, 여러 장을 같은
크기·같은 배치로 맞춰야 보기 좋다. 손으로 찍으면 창 크기가 매번 달라지고, 이름을
바꿀 때마다 다시 찍는 일을 아무도 하지 않는다. 그림도 코드가 그리면 `product` 를
따라온다.

**무엇을 찍는가:** 기기의 진짜 배치가 아니라 `scripts/make_demo_layout.py` 가 지어낸
**Apple 기본 앱만의 시연 배치**다. 이유는 그 스크립트에 적었다 — 스토어 페이지는
영구히 공개되고 되돌릴 수 없다.

기기는 필요 없다. 아이콘만 캐시에 있으면 된다(`make_demo_layout.py` 참고).

    .venv/Scripts/python.exe scripts/make_screenshots.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from ipsm.i18n import set_language  # noqa: E402
from ipsm.ui.main_window import MainWindow  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from make_demo_layout import englishify  # noqa: E402

DEMO = ROOT / "_workspace" / "demo-layout.json"
OUT = ROOT / "_workspace" / "screenshots"

# 스토어가 요구하는 최소는 1366×768 이다. 그보다 넉넉히 잡아야 축소됐을 때 글씨가
# 뭉개지지 않는다.
SIZE = (1760, 880)


def tr_name(language: str) -> str:
    return "미디어" if language == "ko" else "Media"


def shoot(language: str, suffix: str) -> list[Path]:
    set_language(language)

    app = QApplication.instance() or QApplication([])
    window = MainWindow(ROOT)
    window.resize(*SIZE)
    window.show()
    app.processEvents()

    OUT.mkdir(parents=True, exist_ok=True)
    made: list[Path] = []

    def grab(name: str) -> None:
        for _ in range(4):
            app.processEvents()
        path = OUT / f"{name}_{suffix}.png"
        assert window.grab().save(str(path), "PNG"), f"{path} 를 저장하지 못했다"
        made.append(path)

    # 기기를 붙이기 전에 처음 보이는 화면. 심사자의 PC 에는 iPhone 이 없으므로
    # 그 사람이 실제로 보게 될 화면이기도 하다.
    for _ in range(6):
        app.processEvents()
    grab("04_guide")

    state = json.loads(DEMO.read_text(encoding="utf-8"))
    if language != "ko":
        state = englishify(state)
    window._set_document(state, None)
    for _ in range(8):
        app.processEvents()

    # 다섯 장을 한눈에 — 이 앱의 이름값이 그 한 장에 들어 있다.
    window._fit()
    for _ in range(8):
        app.processEvents()

    grab("01_spread")

    # 편집한 뒤의 모습 — 오른쪽에 '무엇이 바뀌는지'가 줄줄이 서고, 그때서야
    # '적용'이 켜진다. 이 앱의 안전 규약이 그림 한 장에 들어 있는 자리다.
    doc = window.doc
    last = doc.pages[-1]
    first = doc.pages[0]
    for node in list(last.items):
        doc.move(node.uid, first.uid, len(first.items))
    doc.rename_folder(
        next(n.uid for n in first.items if n.is_folder), tr_name(language)
    )
    window._refresh()
    grab("03_changes")

    # 묶음 하나를 펼친 모습. 폴더 편집이 되는 앱이라는 것은 펼친 그림으로만 보인다.
    for page in window.doc.pages:
        folder = next((node for node in page.items if node.is_folder), None)
        if folder is not None:
            window._open_folder(folder.uid)
            grab("02_folder")
            window._close_folder()
            break

    # 편집을 되돌려 놓고 닫는다. 그러지 않으면 창이 "적용하지 않은 변경이 있습니다"
    # 라고 물으며 멈춰 선다 — 사람이 없는 자리에서는 아무도 대답하지 않는다.
    while window.doc.can_undo:
        window.doc.undo()
    window.close()
    app.processEvents()
    return made


if __name__ == "__main__":
    made = shoot("ko", "ko") + shoot("en", "en")
    for path in made:
        print(f"{path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")
