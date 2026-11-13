"""Security regressions use fake phones only; no USB writes are performed."""
from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import json
import os
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from ipsm.backup import BackupError, BackupStore, guarded_write, restore
from ipsm.iconstate import compare_after_write, deep_equal
from ipsm.logging_setup import Session, _redact
from ipsm.safeio import atomic_private_write

PHONE_A = hashlib.sha256(b'phone-a').hexdigest()
PHONE_B = hashlib.sha256(b'phone-b').hexdigest()
STATE = [[], [
    {'displayIdentifier': 'a', 'displayName': 'A', 'extra': b'keep'},
    {'displayIdentifier': 'b', 'displayName': 'B'},
]]


class FakePhone:
    def __init__(self, state=None, key=PHONE_A):
        self.device_key = key
        self.state = copy.deepcopy(STATE if state is None else state)
        self.writes = []

    async def get_icon_state(self):
        return copy.deepcopy(self.state)

    async def set_icon_state(self, state):
        self.writes.append(copy.deepcopy(state))
        self.state = copy.deepcopy(state)


class BackupSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = BackupStore(self.root, PHONE_A)
        self.phone = FakePhone()

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_instant_backups_do_not_replace_each_other(self):
        first = self.store.save(STATE, 'edit')
        second_state = copy.deepcopy(STATE)
        second_state[1].reverse()
        second = self.store.save(second_state, 'edit')
        self.assertNotEqual(first.path, second.path)
        self.assertEqual(self.store.load(first.path, for_restore=True), STATE)
        self.assertEqual(len(self.store.list_backups()), 2)

    def test_private_permissions(self):
        if os.name != 'posix':
            self.skipTest('POSIX permissions')
        saved = self.store.save(STATE)
        self.assertEqual(self.store.dir.stat().st_mode & 0o777, 0o700)
        for path in self.store.dir.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_existing_destination_is_never_overwritten(self):
        path = self.root / 'existing'
        path.write_bytes(b'original')
        with self.assertRaises(FileExistsError):
            atomic_private_write(path, b'replacement')
        self.assertEqual(path.read_bytes(), b'original')
        self.assertFalse(list(self.root.glob('.writing-*')))

    def test_backup_failure_stops_write(self):
        with patch.object(self.store, 'save', side_effect=BackupError('disk full')):
            with self.assertRaises(BackupError):
                asyncio.run(guarded_write(self.phone, self.store, STATE, 'edit', expected_state=STATE))
        self.assertEqual(self.phone.writes, [])

    def test_sync_failure_leaves_no_successful_backup(self):
        with patch('ipsm.safeio.sync_directory', side_effect=OSError('disk failed')):
            with self.assertRaises(BackupError):
                self.store.save(STATE)
        self.assertEqual(list(self.store.dir.iterdir()), [])

    def test_stale_layout_is_never_written(self):
        stale = copy.deepcopy(STATE)
        self.phone.state[1].append({'displayIdentifier': 'new'})
        with self.assertRaises(BackupError):
            asyncio.run(guarded_write(self.phone, self.store, stale, 'edit', expected_state=stale))
        self.assertEqual(self.phone.writes, [])

    def test_valid_reorder_is_backed_up_then_written(self):
        edited = copy.deepcopy(STATE)
        edited[1].reverse()
        backup = asyncio.run(guarded_write(self.phone, self.store, edited, 'edit', expected_state=STATE))
        self.assertEqual(self.store.load(backup.path, for_restore=True), STATE)
        self.assertEqual(self.phone.writes, [edited])

    def test_deletion_duplication_and_metadata_changes_are_blocked(self):
        for kind in ('delete', 'duplicate', 'metadata'):
            edited = copy.deepcopy(STATE)
            if kind == 'delete':
                edited[1].pop()
            elif kind == 'duplicate':
                edited[1].append(copy.deepcopy(edited[1][0]))
            else:
                edited[1][0]['extra'] = b'lost'
            with self.subTest(kind=kind), self.assertRaises(BackupError):
                asyncio.run(guarded_write(self.phone, self.store, edited, 'edit', expected_state=STATE))
        self.assertEqual(self.phone.writes, [])

    def test_unsupported_items_cannot_be_shifted_indirectly(self):
        source = [[], [STATE[1][0], {'widget': 'weather'}, STATE[1][1]]]
        edited = copy.deepcopy(source)
        edited[1][0], edited[1][1] = edited[1][1], edited[1][0]
        self.phone.state = source
        with self.assertRaises(BackupError):
            asyncio.run(guarded_write(self.phone, self.store, edited, 'edit', expected_state=source))
        self.assertEqual(self.phone.writes, [])

    def test_unbound_phone_cannot_write(self):
        self.phone.device_key = None
        with self.assertRaises(BackupError):
            asyncio.run(guarded_write(self.phone, self.store, STATE, 'edit'))
        self.assertEqual(self.phone.writes, [])

    def test_wrong_phone_cannot_restore(self):
        backup = self.store.save(STATE)
        other = BackupStore(self.root, PHONE_B)
        phone = FakePhone(key=PHONE_B)
        with self.assertRaises(BackupError):
            asyncio.run(restore(phone, other, backup.path))
        self.assertEqual(phone.writes, [])
        self.assertEqual(other.list_backups(), [])

    def test_tampered_or_missing_integrity_record_cannot_restore(self):
        backup = self.store.save(STATE)
        path = backup.path.with_suffix('.meta.json')
        meta = json.loads(path.read_text())
        meta['sha256'] = 'bad'
        path.write_text(json.dumps(meta))
        with self.assertRaises(BackupError):
            asyncio.run(restore(self.phone, self.store, backup.path))
        path.unlink()
        with self.assertRaises(BackupError):
            asyncio.run(restore(self.phone, self.store, backup.path))
        self.assertEqual(self.phone.writes, [])

    def test_legacy_file_preview_is_allowed_but_restore_is_not(self):
        path = self.root / 'legacy.plist'
        path.write_bytes(plistlib.dumps(STATE))
        self.assertEqual(self.store.load(path), STATE)
        with self.assertRaises(BackupError):
            asyncio.run(restore(self.phone, self.store, path))
        self.assertEqual(self.phone.writes, [])

    def test_restore_preserves_current_layout_before_replacing(self):
        backup = self.store.save(STATE)
        current = copy.deepcopy(STATE)
        current[1].reverse()
        self.phone.state = current
        before_restore = asyncio.run(restore(self.phone, self.store, backup.path))
        self.assertEqual(self.store.load(before_restore.path, for_restore=True), current)
        self.assertEqual(self.phone.state, STATE)

    def test_malformed_layout_cannot_be_written(self):
        for malformed in ([], {}, ['not a page'], [[], [{'listType': 'folder', 'iconLists': 'bad'}]]):
            with self.subTest(state=malformed), self.assertRaises(BackupError):
                asyncio.run(guarded_write(self.phone, self.store, malformed, 'edit'))
        self.assertEqual(self.phone.writes, [])


class ComparisonSecurityTests(unittest.TestCase):
    def test_same_identifier_with_corrupt_content_fails(self):
        after = copy.deepcopy(STATE)
        after[1][0]['extra'] = b'corrupt'
        result = compare_after_write(STATE, after)
        self.assertFalse(result.safe)
        self.assertTrue(result.changed)

    def test_long_unknown_payload_change_is_not_truncated_away(self):
        before = [[], [{'widget': 'x' * 200 + 'before'}]]
        after = [[], [{'widget': 'x' * 200 + 'after'}]]
        self.assertFalse(compare_after_write(before, after).safe)

    def test_bytes_and_hex_string_are_distinct(self):
        self.assertFalse(deep_equal(b'\x12', '12'))

    def test_appended_app_is_separate_from_corruption(self):
        after = copy.deepcopy(STATE)
        after[1].append({'displayIdentifier': 'c'})
        result = compare_after_write(STATE, after)
        self.assertTrue(result.safe)
        self.assertFalse(result.identical)
        self.assertTrue(result.added)


class LoggingSecurityTests(unittest.TestCase):
    def test_all_udid_forms_are_redacted_to_four_characters(self):
        for identifier in ('00008110-0123456789ABCDEF', '000081100123456789ABCDEF', 'a' * 40):
            result = _redact('device=' + identifier)
            self.assertNotIn(identifier, result)
            self.assertEqual(result, 'device=' + identifier[:4] + '*' * (len(identifier) - 4))

    def test_session_files_unique_private_and_artifacts_cannot_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = Session(root, 'test')
            second = Session(root, 'test')
            self.assertNotEqual(first.log_path, second.log_path)
            for name in ('../escape', 'a/../../escape', 'a\\escape'):
                with self.assertRaises(ValueError):
                    second.save_artifact(name, b'secret', fmt='bytes')
            good = second.save_artifact('normal', {'a': 1})
            if os.name == 'posix':
                self.assertEqual(good.stat().st_mode & 0o777, 0o600)
                self.assertEqual(second.log_path.stat().st_mode & 0o777, 0o600)
            import logging
            for handler in list(logging.getLogger().handlers):
                logging.getLogger().removeHandler(handler)
                handler.close()


class DeviceSecurityTests(unittest.TestCase):
    def test_network_only_device_is_never_selected(self):
        from ipsm import device
        found = [SimpleNamespace(serial='a', connection_type='Network')]
        with patch.object(device.usbmux, 'list_devices', AsyncMock(return_value=found)), \
             patch.object(device, 'create_using_usbmux', AsyncMock()) as connect:
            with self.assertRaises(device.DeviceError):
                asyncio.run(device._create_lockdown(None))
            connect.assert_not_called()

    def test_multiple_usb_devices_are_rejected_without_choice(self):
        from ipsm import device
        found = [SimpleNamespace(serial=serial, connection_type='USB') for serial in ('a', 'b')]
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(device, 'data_root', return_value=Path(tmp)), \
             patch.object(device.usbmux, 'list_devices', AsyncMock(return_value=found)), \
             patch.object(device, 'create_using_usbmux', AsyncMock()) as connect:
            with self.assertRaises(device.DeviceError):
                asyncio.run(device._create_lockdown(None))
            connect.assert_not_called()
            asyncio.run(device._create_lockdown('b'))
            self.assertEqual(connect.call_args.kwargs['serial'], 'b')
            self.assertEqual(connect.call_args.kwargs['connection_type'], 'USB')
            self.assertEqual(connect.call_args.kwargs['pairing_records_cache_folder'], Path(tmp) / 'pairing')
            if os.name == 'posix':
                self.assertEqual((Path(tmp) / 'pairing').stat().st_mode & 0o777, 0o700)

    def test_all_device_write_calls_go_through_backup_guard(self):
        sites = []
        for directory in (ROOT / 'src', ROOT / 'scripts'):
            for path in directory.rglob('*.py'):
                tree = ast.parse(path.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'set_icon_state':
                        sites.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(sorted(sites), ['src/ipsm/backup.py', 'src/ipsm/device.py'])


if __name__ == '__main__':
    unittest.main()
