"""Display and export a local preflight report, with no collection or device API."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
                               QLabel, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout)

from ..drafts import OfflineDraft
from ..evidence import EvidenceBundle
from ..i18n import tr
from ..preflight import (build_preflight_report, evidence_source_label,
                         render_preflight_report, save_preflight_report)
from ..safeio import private_directory


class PreflightDialog(QDialog):
    def __init__(self, draft: OfflineDraft, root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Draft preflight report"))
        self.resize(780, 650)
        self.root = Path(root)
        self.evidence: EvidenceBundle | None = None
        build_preflight_report(draft)  # Validate the displayed state, not only a regenerated history.
        # Keep a detached, replay-validated draft snapshot while the dialog is open.
        self.draft = OfflineDraft(draft.origin)
        for operation in draft.operations:
            self.draft.swap(operation.page, operation.index_a, operation.index_b)
        self.report = {}
        self.scope = QLabel(tr("Local inspection only. No device collection or write is performed."))
        self.scope.setTextFormat(Qt.TextFormat.PlainText)
        self.scope.setWordWrap(True)
        self.origin = QLabel()
        self.origin.setTextFormat(Qt.TextFormat.PlainText)
        self.origin.setWordWrap(True)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setObjectName("licenseText")
        self.import_button = QPushButton(tr("Import evidence package"))
        self.import_button.setObjectName("preflightImport")
        self.import_button.clicked.connect(self._import)
        self.export_button = QPushButton(tr("Export preflight report"))
        self.export_button.setObjectName("preflightExport")
        self.export_button.clicked.connect(self._export)
        row = QHBoxLayout()
        row.addWidget(self.import_button)
        row.addWidget(self.export_button)
        row.addStretch(1)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.button(QDialogButtonBox.StandardButton.Close).setText(tr("닫기"))
        close.rejected.connect(self.reject)
        box = QVBoxLayout(self)
        box.addWidget(self.scope)
        box.addWidget(self.origin)
        box.addLayout(row)
        box.addWidget(self.text, 1)
        box.addWidget(close)
        self.refresh_report()

    def refresh_report(self) -> None:
        self.report = build_preflight_report(self.draft, self.evidence)
        self.origin.setText(tr("Evidence: {source}").format(source=evidence_source_label(self.evidence.source)) if self.evidence else
                            tr("No evidence package imported; only the draft's original backup is available."))
        self.text.setPlainText(render_preflight_report(self.report))

    def load_evidence(self, path: Path) -> None:
        evidence = EvidenceBundle.load(Path(path))
        report = build_preflight_report(self.draft, evidence)
        self.evidence, self.report = evidence, report
        self.origin.setText(tr("Evidence: {source}").format(source=evidence_source_label(evidence.source)))
        self.text.setPlainText(render_preflight_report(report))

    def export_report(self, path: Path, *, replace: bool = False) -> Path:
        self.refresh_report()  # A receipt cannot stay fresh just because a dialog stayed open.
        return save_preflight_report(path, self.report, replace=replace)

    def _error(self, exc: Exception) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(tr("Preflight report error"))
        box.setIcon(QMessageBox.Icon.Warning)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(tr("Cannot process the local report: {why}").format(why=exc))
        box.exec()

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("Import evidence package"),
                                              str(self.root / "evidence"), tr("Read-only evidence (*.hsevidence)"))
        if path:
            try:
                self.load_evidence(Path(path))
            except (ValueError, OSError, TypeError) as exc:
                self._error(exc)

    def _export(self) -> None:
        try:
            folder = self.root / "preflight_reports"
            private_directory(folder)
            picker = QFileDialog(self, tr("Export preflight report"), str(folder))
            picker.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            picker.setFileMode(QFileDialog.FileMode.AnyFile)
            picker.setNameFilter(tr("Preflight report (*.hspreflight)"))
            picker.setDefaultSuffix("hspreflight")
            picker.selectFile(f"preflight_{datetime.now():%Y%m%d_%H%M%S}.hspreflight")
            try:
                if picker.exec() != QDialog.DialogCode.Accepted:
                    return
                selected = picker.selectedFiles()
                if not selected:
                    return
                path = selected[0]
            finally:
                picker.deleteLater()
            target = Path(path)
            if not target.suffix:
                target = target.with_suffix(".hspreflight")
                if target.exists() and QMessageBox.question(
                    self, tr("Replace preflight report?"), tr("Replace this existing local preflight report?"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                    return
            self.export_report(target, replace=target.exists())
        except (ValueError, OSError, TypeError) as exc:
            self._error(exc)
