"""macOS UI and worker boundaries; all device operations use in-memory doubles."""

import asyncio
import copy
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox

from ipsm import apple_devices, i18n, paths, product
from ipsm.backup import BackupError
from ipsm.iconstate import compare_after_write
from ipsm.ui import guide, main_window, worker


STATE = [
    [{"displayIdentifier": "phone", "displayName": "电话"}],
    [{"displayIdentifier": "a", "displayName": "地图"},
     {"displayIdentifier": "b", "displayName": "相机"}],
]


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def private_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HOMESPREAD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOMESPREAD_CACHE_DIR", str(tmp_path / "cache"))
    before = i18n.language()
    i18n.set_language("zh_CN")
    yield
    i18n.set_language(before)


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    # Construct real widgets and worker, but never start device communication.
    monkeypatch.setattr(worker.DeviceWorker, "start", lambda self: None)
    monkeypatch.setattr(worker.DeviceWorker, "shutdown", lambda self: None)
    monkeypatch.setattr(apple_devices, "look", lambda: apple_devices.Presence(True, True, "/var/run/usbmuxd"))
    win = main_window.MainWindow(tmp_path)
    yield win
    i18n.off_language_changed(win.retranslate)
    win.deleteLater()
    app.processEvents()


def test_mac_checks_local_unix_socket_not_windows_tcp(monkeypatch):
    monkeypatch.setattr(apple_devices, "sys", SimpleNamespace(platform="darwin"))
    sock = MagicMock()
    sock.__enter__.return_value = sock
    sock.connect_ex.return_value = 0
    factory = MagicMock(return_value=sock)
    monkeypatch.setattr(apple_devices.socket, "socket", factory)
    result = apple_devices.look()
    factory.assert_called_once_with(apple_devices.socket.AF_UNIX, apple_devices.socket.SOCK_STREAM)
    sock.settimeout.assert_called_once_with(0.4)
    sock.connect_ex.assert_called_once_with("/var/run/usbmuxd")
    assert result.ready and result.where == "/var/run/usbmuxd"


def test_mac_data_survives_moving_app_bundle(monkeypatch, tmp_path):
    monkeypatch.delenv("HOMESPREAD_DATA_DIR")
    monkeypatch.delenv("HOMESPREAD_CACHE_DIR")
    fake_sys = SimpleNamespace(platform="darwin", frozen=True, executable="/Applications/Original.app/Contents/MacOS/app")
    monkeypatch.setattr(paths, "sys", fake_sys)
    monkeypatch.setattr(paths.Path, "home", lambda: tmp_path)
    expected = tmp_path / "Library" / "Application Support" / product.NAME
    assert paths.data_root() == expected
    fake_sys.executable = "/Volumes/Other/Renamed.app/Contents/MacOS/app"
    assert paths.data_root() == expected
    assert paths.cache_root() == tmp_path / "Library" / "Caches" / product.NAME


def test_explicit_test_directories_and_private_data_creation(tmp_path):
    root, error = paths.ensure_ready()
    assert error is None
    assert root == tmp_path / "data"
    assert paths.cache_root() == tmp_path / "cache"
    assert root.stat().st_mode & 0o077 == 0
    assert (root / "backups").stat().st_mode & 0o077 == 0


def test_missing_mac_service_has_actionable_chinese_without_store(app, monkeypatch):
    monkeypatch.setattr(guide, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(apple_devices, "look", lambda: apple_devices.Presence(False, True, "/var/run/usbmuxd"))
    opened = MagicMock()
    monkeypatch.setattr(guide.QDesktopServices, "openUrl", opened)
    board = guide.GuideBoard()
    assert "访达" in board.state.text()
    assert "Microsoft Store" not in board.state.text()
    assert board.action.isHidden()
    board._open_store()
    opened.assert_not_called()
    assert "App 资源库" in board.safety.text()
    board.deleteLater()


def test_chinese_window_and_standard_shortcuts(window):
    assert window.act_load.text() == "从设备读取"
    assert window.act_undo.shortcut().matches(QKeySequence(QKeySequence.StandardKey.Undo)) == QKeySequence.SequenceMatch.ExactMatch
    assert window.act_group.shortcut() == QKeySequence("Ctrl+G")
    assert not window.act_apply.isEnabled()
    assert not window.act_restore.isEnabled()


def _edited(window, origin="device"):
    window._device = (origin, "测试")
    window.write_verified = True
    window.worker.write_verified = True
    window._set_document(copy.deepcopy(STATE), None)
    node = window.doc.pages[0].items[0]
    window.doc.move(node.uid, window.doc.dock.uid, 1)
    window._update_actions()
    assert window.doc.dirty


def test_imported_preview_cannot_write_even_after_edit(window, monkeypatch):
    _edited(window, "file")
    applied = MagicMock()
    monkeypatch.setattr(window.worker, "apply", applied)
    monkeypatch.setattr(main_window.ApplyDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    assert not window.act_apply.isEnabled()
    assert not window.act_restore.isEnabled()
    window._apply()
    applied.assert_not_called()


def test_apply_passes_original_state_for_stale_layout_guard(window, monkeypatch):
    _edited(window)
    applied = MagicMock(return_value=True)
    monkeypatch.setattr(window.worker, "apply", applied)
    monkeypatch.setattr(main_window.ApplyDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    assert window.act_apply.isEnabled()
    window._apply()
    assert applied.call_count == 1
    assert applied.call_args.kwargs["expected_state"] == STATE
    assert applied.call_args.args[0] != STATE


def test_busy_close_keeps_window_and_worker_alive(window, monkeypatch):
    window.worker._busy = True
    shutdown = MagicMock()
    monkeypatch.setattr(window.worker, "shutdown", shutdown)
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    shutdown.assert_not_called()
    assert window.statusBar().currentMessage()
    window.worker._busy = False


def test_untrusted_app_name_is_plain_text_in_apply_notice(app):
    dialog = main_window.ApplyDialog(["移动应用"], ["<img src='file:///private/test'>"])
    notices = [label for label in dialog.findChildren(QLabel) if "<img" in label.text()]
    assert len(notices) == 1
    assert notices[0].textFormat() == Qt.TextFormat.PlainText
    assert not dialog._ok.isEnabled()
    dialog.agree.setChecked(True)
    assert dialog._ok.isEnabled()
    dialog.deleteLater()


def test_worker_import_failure_reports_and_rejects_jobs(app, tmp_path, monkeypatch):
    def fail_import():
        raise ImportError("missing test dependency")
    monkeypatch.setattr(worker, "_load_device_layer", fail_import)
    device_worker = worker.DeviceWorker(tmp_path)
    failed = []
    device_worker.failed.connect(lambda *args: failed.append(args))
    device_worker.run()
    assert device_worker._startup_error == "missing test dependency"
    assert device_worker._loop.is_closed()
    assert not device_worker.busy
    assert failed and all(failed[0])
    called = MagicMock()
    assert not device_worker._submit(called, "测试")
    called.assert_not_called()


def test_worker_apply_copies_state_before_queuing(app, tmp_path, monkeypatch):
    device_worker = worker.DeviceWorker(tmp_path)
    device_worker.write_verified = True
    queued = []
    monkeypatch.setattr(device_worker, "_submit", lambda job, what: queued.append(job) or True)
    expected = copy.deepcopy(STATE)
    edited = [STATE[0], list(reversed(STATE[1]))]
    captured = []
    async def fake_write(bridge, store, state, reason, *, expected_state):
        captured.append((copy.deepcopy(state), copy.deepcopy(expected_state)))
        return SimpleNamespace(path=tmp_path / "backup.plist")
    async def ready():
        return SimpleNamespace(get_icon_state=lambda **kwargs: _result(copy.deepcopy(STATE)))
    monkeypatch.setattr(worker, "guarded_write", fake_write)
    monkeypatch.setattr(worker, "_SETTLE_SECONDS", 0)
    monkeypatch.setattr(device_worker, "_bridge_ready", ready)
    assert device_worker.apply(edited, expected_state=expected)
    edited_snapshot = copy.deepcopy(edited)
    expected.clear()
    edited.clear()
    asyncio.run(queued[0]())
    assert captured == [(edited_snapshot, STATE)]


async def _result(value):
    return value


def test_restore_worker_reports_loss_instead_of_unconditional_success(app, tmp_path, monkeypatch):
    device_worker = worker.DeviceWorker(tmp_path)
    assert not device_worker.write_verified  # Recovery is allowed after a failed compatibility check.
    queued, results = [], []
    monkeypatch.setattr(device_worker, "_submit", lambda job, what: queued.append(job) or True)
    device_worker.restoredFrom.connect(results.append)
    loaded = MagicMock(return_value=copy.deepcopy(STATE))
    monkeypatch.setattr(device_worker.backups, "load", loaded)
    lost = [STATE[0], []]
    async def ready():
        return SimpleNamespace(get_icon_state=lambda **kwargs: _result(lost))
    async def fake_restore(*args):
        return SimpleNamespace(path=tmp_path / "before-restore.plist")
    monkeypatch.setattr(device_worker, "_bridge_ready", ready)
    monkeypatch.setattr(worker, "restore", fake_restore)
    monkeypatch.setattr(worker, "_SETTLE_SECONDS", 0)
    backup = tmp_path / "selected.plist"
    assert device_worker.restore_backup(backup)
    asyncio.run(queued[0]())
    loaded.assert_called_once_with(backup, for_restore=True)
    assert len(results) == 1
    assert not results[0]["comparison"].safe
    assert len(results[0]["comparison"].lost) == 2


def test_restore_ui_uses_verified_result_dialog(window, monkeypatch):
    handled = MagicMock()
    monkeypatch.setattr(window, "_on_applied", handled)
    payload = {"backup": "test", "state": copy.deepcopy(STATE), "comparison": "failed comparison"}
    window._on_restored(payload)
    handled.assert_called_once_with(payload)


def test_changed_content_is_explained_in_result_dialog(window, monkeypatch, tmp_path):
    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append((self.text(), self.icon())))
    comparison = SimpleNamespace(safe=False, lost=[], moved=[], changed=["corrupt metadata"], added=[])
    window._on_applied({"backup": SimpleNamespace(path=tmp_path / "safe.plist"),
                        "state": copy.deepcopy(STATE), "comparison": comparison})
    assert len(shown) == 1
    assert "corrupt metadata" in shown[0][0]
    assert shown[0][1] == QMessageBox.Icon.Warning


def test_connected_device_binds_backup_store_before_use(app, tmp_path, monkeypatch):
    class FakeBridge:
        device_key = "a" * 64
        async def connect(self):
            return None
    monkeypatch.setattr(worker, "DeviceBridge", FakeBridge)
    device_worker = worker.DeviceWorker(tmp_path)
    bound = MagicMock()
    monkeypatch.setattr(device_worker.backups, "bind_device", bound)
    bridge = asyncio.run(device_worker._bridge_ready())
    bound.assert_called_once_with(bridge.device_key)


def test_unverified_ui_blocks_edited_apply(window, monkeypatch):
    _edited(window)
    window.write_verified = False
    window._update_actions()
    applied = MagicMock()
    monkeypatch.setattr(window.worker, "apply", applied)
    dialog = MagicMock()
    monkeypatch.setattr(main_window, "ApplyDialog", dialog)
    assert not window.act_apply.isEnabled()
    assert window.act_restore.isEnabled(), "Recovery must remain available after a failed check"
    window._apply()
    dialog.assert_not_called()
    applied.assert_not_called()


def test_compatibility_requires_clean_live_document_and_confirmation(window, monkeypatch):
    checked = MagicMock()
    monkeypatch.setattr(window.worker, "check_compatibility", checked)
    window._device = ("device", "测试")
    window._set_document(copy.deepcopy(STATE), None)
    assert window.act_compatibility.isEnabled()
    monkeypatch.setattr(main_window.ApplyDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    window._check_compatibility()
    checked.assert_not_called()
    monkeypatch.setattr(main_window.ApplyDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    window._check_compatibility()
    checked.assert_called_once_with(STATE)
    checked.reset_mock()
    _edited(window)
    assert not window.act_compatibility.isEnabled()
    window._check_compatibility()
    checked.assert_not_called()
    window._device = ("file", "预览")
    window._set_document(copy.deepcopy(STATE), None)
    assert not window.act_compatibility.isEnabled()
    window._check_compatibility()
    checked.assert_not_called()


def test_worker_cannot_bypass_unverified_apply_ui(app, tmp_path, monkeypatch):
    device_worker = worker.DeviceWorker(tmp_path)
    queued = []
    monkeypatch.setattr(device_worker, "_submit", lambda job, what: queued.append(job) or True)
    ready = MagicMock()
    monkeypatch.setattr(device_worker, "_bridge_ready", ready)
    device_worker.apply(copy.deepcopy(STATE), expected_state=STATE)
    with pytest.raises(BackupError):
        asyncio.run(queued[0]())
    ready.assert_not_called()


@pytest.mark.parametrize("loses_item", [False, True])
def test_compatibility_worker_verifies_readback_before_enabling(app, tmp_path, monkeypatch, loses_item):
    device_worker = worker.DeviceWorker(tmp_path)
    queued, results = [], []
    monkeypatch.setattr(device_worker, "_submit", lambda job, what: queued.append(job) or True)
    device_worker.compatibilityChecked.connect(results.append)
    before = copy.deepcopy(STATE)
    after = copy.deepcopy(STATE)
    if loses_item:
        after[1].pop()
    calls = []
    async def fake_write(bridge, store, state, reason, *, expected_state):
        assert not device_worker.write_verified
        calls.append((state, reason, expected_state))
        return SimpleNamespace(path=tmp_path / "backup.plist")
    async def ready():
        return SimpleNamespace(get_icon_state=lambda **kwargs: _result(after))
    monkeypatch.setattr(device_worker, "_bridge_ready", ready)
    monkeypatch.setattr(worker, "guarded_write", fake_write)
    monkeypatch.setattr(worker, "_SETTLE_SECONDS", 0)
    device_worker.check_compatibility(before)
    before.clear()
    asyncio.run(queued[0]())
    assert calls == [(STATE, "compatibility", STATE)]
    assert device_worker.write_verified is (not loses_item)
    assert results[0]["comparison"].safe is (not loses_item)


def test_compatibility_failure_revokes_ui_write_permissions(window, monkeypatch, tmp_path):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: None)
    window._device = ("device", "测试")
    good = {"backup": SimpleNamespace(path=tmp_path / "safe.plist"),
            "state": copy.deepcopy(STATE), "comparison": compare_after_write(STATE, STATE)}
    window._on_compatibility(good)
    assert window.write_verified
    assert window.act_restore.isEnabled()
    lost = [STATE[0], []]
    window._on_compatibility({**good, "state": lost, "comparison": compare_after_write(STATE, lost)})
    assert not window.write_verified
    assert window.act_restore.isEnabled(), "A failed check must not disable backup recovery"
    assert not window.act_apply.isEnabled()


def test_loading_again_and_operation_failure_revoke_ui_verification(window, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: None)
    window.write_verified = True
    window._on_loaded(copy.deepcopy(STATE), None, SimpleNamespace(summary=lambda: "测试设备"))
    assert not window.write_verified
    window.write_verified = True
    window._on_failed("连接中断", "重新连接")
    assert not window.write_verified
    assert window.act_restore.isEnabled()


def test_unverified_restore_requires_explicit_confirmation(window, monkeypatch, tmp_path):
    window._device = ("device", "测试")
    window._set_document(copy.deepcopy(STATE), None)
    assert not window.write_verified
    restored = MagicMock()
    monkeypatch.setattr(window.worker, "restore_backup", restored)
    monkeypatch.setattr(window.worker.backups, "list_backups", lambda: ["local-backup"])
    chosen = tmp_path / "same-device-backup.plist"
    monkeypatch.setattr(main_window.QFileDialog, "getOpenFileName", lambda *args: (str(chosen), ""))
    monkeypatch.setattr(main_window.ApplyDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    window._restore()
    restored.assert_not_called()
    monkeypatch.setattr(main_window.ApplyDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    window._restore()
    restored.assert_called_once_with(chosen)


def test_worker_failure_revokes_write_verification(app, tmp_path, monkeypatch):
    class FakeDeviceError(Exception):
        action = "重试"
    monkeypatch.setattr(worker, "DeviceError", FakeDeviceError)
    device_worker = worker.DeviceWorker(tmp_path)
    device_worker.write_verified = True
    device_worker._loop = SimpleNamespace(is_closed=lambda: False)
    device_worker._loop_ready.set()
    monkeypatch.setattr(worker.asyncio, "run_coroutine_threadsafe", lambda coro, loop: asyncio.run(coro))
    failures = []
    device_worker.failed.connect(lambda *args: failures.append(args))
    async def fail():
        raise FakeDeviceError("disconnect")
    assert device_worker._submit(fail, "应用")
    assert not device_worker.write_verified
    assert not device_worker.busy
    assert failures == [("disconnect", "重试")]


def test_reading_device_never_performs_compatibility_write(app, tmp_path, monkeypatch):
    device_worker = worker.DeviceWorker(tmp_path)
    device_worker.write_verified = True
    queued, loaded = [], []
    monkeypatch.setattr(device_worker, "_submit", lambda job, what: queued.append(job) or True)
    device_worker.loaded.connect(lambda *args: loaded.append(args))
    fake_bridge = SimpleNamespace(
        info="test device",
        get_icon_state=lambda **kwargs: _result(copy.deepcopy(STATE)),
        get_homescreen_icon_metrics=lambda: _result({}),
        list_installed_apps=lambda: _result({"a": "地图"}),
    )
    monkeypatch.setattr(device_worker, "_bridge_ready", lambda: _result(fake_bridge))
    write = MagicMock(side_effect=AssertionError("A read must not write to the device"))
    monkeypatch.setattr(worker, "guarded_write", write)
    device_worker.load()
    asyncio.run(queued[0]())
    assert not device_worker.write_verified
    assert loaded == [(STATE, {}, "test device")]
    write.assert_not_called()
