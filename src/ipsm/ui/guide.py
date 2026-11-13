"""처음 켰을 때 깔리는 안내판.

빈 화면으로 맞이하면 사용자는 무엇이 잘못됐는지, 무엇을 해야 하는지 알 수 없다.
특히 이 앱은 **Apple 쪽 구성요소가 없으면 아무 일도 일어나지 않는데**, 그 사실이
드러나는 자리가 원래는 '기기에서 읽기'를 누른 뒤의 오류 상자뿐이었다. 그래서 읽기를
누르기 전에, 지금 무엇이 준비됐고 무엇이 없는지 먼저 보여 준다.

세 갈래로만 말한다. 사용자가 다음에 할 일이 갈래마다 다르기 때문이다.

* 준비됨 → 케이블을 꽂고 '기기에서 읽기'
* 설치는 됐는데 아직 안 뜸 → Apple Devices 를 한 번 실행
* 아예 없음 → Microsoft Store 로 데려간다

혼자 3초마다 다시 본다. 사용자가 옆에서 설치를 끝냈을 때 이 화면이 스스로 바뀌지
않으면, 다 해 놓고도 안 된다고 여기게 된다.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import apple_devices
from ..i18n import tr

log = logging.getLogger("ui.guide")

CHECK_EVERY_MS = 3000


class GuideBoard(QWidget):
    """읽기 전의 바탕 화면. 준비물과 다음 할 일을 말한다."""

    readRequested = Signal()

    def __init__(self, parent: QWidget | None = None, *, offline: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("canvasHost")
        self._presence = apple_devices.Presence(False, False, "-")
        self.offline = offline

        self.title = QLabel()
        self.title.setObjectName("guideTitle")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("guideSub")
        self.subtitle.setWordWrap(True)

        self.steps = [QLabel() for _ in range(3)]
        for label in self.steps:
            label.setWordWrap(True)
            label.setObjectName("guideStep")

        self.state = QLabel()
        self.state.setWordWrap(True)
        self.state.setObjectName("guideState")
        self.action = QPushButton()
        self.action.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.action.clicked.connect(self._act)
        self.again = QPushButton()
        self.again.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.again.clicked.connect(self.refresh)

        buttons = QHBoxLayout()
        buttons.addWidget(self.action)
        buttons.addWidget(self.again)
        buttons.addStretch(1)

        self.box = QFrame()
        self.box.setObjectName("guideBox")
        inner = QVBoxLayout(self.box)
        inner.setContentsMargins(14, 12, 14, 12)
        inner.addWidget(self.state)
        inner.addLayout(buttons)

        self.safety = QLabel()
        self.safety.setWordWrap(True)
        self.safety.setObjectName("guideSafety")

        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)
        column.addWidget(self.title)
        column.addWidget(self.subtitle)
        column.addSpacing(6)
        for label in self.steps:
            column.addWidget(label)
        column.addSpacing(6)
        column.addWidget(self.box)
        column.addWidget(self.safety)

        # 가운데에 한 덩어리로 놓는다. 창을 키워도 글줄이 화면 끝까지 늘어나면 읽기 어렵다.
        holder = QWidget()
        holder.setObjectName("canvasHost")
        holder.setMaximumWidth(620)
        holder.setLayout(column)

        outer = QVBoxLayout(self)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(holder)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(2)

        self._timer = QTimer(self)
        self._timer.setInterval(CHECK_EVERY_MS)
        self._timer.timeout.connect(self.refresh)

        self.retranslate()
        self.refresh()

    # ------------------------------------------------------------------ 상태

    def refresh(self) -> None:
        """다시 본다. 방금 설치를 끝냈을 수 있으므로 캐시하지 않는다."""
        if self.offline:
            self._paint()
            return
        before = self._presence
        self._presence = apple_devices.look()
        if (before.running, before.installed) != (self._presence.running, self._presence.installed):
            log.info(
                "Apple 구성요소: 동작 %s · 설치 %s (%s)",
                self._presence.running,
                self._presence.installed,
                self._presence.where,
            )
        self._paint()

    def _paint(self) -> None:
        if self.offline:
            self.state.setText(tr("Offline preview uses a local backup only. No iPhone connection is made."))
            self.box.setProperty("tone", "good")
            self.action.setVisible(False)
            self.again.setVisible(False)
        elif self._presence.running:
            self.state.setText(
                tr("✓ 준비됐습니다. iPhone 을 케이블로 연결하고 잠금을 풀어 주세요.")
            )
            self.box.setProperty("tone", "good")
            self.action.setText(tr("기기에서 읽기"))
            self.action.setVisible(True)
            self.again.setVisible(False)
        elif sys.platform == "darwin":
            self.state.setText(tr("The Mac's iPhone connection service is unavailable. Reconnect the cable, open Finder, and restart your Mac if needed."))
            self.box.setProperty("tone", "wait")
            self.action.setVisible(False)
            self.again.setText(tr("다시 확인"))
            self.again.setVisible(True)
        elif self._presence.installed:
            self.state.setText(
                tr("Apple Devices 는 설치되어 있지만 아직 동작하지 않습니다.\n"
                "한 번 실행하거나 PC 를 다시 시작하면 준비됩니다.")
            )
            self.box.setProperty("tone", "wait")
            self.action.setText(tr("Microsoft Store 에서 열기"))
            self.action.setVisible(True)
            self.again.setText(tr("다시 확인"))
            self.again.setVisible(True)
        else:
            self.state.setText(
                tr("iPhone 과 통신하는 Apple 구성요소가 없습니다.\n"
                "Microsoft Store 의 무료 앱 ‘Apple Devices’ 를 설치해 주세요. (iTunes 도 됩니다)")
            )
            self.box.setProperty("tone", "need")
            self.action.setText(tr("Microsoft Store 에서 Apple Devices 받기"))
            self.action.setVisible(True)
            self.again.setText(tr("다시 확인"))
            self.again.setVisible(True)
        # 속성으로 색을 바꾸는 스타일시트는 다시 계산해 주어야 반영된다
        self.box.style().unpolish(self.box)
        self.box.style().polish(self.box)

    def _act(self) -> None:
        if self.offline:
            return
        if self._presence.running:
            self.readRequested.emit()
            return
        self._open_store()

    def _open_store(self) -> None:
        """Store 로 데려간다. 딥링크가 듣지 않으면 검색으로라도."""
        if sys.platform == "darwin":
            return
        if QDesktopServices.openUrl(QUrl(apple_devices.STORE_LINK)):
            log.info("Store 딥링크를 열었다")
            return
        log.info("딥링크가 듣지 않아 검색으로 연다")
        QDesktopServices.openUrl(QUrl(apple_devices.STORE_SEARCH))

    # ------------------------------------------------------------------ 표시

    def retranslate(self) -> None:
        self.title.setText(tr("iPhone 홈화면을 PC 한 화면에 펼쳐 정리합니다"))
        self.subtitle.setText(
            tr("탈옥도, 개발자 모드도 필요 없습니다. USB 케이블과 ‘신뢰’ 한 번이면 됩니다.")
        )
        self.steps[0].setText(
            tr("① macOS includes iPhone connectivity. No Apple Devices app or iTunes installation is needed.")
            if sys.platform == "darwin" else tr("① Apple 이 만든 구성요소가 USB 를 맡습니다 — Apple Devices 앱 또는 iTunes")
        )
        self.steps[1].setText(
            tr("② iPhone 을 케이블로 연결하고, 잠금을 푼 뒤 ‘신뢰’ 를 눌러 주세요")
        )
        self.steps[2].setText(tr("③ 위쪽 ‘기기에서 읽기’ 를 누르면 홈화면이 펼쳐집니다"))
        self.safety.setText(
            tr("Applying replaces the entire Home Screen after a verified backup. Apps kept only in the App Library may reappear; restoring a backup cannot undo that iOS behavior.")
        )
        self._paint()

    # ----------------------------------------------------------------- 눈뜨기

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()
        if not self.offline:
            self._timer.start()

    def set_offline(self, offline: bool) -> None:
        self.offline = bool(offline)
        if offline:
            self._timer.stop()
        elif self.isVisible():
            self._timer.start()
        self.refresh()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)
