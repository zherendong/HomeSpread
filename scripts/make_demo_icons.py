# -*- coding: utf-8 -*-
"""시연 배치에 쓸 **아이콘을 직접 그린다** — `_workspace/demo-cache/icons/`.

**왜 그리는가:** 예전에는 기기 캐시에 있는 진짜 아이콘을 그대로 스토어 그림에 실었다.
그것은 Apple 의 저작물이고(정책 11.2), 화면을 가득 채우면 심사자에게는 그냥 iPhone
화면으로 보인다(정책 10.1.1 — 실제로 이것으로 거절됐다). 우리가 그린 것이면 두 문제가
한꺼번에 없어진다.

**왜 글자가 아니라 도형인가:** 아이콘은 식별자 하나에 그림 하나이고, 그림 하나를
한국어 목록과 영어 목록이 함께 쓴다. 첫 글자를 새기면 한쪽 언어에서는 이름과 아이콘이
어긋난다. 도형은 어느 언어에도 매이지 않는다.

**왜 `zlib.crc32` 인가:** 파이썬의 `hash()` 는 실행마다 소금이 달라 같은 앱이 어제와
다른 색으로 나온다. 그림을 다시 만들 때마다 배치가 달라 보이면 그것은 재현이 아니다.

    .venv/Scripts/python.exe scripts/make_demo_icons.py
"""

from __future__ import annotations

import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QBrush,
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)

from ipsm.icons import _filename  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from make_demo_layout import all_app_keys, identifier  # noqa: E402

DEST = ROOT / "_workspace" / "demo-cache" / "icons"
SIZE = 180

#: 바탕색 12벌. 각각 (위쪽, 아래쪽)이라 타일에 옅은 기울기가 생긴다.
PALETTE: list[tuple[str, str]] = [
    ("#4C7EF3", "#2F55C4"),   # 파랑
    ("#37B98A", "#1E8A64"),   # 초록
    ("#F2A33C", "#D07A16"),   # 주황
    ("#E4655E", "#B93D3D"),   # 빨강
    ("#8A6BE0", "#5F42B5"),   # 보라
    ("#3AAEC4", "#217D93"),   # 청록
    ("#D96BA8", "#A9407C"),   # 분홍
    ("#6E7B8B", "#4A5666"),   # 회청
    ("#C9A227", "#96760F"),   # 금
    ("#5A9E4B", "#3B7530"),   # 풀
    ("#E07B39", "#B0561F"),   # 호박
    ("#4E63A6", "#2F3F76"),   # 남색
]

MARKS = 10  # 아래 `_mark` 가 그릴 수 있는 도형의 수


def _seed(ident: str) -> int:
    return zlib.crc32(ident.encode("utf-8"))


def _mark(painter: QPainter, kind: int, box: QRectF) -> None:
    """가운데 칸 `box` 안에 흰 도형 하나를 그린다."""
    ink = QColor(255, 255, 255, 235)
    width = box.width() * 0.14
    pen = QPen(ink, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
               Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    cx, cy = box.center().x(), box.center().y()
    w, h = box.width(), box.height()

    if kind == 0:  # 고리
        painter.drawEllipse(box.adjusted(width / 2, width / 2, -width / 2, -width / 2))
    elif kind == 1:  # 채운 원
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(ink))
        painter.drawEllipse(box)
    elif kind == 2:  # 둥근 네모 테두리
        painter.drawRoundedRect(
            box.adjusted(width / 2, width / 2, -width / 2, -width / 2), w * 0.2, w * 0.2
        )
    elif kind == 3:  # 가로 줄 셋
        for i, ratio in enumerate((1.0, 0.72, 0.86)):
            y = box.top() + h * (0.2 + i * 0.3)
            half = w * 0.5 * ratio
            painter.drawLine(QPointF(cx - half, y), QPointF(cx + half, y))
    elif kind == 4:  # 삼각형
        path = QPainterPath(QPointF(cx, box.top() + h * 0.08))
        path.lineTo(QPointF(box.right() - w * 0.06, box.bottom() - h * 0.1))
        path.lineTo(QPointF(box.left() + w * 0.06, box.bottom() - h * 0.1))
        path.closeSubpath()
        painter.drawPath(path)
    elif kind == 5:  # 갈매기표
        path = QPainterPath(QPointF(cx - w * 0.22, cy - h * 0.28))
        path.lineTo(QPointF(cx + w * 0.24, cy))
        path.lineTo(QPointF(cx - w * 0.22, cy + h * 0.28))
        painter.drawPath(path)
    elif kind == 6:  # 점 넷
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(ink))
        radius = w * 0.13
        for dx in (-w * 0.21, w * 0.21):
            for dy in (-h * 0.21, h * 0.21):
                painter.drawEllipse(QPointF(cx + dx, cy + dy), radius, radius)
    elif kind == 7:  # 겹친 원 둘
        radius = w * 0.27
        painter.drawEllipse(QPointF(cx - w * 0.14, cy), radius, radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 150)))
        painter.drawEllipse(QPointF(cx + w * 0.14, cy), radius, radius)
    elif kind == 8:  # 막대 그래프
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(ink))
        bar = w * 0.17
        for i, ratio in enumerate((0.42, 0.78, 0.58)):
            x = box.left() + w * (0.16 + i * 0.29)
            top = box.bottom() - h * ratio
            painter.drawRoundedRect(
                QRectF(x, top, bar, box.bottom() - top), bar / 2, bar / 2
            )
    else:  # 열십자
        painter.drawLine(QPointF(cx, cy - h * 0.3), QPointF(cx, cy + h * 0.3))
        painter.drawLine(QPointF(cx - w * 0.3, cy), QPointF(cx + w * 0.3, cy))


def render(ident: str, size: int = SIZE) -> QImage:
    seed = _seed(ident)
    top, bottom = PALETTE[seed % len(PALETTE)]
    kind = (seed // len(PALETTE)) % MARKS

    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    gradient = QLinearGradient(0, 0, 0, size)
    gradient.setColorAt(0.0, QColor(top))
    gradient.setColorAt(1.0, QColor(bottom))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(gradient))
    radius = size * 0.24
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

    inset = size * 0.3
    _mark(painter, kind, QRectF(inset, inset, size - inset * 2, size - inset * 2))
    painter.end()
    return image


def build(dest: Path = DEST) -> list[Path]:
    """시연 배치에 놓이는 앱 전부의 아이콘을 그려 `IconStore` 가 읽는 모양으로 둔다."""
    QGuiApplication.instance() or QGuiApplication([])
    dest.mkdir(parents=True, exist_ok=True)
    made: list[Path] = []
    for key in all_app_keys():
        ident = identifier(key)
        path = dest / _filename(ident)
        assert render(ident).save(str(path), "PNG"), f"{path} 를 저장하지 못했다"
        made.append(path)
    return made


if __name__ == "__main__":
    made = build()
    print(f"{DEST} — 아이콘 {len(made)}개")
