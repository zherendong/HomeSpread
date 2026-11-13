"""Offline draft user workflows with synthetic layouts and real Qt events."""
import copy
import os
from pathlib import Path
import plistlib
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from ipsm import apple_devices, i18n
from ipsm.draft_rules import DraftError
from ipsm.ui.main_window import MainWindow
from ipsm.ui.worker import DeviceWorker


def app(number):
    return {"displayIdentifier": f"example.draft.app{number}", "displayName": f"示例 {number}"}


def widget(stack=False):
    raw = {"iconType": "custom", "displayIdentifier": "example.draft.widget", "gridSize": "medium", "iconLists": []}
    if stack:
        raw["elements"] = [{"elementType": "widget", "widgetIdentifier": f"example.draft.widget{n}",
                            "uniqueIdentifier": f"example.draft.member{n}"} for n in range(7)]
        raw["userSelectedElementIdentifier"] = "example.draft.member2"
    else:
        raw.update(elementType="widget", widgetIdentifier="example.draft.independent")
    return raw


STATE = [[app(90)], [widget(True), app(0), app(1),
         {"listType": "folder", "displayName": "示例文件夹", "iconLists": [[app(9)]]}, app(2)],
         [widget(), app(3), app(4)]]


@pytest.fixture(scope="session")
def qtapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qtapp, tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESPREAD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOMESPREAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(DeviceWorker, "start", lambda self: None)
    monkeypatch.setattr(DeviceWorker, "shutdown", lambda self: None)
    monkeypatch.setattr(apple_devices, "look", lambda: (_ for _ in ()).throw(AssertionError("No USB in offline UI tests")))
    previous = i18n.language()
    i18n.set_language("en")
    win = MainWindow(tmp_path, offline=True)
    backup = tmp_path / "original.plist"
    backup.write_bytes(plistlib.dumps(STATE, fmt=plistlib.FMT_BINARY))
    win.open_preview(backup)
    yield win
    monkeypatch.setattr(win, "_confirm_draft_transition", lambda: True)
    win.close()
    i18n.off_language_changed(win.retranslate)
    win.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qtapp.processEvents()
    i18n.set_language(previous)


def choose_pair(window):
    window._on_selected(window.doc.pages[0].items[1].uid)
    window._on_selected(window.doc.pages[0].items[2].uid)


def test_real_click_selection_swap_undo_redo_and_original_view(window, qtapp):
    original = plistlib.dumps(STATE, fmt=plistlib.FMT_BINARY)
    window.show()
    QTest.mouseClick(window.draft_action_buttons["start"], Qt.MouseButton.LeftButton)
    qtapp.processEvents()
    assert window.draft is not None
    view = window._pages[0].view
    for index in (1, 2):
        QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=view._icon_rect(index).center())
    assert window.act_swap_draft.isEnabled()
    QTest.mouseClick(window.draft_action_buttons["swap"], Qt.MouseButton.LeftButton)
    qtapp.processEvents()
    assert len(window.draft.diff()) == 2
    assert window.change_list.count() == 2
    assert window.draft.current_state[1][1] == STATE[1][2]
    assert window.draft.current_state[1][0] == STATE[1][0]
    assert not window.selection
    assert window.act_undo.isEnabled()
    window._undo()
    assert not window.draft.diff()
    assert window.act_redo.isEnabled()
    window._redo()
    assert len(window.draft.diff()) == 2
    # Checked-state activation is the Cocoa accessibility path, not clicked().
    window.draft_view_buttons["original"].setChecked(True)
    assert window.draft_view == "original"
    assert plistlib.dumps(window.doc.origin, fmt=plistlib.FMT_BINARY) == original
    assert not window.act_swap_draft.isEnabled()
    window.draft_view_buttons["draft"].setChecked(True)
    assert window.doc.origin == window.draft.current_state
    assert plistlib.dumps(window.draft.origin, fmt=plistlib.FMT_BINARY) == original


def test_widget_folder_dock_and_cross_page_selection_refused(window):
    window.start_draft()
    for uid in (window.doc.pages[0].items[0].uid, window.doc.pages[0].items[3].uid, window.doc.dock.items[0].uid,
                window.doc.pages[0].items[3].pages[0].items[0].uid):
        window._on_selected(uid)
        assert not window.selection
        assert not window.act_swap_draft.isEnabled()
    window._on_selected(window.doc.pages[0].items[1].uid)
    window._on_selected(window.doc.pages[1].items[1].uid)
    assert len(window.selection) == 1
    assert not window.act_swap_draft.isEnabled()
    assert window.draft.current_state == STATE


def test_saved_draft_reopens_clean_with_undo_and_no_source_changes(window, tmp_path):
    window.start_draft()
    choose_pair(window)
    window._swap_draft_apps()
    draft_state = window.draft.current_state
    target = tmp_path / "example.hsdraft"
    assert window.save_draft(target)
    assert not window.draft.dirty
    assert window.end_draft()
    assert window.doc.origin == STATE
    assert window.open_draft(target)
    assert window.draft.current_state == draft_state
    assert not window.draft.dirty
    assert window.draft.can_undo
    assert window.worker.offline_mode and window.offline
    assert plistlib.loads((tmp_path / "original.plist").read_bytes()) == STATE


def test_original_view_does_not_select_or_mutate(window):
    window.start_draft()
    window.set_draft_view("original")
    choose_pair(window)
    window._swap_draft_apps()
    assert not window.selection
    assert not window.draft.has_changes
    assert not window.act_swap_draft.isEnabled()


def test_all_device_paths_and_ordinary_edit_controls_stay_disabled(window, monkeypatch):
    window.start_draft()
    for name in ("load", "fetch_icons", "apply", "restore_backup", "check_compatibility"):
        monkeypatch.setattr(window.worker, name, lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("No device operation")))
    window._device = ("device", "forged")
    window.offline = False
    window.write_verified = True
    for profile in ("pages", "duo"):
        window.set_preview_profile(profile)
        window._load(); window._fetch_icons(); window._apply(); window._restore(); window._check_compatibility()
        for action in (window.act_load, window.act_icons, window.act_apply, window.act_restore, window.act_compatibility,
                       window.act_add_page, window.act_group, window.act_rename):
            assert not action.isEnabled()
    assert window.draft.current_state == STATE


def test_save_cannot_overwrite_original_plist(window, tmp_path):
    window.start_draft()
    choose_pair(window)
    window._swap_draft_apps()
    backup = tmp_path / "original.plist"
    before = backup.read_bytes()
    with pytest.raises(DraftError):
        window.save_draft(backup, replace=True)
    assert backup.read_bytes() == before
    assert window.draft.dirty


def test_unsupported_preview_cannot_begin_draft(window):
    state = copy.deepcopy(STATE)
    state[1].append({"unrecognized": True})
    window._set_document(state, None)
    assert not window.act_start_draft.isEnabled()
    with pytest.raises(DraftError):
        window.start_draft()
    assert window.draft is None


def test_mode_switches_preserve_local_draft_and_readonly_tiles(window, qtapp):
    window.start_draft()
    choose_pair(window)
    window._swap_draft_apps()
    expected = window.draft.current_state
    for profile in ("duo", "pages", "duo"):
        window.profile_buttons[profile].setChecked(True)
        qtapp.processEvents()
        assert window.doc.origin == expected
        assert window.draft.current_state == expected
        assert all(frame.view.read_only for frame in window._pages)
        assert not window.act_apply.isEnabled()


def test_replaced_dock_is_hidden_before_deferred_destruction(window):
    old_dock = window.dock_frame
    window.show()
    window.set_preview_profile("duo")
    assert old_dock.isHidden()  # Prevent stale widgets covering the refreshed draft.
