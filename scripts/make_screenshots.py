# -*- coding: utf-8 -*-
"""스토어 목록에 올릴 화면 그림을 찍는다 — `_workspace/screenshots/`.

**왜 손으로 찍지 않는가:** 스토어 그림은 1366×768 이상이어야 하고, 여러 장을 같은
크기·같은 배치로 맞춰야 보기 좋다. 손으로 찍으면 창 크기가 매번 달라지고, 이름을
바꿀 때마다 다시 찍는 일을 아무도 하지 않는다. 그림도 코드가 그리면 `product` 를
따라온다.

**무엇을 찍는가:** 기기의 진짜 배치가 아니라 `scripts/make_demo_layout.py` 가 지어낸
**아무의 것도 아닌 시연 배치**다. 아이콘도 `scripts/make_demo_icons.py` 가 그린
것이라 기기도 백업도 필요 없다. 이유는 그 두 스크립트에 적었다.

**왜 창테두리까지 찍는가(2026-08-31):** `window.grab()` 은 창의 **속**만 찍는다.
제목 표시줄도 테두리도 없는 그림은 그 자체로는 무엇 위에서 도는 프로그램인지
말해 주지 않는다. 스토어 인증이 "Windows 가 아닌 UI 로 보인다"며 거절한 그림이
그것이었다. 그래서 화면에 실제로 떠 있는 창을 **Windows 가 그린 제목 표시줄째로**
잘라 온다. 제목 표시줄에는 `product.NAME` 과 판 번호가 적혀 있다.

    .venv/Scripts/python.exe scripts/make_screenshots.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import ipsm.ui.worker as worker_module  # noqa: E402
from ipsm.i18n import set_language  # noqa: E402
from ipsm.ui.main_window import MainWindow  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import make_demo_icons  # noqa: E402
from make_demo_layout import build as build_layout, englishify  # noqa: E402

DEMO = ROOT / "_workspace" / "demo-layout.json"
CACHE = ROOT / "_workspace" / "demo-cache"
OUT = ROOT / "_workspace" / "screenshots"

# 스토어가 요구하는 최소는 1366×768 이다. 그보다 넉넉히 잡아야 축소됐을 때 글씨가
# 뭉개지지 않는다. 창테두리가 더해지므로 실제 그림은 이보다 조금 크다.
SIZE = (1760, 880)


def tr_name(language: str) -> str:
    return "미디어" if language == "ko" else "Media"


def _use_demo_icons() -> None:
    """기기 아이콘 대신 우리가 그린 것을 쓰게 한다.

    `Worker` 가 `cache_root()` 로 자리를 묻는 그 이름 하나만 갈아 끼운다 — 제품
    코드에 '그림 찍을 때만'을 위한 갈림길을 두지 않기 위해서다.
    """
    make_demo_icons.build(CACHE / "icons")
    worker_module.cache_root = lambda: CACHE


def _fingerprint(pixmap: QPixmap) -> QImage:
    """그림 두 장을 견주기 위한 아주 작은 회색 축소판."""
    return (
        pixmap.toImage()
        .scaled(96, 96, Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
        .convertToFormat(QImage.Format.Format_Grayscale8)
    )


def _difference(a: QImage, b: QImage) -> float:
    """두 축소판의 평균 밝기 차(0~255). 같은 그림이면 0에 가깝다."""
    total = 0
    for y in range(a.height()):
        for x in range(a.width()):
            total += abs(a.pixelColor(x, y).red() - b.pixelColor(x, y).red())
    return total / (a.width() * a.height())


def _grab(window, app: QApplication) -> QPixmap:
    """화면에 떠 있는 창을 **Windows 제목 표시줄째로** 잘라 온다.

    **왜 잘라 온 것을 다시 확인하는가(2026-08-31):** 화면을 잘라 오는 일은 그 자리에
    무엇이 있든 그대로 가져온다. 우리 창이 앞에 서지 못한 첫 시도에서 실제로 **다른
    프로그램의 창**(대화·메일·달력)이 그림에 담겼다. 스토어 그림은 영구히 공개되므로
    이런 그림 한 장은 되돌릴 수 없는 유출이다. 그래서 잘라 온 것의 **창 속**을
    `window.grab()` 이 그린 것과 견주어, 우리 창이 아니면 **저장하지 않고 멈춘다.**
    """
    window.raise_()
    window.activateWindow()
    for _ in range(4):
        app.processEvents()
    time.sleep(0.4)  # 표시줄이 활성 상태로 다시 그려질 틈
    app.processEvents()

    screen = window.screen() or app.primaryScreen()
    frame, inner = window.frameGeometry(), window.geometry()
    shot = screen.grabWindow(0, frame.x(), frame.y(), frame.width(), frame.height())
    if shot.isNull():
        raise SystemExit("[X] 화면을 잘라 오지 못했다 — 그림을 남기지 않는다")

    # 잘라 온 것 안에서 '창 속'이 있어야 할 자리. 화면 배율이 걸리면 잘라 온 그림이
    # 더 클 수 있으므로 비율로 환산한다.
    scale = shot.width() / frame.width()
    region = shot.copy(
        round((inner.x() - frame.x()) * scale), round((inner.y() - frame.y()) * scale),
        round(inner.width() * scale), round(inner.height() * scale),
    )
    gap = _difference(_fingerprint(region), _fingerprint(window.grab()))
    if gap > 24.0:
        raise SystemExit(
            f"[X] 잘라 온 그림이 우리 창이 아니다 (차이 {gap:.1f}). 다른 창이 위에\n"
            "    있었을 수 있다. 그림을 남기지 않았다 — 화면을 비우고 다시 실행하라."
        )
    return shot


def shoot(language: str, suffix: str) -> list[Path]:
    set_language(language)

    app = QApplication.instance() or QApplication([])
    window = MainWindow(ROOT)
    # 다른 창 위에 세운다. 화면을 잘라 오는 방식이라 우리 창이 가려지면 그 순간
    # 남의 창이 그림에 담긴다 — 아래 `_grab` 의 확인과 함께 두 겹으로 막는다.
    window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    window.resize(*SIZE)
    window.show()
    app.processEvents()

    OUT.mkdir(parents=True, exist_ok=True)
    made: list[Path] = []

    def grab(name: str) -> None:
        for _ in range(4):
            app.processEvents()
        path = OUT / f"{name}_{suffix}.png"
        assert _grab(window, app).save(str(path), "PNG"), f"{path} 를 저장하지 못했다"
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
    # 창을 만들 수 있는 `QApplication` 을 **가장 먼저** 세운다. 아이콘을 그리는 쪽은
    # 화면이 필요 없어 `QGuiApplication` 으로 족한데, 그것이 먼저 서 버리면
    # `QApplication.instance()` 가 그 반쪽짜리를 돌려주고 창을 만들 수 없다.
    QApplication.instance() or QApplication([])

    # 배치와 아이콘을 먼저 갖춘다 — 저장소만 받은 사람도 이 한 줄로 그림까지 간다.
    DEMO.parent.mkdir(parents=True, exist_ok=True)
    DEMO.write_text(json.dumps(build_layout(), ensure_ascii=False, indent=1), encoding="utf-8")
    _use_demo_icons()

    made = shoot("ko", "ko") + shoot("en", "en")
    for path in made:
        print(f"{path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")
