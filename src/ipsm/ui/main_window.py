"""주 창 — 읽고, 펼치고, 끌어 옮기고, 확인한 뒤에 쓴다.

화면의 순서가 곧 안전 규약의 순서다.

    읽기 → 펼치기 → 편집 → **변경 목록 확인** → 백업 → 쓰기 → 결과 대조

가운데의 '변경 목록 확인'을 건너뛸 수 있게 만들면 안 된다. `setIconState` 는 부분
수정이 아니라 전체 덮어쓰기여서, 잘못 끌어다 놓은 것 하나가 그대로 기기에 반영된다.
되돌릴 수는 있지만(백업), 되돌릴 일을 만들지 않는 편이 훨씬 낫다.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .. import i18n, product
from ..i18n import tr
from ..layout import Grid, LayoutDocument, LayoutError
from ..version import VERSION_TEXT
from ..icons import wanted_icons
from .canvas import DockFrame, FlowLayout, FolderPanel, PageFrame
from .about import AboutDialog
from .guide import GuideBoard
from .tiles import IconCache
from .worker import DeviceWorker

log = logging.getLogger("ui.window")

MIN_TILE = 22
MAX_TILE = 120

STYLE = """
/* 배경을 우리가 어둡게 칠하는 이상, 글자색도 우리가 전부 칠해야 한다.
   빠뜨린 위젯은 Windows 기본 팔레트의 검은 글씨를 그대로 쓰는데, 그것이 어두운
   배경 위에 얹히면 사실상 보이지 않는다. 도구모음이 정확히 그랬다.
   그래서 맨 위에 QWidget 전체를 덮는 글자색을 하나 둔다 — 개별 규칙을 하나
   빠뜨려도 최소한 읽을 수는 있게. */
QWidget { color: #e6e9f0; }
QMainWindow, QWidget#canvasHost, QDialog, QMessageBox { background: #171a21; }
QLabel#pageTitle { color: #a8b0c2; font-size: 11px; }
QLabel#folderTitle { color: #e6e9f0; font-size: 13px; font-weight: bold; }
QFrame#pageFrame, QFrame#dockFrame {
    background: #1e2230; border: 1px solid #2c3245; border-radius: 10px;
}
QFrame#folderPanel {
    background: #1b1f2b; border-top: 1px solid #333a50;
}
QPushButton#pageButton {
    background: #2a3044; color: #cdd4e4; border: none; border-radius: 4px;
    font-size: 10px; padding: 2px 6px; min-width: 0;
}
QPushButton#pageButton:hover { background: #3a4462; }
QPushButton#pageButton:disabled { color: #565e75; background: #232838; }
QListWidget {
    background: #1e2230; color: #dde2ee; border: 1px solid #2c3245; border-radius: 6px;
}

/* 도구모음 */
QToolBar { background: #1b1f29; border: none; spacing: 3px; padding: 4px; }
QToolBar QToolButton {
    color: #e6e9f0; background: transparent;
    border: 1px solid transparent; border-radius: 5px; padding: 5px 10px;
}
QToolBar QToolButton:hover { background: #2a3044; border-color: #3f4a6b; }
QToolBar QToolButton:pressed { background: #3a4462; }
QToolBar QToolButton:disabled { color: #5b6377; }
QToolBar::separator { background: #333a50; width: 1px; margin: 5px 7px; }

/* 대화상자 단추 — 여기도 칠하지 않으면 검은 글씨가 된다 */
QPushButton {
    background: #2a3044; color: #e6e9f0; border: 1px solid #3a4462;
    border-radius: 5px; padding: 5px 16px; min-width: 74px;
}
QPushButton:hover { background: #3a4462; }
QPushButton:disabled { color: #5b6377; background: #232838; border-color: #2c3245; }
QCheckBox { color: #e6e9f0; spacing: 7px; }
QCheckBox::indicator {
    width: 15px; height: 15px; border-radius: 3px;
    border: 1px solid #4a5473; background: #1e2230;
}
QCheckBox::indicator:checked { background: #5a76c4; border-color: #7f95d6; }

/* 입력창 — 바탕은 Windows 기본 흰색인데 위의 QWidget 규칙이 글자를 흰색으로
   칠해 버려, 흰 바탕에 흰 글씨가 됐다. 이름 바꾸기 창이 정확히 그랬다.
   글자색을 정하는 곳에서는 바탕색도 같이 정해야 한다. */
QLineEdit {
    background: #12151c; color: #e6e9f0; border: 1px solid #3a4462;
    border-radius: 5px; padding: 5px 8px;
    selection-background-color: #4a5a86; selection-color: #ffffff;
}
QLineEdit:focus { border-color: #5a76c4; }
QLineEdit:disabled { background: #1b1f2b; color: #5b6377; border-color: #2c3245; }

/* 고르는 칸. 여기서 같은 실수가 세 번째로 났다 — 칸 자체는 어둡게 칠했는데
   **펼쳐지는 목록은 QComboBox 가 아니라 그 안의 QAbstractItemView** 라서
   바탕이 Windows 기본 흰색으로 남았고, 위의 QWidget 규칙이 글자를 흰색으로
   칠해 흰 바탕에 흰 글씨가 됐다. 목록은 따로 칠해야 한다. */
QComboBox {
    background: #12151c; color: #e6e9f0; border: 1px solid #3a4462;
    border-radius: 5px; padding: 5px 8px;
}
QComboBox:hover { border-color: #5a76c4; }
QComboBox:disabled { background: #1b1f2b; color: #5b6377; border-color: #2c3245; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #12151c; color: #e6e9f0;
    border: 1px solid #3a4462;
    selection-background-color: #3a4462; selection-color: #ffffff;
    outline: none;
}
QComboBox QAbstractItemView::item { padding: 4px 8px; }

QPushButton#donateButton {
    background: #37324a; color: #ead9f7; border: 1px solid #5a4a80;
}
QPushButton#donateButton:hover { background: #463c62; }
QFrame#settingsRule { color: #2c3245; }
QLabel#aboutName { color:#f0f3fa; font-size:19px; font-weight:bold; }
QLabel#aboutTagline { color:#a8b0c2; font-size:12px; }
QLabel#aboutBody { color:#cdd4e4; font-size:12px; }
QPlainTextEdit#licenseText {
    background:#12151c; color:#d7dced; border:1px solid #2c3245; border-radius:5px;
    font-family:"Consolas","D2Coding",monospace; font-size:12px;
}

/* 풍선 도움말도 QWidget 이라 위의 글자색을 물려받는다. 바탕을 같이 칠하지
   않으면 밝은 바탕에 밝은 글씨가 되어 같은 일이 반복된다. */
QToolTip {
    background: #12151c; color: #e6e9f0;
    border: 1px solid #3a4462; padding: 3px 6px;
}

QSlider::groove:horizontal { background: #2c3245; height: 4px; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #8fa0c8; width: 12px; margin: -5px 0; border-radius: 6px;
}
QProgressBar {
    background: #1e2230; color: #e6e9f0; border: 1px solid #2c3245;
    border-radius: 5px; text-align: center;
}
QProgressBar::chunk { background: #4a5a86; border-radius: 4px; }

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #171a21; width: 12px; margin: 0; }
QScrollBar:horizontal { background: #171a21; height: 12px; margin: 0; }
QScrollBar::handle:vertical { background: #333a50; border-radius: 5px; min-height: 26px; }
QScrollBar::handle:horizontal { background: #333a50; border-radius: 5px; min-width: 26px; }
QScrollBar::handle:hover { background: #47516f; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QStatusBar { color: #a8b0c2; background: #1b1f29; }

/* 시작 안내판 */
QLabel#guideTitle { color: #f0f3fa; font-size: 19px; font-weight: bold; }
QLabel#guideSub { color: #a8b0c2; font-size: 12px; }
QLabel#guideStep { color: #cdd4e4; font-size: 12px; }
QLabel#guideSafety { color: #8f97ab; font-size: 11px; }
QFrame#guideBox {
    background: #1e2230; border: 1px solid #2c3245; border-radius: 8px;
}
QFrame#guideBox[tone="good"] { background: #1a2a20; border-color: #2f6b45; }
QFrame#guideBox[tone="wait"] { background: #2b2417; border-color: #6a5620; }
QFrame#guideBox[tone="need"] { background: #241d2b; border-color: #57407a; }
QLabel#guideState { color: #e6e9f0; font-size: 13px; }
"""


class ApplyDialog(QDialog):
    """적용 직전 확인 (REQ-015).

    여기서 반드시 말해야 하는 것이 하나 있다. 실기기 확인 결과, `setIconState` 로 쓰면
    iOS 가 **앱 라이브러리에만 있던 앱을 마지막 페이지 끝에 되붙인다.** 우리가 만든
    변화가 아니고, 백업 복원도 쓰기이므로 이것만은 되돌려지지 않는다. 나중에 발견하면
    앱이 제멋대로 늘어난 것처럼 보이므로, 쓰기 전에 알려 둔다.
    """

    def __init__(
        self,
        changes: list[str],
        unplaced: Optional[list[str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("iPhone 홈화면에 적용"))
        self.setMinimumWidth(560)

        head = QLabel(tr("아래 {n}건을 iPhone 홈화면에 적용합니다.").format(n=len(changes)))
        head.setStyleSheet("font-size: 14px; font-weight: bold;")

        listing = QListWidget()
        listing.addItems(changes or [tr("(변경 없음)")])
        listing.setMinimumHeight(180)

        warnings = [
            tr("• 적용 전에 현재 홈화면을 자동으로 백업합니다. 백업에 실패하면 쓰지 않습니다."),
            tr("• 홈화면은 부분 수정이 아니라 전체가 한 번에 덮어써집니다."),
        ]
        if unplaced:
            shown = ", ".join(unplaced[:6])
            more = tr(" 외 {n}개").format(n=len(unplaced) - 6) if len(unplaced) > 6 else ""
            warnings.append(
                tr(
                    "• 지금 홈화면에 없는 앱 {n}개가 마지막 페이지 끝에 붙습니다:\n"
                    "   {names}{more}\n"
                    "   iOS 의 동작이라 백업 복원으로도 되돌아가지 않습니다."
                    " 적용 후 직접 정리해 주세요."
                ).format(n=len(unplaced), names=shown, more=more)
            )
        else:
            warnings.append(
                tr("• 앱 라이브러리에만 있던 앱이 마지막 페이지 끝에 붙을 수 있습니다. iOS 의 동작이며\n"
                "   백업 복원으로도 되돌아가지 않습니다.")
            )
        warnings.append(tr("• 적용 중에는 케이블을 뽑지 마세요. 1초 남짓 걸립니다."))
        notice = QLabel("\n".join(warnings))
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "background:#2b2417; border:1px solid #6a5620; border-radius:6px;"
            "padding:8px; color:#f0e2bd;"
        )

        self.agree = QCheckBox(tr("위 내용을 확인했습니다."))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("백업하고 적용"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("취소"))
        self._ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok.setEnabled(False)
        self.agree.toggled.connect(self._ok.setEnabled)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        box = QVBoxLayout(self)
        box.addWidget(head)
        box.addWidget(listing)
        box.addWidget(notice)
        box.addWidget(self.agree)
        box.addWidget(buttons)


class SettingsDialog(QDialog):
    """설정 — 언어와 후원.

    목록에 적히는 이름은 **그 언어로 쓴** 이름이다. 지금 화면이 한국어든 영어든
    "English" 와 "한국어" 는 그대로여야, 읽지 못하는 말로 켜진 사람도 자기 말을
    찾을 수 있다. 그래서 이 목록만은 `tr()` 을 거치지 않는다.

    후원 단추는 **누른 사람만** 바깥으로 나간다. 앱이 스스로 어딘가에 접속하는 일은
    없고, 누르면 기본 브라우저에 PayPal 결제 창이 열린다. 이 앱은 무료이고 소스가
    공개되어 있으므로, 후원은 갚아야 할 것이 아니라 응원이다 — 그래서 안 눌러도
    아무것도 달라지지 않는다는 말을 함께 적는다.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("설정"))
        self.setMinimumWidth(320)

        self.language = QComboBox()
        for code, name in i18n.LANGUAGES.items():
            self.language.addItem(name, code)
        here = self.language.findData(i18n.language())
        if here >= 0:
            self.language.setCurrentIndex(here)

        row = QHBoxLayout()
        row.addWidget(QLabel(tr("언어")))
        row.addWidget(self.language, 1)

        note = QLabel(tr("바꾸면 곧바로 화면에 적용되고, 다음에 켤 때도 그대로입니다."))
        note.setWordWrap(True)
        note.setStyleSheet("color:#8f97ab; font-size:11px;")

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("settingsRule")

        support = QLabel(
            tr("이 앱은 무료이고 소스가 공개되어 있습니다. 마음이 내키면 개발을 응원해 주세요.")
        )
        support.setWordWrap(True)
        support.setStyleSheet("color:#8f97ab; font-size:11px;")

        self.donate = QPushButton(tr("♥ PayPal 로 후원하기"))
        self.donate.setObjectName("donateButton")
        self.donate.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.donate.setToolTip(product.donate_url())
        self.donate.clicked.connect(self._donate)

        donate_row = QHBoxLayout()
        donate_row.addWidget(self.donate)
        donate_row.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("확인"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("취소"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        box = QVBoxLayout(self)
        box.addLayout(row)
        box.addWidget(note)
        box.addWidget(line)
        box.addWidget(support)
        box.addLayout(donate_row)
        box.addWidget(buttons)

    def _donate(self) -> None:
        """기본 브라우저에서 PayPal 을 연다. 주소는 `product` 가 짓는다."""
        url = product.donate_url()
        log.info("후원 창을 연다: %s", url)
        QDesktopServices.openUrl(QUrl(url))

    def chosen(self) -> str:
        return str(self.language.currentData())


class MainWindow(QMainWindow):
    """창 하나 = 기기 하나."""

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = Path(root)
        self.doc: Optional[LayoutDocument] = None
        self.metrics: Optional[dict[str, Any]] = None
        # 창 제목의 기기 이름을 완성된 문장으로 들고 있으면, 언어를 바꿨을 때
        # 제목만 옛 말로 남는다. 그래서 '무엇인지 + 값' 으로 두고 그릴 때 짓는다.
        self._device: tuple[str, str] = ("none", "")
        # 항등 검사를 통과하지 못한 홈화면은 편집해도 쓰지 않는다. 경고만 띄우고
        # 버튼은 살려 두면, 경고를 닫은 사용자에게는 아무 일도 없었던 것과 같다.
        self.writable = False
        self.installed: dict[str, str] = {}  # 번들 ID -> 이름 (기기에서 받은 설치 목록)

        self.worker = DeviceWorker(self.root)
        self.icons = IconCache(self.worker.icons)
        self.worker.start()

        # 제품 이름과 번호에는 옮길 것이 없다. 기기 이름 쪽이 언어를 따라 바뀐다.
        self.setWindowTitle(f"{product.NAME} {VERSION_TEXT}")
        self.resize(1280, 860)
        self.setStyleSheet(STYLE)

        self._pages: list[PageFrame] = []
        # 고른 항목. 판(ContainerView)이 저마다 들고 있으면 페이지를 건너
        # 여러 개를 고를 수 없다 — 묶기는 페이지를 건너 고르는 일이 흔하다.
        self.selection: set[str] = set()
        self._tile = 62
        self._refresh_pending = False

        self._build_ui()
        self._wire_worker()
        self._update_actions()
        i18n.on_language_changed(self.retranslate)

    @property
    def device_summary(self) -> str:
        kind, value = self._device
        if kind == "file":
            return tr("파일: {name}").format(name=value)
        if kind == "device":
            return value
        if kind == "connected":
            return tr("연결됨")
        return tr("연결되지 않음")

    # ------------------------------------------------------------------ 구성

    def _build_ui(self) -> None:
        bar = self.addToolBar("main")
        bar.setMovable(False)

        self.act_load = QAction(tr("기기에서 읽기"), self)
        self.act_load.triggered.connect(self._load)
        self.act_open = QAction(tr("백업 파일 열기"), self)
        self.act_open.triggered.connect(self._open_backup_file)
        self.act_icons = QAction(tr("아이콘 받기"), self)
        self.act_icons.triggered.connect(self._fetch_icons)
        self.act_undo = QAction(tr("실행 취소"), self)
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.triggered.connect(self._undo)
        self.act_redo = QAction(tr("다시 실행"), self)
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.act_redo.triggered.connect(self._redo)
        self.act_add_page = QAction(tr("페이지 추가"), self)
        self.act_add_page.triggered.connect(self._add_page)
        self.act_group = QAction(tr("묶기"), self)
        self.act_group.setShortcut(QKeySequence("Ctrl+G"))
        self.act_group.setToolTip(tr("고른 앱들을 새 묶음(폴더)으로 (Ctrl 을 누른 채 눌러 여러 개 고름)"))
        self.act_group.triggered.connect(self._group)
        self.act_rename = QAction(tr("이름 바꾸기"), self)
        self.act_rename.setShortcut(QKeySequence("F2"))
        self.act_rename.setToolTip(tr("고른 묶음의 이름을 바꾼다"))
        self.act_rename.triggered.connect(self._rename)
        self.act_apply = QAction(tr("적용"), self)
        self.act_apply.triggered.connect(self._apply)
        self.act_restore = QAction(tr("백업으로 복원"), self)
        self.act_restore.triggered.connect(self._restore)
        self.act_settings = QAction(tr("설정"), self)
        self.act_settings.setToolTip(tr("언어를 고릅니다"))
        self.act_settings.triggered.connect(self._settings)
        self.act_about = QAction(tr("정보"), self)
        self.act_about.setToolTip(tr("판·라이선스·소스"))
        self.act_about.triggered.connect(self._about)

        bar.addAction(self.act_load)
        bar.addAction(self.act_open)
        bar.addAction(self.act_icons)
        bar.addSeparator()
        bar.addAction(self.act_undo)
        bar.addAction(self.act_redo)
        bar.addAction(self.act_add_page)
        bar.addAction(self.act_group)
        bar.addAction(self.act_rename)
        bar.addSeparator()
        bar.addAction(self.act_apply)
        bar.addAction(self.act_restore)
        bar.addSeparator()

        self.zoom = QSlider(Qt.Orientation.Horizontal)
        self.zoom.setRange(MIN_TILE, MAX_TILE)
        self.zoom.setValue(self._tile)
        self.zoom.setFixedWidth(140)
        self.zoom.valueChanged.connect(self._set_tile)
        self.zoom_label = QLabel(tr(" 크기 "))
        bar.addWidget(self.zoom_label)
        bar.addWidget(self.zoom)
        self.fit_button = QPushButton(tr("모두 보이게"))
        self.fit_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.fit_button.clicked.connect(self._fit)
        bar.addWidget(self.fit_button)
        bar.addSeparator()
        bar.addAction(self.act_settings)
        bar.addAction(self.act_about)

        # 캔버스
        host = QWidget()
        host.setObjectName("canvasHost")
        self.flow = FlowLayout(host)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(host)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._host = host

        self.dock_frame: Optional[DockFrame] = None
        self.dock_row = QHBoxLayout()
        self.dock_row.setContentsMargins(0, 0, 0, 6)
        self.dock_row.addStretch(1)
        self.dock_row.addStretch(1)

        self.folder_panel: Optional[FolderPanel] = None
        self.folder_holder = QVBoxLayout()
        self.folder_holder.setContentsMargins(0, 0, 0, 0)

        center = QWidget()
        center.setObjectName("canvasHost")
        column = QVBoxLayout(center)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        # 읽기 전에는 안내판이 캔버스 자리를 대신 채운다. 빈 화면으로 맞이하면
        # 무엇이 없어서 안 되는지가 '기기에서 읽기'를 누른 뒤에야 드러난다.
        self.guide = GuideBoard()
        self.guide.readRequested.connect(self._load)
        column.addWidget(self.guide, 1)
        column.addWidget(self.scroll, 1)
        column.addLayout(self.folder_holder)
        column.addLayout(self.dock_row)
        self._show_guide(True)

        # 변경 목록
        side = QWidget()
        side.setObjectName("canvasHost")
        side.setFixedWidth(330)
        self.change_head = QLabel(tr("변경 없음"))
        self.change_head.setStyleSheet("font-weight: bold;")
        self.change_list = QListWidget()
        self.note = QLabel(
            tr("아이콘을 끌어 옮기고, 폴더는 두 번 눌러 엽니다.\n"
            "폴더 한가운데에 놓으면 폴더 안으로, 옆에 놓으면 그 자리에 끼웁니다.")
        )
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color:#8f97ab; font-size:11px;")
        # 홈화면에 없는 앱은 적용할 때 iOS 가 끝에 되붙인다. 그때 처음 알면 앱이
        # 제멋대로 늘어난 것으로 보이므로, 편집하는 동안 늘 보이는 곳에 둔다.
        self.unplaced_head = QLabel(tr("미배치 앱"))
        self.unplaced_head.setStyleSheet("font-weight: bold; color:#e8c977;")
        self.unplaced_list = QListWidget()
        self.unplaced_list.setMaximumHeight(120)
        self.unplaced_note = QLabel(tr("적용하면 마지막 페이지 끝에 붙습니다 (iOS 동작)."))
        self.unplaced_note.setWordWrap(True)
        self.unplaced_note.setStyleSheet("color:#8f97ab; font-size:11px;")

        side_box = QVBoxLayout(side)
        side_box.setContentsMargins(8, 8, 8, 8)
        side_box.addWidget(self.change_head)
        side_box.addWidget(self.change_list, 1)
        side_box.addWidget(self.unplaced_head)
        side_box.addWidget(self.unplaced_list)
        side_box.addWidget(self.unplaced_note)
        side_box.addWidget(self.note)
        self._show_unplaced([])

        wrapper = QWidget()
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(center, 1)
        row.addWidget(side)
        self.setCentralWidget(wrapper)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(200)
        self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().showMessage(tr("iPhone 을 연결하고 ‘기기에서 읽기’를 눌러 주세요."))

    def _about(self) -> None:
        """이 프로그램이 무엇이고 무엇 위에 서 있는지. 라이선스 원문도 여기서 읽는다."""
        AboutDialog(self).exec()

    def _settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        code = dialog.chosen()
        if code == i18n.language():
            return
        i18n.choose(code)  # 저장까지 한다. 화면은 알림을 받아 retranslate() 로 이어진다
        log.info("언어를 바꿨다: %s", code)

    def retranslate(self) -> None:
        """언어가 바뀌면 창의 말을 전부 다시 칠한다.

        Qt 는 한 번 넣은 글자를 스스로 바꾸지 않는다. 그래서 **문구를 넣은 자리마다**
        여기에 짝이 있어야 한다 — 짝이 없는 위젯은 앱을 다시 켤 때까지 옛 말로 남는다.
        캔버스는 통째로 다시 지어서 짝을 일일이 적지 않는다 (열어 둔 묶음은 되살린다).
        """
        self.act_load.setText(tr("기기에서 읽기"))
        self.act_open.setText(tr("백업 파일 열기"))
        self.act_icons.setText(tr("아이콘 받기"))
        self.act_undo.setText(tr("실행 취소"))
        self.act_redo.setText(tr("다시 실행"))
        self.act_add_page.setText(tr("페이지 추가"))
        self.act_group.setText(tr("묶기"))
        self.act_group.setToolTip(tr("고른 앱들을 새 묶음(폴더)으로 (Ctrl 을 누른 채 눌러 여러 개 고름)"))
        self.act_rename.setText(tr("이름 바꾸기"))
        self.act_rename.setToolTip(tr("고른 묶음의 이름을 바꾼다"))
        self.act_apply.setText(tr("적용"))
        self.act_restore.setText(tr("백업으로 복원"))
        self.act_settings.setText(tr("설정"))
        self.act_settings.setToolTip(tr("언어를 고릅니다"))
        self.act_about.setText(tr("정보"))
        self.act_about.setToolTip(tr("판·라이선스·소스"))
        self.act_settings.setToolTip(tr("언어를 고릅니다"))
        self.zoom_label.setText(tr(" 크기 "))
        self.fit_button.setText(tr("모두 보이게"))
        self.note.setText(
            tr("아이콘을 끌어 옮기고, 폴더는 두 번 눌러 엽니다.\n"
            "폴더 한가운데에 놓으면 폴더 안으로, 옆에 놓으면 그 자리에 끼웁니다.")
        )
        self.unplaced_note.setText(tr("적용하면 마지막 페이지 끝에 붙습니다 (iOS 동작)."))

        self.guide.retranslate()
        opened = self.folder_panel.node_uid if self.folder_panel is not None else None
        self._rebuild_canvas()
        if opened is not None and self.folder_panel is not None:
            self.folder_panel.open_folder(opened)
        self._refresh()  # 변경 목록·미배치 앱·창 제목이 여기서 다시 지어진다
        self.statusBar().showMessage(
            self.doc.summary()
            if self.doc is not None
            else tr("iPhone 을 연결하고 ‘기기에서 읽기’를 눌러 주세요.")
        )

    def _show_guide(self, showing: bool) -> None:
        """안내판과 캔버스는 같은 자리를 나눠 쓴다 — 둘 다 보이면 어느 쪽도 넓지 않다."""
        self.guide.setVisible(showing)
        self.scroll.setVisible(not showing)

    def _wire_worker(self) -> None:
        self.worker.loaded.connect(self._on_loaded)
        self.worker.installedListed.connect(self._on_installed)
        self.worker.iconsUpdated.connect(self._on_icons)
        self.worker.applied.connect(self._on_applied)
        self.worker.restoredFrom.connect(self._on_restored)
        self.worker.progressed.connect(self._on_progress)
        self.worker.busyChanged.connect(self._on_busy)
        self.worker.failed.connect(self._on_failed)

    # ------------------------------------------------------------------ 문서

    def _set_document(self, state: list[Any], metrics: Optional[dict[str, Any]]) -> None:
        self.metrics = metrics
        self.doc = LayoutDocument(state, Grid.from_metrics(metrics))
        self.writable = self.doc.verify_identity()
        if not self.writable:
            # 편집 전인데 원본과 다르다면 우리가 해석하지 못한 구조가 있다는 뜻이다.
            # 이 상태로 쓰면 그 부분이 사라진다. 읽기까지만 허용한다.
            QMessageBox.critical(
                self,
                tr("이 홈화면은 편집할 수 없습니다"),
                tr("읽어 들인 홈화면을 그대로 되돌려 쓸 수 없는 구조가 섞여 있습니다.\n"
                "안전을 위해 쓰기를 막습니다. logs/ 의 기록을 확인해 주세요."),
            )
            log.error("항등 검사 실패 — 쓰기를 막는다")
        self._show_guide(False)
        self._rebuild_canvas()
        self._refresh()
        self.statusBar().showMessage(self.doc.summary())
        wanted = wanted_icons(self.doc)
        if self.worker.icons.missing(wanted):
            self.statusBar().showMessage(
                self.doc.summary() + tr(" · 아이콘이 없습니다. ‘아이콘 받기’를 눌러 주세요.")
            )

    def _rebuild_canvas(self) -> None:
        while self.flow.count():
            item = self.flow.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._pages = []
        if self.dock_frame is not None:
            self.dock_row.removeWidget(self.dock_frame)
            self.dock_frame.deleteLater()
            self.dock_frame = None
        if self.folder_panel is not None:
            self.folder_holder.removeWidget(self.folder_panel)
            self.folder_panel.deleteLater()
            self.folder_panel = None
        if self.doc is None:
            return

        for page in self.doc.pages:
            frame = PageFrame(self.doc, page.uid, self.icons, self._tile, parent=self._host)
            frame.edited.connect(self._schedule_refresh)
            frame.folderRequested.connect(self._open_folder)
            frame.statusChanged.connect(self._on_status)
            frame.selected.connect(self._on_selected)
            frame.toggled.connect(self._on_toggled)
            frame.grouped.connect(self._on_grouped)
            frame.pageMoved.connect(self._move_page)
            frame.pageRemoved.connect(self._remove_page)
            self.flow.addWidget(frame)
            frame.show()
            self._pages.append(frame)

        self.dock_frame = DockFrame(self.doc, self.icons, self._tile)
        self.dock_frame.edited.connect(self._schedule_refresh)
        self.dock_frame.folderRequested.connect(self._open_folder)
        self.dock_frame.statusChanged.connect(self._on_status)
        self.dock_frame.selected.connect(self._on_selected)
        self.dock_frame.toggled.connect(self._on_toggled)
        self.dock_frame.grouped.connect(self._on_grouped)
        self.dock_row.insertWidget(1, self.dock_frame)

        self.folder_panel = FolderPanel(self.doc, self.icons, self._tile)
        self.folder_panel.edited.connect(self._schedule_refresh)
        self.folder_panel.statusChanged.connect(self._on_status)
        self.folder_panel.selected.connect(self._on_selected)
        self.folder_panel.toggled.connect(self._on_toggled)
        self.folder_panel.grouped.connect(self._on_grouped)
        self.folder_panel.renameRequested.connect(self._rename_folder)
        self.folder_panel.closed.connect(self._close_folder)
        self.folder_holder.addWidget(self.folder_panel)

    def _schedule_refresh(self) -> None:
        """다시 그리기는 항상 다음 차례로 미룬다.

        드롭 처리 도중에 그 드롭을 받은 위젯을 지우면 앱이 죽는다. 편집은 위젯 안에서
        일어나므로, 화면 갱신은 그 이벤트가 끝난 뒤로 미뤄야 안전하다.
        """
        if self._refresh_pending:
            return
        self._refresh_pending = True
        QTimer.singleShot(0, self._do_refresh)

    def _do_refresh(self) -> None:
        self._refresh_pending = False
        self._refresh()

    def _refresh(self) -> None:
        if self.doc is None:
            self._update_actions()
            return
        expected = [page.uid for page in self.doc.pages]
        current = [frame.container_uid for frame in self._pages]
        if expected != current:
            self._rebuild_canvas()  # 페이지가 늘거나 줄거나 순서가 바뀌었다
        for frame in self._pages:
            frame.refresh()
        if self.dock_frame is not None:
            self.dock_frame.refresh()
        if self.folder_panel is not None:
            self.folder_panel.refresh()

        changes = self.doc.changes()
        self.change_list.clear()
        self.change_list.addItems(changes)
        self.change_head.setText(
            tr("미적용 변경 {n}건").format(n=len(changes)) if changes else tr("변경 없음")
        )
        self._show_unplaced(self._unplaced())
        self._apply_selection()
        self._update_actions()

    def _show_unplaced(self, entries: list[tuple[str, str]]) -> None:
        self.unplaced_list.clear()
        self.unplaced_list.addItems([name for _bundle_id, name in entries])
        visible = bool(entries)
        self.unplaced_head.setText(tr("미배치 앱 {n}개").format(n=len(entries)))
        self.unplaced_head.setVisible(visible)
        self.unplaced_list.setVisible(visible)
        self.unplaced_note.setVisible(visible)

    def _unplaced(self) -> list[tuple[str, str]]:
        if self.doc is None or not self.installed:
            return []
        return self.doc.unplaced_apps(self.installed)

    def _on_installed(self, installed: object) -> None:
        self.installed = dict(installed or {})
        self._show_unplaced(self._unplaced())
        if self.installed:
            log.info("설치 %d개 · 미배치 %d개", len(self.installed), len(self._unplaced()))

    def _update_actions(self) -> None:
        has = self.doc is not None
        busy = self.worker.busy
        dirty = bool(has and self.doc.dirty)
        self.act_undo.setEnabled(has and self.doc.can_undo and not busy)
        self.act_redo.setEnabled(has and self.doc.can_redo and not busy)
        self.act_add_page.setEnabled(has and not busy)
        self.act_group.setEnabled(
            has and not busy and self.doc.can_group(sorted(self.selection)) is None
        )
        self.act_rename.setEnabled(has and not busy and self._rename_target() is not None)
        self.act_apply.setEnabled(dirty and self.writable and not busy)
        self.act_icons.setEnabled(has and not busy)
        self.act_load.setEnabled(not busy)
        self.act_restore.setEnabled(not busy)
        mark = " •" if dirty else ""
        self.setWindowTitle(
            f"{product.NAME} {VERSION_TEXT} — {self.device_summary}{mark}"
        )

    # ------------------------------------------------------------------ 조작

    def _set_tile(self, value: int) -> None:
        self._tile = value
        self.icons.clear_scaled()
        for frame in self._pages:
            frame.set_tile(value)
        if self.dock_frame is not None:
            self.dock_frame.set_tile(value)
        if self.folder_panel is not None:
            self.folder_panel.set_tile(value)
        self.flow.invalidate()

    def _fit(self) -> None:
        """페이지 전부가 보이는 가장 큰 배율을 찾는다 (REQ-012)."""
        if self.doc is None or not self._pages:
            return
        viewport = self.scroll.viewport().size()
        count = len(self._pages)
        grid = self.doc.grid
        for tile in range(MAX_TILE, MIN_TILE - 1, -1):
            cell_w = tile + max(8, tile // 4)
            cell_h = tile + max(11, int(tile * 0.30)) + max(6, tile // 6)
            pad = max(6, tile // 8) * 2
            page_w = grid.columns * cell_w + pad + 10
            page_h = grid.rows * cell_h + pad + 28
            per_row = max(1, (viewport.width() - 20) // (page_w + 14))
            rows = (count + per_row - 1) // per_row
            if rows * (page_h + 14) <= viewport.height() - 20:
                self.zoom.setValue(tile)
                self.statusBar().showMessage(
                    tr("페이지 {n}장을 한 화면에 폈습니다.").format(n=count)
                )
                return
        # 가장 작게 줄여도 안 들어간다. 조용히 최소 배율에 머무르면 사용자는 버튼이
        # 고장 난 줄 안다 — 무엇이 부족한지 말한다.
        self.zoom.setValue(MIN_TILE)
        self.statusBar().showMessage(
            tr("페이지 {n}장은 이 창 크기에 다 들어가지 않습니다. 창을 키우면 더 보입니다.")
            .format(n=count)
        )

    def _undo(self) -> None:
        if self.doc is None:
            return
        try:
            self.doc.undo()
        except LayoutError as exc:
            self.statusBar().showMessage(str(exc))
        self._refresh()

    def _redo(self) -> None:
        if self.doc is None:
            return
        try:
            self.doc.redo()
        except LayoutError as exc:
            self.statusBar().showMessage(str(exc))
        self._refresh()

    def _add_page(self) -> None:
        if self.doc is None:
            return
        try:
            self.doc.add_page()
        except LayoutError as exc:
            self.statusBar().showMessage(str(exc))
            return
        self._refresh()

    def _move_page(self, source: int, target: int) -> None:
        if self.doc is None:
            return
        try:
            self.doc.reorder_pages(source, target)
        except LayoutError as exc:
            self.statusBar().showMessage(str(exc))
            return
        self._schedule_refresh()

    def _remove_page(self, index: int) -> None:
        if self.doc is None:
            return
        try:
            self.doc.remove_page(index)
        except LayoutError as exc:
            self.statusBar().showMessage(str(exc))
            return
        self._schedule_refresh()

    def _open_folder(self, node_uid: str) -> None:
        if self.folder_panel is not None:
            self.folder_panel.open_folder(node_uid)

    def _close_folder(self) -> None:
        if self.folder_panel is not None:
            self.folder_panel.hide()
            self.folder_panel.node_uid = None

    def _on_status(self, message: str) -> None:
        if message:
            self.statusBar().showMessage(message)

    def _on_selected(self, node_uid: str) -> None:
        self.selection = {node_uid} if node_uid else set()
        self._apply_selection()
        self._update_actions()

    def _on_toggled(self, node_uid: str) -> None:
        """Ctrl 을 누른 채 누른 것 — 골라 놓은 것에 더하거나 뺀다."""
        if not node_uid:
            return
        self.selection.symmetric_difference_update({node_uid})
        self._apply_selection()
        self._update_actions()

    def _apply_selection(self) -> None:
        # 사라진 항목(묶여 들어갔거나 되돌려진 것)은 조용히 뺀다. 없는 것을 고른
        # 상태로 두면 '묶기'가 켜져 있는데 눌러도 아무 일이 없다.
        if self.doc is not None:
            alive = {
                node.uid for container in self.doc.containers() for node in container.items
            }
            self.selection &= alive
        for frame in self._pages:
            frame.set_selection(self.selection)
        if self.dock_frame is not None:
            self.dock_frame.set_selection(self.selection)
        if self.folder_panel is not None:
            self.folder_panel.set_selection(self.selection)
        if len(self.selection) > 1:
            self.statusBar().showMessage(
                tr("{n}개 골랐습니다 — 묶기(Ctrl+G)로 하나로 묶을 수 있습니다.").format(
                    n=len(self.selection)
                )
            )

    # -------------------------------------------------------------- 묶기

    def _on_grouped(self, dragged_uid: str, target_uid: str) -> None:
        """앱 위에 앱을 놓았다 — iPhone 에서와 같이 둘만 묶는다."""
        self.selection = {dragged_uid, target_uid}
        self._apply_selection()
        self._group()

    def _group(self) -> None:
        if self.doc is None:
            return
        chosen = sorted(self.selection)
        reason = self.doc.can_group(chosen)
        if reason:
            self.statusBar().showMessage(reason)
            return
        name, ok = QInputDialog.getText(
            self,
            tr("새 묶음"),
            tr("{n}개를 묶습니다. 묶음 이름:").format(n=len(chosen)),
            text=self.doc.suggest_group_name(chosen),
        )
        if not ok:
            return
        try:
            uid = self.doc.group(chosen, name)
        except LayoutError as exc:
            self.statusBar().showMessage(str(exc))
            return
        # 묶고 나면 묶음 하나만 골라 둔다 — 안에 든 것은 이제 그 안에 있다.
        self.selection = {uid}
        self.statusBar().showMessage(
            tr("묶음 “{name}” 을(를) 만들었습니다. 두 번 누르면 열립니다.").format(
                name=self.doc.node(uid).label
            )
        )
        self._schedule_refresh()

    def _rename_target(self) -> Optional[str]:
        """이름을 바꿀 묶음. 하나만 골랐고 그것이 묶음일 때만."""
        if self.doc is None or len(self.selection) != 1:
            return None
        uid = next(iter(self.selection))
        try:
            return uid if self.doc.node(uid).is_folder else None
        except LayoutError:
            return None

    def _rename(self) -> None:
        uid = self._rename_target()
        if uid is None:
            self.statusBar().showMessage(tr("이름을 바꿀 묶음을 하나 골라 주세요."))
            return
        self._rename_folder(uid)

    def _rename_folder(self, node_uid: str) -> None:
        if self.doc is None:
            return
        try:
            node = self.doc.node(node_uid)
        except LayoutError as exc:
            self.statusBar().showMessage(str(exc))
            return
        name, ok = QInputDialog.getText(
            self, tr("묶음 이름 바꾸기"), tr("새 이름:"), text=node.label
        )
        if not ok:
            return
        try:
            self.doc.rename_folder(node_uid, name)
        except LayoutError as exc:
            self.statusBar().showMessage(str(exc))
            return
        self._schedule_refresh()

    # ------------------------------------------------------------------ 기기

    def _load(self) -> None:
        if self.doc is not None and self.doc.dirty:
            answer = QMessageBox.question(
                self,
                tr("적용하지 않은 변경이 있습니다"),
                tr("기기에서 다시 읽으면 지금까지의 편집이 사라집니다. 계속할까요?"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.worker.load()

    def _open_backup_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("백업 파일 열기"), str(self.root / "backups"), tr("홈화면 백업 (*.plist)")
        )
        if not path:
            return
        try:
            state = self.worker.backups.load(Path(path))
        except Exception as exc:
            QMessageBox.warning(self, tr("열 수 없습니다"), str(exc))
            return
        self._device = ("file", Path(path).name)
        self._set_document(state, self.metrics)

    def _fetch_icons(self) -> None:
        if self.doc is None:
            return
        self.worker.fetch_icons(wanted_icons(self.doc))

    def _apply(self) -> None:
        if self.doc is None:
            return
        changes = self.doc.changes()
        if not changes:
            self.statusBar().showMessage(tr("적용할 변경이 없습니다."))
            return
        dialog = ApplyDialog(changes, [name for _bid, name in self._unplaced()], self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.worker.apply(self.doc.to_state(), reason="before-edit")

    def _restore(self) -> None:
        backups = self.worker.backups.list_backups()
        if not backups:
            QMessageBox.information(self, tr("백업 없음"), tr("아직 만들어진 백업이 없습니다."))
            return
        path, _ = QFileDialog.getOpenFileName(
            self, tr("복원할 백업 선택"), str(self.worker.backups.dir), tr("홈화면 백업 (*.plist)")
        )
        if not path:
            return
        answer = QMessageBox.question(
            self,
            tr("백업으로 복원"),
            tr(
                "{name} 시점으로 홈화면을 되돌립니다.\n"
                "복원도 쓰기이므로, 복원 직전 상태를 먼저 백업합니다. 계속할까요?"
            ).format(name=Path(path).name),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.worker.restore_backup(Path(path))

    # ------------------------------------------------------------- 워커 응답

    def _on_loaded(self, state: object, metrics: object, info: object) -> None:
        if info is not None:
            summary = getattr(info, "summary", None)
            self._device = ("device", summary()) if summary else ("connected", "")
        self._set_document(list(state), dict(metrics) if metrics else None)

    def _on_icons(self, fetched: int, requested: int) -> None:
        self.icons.invalidate()
        self._refresh()
        if requested == 0:
            self.statusBar().showMessage(tr("아이콘이 모두 준비되어 있습니다."))
        else:
            missed = requested - fetched
            tail = tr(
                " (받지 못한 {n}개는 웹 클립처럼 원래 이미지가 없는 항목일 수 있습니다)"
            ).format(n=missed)
            self.statusBar().showMessage(
                tr("아이콘 {done}/{total}개를 받았습니다.").format(
                    done=fetched, total=requested
                )
                + (tail if missed else "")
            )

    def _on_applied(self, result: object) -> None:
        payload = dict(result)  # type: ignore[arg-type]
        comparison = payload["comparison"]
        backup = payload["backup"]
        state = payload["state"]

        lines = [tr("백업: {name}").format(name=Path(backup.path).name)]
        if comparison.safe:
            lines.append(tr("사용자 배치가 그대로 반영되었습니다. 손실·이동 없음."))
        else:
            lines.append(
                tr("⚠ 손실 {lost}건 · 의도치 않은 이동 {moved}건").format(
                    lost=len(comparison.lost), moved=len(comparison.moved)
                )
            )
            lines.extend(comparison.lost[:5])
            lines.extend(comparison.moved[:5])
        if comparison.added:
            lines.append(
                tr(
                    "iOS 가 앱 {n}개를 마지막 페이지 끝에 되붙였습니다"
                    " (앱 라이브러리에만 있던 앱)."
                ).format(n=len(comparison.added))
            )

        # 기기에서 되읽은 것을 새 원본으로 삼는다. 그래야 다음 편집의 기준이 실제와 같다.
        self._set_document(list(state), self.metrics)
        self.statusBar().showMessage(" · ".join(lines[:2]))
        box = QMessageBox(self)
        box.setWindowTitle(tr("적용 완료") if comparison.safe else tr("적용했지만 확인이 필요합니다"))
        box.setIcon(
            QMessageBox.Icon.Information if comparison.safe else QMessageBox.Icon.Warning
        )
        box.setText("\n".join(lines))
        box.exec()

    def _on_restored(self, result: object) -> None:
        payload = dict(result)  # type: ignore[arg-type]
        self._set_document(list(payload["state"]), self.metrics)
        QMessageBox.information(
            self,
            tr("복원 완료"),
            tr("복원 직전 상태를 {name} 로 백업했습니다.").format(
                name=Path(payload["backup"].path).name
            ),
        )

    def _on_progress(self, message: str, done: int, total: int) -> None:
        self.statusBar().showMessage(message)
        if total > 0:
            self.progress.setVisible(True)
            self.progress.setRange(0, total)
            self.progress.setValue(done)
        else:
            self.progress.setVisible(True)
            self.progress.setRange(0, 0)

    def _on_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        if not busy:
            self.progress.setRange(0, 1)
        self.setCursor(Qt.CursorShape.BusyCursor if busy else Qt.CursorShape.ArrowCursor)
        self._update_actions()

    def _on_failed(self, message: str, action: str) -> None:
        self.statusBar().showMessage(message)
        box = QMessageBox(self)
        box.setWindowTitle(tr("문제가 생겼습니다"))
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(message)
        if action:
            box.setInformativeText(action)
        box.exec()

    # ------------------------------------------------------------------ 종료

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.doc is not None and self.doc.dirty:
            answer = QMessageBox.question(
                self,
                tr("적용하지 않은 변경이 있습니다"),
                tr("편집한 내용은 iPhone 에 반영되지 않았습니다. 그대로 닫을까요?"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        i18n.off_language_changed(self.retranslate)
        self.worker.shutdown()
        event.accept()
