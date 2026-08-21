"""여러 페이지를 한 화면에 펼치는 캔버스 (REQ-012).

이 앱이 존재하는 이유가 이 화면이다. iPhone 에서는 페이지를 한 번에 하나씩만 볼 수
있고, 그래서 "6페이지의 저 앱을 2페이지로" 같은 정리가 어렵다. 여기서는 페이지를
나란히 늘어놓고 양쪽을 동시에 본 채로 끌어다 놓는다.

페이지 배치에 `FlowLayout` 을 쓰는 이유: 창 너비에 맞춰 페이지가 알아서 줄바꿈되어야
가로 스크롤이 생기지 않는다. 가로로만 늘어놓으면 페이지가 10개일 때 화면 밖으로 나가고,
그러면 "한 화면에 펼친다"는 목적 자체가 사라진다. 페이지가 많으면 확대 배율을 줄여
전부 들어오게 한다 — 배율 조절이 이 화면의 유일한 필수 조작이다.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QMargins, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..layout import LayoutDocument, LayoutError
from .tiles import ContainerView, IconCache


class FlowLayout(QLayout):
    """넣은 순서대로 놓다가 폭이 모자라면 다음 줄로 넘기는 배치."""

    def __init__(self, parent: Optional[QWidget] = None, spacing: int = 14) -> None:
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self.setContentsMargins(QMargins(10, 10, 10, 10))

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._arrange(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._arrange(rect, apply=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _arrange(self, rect: QRect, apply: bool) -> int:
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, line_height = area.x(), area.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > area.right() and line_height > 0:
                x = area.x()
                y = y + line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class PageFrame(QFrame):
    """페이지 한 장 — 머리글(번호·개수·조작)과 판 하나."""

    edited = Signal()
    folderRequested = Signal(str)
    statusChanged = Signal(str)
    selected = Signal(str)
    toggled = Signal(str)
    grouped = Signal(str, str)
    pageMoved = Signal(int, int)
    pageRemoved = Signal(int)

    def __init__(
        self,
        document: LayoutDocument,
        container_uid: str,
        icons: IconCache,
        tile: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.doc = document
        self.container_uid = container_uid
        self.setObjectName("pageFrame")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.title = QLabel()
        self.title.setObjectName("pageTitle")

        self.left = QPushButton("◀")
        self.right = QPushButton("▶")
        self.remove = QPushButton("✕")
        for button in (self.left, self.right, self.remove):
            button.setObjectName("pageButton")
            button.setFixedSize(22, 20)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.left.setToolTip(tr("이 페이지를 앞으로"))
        self.right.setToolTip(tr("이 페이지를 뒤로"))
        self.remove.setToolTip(tr("빈 페이지 삭제"))

        self.left.clicked.connect(lambda: self._move(-1))
        self.right.clicked.connect(lambda: self._move(1))
        self.remove.clicked.connect(self._remove)

        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 4, 2)
        header.setSpacing(3)
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.left)
        header.addWidget(self.right)
        header.addWidget(self.remove)

        self.view = ContainerView(
            document,
            container_uid,
            document.grid.columns,
            document.grid.rows,
            icons,
            tile=tile,
        )
        self.view.edited.connect(self.edited)
        self.view.folderRequested.connect(self.folderRequested)
        self.view.statusChanged.connect(self.statusChanged)
        self.view.selected.connect(self.selected)
        self.view.toggled.connect(self.toggled)
        self.view.grouped.connect(self.grouped)

        box = QVBoxLayout(self)
        box.setContentsMargins(4, 4, 4, 4)
        box.setSpacing(0)
        box.addLayout(header)
        box.addWidget(self.view)
        self.refresh()

    def set_selection(self, uids: set[str]) -> None:
        self.view.selected_uids = uids
        self.view.update()

    def _index(self) -> int:
        return [page.uid for page in self.doc.pages].index(self.container_uid)

    def _move(self, delta: int) -> None:
        try:
            index = self._index()
        except ValueError:
            return
        target = index + delta
        if 0 <= target < len(self.doc.pages):
            self.pageMoved.emit(index, target)

    def _remove(self) -> None:
        try:
            self.pageRemoved.emit(self._index())
        except ValueError:
            return

    def set_tile(self, tile: int) -> None:
        self.view.set_tile(tile)
        self.updateGeometry()

    def refresh(self) -> None:
        container = None
        try:
            container = self.doc.container(self.container_uid)
            index = self._index()
        except (LayoutError, ValueError):
            return
        count = len(container.items)
        self.title.setText(
            tr("{n}페이지 · {count}/{capacity}").format(
                n=index + 1, count=count, capacity=container.capacity
            )
        )
        self.left.setEnabled(index > 0)
        self.right.setEnabled(index < len(self.doc.pages) - 1)
        self.remove.setEnabled(count == 0 and len(self.doc.pages) > 1)
        self.view.update()


class DockFrame(QFrame):
    """독. 페이지를 넘겨도 늘 보이는 자리이므로 화면에서도 따로 둔다."""

    edited = Signal()
    folderRequested = Signal(str)
    statusChanged = Signal(str)
    selected = Signal(str)
    toggled = Signal(str)
    grouped = Signal(str, str)

    def __init__(
        self,
        document: LayoutDocument,
        icons: IconCache,
        tile: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.doc = document
        self.setObjectName("dockFrame")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.title = QLabel(tr("독"))
        self.title.setObjectName("pageTitle")
        self.view = ContainerView(
            document, "dock", document.grid.dock_capacity, 1, icons, tile=tile
        )
        self.view.edited.connect(self.edited)
        self.view.folderRequested.connect(self.folderRequested)
        self.view.statusChanged.connect(self.statusChanged)
        self.view.selected.connect(self.selected)
        self.view.toggled.connect(self.toggled)
        self.view.grouped.connect(self.grouped)

        box = QVBoxLayout(self)
        box.setContentsMargins(4, 4, 4, 4)
        box.setSpacing(2)
        box.addWidget(self.title)
        box.addWidget(self.view)
        self.refresh()

    def set_selection(self, uids: set[str]) -> None:
        self.view.selected_uids = uids
        self.view.update()

    def set_tile(self, tile: int) -> None:
        self.view.set_tile(tile)
        self.updateGeometry()

    def refresh(self) -> None:
        self.title.setText(
            tr("독 · {count}/{capacity}").format(
                count=len(self.doc.dock.items), capacity=self.doc.dock.capacity
            )
        )
        self.view.update()


class FolderPanel(QFrame):
    """폴더를 열어 놓는 자리.

    폴더 안팎으로 항목을 끌어내려면 두 자리가 **동시에 보여야** 한다. 그래서 새 창이
    아니라 같은 창의 아래쪽에 편다 — 창이 뜨면 뒤가 가려지고, 가려진 곳으로는 끌 수 없다.
    """

    edited = Signal()
    statusChanged = Signal(str)
    selected = Signal(str)
    toggled = Signal(str)
    grouped = Signal(str, str)
    renameRequested = Signal(str)
    closed = Signal()

    def __init__(
        self,
        document: LayoutDocument,
        icons: IconCache,
        tile: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.doc = document
        self.icons = icons
        self.tile = tile
        self.node_uid: Optional[str] = None
        self._views: list[ContainerView] = []
        # 판을 다시 지을 때마다 선택이 사라지면, 폴더를 열었다는 이유만으로
        # 고른 것이 풀린다. 선택은 판이 아니라 이 자리가 들고 있는다.
        self._selection: set[str] = set()
        self.setObjectName("folderPanel")

        self.title = QLabel()
        self.title.setObjectName("folderTitle")
        rename = QPushButton(tr("이름 바꾸기"))
        rename.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        rename.clicked.connect(self._ask_rename)
        close = QPushButton(tr("닫기"))
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close.clicked.connect(self.closed)

        header = QHBoxLayout()
        header.setContentsMargins(6, 4, 6, 0)
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(rename)
        header.addWidget(close)

        self._pages = QHBoxLayout()
        self._pages.setContentsMargins(6, 2, 6, 6)
        self._pages.setSpacing(10)

        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        box.addLayout(header)
        box.addLayout(self._pages)
        self.hide()

    def open_folder(self, node_uid: str) -> None:
        self.node_uid = node_uid
        self.rebuild()
        self.show()

    def set_selection(self, uids: set[str]) -> None:
        self._selection = uids
        for view in self._views:
            view.selected_uids = uids
            view.update()

    def _ask_rename(self) -> None:
        if self.node_uid is not None:
            self.renameRequested.emit(self.node_uid)

    def rebuild(self) -> None:
        self._views.clear()
        while self._pages.count():
            item = self._pages.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        if self.node_uid is None:
            return
        try:
            node = self.doc.node(self.node_uid)
        except LayoutError:
            self.hide()
            self.node_uid = None
            return
        if not node.is_folder:
            self.hide()
            self.node_uid = None
            return

        self.title.setText(
            tr("폴더 “{name}” · {n}개").format(name=node.label, n=node.child_count())
        )
        for number, page in enumerate(node.pages, start=1):
            box = QVBoxLayout()
            label = QLabel(
                tr("{n}페이지 · {count}/{capacity}").format(
                    n=number, count=len(page.items), capacity=page.capacity
                )
            )
            label.setObjectName("pageTitle")
            view = ContainerView(
                self.doc,
                page.uid,
                self.doc.grid.folder_columns,
                self.doc.grid.folder_rows,
                self.icons,
                tile=self.tile,
            )
            view.edited.connect(self.edited)
            view.statusChanged.connect(self.statusChanged)
            view.selected.connect(self.selected)
            view.toggled.connect(self.toggled)
            view.grouped.connect(self.grouped)
            view.selected_uids = self._selection
            self._views.append(view)
            holder = QWidget()
            holder.setLayout(box)
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(2)
            box.addWidget(label)
            box.addWidget(view)
            self._pages.addWidget(holder)
        self._pages.addStretch(1)

    def set_tile(self, tile: int) -> None:
        self.tile = tile
        if self.isVisible():
            self.rebuild()

    def refresh(self) -> None:
        if not self.isVisible():
            return
        self.rebuild()
