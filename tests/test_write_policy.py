"""Independent unsupported-layout write checks; every phone here is a fake.

Fixtures are invented protocol-shaped data, never saved personal layouts.
"""
from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import os
import plistlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ipsm.backup import BackupError, BackupStore, guarded_write, restore
from ipsm.iconstate import compare_after_write
from ipsm.write_policy import device_write_block_reason, write_block_reason

PHONE_KEY = hashlib.sha256(b"synthetic-policy-phone").hexdigest()
PLAIN = [[], [{"displayIdentifier": "example.test.alpha", "displayName": "Alpha"}]]
WIDGET = {
    "displayIdentifier": "synthetic-widget-id",
    "iconType": "custom",
    "elementType": "widget",
    "widgetIdentifier": "example.test.widget",
    "gridSize": "medium",
    "iconLists": [],
    "privateFutureField": {"raw": b"keep all bytes"},
}
STACK = {
    "displayIdentifier": "synthetic-stack-id", "iconType": "custom",
    "gridSize": "medium", "iconLists": [],
    "elements": [{"elementType": "widget", "widgetIdentifier": f"example.test.member{i}",
                  "uniqueIdentifier": f"synthetic-member-{i}"} for i in range(7)],
    "userSelectedElementIdentifier": "synthetic-member-3",
    "allowsSuggestions": True,
}
UNSUPPORTED = [
    WIDGET,
    STACK,
    {"displayIdentifier": "example.odd.widget", "widgetIdentifier": "example.test.kind",
     "elementType": "widget", "gridSize": "unknownFutureSize"},
    {"iconLists": [], "displayName": "Unverified legacy container"},
    {"unknownFuturePayload": {"bytes": b"retain"}},
    None,
]


def layout_with(item):
    return [[], [copy.deepcopy(item), copy.deepcopy(PLAIN[1][0])]]


class FakePhone:
    def __init__(self, state, product_type="iPhone14,7"):
        self.state = copy.deepcopy(state)
        self.info = SimpleNamespace(product_type=product_type)
        self.device_key = PHONE_KEY
        self.reads = 0
        self.writes = []

    async def get_icon_state(self, **kwargs):
        self.reads += 1
        return copy.deepcopy(self.state)

    async def set_icon_state(self, state):
        self.writes.append(copy.deepcopy(state))


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESPREAD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOMESPREAD_CACHE_DIR", str(tmp_path / "cache"))


@pytest.mark.parametrize("item", UNSUPPORTED)
def test_policy_recognizes_unsupported_raw_items_without_mutation(item):
    state = layout_with(item)
    snapshot = plistlib.dumps(state, fmt=plistlib.FMT_BINARY)
    assert write_block_reason(state)
    assert plistlib.dumps(state, fmt=plistlib.FMT_BINARY) == snapshot


def test_known_duo_blocks_even_without_widgets():
    assert device_write_block_reason("iPhone19,4")
    assert write_block_reason(PLAIN, product_type="iPhone19,4")
    assert write_block_reason(PLAIN, product_type="iPhone14,7") is None


@pytest.mark.parametrize("reason", ["before-edit", "compatibility", "before-restore", "verify-edit"])
@pytest.mark.parametrize("item", UNSUPPORTED)
def test_unsupported_target_never_reaches_phone_or_backup(tmp_path, monkeypatch, item, reason):
    store = BackupStore(tmp_path, PHONE_KEY)
    save = MagicMock(side_effect=AssertionError("Unsupported writes must stop before backup"))
    monkeypatch.setattr(store, "save", save)
    phone = FakePhone(PLAIN)
    with pytest.raises(BackupError):
        asyncio.run(guarded_write(phone, store, layout_with(item), reason))
    assert phone.reads == 0
    assert phone.writes == []
    save.assert_not_called()


@pytest.mark.parametrize("item", UNSUPPORTED)
def test_unsupported_current_layout_cannot_be_overwritten_by_plain_target(tmp_path, item):
    store = BackupStore(tmp_path, PHONE_KEY)
    phone = FakePhone(layout_with(item))
    with pytest.raises(BackupError):
        asyncio.run(guarded_write(phone, store, PLAIN, "before-restore"))
    assert phone.writes == []
    assert store.list_backups() == []


@pytest.mark.parametrize("reason", ["before-edit", "compatibility", "before-restore", "verify-edit"])
def test_device_policy_survives_forged_verification_or_arbitrary_reason(tmp_path, reason):
    phone = FakePhone(PLAIN, product_type="iPhone19,4")
    store = BackupStore(tmp_path, PHONE_KEY)
    with pytest.raises(BackupError):
        asyncio.run(guarded_write(phone, store, PLAIN, reason, expected_state=PLAIN))
    assert phone.writes == []
    assert store.list_backups() == []


@pytest.mark.parametrize("target_has_widgets,current_has_widgets", [(True, False), (False, True), (True, True)])
def test_restore_cannot_bypass_unsupported_layout_policy(tmp_path, target_has_widgets, current_has_widgets):
    store = BackupStore(tmp_path, PHONE_KEY)
    target = layout_with(STACK) if target_has_widgets else copy.deepcopy(PLAIN)
    saved = store.save(target, "synthetic-readonly")
    phone = FakePhone(layout_with(WIDGET) if current_has_widgets else PLAIN)
    with pytest.raises(BackupError):
        asyncio.run(restore(phone, store, saved.path))
    assert phone.writes == []
    assert store.load(saved.path, for_restore=True) == target


def test_duo_restore_is_blocked_even_with_valid_same_device_backup(tmp_path):
    store = BackupStore(tmp_path, PHONE_KEY)
    saved = store.save(PLAIN)
    phone = FakePhone(PLAIN, product_type="iPhone19,4")
    with pytest.raises(BackupError):
        asyncio.run(restore(phone, store, saved.path))
    assert phone.writes == []


def test_readonly_widget_backup_remains_complete_and_verifiable(tmp_path):
    state = [[], [copy.deepcopy(WIDGET), copy.deepcopy(STACK)]]
    store = BackupStore(tmp_path, PHONE_KEY)
    saved = store.save(state, "synthetic-readonly")
    restored = store.load(saved.path, for_restore=True)
    assert restored == state
    assert saved.path.read_bytes() == plistlib.dumps(state, fmt=plistlib.FMT_BINARY)


@pytest.mark.parametrize("change", ["stack_member", "selected_member", "widget_payload", "iconLists"])
def test_widget_and_stack_content_damage_is_reported(change):
    before = [[], [copy.deepcopy(WIDGET), copy.deepcopy(STACK)]]
    after = copy.deepcopy(before)
    if change == "stack_member":
        after[1][1]["elements"][0]["widgetIdentifier"] = "example.test.changed"
    elif change == "selected_member":
        after[1][1]["userSelectedElementIdentifier"] = "synthetic-member-5"
    elif change == "widget_payload":
        after[1][0]["privateFutureField"]["raw"] = b"corruption"
    else:
        after[1][0]["iconLists"] = [[{"displayIdentifier": "example.hidden"}]]
    comparison = compare_after_write(before, after)
    assert not comparison.safe


@pytest.fixture
def qt_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("operation", ["apply", "check_compatibility", "restore_backup"])
def test_worker_entrypoints_cannot_bypass_widget_policy(qt_app, tmp_path, monkeypatch, operation):
    from ipsm.ui import worker
    device_worker = worker.DeviceWorker(tmp_path)
    device_worker.write_verified = True
    phone = FakePhone(layout_with(WIDGET))
    queued = []
    monkeypatch.setattr(device_worker, "_submit", lambda job, what: queued.append(job) or True)
    async def ready():
        return phone
    monkeypatch.setattr(device_worker, "_bridge_ready", ready)
    if operation == "apply":
        device_worker.apply(layout_with(WIDGET), expected_state=layout_with(WIDGET))
    elif operation == "check_compatibility":
        device_worker.check_compatibility(layout_with(WIDGET))
    else:
        device_worker.backups.bind_device(PHONE_KEY)
        saved = device_worker.backups.save(layout_with(WIDGET), "synthetic-readonly")
        device_worker.restore_backup(saved.path)
    assert queued
    with pytest.raises(BackupError):
        asyncio.run(queued[0]())
    assert phone.writes == []


@pytest.mark.parametrize("operation", ["apply", "check_compatibility", "restore_backup"])
def test_duo_preview_profile_cannot_enable_write_by_forging_verified_flag(qt_app, tmp_path, monkeypatch, operation):
    from ipsm.ui import worker
    device_worker = worker.DeviceWorker(tmp_path)
    device_worker.set_preview_profile("duo")
    device_worker.write_verified = True
    phone = FakePhone(PLAIN)
    queued = []
    monkeypatch.setattr(device_worker, "_submit", lambda job, what: queued.append(job) or True)
    async def ready():
        return phone
    monkeypatch.setattr(device_worker, "_bridge_ready", ready)
    if operation == "apply":
        device_worker.apply(PLAIN, expected_state=PLAIN)
    elif operation == "check_compatibility":
        device_worker.check_compatibility(PLAIN)
    else:
        device_worker.backups.bind_device(PHONE_KEY)
        saved = device_worker.backups.save(PLAIN)
        device_worker.restore_backup(saved.path)
    assert queued
    with pytest.raises(BackupError):
        asyncio.run(queued[0]())
    assert phone.writes == []


def test_cli_scripts_have_no_alternate_device_write_path():
    for filename in ("src/ipsm/probe.py", "scripts/verify_edits.py"):
        tree = ast.parse((ROOT / filename).read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        assert not any(isinstance(node.func, ast.Attribute) and node.func.attr == "set_icon_state" for node in calls)
        assert any(isinstance(node.func, ast.Name) and node.func.id == "guarded_write" for node in calls)

@pytest.mark.parametrize("current,target,product_type", [
    (None, layout_with(WIDGET), "iPhone14,7"),
    (layout_with(STACK), PLAIN, "iPhone14,7"),
    (None, PLAIN, "iPhone19,4"),
])
def test_device_bridge_rejects_before_opening_springboard(monkeypatch, current, target, product_type):
    from ipsm.device import DeviceBridge, DeviceError
    bridge = DeviceBridge()
    bridge.info = SimpleNamespace(product_type=product_type)
    bridge._last_icon_state = copy.deepcopy(current)
    service = MagicMock(side_effect=AssertionError("No SpringBoard service may be opened"))
    monkeypatch.setattr(bridge, "_springboard", service)
    with pytest.raises(DeviceError):
        asyncio.run(bridge.set_icon_state(copy.deepcopy(target)))
    service.assert_not_called()


def test_offline_worker_refuses_connection_before_device_construction(qt_app, tmp_path, monkeypatch):
    from ipsm.ui import worker
    device_worker = worker.DeviceWorker(tmp_path)
    device_worker.set_offline_mode(True)
    factory = MagicMock(side_effect=AssertionError("Offline mode cannot create a phone connection"))
    monkeypatch.setattr(worker, "DeviceBridge", factory)
    with pytest.raises(BackupError):
        asyncio.run(device_worker._bridge_ready())
    factory.assert_not_called()


def test_offline_preview_window_never_probes_usb_service(qt_app, tmp_path, monkeypatch):
    from ipsm import apple_devices, i18n
    from ipsm.ui import main_window, worker
    monkeypatch.setattr(worker.DeviceWorker, "start", lambda self: None)
    monkeypatch.setattr(worker.DeviceWorker, "shutdown", lambda self: None)
    probe = MagicMock(side_effect=AssertionError("Offline preview cannot query USB readiness"))
    monkeypatch.setattr(apple_devices, "look", probe)
    path = tmp_path / "synthetic-preview.plist"
    state = [[], [copy.deepcopy(STACK)] + [
        {"displayIdentifier": f"example.test.app{i}"} for i in range(8)]]
    path.write_bytes(plistlib.dumps(state, fmt=plistlib.FMT_BINARY))
    window = main_window.MainWindow(tmp_path / "window", offline=True)
    try:
        window.set_preview_profile("duo")
        window.open_preview(path)
        window.guide.refresh()
        window.show()
        qt_app.processEvents()
        assert window.doc.to_state() == state
        assert window.worker.offline_mode
        assert not window.act_apply.isEnabled()
        assert not window.act_restore.isEnabled()
        assert not window.act_compatibility.isEnabled()
        assert not window.act_icons.isEnabled()
        probe.assert_not_called()
    finally:
        i18n.off_language_changed(window.retranslate)
        window.deleteLater()
        qt_app.processEvents()

def test_real_preview_buttons_toggle_repeatedly_without_mutating_layout(qt_app, tmp_path, monkeypatch):
    """Exercise Qt mouse events and queued deletion, not only the public setter."""
    from PySide6.QtCore import QCoreApplication, QEvent, Qt
    from PySide6.QtTest import QTest
    from ipsm import apple_devices, i18n
    from ipsm.ui import main_window, worker

    monkeypatch.setattr(worker.DeviceWorker, "start", lambda self: None)
    monkeypatch.setattr(worker.DeviceWorker, "shutdown", lambda self: None)
    probe = MagicMock(side_effect=AssertionError("Offline mode cannot query USB readiness"))
    monkeypatch.setattr(apple_devices, "look", probe)
    state = [copy.deepcopy(PLAIN[1])]
    for page in range(7):
        content = [{"displayIdentifier": f"example.mouse.page{page}.app{i}"} for i in range(8)]
        if page == 0:
            content.insert(0, copy.deepcopy(STACK))
        elif page in (1, 2):
            content.insert(0, copy.deepcopy(WIDGET))
        state.append(content)
    before = plistlib.dumps(state, fmt=plistlib.FMT_BINARY)
    window = main_window.MainWindow(tmp_path / "button-window", offline=True)
    try:
        window._set_document(copy.deepcopy(state), None)
        window.show()
        qt_app.processEvents()
        assert window.profile_buttons["pages"].isChecked()
        for profile in ("duo", "pages", "duo", "pages", "duo", "pages"):
            QTest.mouseClick(window.profile_buttons[profile], Qt.MouseButton.LeftButton)
            qt_app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            assert window.preview_profile == profile
            assert window.profile_buttons[profile].isChecked()
            assert sum(button.isChecked() for button in window.profile_buttons.values()) == 1
            assert len(window._pages) == 7
            assert len(window._duo_groups) == (4 if profile == "duo" else 0)
            assert not window.act_apply.isEnabled()
            assert not window.act_restore.isEnabled()
            assert not window.act_compatibility.isEnabled()
            assert not window.act_group.isEnabled()
            assert plistlib.dumps(window.doc.to_state(), fmt=plistlib.FMT_BINARY) == before
        probe.assert_not_called()
    finally:
        i18n.off_language_changed(window.retranslate)
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qt_app.processEvents()


def test_accessibility_checked_state_changes_the_actual_preview(qt_app, tmp_path, monkeypatch):
    """Cocoa AX toggle changes checked state without a Qt mouse clicked signal."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from ipsm import i18n
    from ipsm.ui import main_window, worker

    monkeypatch.setattr(worker.DeviceWorker, "start", lambda self: None)
    monkeypatch.setattr(worker.DeviceWorker, "shutdown", lambda self: None)
    window = main_window.MainWindow(tmp_path / "accessible-preview", offline=True)
    state = [[], [copy.deepcopy(STACK)], [copy.deepcopy(WIDGET)]]
    before = plistlib.dumps(state, fmt=plistlib.FMT_BINARY)
    try:
        window._set_document(state, None)
        for profile in ("duo", "pages", "duo"):
            window.profile_buttons[profile].setChecked(True)
            qt_app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            assert window.preview_profile == profile
            assert len(window._duo_groups) == (1 if profile == "duo" else 0)
            assert not window.act_apply.isEnabled()
            assert plistlib.dumps(window.doc.to_state(), fmt=plistlib.FMT_BINARY) == before
    finally:
        i18n.off_language_changed(window.retranslate)
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qt_app.processEvents()
