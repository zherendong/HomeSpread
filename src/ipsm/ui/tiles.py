"""한 자리(독·페이지·폴더 페이지)를 그리고, 그 위의 드래그를 받는 위젯.

아이콘 하나마다 위젯을 두지 않고 **한 위젯이 자기 칸을 전부 그린다.** 항목이 300개를
넘고 페이지를 한 화면에 다 펼치는 것이 이 앱의 요구(REQ-012)이므로, 위젯 300개를
만들면 확대·축소마다 레이아웃이 300번 다시 계산된다. 직접 그리면 칸 계산이 산술 한 줄로
끝나고, 그 산술이 곧 드롭 위치 계산이기도 하다 — 그리는 자리와 떨어지는 자리가 같은
식에서 나오므로 둘이 어긋날 수 없다.

옮길 수 있는가는 **이 파일에서 판단하지 않는다.** 전부 `LayoutDocument.can_move()` 에
묻는다. 규칙을 화면과 모델 양쪽에 적으면 반드시 어긋나고, 어긋난 쪽이 화면이면 사용자는
막혀야 할 곳에 놓을 수 있다고 믿게 된다.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QMimeData, QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDrag,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from ..i18n import tr
from ..layout import Container, LayoutDocument, LayoutError, Node
from ..placement import place_items

log = logging.getLogger("ui.tiles")

MIME_NODE = "application/x-ipsm-node"

# 폴더 안으로 떨어뜨리는 판정 영역. 아이콘 한가운데 이 비율 안에 커서가 있으면
# '폴더 안'으로, 밖이면 '폴더 옆'으로 본다. 둘 다 필요하다 — 폴더 옆에 아이콘을
# 끼워 넣지 못하면 폴더가 많은 페이지는 편집이 불가능해진다.
_FOLDER_ZONE = 0.62

PAGE_BG = QColor(38, 42, 54)
PAGE_BG_HOVER = QColor(46, 52, 68)
SLOT_LINE = QColor(255, 255, 255, 22)
LABEL_FG = QColor(236, 238, 244)
LABEL_DIM = QColor(236, 238, 244, 130)
CARET = QColor(90, 170, 255)
RING_OK = QColor(90, 200, 140)
RING_BAD = QColor(230, 96, 96)
FOLDER_BG = QColor(255, 255, 255, 38)
PLACEHOLDER_BG = QColor(120, 128, 150)
UNKNOWN_BG = QColor(90, 94, 110)
SELECT_RING = QColor(255, 214, 90)


class IconCache:
    """식별자 → QPixmap. 원본은 `IconStore` 가 디스크에 들고 있고 여기서는 그린 것만 캔다."""

    def __init__(self, store) -> None:
        self.store = store
        self._full: dict[str, Optional[QPixmap]] = {}
        self._scaled: dict[tuple[str, int], QPixmap] = {}

    def clear_scaled(self) -> None:
        self._scaled.clear()

    def invalidate(self) -> None:
        self._full.clear()
        self._scaled.clear()

    def pixmap(self, identifier: Optional[str], size: int) -> Optional[QPixmap]:
        if not identifier:
            return None
        key = (identifier, size)
        hit = self._scaled.get(key)
        if hit is not None:
            return hit
        if identifier not in self._full:
            data = self.store.get(identifier)
            pixmap = QPixmap()
            if not data or not pixmap.loadFromData(data, "PNG"):
                self._full[identifier] = None
            else:
                self._full[identifier] = pixmap
        source = self._full.get(identifier)
        if source is None:
            return None
        scaled = source.scaled(
            size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self._scaled[key] = scaled
        return scaled


class ContainerView(QWidget):
    """자리 하나를 그리는 판. 독이든 페이지든 폴더 페이지든 같은 판을 쓴다."""

    edited = Signal()  # 문서가 바뀌었다 — 화면 전체를 다시 그려야 한다
    folderRequested = Signal(str)  # 폴더 노드 uid — 폴더를 열어 달라
    statusChanged = Signal(str)  # 상태줄에 띄울 한 줄
    selected = Signal(str)  # 항목 uid (없으면 빈 문자열) — 그냥 누른 것
    toggled = Signal(str)  # 항목 uid — Ctrl 을 누른 채 눌러 선택에 더하거나 뺀 것
    grouped = Signal(str, str)  # 끌어온 uid, 위에 놓인 uid — 둘을 묶어 달라

    def __init__(
        self,
        document: LayoutDocument,
        container_uid: str,
        columns: int,
        rows: int,
        icons: IconCache,
        tile: int = 64,
        parent: Optional[QWidget] = None,
        *,
        read_only: bool = False,
    ) -> None:
        super().__init__(parent)
        self.doc = document
        self.container_uid = container_uid
        self.columns = max(1, columns)
        self.rows = max(1, rows)
        self.icons = icons
        self.tile = tile
        self.selected_uids: set[str] = set()
        self.read_only = read_only

        self._press_pos: Optional[QPoint] = None
        self._press_index: Optional[int] = None
        self._hover_index: Optional[int] = None
        self._drop_index: Optional[int] = None
        self._drop_folder: Optional[int] = None  # 폴더/묶기 대상 칸 (테두리를 그린다)
        self._drop_group: Optional[str] = None  # 놓으면 새 묶음이 되는 상대 노드 uid
        self._drop_bad = False

        self.setAcceptDrops(self.editing_enabled)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    # ------------------------------------------------------------- 기하

    @property
    def container(self) -> Optional[Container]:
        try:
            return self.doc.container(self.container_uid)
        except LayoutError:
            return None  # 페이지가 지워진 직후 다시 그려질 수 있다

    @property
    def editing_enabled(self) -> bool:
        return not self.read_only and not self.doc.readonly_reason

    def placement(self):
        container = self.container
        return place_items(container.items if container else [], self.columns, self.rows)

    def set_read_only(self, value: bool) -> None:
        self.read_only = value
        self.setAcceptDrops(self.editing_enabled)
        self._press_pos = None
        self._clear_drop()

    @property
    def _pad(self) -> int:
        return max(6, self.tile // 8)

    @property
    def _label_h(self) -> int:
        return max(11, int(self.tile * 0.30))

    @property
    def _cell_w(self) -> int:
        return self.tile + max(8, self.tile // 4)

    @property
    def _cell_h(self) -> int:
        return self.tile + self._label_h + max(6, self.tile // 6)

    def sizeHint(self) -> QSize:
        return QSize(
            self.columns * self._cell_w + self._pad * 2,
            self.rows * self._cell_h + self._pad * 2,
        )

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def set_tile(self, tile: int) -> None:
        self.tile = tile
        self.updateGeometry()
        self.update()

    def _cell_rect(self, index: int) -> QRect:
        placed = next((p for p in self.placement().cells if p.index == index), None)
        if placed is not None:
            return QRect(self._pad + placed.column * self._cell_w,
                         self._pad + placed.row * self._cell_h,
                         placed.width * self._cell_w, placed.height * self._cell_h)
        return self._grid_cell_rect(index)

    def _grid_cell_rect(self, index: int) -> QRect:
        row, col = divmod(index, self.columns)
        return QRect(
            self._pad + col * self._cell_w,
            self._pad + row * self._cell_h,
            self._cell_w,
            self._cell_h,
        )

    def _icon_rect(self, index: int) -> QRect:
        cell = self._cell_rect(index)
        left = cell.x() + (cell.width() - self.tile) // 2
        return QRect(left, cell.y(), self.tile, self.tile)

    def _index_at(self, pos: QPoint) -> Optional[int]:
        x = pos.x() - self._pad
        y = pos.y() - self._pad
        if x < 0 or y < 0:
            return None
        col = x // self._cell_w
        row = y // self._cell_h
        if col >= self.columns or row >= self.rows:
            return None
        return int(row * self.columns + col)

    def _item_at(self, pos: QPoint) -> Optional[int]:
        """항목이 실제로 있는 칸만 돌려준다."""
        for placed in self.placement().cells:
            if self._cell_rect(placed.index).contains(pos):
                return placed.index
        return None

    # ------------------------------------------------------------- 그리기

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 규약
        container = self.container
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        radius = max(8, self.tile // 5)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setBrush(PAGE_BG_HOVER if self.underMouse() else PAGE_BG)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)
        if container is None:
            painter.end()
            return

        # 빈 칸의 윤곽. 어디에 놓을 수 있는지를 말없이 알려 준다.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(SLOT_LINE, 1, Qt.PenStyle.DashLine))
        placement = self.placement()
        occupied = {(p.row + y, p.column + x) for p in placement.cells
                    for y in range(p.height) for x in range(p.width)}
        for index in range(self.columns * self.rows):
            if not placement.complete:
                break  # Blank regions are not known-free slots after unresolved geometry.
            if divmod(index, self.columns) in occupied:
                continue
            cell = self._grid_cell_rect(index)
            rect = QRect(cell.x() + (cell.width() - self.tile) // 2,
                         cell.y(), self.tile, self.tile)
            painter.drawRoundedRect(QRectF(rect), self.tile / 4.8, self.tile / 4.8)

        for placed in placement.cells:
            self._paint_node(painter, placed.index, container.items[placed.index])

        if self._drop_folder is not None:
            rect = self._icon_rect(self._drop_folder).adjusted(-3, -3, 3, 3)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(RING_BAD if self._drop_bad else RING_OK, 3))
            painter.drawRoundedRect(QRectF(rect), self.tile / 4.2, self.tile / 4.2)
        elif self._drop_index is not None:
            self._paint_caret(painter, self._drop_index)

        painter.end()

    def _paint_caret(self, painter: QPainter, index: int) -> None:
        limit = self.columns * self.rows
        position = min(index, limit)
        row, col = divmod(position, self.columns)
        if row >= self.rows:  # 마지막 칸 뒤 — 마지막 줄 오른쪽 끝에 세운다
            row, col = self.rows - 1, self.columns
        x = self._pad + col * self._cell_w
        y = self._pad + row * self._cell_h
        painter.setPen(QPen(RING_BAD if self._drop_bad else CARET, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(x, y + 2, x, y + self._cell_h - 4)

    def _paint_node(self, painter: QPainter, index: int, node: Node) -> None:
        if node.is_widget:
            self._paint_widget(painter, index, node)
            return
        rect = self._icon_rect(index)
        self.paint_icon(painter, rect, node, self.icons)

        if node.uid in self.selected_uids:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(SELECT_RING, 2))
            painter.drawRoundedRect(QRectF(rect.adjusted(-2, -2, 2, 2)), self.tile / 4.2, self.tile / 4.2)

        cell = self._cell_rect(index)
        font = QFont(self.font())
        font.setPointSizeF(max(6.5, self.tile * 0.155))
        painter.setFont(font)
        painter.setPen(LABEL_FG if node.movable else LABEL_DIM)
        metrics = QFontMetrics(font)
        text = metrics.elidedText(node.label, Qt.TextElideMode.ElideRight, cell.width() - 4)
        painter.drawText(
            QRect(cell.x(), rect.bottom() + 2, cell.width(), self._label_h),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
            text,
        )

    def _paint_widget(self, painter: QPainter, index: int, node: Node) -> None:
        """Show shape and stack membership without inventing live widget content."""
        cell = self._cell_rect(index)
        gap = max(8, self.tile // 4)
        rect = cell.adjusted(gap // 2, 0, -gap // 2, -self._label_h - 5)
        painter.setPen(QPen(QColor("#526886"), 1))
        painter.setBrush(QColor("#26384b"))
        painter.drawRoundedRect(QRectF(rect), max(8, self.tile // 4), max(8, self.tile // 4))
        font = QFont(self.font())
        font.setPointSizeF(max(7.0, self.tile * 0.17))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(LABEL_FG)
        title = QFontMetrics(font).elidedText(node.widget_label, Qt.TextElideMode.ElideRight, rect.width() - 14)
        painter.drawText(rect.adjusted(7, 5, -7, -rect.height() // 2),
                         int(Qt.AlignmentFlag.AlignCenter), title)
        font.setBold(False)
        font.setPointSizeF(max(6.0, self.tile * 0.13))
        painter.setFont(font)
        painter.setPen(QColor("#b2c7de"))
        body = tr("Layout placeholder · no live content")
        painter.drawText(rect.adjusted(8, rect.height() // 2, -8, -4),
                         int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), body)
        painter.setPen(LABEL_DIM)
        span = node.widget_span
        label = tr("{columns} × {rows} cells").format(columns=span[0], rows=span[1]) if span else tr("Unknown size")
        painter.drawText(QRect(cell.x(), rect.bottom() + 2, cell.width(), self._label_h),
                         int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), label)

    @staticmethod
    def paint_icon(painter: QPainter, rect: QRect, node: Node, icons: IconCache) -> None:
        """아이콘 한 개를 그린다. 드래그 그림자도 같은 함수를 쓴다 — 잡은 것과 보이는 것이 같아야 한다."""
        radius = rect.width() / 4.6
        if node.is_folder:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(FOLDER_BG)
            painter.drawRoundedRect(QRectF(rect), radius, radius)
            children = [child for page in node.pages for child in page.items][:9]
            inner = max(6, int(rect.width() * 0.24))
            gap = max(2, int(rect.width() * 0.045))
            span = inner * 3 + gap * 2
            origin_x = rect.x() + (rect.width() - span) // 2
            origin_y = rect.y() + (rect.height() - span) // 2
            for position, child in enumerate(children):
                row, col = divmod(position, 3)
                spot = QRect(
                    origin_x + col * (inner + gap), origin_y + row * (inner + gap), inner, inner
                )
                pixmap = icons.pixmap(child.identifier, inner)
                if pixmap is not None:
                    painter.drawPixmap(spot, pixmap)
                else:
                    painter.setBrush(PLACEHOLDER_BG)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(QRectF(spot), inner / 4.0, inner / 4.0)
            return

        pixmap = icons.pixmap(node.identifier, rect.width())
        if pixmap is not None:
            painter.drawPixmap(rect, pixmap)
            return

        # 아이콘을 받지 못한 항목 — 웹 클립처럼 원래 못 받는 것도 있다.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(UNKNOWN_BG if not node.movable else PLACEHOLDER_BG)
        painter.drawRoundedRect(QRectF(rect), radius, radius)
        letter = "?" if not node.movable else (node.label[:1] or "?")
        font = QFont(painter.font())
        font.setPointSizeF(max(8.0, rect.width() * 0.42))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 220))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), letter)

    def _drag_pixmap(self, node: Node) -> QPixmap:
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(int(self.tile * ratio), int(self.tile * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.paint_icon(painter, QRect(0, 0, self.tile, self.tile), node, self.icons)
        painter.end()
        return pixmap

    # ------------------------------------------------------------- 마우스

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._press_pos = event.position().toPoint()
        self._press_index = self._item_at(self._press_pos)
        container = self.container
        if container is None or self._press_index is None:
            self.selected.emit("")
            return
        node = container.items[self._press_index]
        # Ctrl 을 누른 채 누르면 골라 놓은 것을 잃지 않고 더한다 — 여러 개를 묶으려면
        # 하나씩 누르는 동안 앞의 선택이 남아 있어야 한다.
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.toggled.emit(node.uid)
        else:
            self.selected.emit(node.uid)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        hover = self._item_at(event.position().toPoint())
        if hover != self._hover_index:
            self._hover_index = hover
            container = self.container
            if hover is not None and container is not None:
                node = container.items[hover]
                where = self.doc.container_label(self.container_uid)
                extra = (
                    tr(" · {n}개").format(n=node.child_count()) if node.is_folder else ""
                )
                self.statusChanged.emit(
                    tr("{name} — {where} {n}번째{extra}").format(
                        name=node.label, where=where, n=hover + 1, extra=extra
                    )
                )

        if not self.editing_enabled or self._press_pos is None or self._press_index is None:
            return
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        moved = (event.position().toPoint() - self._press_pos).manhattanLength()
        if moved < 8:
            return
        container = self.container
        if container is None or self._press_index >= len(container.items):
            return
        node = container.items[self._press_index]
        self._press_pos = None
        if not node.movable:
            self.statusChanged.emit(
                tr("이 항목은 우리가 해석하지 못한 것이라, 안전을 위해 옮기지 않습니다.")
            )
            return

        mime = QMimeData()
        mime.setData(MIME_NODE, node.uid.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        pixmap = self._drag_pixmap(node)
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(self.tile // 2, self.tile // 2))
        drag.exec(Qt.DropAction.MoveAction)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        index = self._item_at(event.position().toPoint())
        container = self.container
        if index is None or container is None:
            return
        node = container.items[index]
        if node.is_folder:
            self.folderRequested.emit(node.uid)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_index = None
        self.update()

    # ------------------------------------------------------------- 드래그

    def _resolve_target(
        self, pos: QPoint, node_uid: str
    ) -> tuple[Optional[str], int, Optional[int], Optional[str], Optional[str]]:
        """커서 위치를 '어디에 놓이는가'로 옮긴다.

        돌려주는 것: (대상 자리 uid, 끼울 위치, 테두리를 칠할 칸,
                      놓으면 묶일 상대 uid, 막힌 이유)
        """
        if not self.editing_enabled:
            return None, 0, None, None, tr("This preview is read-only; layout changes are disabled.")
        container = self.container
        if container is None:
            return None, 0, None, None, tr("자리를 찾을 수 없습니다.")
        slot = self._index_at(pos)
        if slot is None:
            slot = len(container.items)

        # 1) 다른 항목 한가운데인가
        if slot < len(container.items):
            target_node = container.items[slot]
            if target_node.uid != node_uid and self._in_center(pos, slot):
                if target_node.is_folder:
                    # 빈자리가 있는 페이지가 먼저. 다 찼으면 마지막 페이지를 겨눈다 —
                    # 페이지를 더 펼 수 있는지는 모델이 판단한다 (여기서 또 세면 어긋난다).
                    pages = target_node.pages
                    page = next((p for p in pages if not p.full), pages[-1] if pages else None)
                    if page is None:
                        return None, 0, slot, None, tr("이 묶음에는 넣을 수 없습니다.")
                    reason = self.doc.can_move(node_uid, page.uid, len(page.items))
                    return page.uid, len(page.items), slot, None, reason
                # 앱 위에 앱을 겹치면 iPhone 에서와 같이 새 묶음이 된다.
                reason = self.doc.can_group([target_node.uid, node_uid])
                return None, 0, slot, target_node.uid, reason

        # 2) 아니면 이 자리의 몇 번째에 끼우는가
        index = min(slot, len(container.items))
        if slot < len(container.items):
            cell = self._cell_rect(slot)
            if pos.x() > cell.center().x():
                index = slot + 1
        # 겨눈 자리까지 함께 묻는다. 꽉 찬 페이지라도 **자리를 겨눈** 놓기는
        # 밀어내기로 받아들여진다 — 그 판단은 모델이 한다 (계약: can_move 가 유일한
        # 판정자). 여기서 자리를 빼고 물으면 되는 놓기가 막힌 것처럼 보인다.
        reason = self.doc.can_move(node_uid, self.container_uid, index)
        return self.container_uid, index, None, None, reason

    def _in_center(self, pos: QPoint, slot: int) -> bool:
        """아이콘 한가운데 — 겹쳐 놓는 자리인가. 가장자리는 '옆에 끼우기'로 남긴다."""
        icon = self._icon_rect(slot)
        margin = icon.width() * (1 - _FOLDER_ZONE) / 2
        return QRectF(icon).adjusted(margin, margin, -margin, -margin).contains(pos)

    def _node_uid(self, event) -> Optional[str]:
        data = event.mimeData()
        if not data.hasFormat(MIME_NODE):
            return None
        return bytes(data.data(MIME_NODE)).decode("utf-8")

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if not self.editing_enabled or self._node_uid(event) is None:
            event.ignore()
            return
        event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if not self.editing_enabled:
            event.ignore()
            return
        node_uid = self._node_uid(event)
        if node_uid is None:
            event.ignore()
            return
        try:
            target, index, folder_slot, group_uid, reason = self._resolve_target(
                event.position().toPoint(), node_uid
            )
        except LayoutError as exc:
            target, index, folder_slot, group_uid, reason = None, 0, None, None, str(exc)

        self._drop_bad = reason is not None or (target is None and group_uid is None)
        self._drop_folder = folder_slot
        self._drop_group = None if self._drop_bad else group_uid
        self._drop_index = None if folder_slot is not None else index
        self.update()

        if self._drop_bad:
            self.statusChanged.emit(reason or tr("여기에는 놓을 수 없습니다."))
            event.ignore()  # 커서가 '금지'로 바뀐다 — 놓아 보기 전에 알 수 있다
        else:
            if self._drop_group is not None:
                other = self.doc.node(self._drop_group).label
                self.statusChanged.emit(
                    tr("놓으면 “{name}” 와(과) 새 묶음이 됩니다.").format(name=other)
                )
            else:
                self.statusChanged.emit("")
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._clear_drop()

    def _clear_drop(self) -> None:
        self._drop_index = None
        self._drop_folder = None
        self._drop_group = None
        self._drop_bad = False
        self.update()

    def dropEvent(self, event) -> None:  # noqa: N802
        if not self.editing_enabled:
            event.ignore()
            return
        node_uid = self._node_uid(event)
        self._clear_drop()
        if node_uid is None:
            event.ignore()
            return
        try:
            target, index, _folder, group_uid, reason = self._resolve_target(
                event.position().toPoint(), node_uid
            )
            if reason is not None or (target is None and group_uid is None):
                self.statusChanged.emit(reason or tr("여기에는 놓을 수 없습니다."))
                event.ignore()
                return
            if group_uid is not None:
                # 묶기는 이름을 물어야 한다. 창을 띄우는 일은 창 주인이 한다 —
                # 이 판은 문서를 바꾸지 않고 사실만 알린다.
                event.acceptProposedAction()
                self.grouped.emit(node_uid, group_uid)
                return
            self.doc.move(node_uid, target, index)
        except LayoutError as exc:
            # 모델이 거절한 것은 오류가 아니라 규칙이다. 그대로 사용자 말로 전한다.
            self.statusChanged.emit(str(exc))
            event.ignore()
            return
        event.acceptProposedAction()
        self.selected.emit(node_uid)
        self.edited.emit()
