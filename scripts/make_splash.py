# -*- coding: utf-8 -*-
"""시작 그림(splash)을 그린다 — `assets/splash.png`.

**왜 그림 파일을 손으로 만들지 않는가:** 이름과 부제는 `product.py` 한 곳에서만
선언하기로 했다(상표 지침 때문이다). 그림을 손으로 만들어 두면 이름을 바꿀 때
아무도 그림을 고치지 않는다. 그래서 그림도 `product` 를 읽어 그린다.

**왜 이 그림이 필요한가:** 단일 exe 는 실행할 때마다 자기 안을 임시 폴더에 푼다.
그동안에는 우리 파이썬 코드가 아직 시작조차 하지 않았으므로 Qt 로는 아무것도
띄울 수 없다. PyInstaller 의 부트로더가 직접 띄우는 이 그림만이 그 구간을 채운다.

    .venv/Scripts/python.exe scripts/make_splash.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter  # noqa: E402

from ipsm import product  # noqa: E402

WIDTH, HEIGHT = 460, 220
OUT = ROOT / "assets" / "splash.png"

# 창의 어두운 바탕과 같은 색을 쓴다. 그림이 사라지고 창이 뜰 때 색이 튀지 않는다.
BACK = QColor("#1b1e26")
EDGE = QColor("#2c3245")
NAME = QColor("#f0f3fa")
SUB = QColor("#a8b0c2")
HINT = QColor("#7f8899")


def draw() -> Path:
    # 여기서 offscreen 플랫폼을 쓰지 않는다 — 글꼴을 하나도 못 찾아 글자가 전부
    # 네모(두부)로 그려진다. 창을 만들지 않고 QImage 에만 그리므로 기본 플랫폼으로
    # 충분하다.
    app = QGuiApplication.instance() or QGuiApplication([])

    image = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32)
    image.fill(BACK)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    painter.setPen(EDGE)
    painter.drawRect(QRect(0, 0, WIDTH - 1, HEIGHT - 1))

    painter.setPen(NAME)
    painter.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
    painter.drawText(
        QRect(0, 58, WIDTH, 48), Qt.AlignmentFlag.AlignHCenter, product.NAME
    )

    painter.setPen(SUB)
    painter.setFont(QFont("Segoe UI", 11))
    painter.drawText(
        QRect(0, 108, WIDTH, 24), Qt.AlignmentFlag.AlignHCenter, product.TAGLINE
    )

    painter.setPen(HINT)
    painter.setFont(QFont("Segoe UI", 10))
    # 이 문구는 옮기지 않는다 — 그림은 언어 설정을 읽기 전에 뜬다.
    painter.drawText(
        QRect(0, 150, WIDTH, 22),
        Qt.AlignmentFlag.AlignHCenter,
        "시작하는 중입니다  ·  Starting…",
    )
    painter.end()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    assert image.save(str(OUT), "PNG"), "그림을 저장하지 못했다"
    del app
    return OUT


if __name__ == "__main__":
    path = draw()
    print(f"{path} ({path.stat().st_size} bytes)")
