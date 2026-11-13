"""Synthetic widget and Duo previews. No live device or personal layout fixtures."""
import copy
import os
import plistlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QCoreApplication, QEvent, QMimeData, QPoint, Qt
from PySide6.QtGui import QDragEnterEvent
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

from ipsm import apple_devices, i18n
from ipsm.icons import IconStore
from ipsm.layout import Grid, LayoutDocument
from ipsm.ui.canvas import PageFrame
from ipsm.ui.main_window import MainWindow
from ipsm.ui.tiles import IconCache, MIME_NODE
from ipsm.ui.worker import DeviceWorker


def app_icon(number):
    return {"displayIdentifier": f"example.synthetic.app{number}", "displayName": f"示例 {number}"}


def widget(size="medium", members=0):
    raw = {"displayIdentifier": "example.synthetic.widget", "iconType": "custom",
           "gridSize": size, "iconLists": []}
    if members:
        raw["elements"] = [{"elementType": "widget", "widgetIdentifier": f"example.stack.{n}"} for n in range(members)]
    else:
        raw.update(elementType="widget", widgetIdentifier="example.widget")
    return raw


STATE = [[app_icon(100), app_icon(101), app_icon(102)],
         [widget(members=7)] + [app_icon(n) for n in range(8)],
         [widget()] + [app_icon(n) for n in range(8, 24)],
         [widget("small"), {"listType": "folder", "displayName": "示例文件夹", "iconLists": [[app_icon(30)]]}]]


@pytest.fixture(scope="session")
def qtapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESPREAD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOMESPREAD_CACHE_DIR", str(tmp_path / "cache"))
    language = i18n.language()
    i18n.set_language("en")
    yield
    i18n.set_language(language)


@pytest.fixture
def window(qtapp, tmp_path, monkeypatch):
    monkeypatch.setattr(DeviceWorker, "start", lambda self: None)
    monkeypatch.setattr(DeviceWorker, "shutdown", lambda self: None)
    monkeypatch.setattr(apple_devices, "look", lambda: (_ for _ in ()).throw(AssertionError("No USB detection in offline preview")))
    win = MainWindow(tmp_path, offline=True)
    yield win
    win.close()
    i18n.off_language_changed(win.retranslate)
    win.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture
def page_factory(qtapp, tmp_path):
    frames = []
    def create(doc, index):
        frame = PageFrame(doc, doc.pages[index].uid, IconCache(IconStore(tmp_path)), 64)
        frames.append(frame)
        return frame
    yield create
    # Parentless Qt test widgets retain signal cycles; destroy them while the
    # QApplication is alive, not during Python's interpreter teardown.
    for frame in frames:
        frame.close()
        frame.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_medium_widget_reserves_two_rows_and_preserves_hit_testing(page_factory):
    doc = LayoutDocument(copy.deepcopy(STATE), Grid())
    frame = page_factory(doc, 0)
    view = frame.view
    assert view.placement().occupied_cells == 16
    assert "9 items" in frame.title.text() and "16/24 cells" in frame.title.text()
    widget_rect = view._cell_rect(0)
    first_app = view._cell_rect(1)
    assert widget_rect.width() == 4 * view._cell_w
    assert widget_rect.height() == 2 * view._cell_h
    assert first_app.top() == view._pad + 2 * view._cell_h
    assert view._item_at(widget_rect.bottomRight() - QPoint(1, 1)) == 0
    assert view._item_at(first_app.center()) == 1
    assert not view.acceptDrops()
    assert not frame.left.isEnabled() and not frame.right.isEnabled()
    assert doc.to_state() == STATE


def test_medium_plus_sixteen_icons_fills_twenty_four_cells(page_factory):
    doc = LayoutDocument(copy.deepcopy(STATE), Grid())
    frame = page_factory(doc, 1)
    placement = frame.view.placement()
    assert placement.complete and placement.occupied_cells == 24
    assert "17 items" in frame.title.text() and "24/24 cells" in frame.title.text()
    assert (placement.cells[-1].row, placement.cells[-1].column) == (5, 3)
    frame.resize(frame.sizeHint())
    assert not frame.grab().isNull()


def test_unverified_widget_geometry_keeps_all_items_visible_in_warning(page_factory):
    doc = LayoutDocument([[], [widget("futureSize"), app_icon(1)]], Grid())
    frame = page_factory(doc, 0)
    assert not frame.view.placement().complete
    assert frame.view.placement().cells == ()
    assert "?/24 cells" in frame.title.text()
    assert not frame.preview_warning.isHidden()
    assert "item 1" in frame.preview_warning.text() and "item 2" in frame.preview_warning.text()
    assert "example.synthetic.widget" not in frame.preview_warning.text()


def test_readonly_preview_rejects_drag_and_keeps_folder_inspection(window):
    window._set_document(copy.deepcopy(STATE), None)
    view = window._pages[0].view
    mime = QMimeData()
    mime.setData(MIME_NODE, window.doc.pages[0].items[1].uid.encode())
    event = QDragEnterEvent(QPoint(5, 5), Qt.DropAction.MoveAction, mime,
                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    view.dragEnterEvent(event)
    assert not event.isAccepted()
    assert view._resolve_target(QPoint(10, 10), window.doc.pages[0].items[1].uid)[-1]
    folder = window.doc.pages[2].items[1]
    window._open_folder(folder.uid)
    assert window.folder_panel.node_uid == folder.uid
    assert not window.folder_panel.rename_button.isEnabled()
    assert all(not child.acceptDrops() for child in window.folder_panel._views)


def test_duo_pairs_logical_pages_and_places_dock_on_the_right(window):
    window._set_document(copy.deepcopy(STATE), None)
    original = plistlib.dumps(window.doc.to_state())
    window.set_preview_profile("duo")
    assert len(window.doc.pages) == 3
    assert len(window._duo_groups) == 2
    assert [len(g.pages) for g in window._duo_groups] == [2, 1]
    assert window._duo_groups[1].unpaired_notice.text() == "No next page"
    for group in window._duo_groups:
        assert group.dock.vertical
        assert group.dock.view.columns == 1
        assert group.dock.view.rows == 4
        assert group.layout().itemAt(group.layout().count() - 1).widget() is group.dock
    assert plistlib.dumps(window.doc.to_state()) == original
    window.set_preview_profile("pages")
    assert not window._duo_groups
    assert not window.dock_frame.vertical
    assert plistlib.dumps(window.doc.to_state()) == original


def test_all_edits_and_write_handlers_are_blocked_even_with_old_verified_flag(window, monkeypatch):
    window.offline = False
    window._device = ("device", "Synthetic phone")
    window._set_document(copy.deepcopy(STATE), None)
    window.write_verified = True
    window._update_actions()
    window.worker.apply = MagicMock()
    window.worker.check_compatibility = MagicMock()
    window.worker.restore_backup = MagicMock()
    monkeypatch.setattr(QDialog, "exec", lambda self: (_ for _ in ()).throw(AssertionError("No write dialogs")))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (_ for _ in ()).throw(AssertionError("No restore dialog")))
    before = copy.deepcopy(window.doc.to_state())
    for action in (window.act_undo, window.act_redo, window.act_add_page, window.act_group,
                   window.act_rename, window.act_apply, window.act_compatibility, window.act_restore):
        assert not action.isEnabled()
    window._apply(); window._check_compatibility(); window._restore()
    window._add_page(); window._move_page(0, 1); window._remove_page(0)
    window._group(); window._rename_folder(window.doc.pages[2].items[1].uid)
    window.worker.apply.assert_not_called()
    window.worker.check_compatibility.assert_not_called()
    window.worker.restore_backup.assert_not_called()
    assert window.doc.to_state() == before


def test_actual_duo_device_remains_blocked_after_switching_to_pages(window):
    window.offline = False
    window._device = ("device", "Synthetic Duo")
    info = SimpleNamespace(product_type="iPhone19,4", summary=lambda: "Synthetic Duo")
    window._on_loaded([[app_icon(100)], [app_icon(1)]], {}, info)
    assert window.preview_profile == "duo"
    window.set_preview_profile("pages")
    window.write_verified = True
    window._update_actions()
    assert window.readonly_reason
    assert not window.act_restore.isEnabled()
    assert not window.act_compatibility.isEnabled()
    assert not window._pages[0].view.acceptDrops()
    window.worker.apply = MagicMock()
    window.worker.check_compatibility = MagicMock()
    window.worker.restore_backup = MagicMock()
    window._apply(); window._check_compatibility(); window._restore()
    window.worker.apply.assert_not_called()
    window.worker.check_compatibility.assert_not_called()
    window.worker.restore_backup.assert_not_called()


def test_open_preview_is_offline_and_never_loads_or_fetches_icons(window, tmp_path):
    path = tmp_path / "synthetic.plist"
    path.write_bytes(plistlib.dumps(STATE))
    window.worker.load = MagicMock()
    window.worker.fetch_icons = MagicMock()
    window.open_preview(path)
    assert window.offline and window.worker.offline_mode
    assert window._device[0] == "file"
    assert not window.act_icons.isEnabled()
    window._fetch_icons()
    window.worker.load.assert_not_called()
    window.worker.fetch_icons.assert_not_called()
    assert window.doc.to_state() == STATE
