# -*- coding: utf-8 -*-
"""앱 표시를 그린다 — MSIX 로고 한 벌과 exe 아이콘(`assets/`).

**왜 그림을 손으로 만들지 않는가:** 시작 그림과 같은 이유다. 손으로 만든 그림은
이름이나 색이 바뀔 때 아무도 따라 고치지 않는다. 크기만 열 가지가 넘는 MSIX
로고라면 더 그렇다. 그래서 한 벌을 코드가 그린다.

**왜 어두운 판을 함께 그리는가:** 투명 배경에 밝은 글리프만 두면 밝은 테마의
작업 표시줄에서 사라진다. 반대로 어두운 판을 깔면 어디서든 보인다. 판의 색은
매니페스트의 `BackgroundColor` 와 같아서, 타일의 남는 자리와 이어져 보인다.

**표시가 뜻하는 것:** 펼쳐 놓은 페이지 석 장. 가운데 한 장만 밝은 것은 여러 장을
한 화면에 펼쳐 놓고 그중 하나를 다루는 이 프로그램의 일이다.

    .venv/Scripts/python.exe scripts/make_logos.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402

OUT = ROOT / "assets" / "logo"

# 시작 그림과 같은 색을 쓴다. 여기서 색이 갈리면 설치 목록과 시작 화면이 다른
# 프로그램처럼 보인다.
PLATE = QColor("#1b1e26")
PAGE_DIM = QColor("#6b7699")
PAGE_LIT = QColor("#f0f3fa")

#: MSIX 가 요구하는 이름과 크기. 이름은 매니페스트가 그대로 가리킨다.
TILES = {
    "Square44x44Logo.png": (44, 44),
    "Square71x71Logo.png": (71, 71),
    "Square150x150Logo.png": (150, 150),
    "Square310x310Logo.png": (310, 310),
    "Wide310x150Logo.png": (310, 150),
    "StoreLogo.png": (50, 50),
    # 배율 변형. Windows 는 화면 배율에 따라 이 중 하나를 고른다. 없으면 기본을
    # 늘려 쓰므로 200% 화면에서 흐려진다.
    "Square44x44Logo.scale-200.png": (88, 88),
    "Square150x150Logo.scale-200.png": (300, 300),
    "StoreLogo.scale-200.png": (100, 100),
    # 목록 아이콘은 배율이 아니라 '목표 크기'로도 요청된다.
    "Square44x44Logo.targetsize-16.png": (16, 16),
    "Square44x44Logo.targetsize-24.png": (24, 24),
    "Square44x44Logo.targetsize-32.png": (32, 32),
    "Square44x44Logo.targetsize-48.png": (48, 48),
    "Square44x44Logo.targetsize-256.png": (256, 256),
}

#: 스토어 목록 페이지가 따로 요구하는 크기(300x300 이상).
STORE_LISTING = ("store-listing-300.png", (300, 300))

#: exe 에 박을 아이콘에 들어갈 크기들.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _draw(width: int, height: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    # 어두운 판. 정사각형일 때만 모서리를 둥글린다 — 넓은 타일은 꽉 채워야 한다.
    painter.setBrush(PLATE)
    if width == height:
        radius = width * 0.22
        painter.drawRoundedRect(QRectF(0, 0, width, height), radius, radius)
    else:
        painter.drawRect(QRectF(0, 0, width, height))

    # 표시가 놓일 자리. 정사각형 판 안에서 여백을 남긴다.
    side = min(width, height)
    box = side * 0.60
    left = (width - box) / 2.0
    top = (height - box) / 2.0

    page_w = box * 0.26
    gap = box * 0.11
    for index in range(3):
        lit = index == 1
        page_h = box * (0.96 if lit else 0.74)
        x = left + index * (page_w + gap)
        y = top + (box - page_h) / 2.0
        painter.setBrush(PAGE_LIT if lit else PAGE_DIM)
        corner = page_w * 0.22
        painter.drawRoundedRect(QRectF(x, y, page_w, page_h), corner, corner)

        # 가운데 장에만 아이콘 격자를 넣는다. 작은 크기에서는 점이 뭉개져
        # 오히려 지저분해지므로 넣지 않는다.
        if lit and side >= 64:
            painter.setBrush(PLATE)
            dot = page_w * 0.24
            cols, rows = 2, 3
            span_x = page_w * 0.62
            span_y = page_h * 0.62
            ox = x + (page_w - span_x) / 2.0
            oy = y + (page_h - span_y) / 2.0
            for r in range(rows):
                for c in range(cols):
                    cx = ox + c * (span_x - dot) / (cols - 1)
                    cy = oy + r * (span_y - dot) / (rows - 1)
                    painter.drawRoundedRect(
                        QRectF(cx, cy, dot, dot), dot * 0.3, dot * 0.3
                    )

    painter.end()
    return image


def draw() -> list[Path]:
    app = QGuiApplication.instance() or QGuiApplication([])
    OUT.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for name, (width, height) in TILES.items():
        path = OUT / name
        assert _draw(width, height).save(str(path), "PNG"), name
        written.append(path)

    name, (width, height) = STORE_LISTING
    path = ROOT / "assets" / name
    assert _draw(width, height).save(str(path), "PNG"), name
    written.append(path)

    # exe 아이콘. Qt 의 ICO 쓰기는 크기를 하나만 담으므로 Pillow 로 엮는다 —
    # 16px 자리에 256px 그림을 밀어 넣으면 작업 표시줄에서 뭉개진다.
    from PIL import Image

    biggest = OUT / "Square44x44Logo.targetsize-256.png"
    ico = ROOT / "assets" / "app.ico"
    Image.open(biggest).save(ico, sizes=[(s, s) for s in ICO_SIZES])
    written.append(ico)

    del app
    return written


if __name__ == "__main__":
    for item in draw():
        print(f"{item.relative_to(ROOT)} ({item.stat().st_size} bytes)")
