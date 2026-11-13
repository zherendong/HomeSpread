"""Independent offline-draft boundaries using fabricated local data only."""
from __future__ import annotations

import ast
import asyncio
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
from unittest.mock import MagicMock

import pytest

from ipsm.backup import BackupError, BackupStore, restore
from ipsm.drafts import OfflineDraft
from ipsm.draft_rules import DraftError
from ipsm.write_policy import write_block_reason

ROOT = Path(__file__).resolve().parents[1]


def app(index: int):
    return {"displayIdentifier": f"example.draft-boundary.app{index}",
            "bundleIdentifier": f"example.draft-boundary.app{index}",
            "displayName": f"Example {index}",
            "iconModDate": datetime(2026, 1, 2, 3, 4, 5, 123456),
            "opaqueField": {"flag": True, "integer": 1, "bytes": b"\x00\xff\x01"}}


STACK = {"displayIdentifier": "example-draft-stack", "iconType": "custom",
         "gridSize": "medium", "iconLists": [],
         "elements": [{"elementType": "widget", "widgetIdentifier": f"example.stack{i}",
                       "uniqueIdentifier": f"example-draft-member-{i}",
                       "parameters": {"opaque": b"\x00\xfe", "flag": True}} for i in range(7)],
         "userSelectedElementIdentifier": "example-draft-member-3", "allowsSuggestions": True}
FOLDER = {"listType": "folder", "displayName": "Example Folder",
          "iconLists": [[app(40), app(41)]], "unknownFolderField": b"keep"}
STATE = [[app(99)], [deepcopy(STACK), app(1), app(2), app(3), deepcopy(FOLDER)],
         [app(4), app(5)]]


def binary(value):
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY, sort_keys=True)


def saved_file(tmp_path):
    draft = OfflineDraft(deepcopy(STATE))
    draft.swap(1, 1, 2)
    path = tmp_path / "example.hsdraft"
    draft.save(path)
    return path, plistlib.loads(path.read_bytes())


def test_draft_lifecycle_preserves_source_and_typed_widget_payload(tmp_path):
    original = deepcopy(STATE)
    source = tmp_path / "original.plist"
    source.write_bytes(binary(original))
    original_bytes = source.read_bytes()
    draft = OfflineDraft(plistlib.loads(original_bytes))
    assert not draft.dirty and not draft.has_changes
    draft.swap(1, 1, 2)
    draft.swap(2, 0, 1)
    assert draft.dirty and draft.has_changes
    assert binary(draft.origin) == original_bytes
    assert binary(draft.current_state[1][0]) == binary(STACK)
    assert binary(draft.current_state[1][4]) == binary(FOLDER)
    assert binary(draft.current_state[0]) == binary(STATE[0])
    path = draft.save(tmp_path / "local.hsdraft")
    assert not draft.dirty
    loaded = OfflineDraft.load(path)
    assert binary(loaded.current_state) == binary(draft.current_state)
    assert loaded.can_undo and not loaded.can_redo
    assert not loaded.dirty
    assert loaded.undo() and loaded.undo()
    assert binary(loaded.current_state) == original_bytes
    assert loaded.redo() and loaded.redo()
    assert not loaded.dirty
    assert source.read_bytes() == original_bytes
    assert write_block_reason(loaded.current_state, product_type="iPhone19,4")


def test_dirty_tracks_saved_snapshot_and_redo_branch_is_replaced(tmp_path):
    draft = OfflineDraft(deepcopy(STATE))
    draft.swap(1, 1, 2)
    draft.save(tmp_path / "checkpoint.hsdraft")
    saved = binary(draft.current_state)
    assert not draft.dirty
    draft.undo()
    assert draft.dirty and draft.can_redo
    draft.redo()
    assert not draft.dirty and binary(draft.current_state) == saved
    draft.undo()
    draft.swap(1, 1, 3)
    assert draft.dirty and not draft.can_redo
    assert not draft.redo()
    # Two inverse operations may yield no net edit, but differ from the saved state.
    draft.swap(1, 1, 3)
    assert not draft.has_changes and draft.dirty


def test_snapshot_properties_never_expose_mutable_internal_baseline():
    draft = OfflineDraft(deepcopy(STATE))
    before = binary(draft.origin)
    draft.origin[1][0]["elements"].clear()
    draft.current_state[1][1]["opaqueField"]["flag"] = 1
    draft.current[0].clear()
    assert binary(draft.origin) == before == binary(draft.current_state)
    draft.swap(1, 1, 2)
    changes = draft.diff()
    assert {(change.page, change.index) for change in changes} == {(1, 1), (1, 2)}


@pytest.mark.parametrize("suffix", [".plist", ".json", "", ".txt"])
def test_draft_save_never_overwrites_source_backup(tmp_path, suffix):
    source = tmp_path / ("original" + suffix)
    source.write_bytes(binary(STATE))
    before = source.read_bytes()
    draft = OfflineDraft(deepcopy(STATE))
    draft.swap(1, 1, 2)
    with pytest.raises(DraftError):
        draft.save(source, replace=True)
    assert source.read_bytes() == before
    assert draft.dirty


def test_misnamed_backup_is_not_overwritten_as_draft(tmp_path):
    path = tmp_path / "actually-a-backup.hsdraft"
    path.write_bytes(binary(STATE))
    before = path.read_bytes()
    draft = OfflineDraft(deepcopy(STATE))
    draft.swap(1, 1, 2)
    with pytest.raises(DraftError):
        draft.save(path, replace=True)
    assert path.read_bytes() == before and draft.dirty


def test_draft_cannot_be_loaded_as_restoration_backup_even_renamed(tmp_path):
    path, payload = saved_file(tmp_path)
    assert type(payload) is dict and payload["device_write_allowed"] is False
    renamed = tmp_path / "renamed.plist"
    renamed.write_bytes(path.read_bytes())
    store = BackupStore(tmp_path / "store")
    for target in (path, renamed):
        with pytest.raises(BackupError):
            store.load(target)


def test_forged_backup_metadata_cannot_make_a_draft_restorable(tmp_path):
    path, _ = saved_file(tmp_path)
    key = hashlib.sha256(b"fabricated-draft-boundary-device").hexdigest()
    store = BackupStore(tmp_path / "store", device_key=key)
    renamed = store.dir / "forged.plist"
    renamed.write_bytes(path.read_bytes())
    renamed.with_suffix(".meta.json").write_text(json.dumps({
        "schema": 1, "device_key": key,
        "sha256": hashlib.sha256(renamed.read_bytes()).hexdigest(),
    }))

    class Phone:
        device_key = key
        reads = 0
        writes = 0

        async def get_icon_state(self):
            self.reads += 1
            raise AssertionError("A draft must be rejected before a phone read")

        async def set_icon_state(self, state):
            self.writes += 1
            raise AssertionError("A draft must never become a restore request")

    phone = Phone()
    with pytest.raises(BackupError):
        asyncio.run(restore(phone, store, renamed))
    assert phone.reads == 0 and phone.writes == 0


@pytest.mark.parametrize("field,value", [
    ("format", "other-format"), ("schema_version", True), ("schema_version", 2),
    ("purpose", "device-write"), ("device_write_allowed", True),
    ("device_write_allowed", 0), ("origin_sha256", "0" * 64),
    ("current_sha256", "0" * 64),
])
def test_loader_rejects_forged_headers_and_hashes(tmp_path, field, value):
    path, payload = saved_file(tmp_path)
    payload[field] = value
    path.write_bytes(binary(payload))
    with pytest.raises(DraftError):
        OfflineDraft.load(path)


@pytest.mark.parametrize("mutation", ["widget_bool", "selection", "third_app", "dock", "folder", "wrong_intent"])
def test_recomputed_current_hash_does_not_bypass_replay_validation(tmp_path, mutation):
    path, payload = saved_file(tmp_path)
    if mutation == "widget_bool":
        payload["current"][1][0]["allowsSuggestions"] = 1
    elif mutation == "selection":
        payload["current"][1][0]["userSelectedElementIdentifier"] = "example-draft-member-5"
    elif mutation == "third_app":
        payload["current"][1][3]["opaqueField"]["bytes"] = b"corrupt"
    elif mutation == "dock":
        payload["current"][0].clear()
    elif mutation == "folder":
        payload["current"][1][4]["displayName"] = "changed"
    else:
        payload["operations"][0]["index_b"] = 3
    payload["current_sha256"] = hashlib.sha256(binary(payload["current"])).hexdigest()
    path.write_bytes(binary(payload))
    with pytest.raises(DraftError):
        OfflineDraft.load(path)


def test_file_limits_truncation_and_operation_limits_are_fail_closed(tmp_path, monkeypatch):
    import ipsm.drafts as drafts
    path, payload = saved_file(tmp_path)
    original = path.read_bytes()
    path.write_bytes(original[:len(original) // 2])
    with pytest.raises(DraftError):
        OfflineDraft.load(path)
    path.write_bytes(original)
    monkeypatch.setattr(drafts, "MAX_FILE_BYTES", len(original) - 1)
    with pytest.raises(DraftError):
        OfflineDraft.load(path)
    monkeypatch.setattr(drafts, "MAX_FILE_BYTES", len(original) * 10)
    monkeypatch.setattr(drafts, "MAX_OPERATIONS", 0)
    with pytest.raises(DraftError):
        OfflineDraft.load(path)


def test_failed_save_retains_dirty_state_and_original_files(tmp_path, monkeypatch):
    import ipsm.drafts as drafts
    draft = OfflineDraft(deepcopy(STATE))
    draft.swap(1, 1, 2)
    monkeypatch.setattr(drafts, "atomic_private_write", MagicMock(side_effect=OSError("disk unavailable")))
    path = tmp_path / "failed.hsdraft"
    with pytest.raises(DraftError):
        draft.save(path)
    assert draft.dirty and draft.path is None
    assert not path.exists()


def test_private_file_permissions(tmp_path):
    path, _ = saved_file(tmp_path)
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_offline_storage_layer_has_no_transport_or_dynamic_imports():
    path = ROOT / "src/ipsm/drafts.py"
    allowed = {"__future__", "collections", "copy", "dataclasses", "datetime", "hashlib",
               "itertools", "json", "os", "pathlib", "plistlib", "typing"}
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] in allowed for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert ((node.level == 1 and node.module in {"draft_rules", "safeio", "i18n"})
                    or (node.level == 0 and (node.module or "").split(".")[0] in allowed))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec", "__import__", "compile"}


@pytest.fixture(scope="session")
def draft_qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def draft_window(draft_qt_app, tmp_path, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QEvent
    from ipsm import apple_devices, i18n
    from ipsm.ui import main_window, worker
    import socket

    monkeypatch.setenv("HOMESPREAD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOMESPREAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(worker.DeviceWorker, "start", lambda self: None)
    monkeypatch.setattr(worker.DeviceWorker, "shutdown", lambda self: None)
    guards = []
    for owner, name in [(apple_devices, "look"), (socket, "socket"), (worker, "DeviceBridge")]:
        guard = MagicMock(side_effect=AssertionError(f"Offline draft must not call {name}"))
        monkeypatch.setattr(owner, name, guard)
        guards.append(guard)
    window = main_window.MainWindow(tmp_path / "app", offline=True)
    for name in ("load", "fetch_icons", "apply", "check_compatibility", "restore_backup"):
        guard = MagicMock(side_effect=AssertionError(f"Offline draft must not submit {name}"))
        monkeypatch.setattr(window.worker, name, guard)
        guards.append(guard)
    source = tmp_path / "original.plist"
    source.write_bytes(binary(STATE))
    assert window.open_preview(source)
    assert window.start_draft()
    yield window, source, guards
    for guard in guards:
        guard.assert_not_called()
    monkeypatch.setattr(window, "_confirm_draft_transition", lambda: True)
    window.close()
    i18n.off_language_changed(window.retranslate)
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    draft_qt_app.processEvents()


def select_pair(window, page=1, a=1, b=2):
    window._on_selected(window.doc.pages[page - 1].items[a].uid)
    window._on_selected(window.doc.pages[page - 1].items[b].uid)


def test_ui_draft_full_lifecycle_never_accesses_phone(draft_window, tmp_path):
    window, source, _ = draft_window
    before = source.read_bytes()
    select_pair(window)
    window._swap_draft_apps()
    assert window.draft.dirty and len(window.draft.diff()) == 2
    path = tmp_path / "ui-roundtrip.hsdraft"
    assert window.save_draft(path)
    assert not window.draft.dirty
    window.set_draft_view("original")
    assert binary(window.doc.to_state()) == before
    window.set_draft_view("draft")
    assert binary(window.doc.to_state()) == binary(window.draft.current_state)
    window._undo()
    assert binary(window.doc.to_state()) == before
    window._redo()
    assert not window.draft.dirty
    assert window.open_draft(path)
    assert len(window.draft.diff()) == 2 and not window.draft.dirty
    assert window.offline and window.worker.offline_mode
    assert source.read_bytes() == before


@pytest.mark.parametrize("profile", ["pages", "duo"])
def test_forged_verified_flags_do_not_enable_any_device_action(draft_window, profile):
    window, _, _ = draft_window
    window.set_preview_profile(profile)
    window.write_verified = True
    window.worker.write_verified = True
    window._device = ("device", "Fabricated connection")
    window.product_type = "iPhone14,7"  # Ordinary model cannot bypass draft isolation.
    window._update_actions()
    for action in (window.act_load, window.act_icons, window.act_apply, window.act_restore, window.act_compatibility):
        assert not action.isEnabled()
    window._load()
    window._fetch_icons()
    window._apply()
    window._restore()
    window._check_compatibility()
    assert window.offline and window.worker.offline_mode


def test_original_view_and_non_app_endpoints_cannot_mutate_draft(draft_window):
    window, _, _ = draft_window
    before = binary(window.draft.current_state)
    window.set_draft_view("original")
    select_pair(window)
    window._swap_draft_apps()
    assert binary(window.draft.current_state) == before
    window.set_draft_view("draft")
    window._on_selected(window.doc.pages[0].items[1].uid)
    kept = set(window.selection)
    for uid in (window.doc.pages[0].items[0].uid, window.doc.pages[0].items[4].uid,
                window.doc.dock.items[0].uid, window.doc.pages[1].items[0].uid,
                window.doc.pages[0].items[4].pages[0].items[0].uid):
        window._on_selected(uid)
        assert window.selection == kept
        window._swap_draft_apps()
        assert binary(window.draft.current_state) == before


def test_accessibility_view_buttons_change_actual_source_or_draft(draft_window, draft_qt_app):
    window, source, _ = draft_window
    select_pair(window)
    window._swap_draft_apps()
    changed = binary(window.draft.current_state)
    for view in ("original", "draft", "original", "draft"):
        window.draft_view_buttons[view].setChecked(True)
        draft_qt_app.processEvents()
        assert window.draft_view == view
        assert binary(window.doc.to_state()) == (source.read_bytes() if view == "original" else changed)
        assert not window.act_apply.isEnabled()


def test_cancel_close_open_and_end_preserves_unsaved_draft(draft_window, tmp_path, monkeypatch):
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox
    window, source, _ = draft_window
    select_pair(window)
    window._swap_draft_apps()
    session = window.draft
    before = binary(session.current_state)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Cancel)
    other = tmp_path / "other.plist"
    other.write_bytes(binary([[], [app(5), app(6)]]))
    other_draft = OfflineDraft([[], [app(5), app(6)]])
    other_draft.save(tmp_path / "other.hsdraft")
    assert not window.open_preview(other)
    assert not window.open_draft(tmp_path / "other.hsdraft")
    assert not window.end_draft()
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    assert window.draft is session and session.dirty
    assert binary(session.current_state) == before
    assert source.read_bytes() == binary(STATE)


def test_cancel_save_dialog_also_cancels_close(draft_window, monkeypatch):
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    window, _, _ = draft_window
    select_pair(window)
    window._swap_draft_apps()
    session = window.draft
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    assert window.draft is session and session.dirty and session.path is None


def test_invalid_open_preserves_existing_unsaved_session(draft_window, tmp_path):
    window, _, _ = draft_window
    select_pair(window)
    window._swap_draft_apps()
    session = window.draft
    invalid = tmp_path / "invalid.hsdraft"
    invalid.write_bytes(b"invalid draft")
    with pytest.raises(DraftError):
        window.open_draft(invalid)
    assert window.draft is session and session.dirty


@pytest.mark.parametrize("confirm", [False, True])
def test_appended_extension_never_bypasses_overwrite_confirmation(draft_window, tmp_path, monkeypatch, confirm):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    window, source, _ = draft_window
    existing = tmp_path / "same-name.hsdraft"
    OfflineDraft(deepcopy(STATE)).save(existing)
    old_bytes = existing.read_bytes()
    select_pair(window)
    window._swap_draft_apps()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(existing.with_suffix("")), ""))
    confirmation = MagicMock(return_value=QMessageBox.StandardButton.Yes if confirm else QMessageBox.StandardButton.No)
    monkeypatch.setattr(QMessageBox, "question", confirmation)
    assert window._save_draft_dialog() is confirm
    confirmation.assert_called_once()
    if confirm:
        assert not window.draft.dirty
        assert binary(OfflineDraft.load(existing).current_state) == binary(window.draft.current_state)
    else:
        assert window.draft.dirty and existing.read_bytes() == old_bytes
    assert source.read_bytes() == binary(STATE)
