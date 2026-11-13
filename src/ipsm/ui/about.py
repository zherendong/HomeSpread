# -*- coding: utf-8 -*-
"""정보 창 — 이 프로그램이 무엇이고, 누구의 것을 빌려 썼는가.

**왜 창 안에서 원문을 보여주는가:** 라이선스 파일을 바깥 프로그램(메모장 등)으로
열면 exe 로 묶였을 때 곤란해진다. 묶인 파일은 임시 폴더에 잠깐 풀렸다가 프로그램이
끝나면 지워지므로, 메모장이 열어 둔 파일이 사라지거나 애초에 열리지 않는다. 그래서
읽어서 창에 그린다 — 어디서 실행하든 똑같이 보인다.

**왜 GPL 인가:** 기기와 말하는 일을 `pymobiledevice3` 가 하는데 그것이 GPL 이다.
함께 묶어 내보내는 순간 이 프로그램 전체가 GPL 이 된다. 고를 수 있는 것이 아니라
따라오는 결과이므로, 숨기지 않고 첫 화면에 적는다.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import paths, product
from ..i18n import tr
from ..version import VERSION_TEXT


class TextWindow(QDialog):
    """긴 원문 하나를 그대로 보여주는 창. 고칠 수 없고, 복사는 된다."""

    def __init__(self, title: str, body: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 560)

        self.body = QPlainTextEdit()
        self.body.setPlainText(body)
        self.body.setReadOnly(True)
        # 원문은 줄 길이가 정해져 있다. 접으면 문단 모양이 흐트러져 읽기 나빠진다.
        self.body.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.body.setObjectName("licenseText")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(tr("닫기"))
        buttons.rejected.connect(self.reject)

        box = QVBoxLayout(self)
        box.addWidget(self.body, 1)
        box.addWidget(buttons)


class AboutDialog(QDialog):
    """이름·판·라이선스·소스 받는 길."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("정보"))
        self.setMinimumWidth(430)

        # 이름과 번호에는 옮길 것이 없다.
        name = QLabel(f"{product.NAME} {VERSION_TEXT}")
        name.setObjectName("aboutName")
        tagline = QLabel(tr(product.TAGLINE))
        tagline.setObjectName("aboutTagline")

        summary = QLabel(
            tr(
                "이 프로그램은 자유 소프트웨어입니다. {license} 아래에서 누구나 자유롭게 "
                "쓰고, 뜯어보고, 고쳐서 다시 나눠 줄 수 있습니다. 보증은 없습니다."
            ).format(license=product.LICENSE_SPDX)
        )
        summary.setWordWrap(True)
        summary.setObjectName("aboutBody")

        self.source = QLabel(self._source_words())
        self.source.setWordWrap(True)
        self.source.setObjectName("aboutBody")
        self.source.setOpenExternalLinks(True)

        self.license_button = QPushButton(tr("라이선스 전문"))
        self.license_button.clicked.connect(self._show_license)
        self.notices_button = QPushButton(tr("함께 실려 오는 것들"))
        self.notices_button.clicked.connect(self._show_notices)
        self.privacy_button = QPushButton(tr("개인정보 처리방침"))
        self.privacy_button.clicked.connect(self._show_privacy)

        row = QHBoxLayout()
        row.addWidget(self.license_button)
        row.addWidget(self.notices_button)
        row.addWidget(self.privacy_button)
        row.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(tr("닫기"))
        buttons.rejected.connect(self.reject)

        box = QVBoxLayout(self)
        box.addWidget(name)
        box.addWidget(tagline)
        box.addSpacing(8)
        box.addWidget(summary)
        box.addWidget(self.source)
        box.addSpacing(4)
        box.addLayout(row)
        box.addWidget(buttons)

    def _source_words(self) -> str:
        """소스를 받는 길. 주소가 없으면 없는 대로 말한다.

        GPL 은 실행 파일을 받은 사람이 소스에 닿을 수 있기를 요구한다. 아직 공개
        저장소가 없다면 있지도 않은 주소를 적는 대신, 무엇을 요구할 수 있는지를
        알려 주는 편이 정직하고 또 실제로 도움이 된다.
        """
        if product.SOURCE_URL:
            upstream = tr("Upstream source: {url}").format(
                url=f'<a href="{product.SOURCE_URL}">{product.SOURCE_URL}</a>'
            )
            source = paths.bundled(f"{product.NAME}-source.zip")
            if source is not None:
                upstream += "<br>" + tr("Modified source included in this app: {url}").format(
                    url=f'<a href="{QUrl.fromLocalFile(str(source)).toString()}">{product.NAME}-source.zip</a>')
            return upstream
        return tr("소스 전체를 요구할 권리가 있습니다. 배포한 사람에게 요청하세요.")

    def _read(self, name: str) -> str:
        found = paths.bundled(name)
        if found is None:
            return tr("'{name}' 을(를) 찾을 수 없습니다.").format(name=name)
        try:
            return found.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return tr("'{name}' 을(를) 읽을 수 없습니다 ({why}).").format(
                name=name, why=exc.__class__.__name__
            )

    def _show_license(self) -> None:
        TextWindow(tr("라이선스 전문"), self._read("LICENSE"), self).exec()

    def _show_notices(self) -> None:
        TextWindow(
            tr("함께 실려 오는 것들"), self._read("THIRD-PARTY-NOTICES.md"), self
        ).exec()

    def _show_privacy(self) -> None:
        """스토어가 요구하는 방침을 프로그램 안에서도 읽을 수 있게 한다.

        Partner Center 에는 주소를 적어야 하지만, 그 주소는 인터넷이 있어야 열린다.
        정작 이 프로그램은 인터넷 없이 도는 것이 요점이므로 원문도 함께 싣는다.
        """
        from ..i18n import language

        filename = "PRIVACY.zh-CN.md" if language() == "zh_CN" else "PRIVACY.md"
        TextWindow(tr("개인정보 처리방침"), self._read(filename), self).exec()

    def open_source_page(self) -> None:
        """주소가 있을 때만 브라우저를 연다."""
        if product.SOURCE_URL:
            QDesktopServices.openUrl(QUrl(product.SOURCE_URL))
