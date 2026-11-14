"""Independent evidence/preflight/simulator boundaries. Synthetic data only.

Never run the real USB collection entry point; all collector/GUI calls below use
fake adapters or trap device factories before they can be invoked.
"""
from __future__ import annotations

import asyncio
import ast
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
from unittest.mock import MagicMock

import pytest

from ipsm.backup import BackupError, BackupStore, restore
from ipsm.drafts import OfflineDraft
from ipsm.write_policy import write_block_reason
from research.duo_simulator import (
    FakeTransport, InventoryQuery, Observation, Scenario, Status,
    builtin_scenarios, simulate, synthetic_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
PHONE_A = "a" * 64
PHONE_B = "b" * 64


@pytest.fixture(autouse=True)
def isolated_app_state(tmp_path, monkeypatch):
    from ipsm import i18n
    previous = i18n.language()
    monkeypatch.setenv("HOMESPREAD_DATA_DIR", str(tmp_path / "isolated-data"))
    monkeypatch.setenv("HOMESPREAD_CACHE_DIR", str(tmp_path / "isolated-cache"))
    yield
    i18n.set_language(previous)


def binary(value):
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY, sort_keys=True)


@pytest.mark.parametrize("behavior", ["no_reply", "timeout_before_effect", "timeout_after_effect",
                                     "disconnect_before_effect", "disconnect_after_effect"])
def test_ambiguous_fake_send_never_retries_or_automatically_restores(behavior):
    base = synthetic_scenario()
    scenario = replace(base, send_behavior=behavior,
                       readbacks=(Observation("failure"), Observation("timeout")),
                       max_readback_attempts=5)
    before = binary(scenario.current)
    result = simulate(scenario)
    assert result.status is Status.UNCERTAIN
    assert result.send_attempts == 1 and result.rollback_attempts == 0
    assert result.read_attempts == 5
    assert result.fresh_connection_ids == tuple(range(1, 6))
    assert result.send_uncertain
    assert not result.can_write and not result.fully_verified
    assert binary(scenario.current) == before


def test_match_after_no_reply_is_only_partial_export_verification():
    result = simulate(replace(synthetic_scenario(), send_behavior="no_reply"))
    assert result.status is Status.EXPORTED_FIELDS_MATCH_ONLY
    assert result.send_uncertain and result.send_attempts == 1
    assert result.unverified_factors
    assert {"hidden_page_visibility", "native_gaps", "widget_runtime_configuration"} <= set(result.unverified_factors)
    assert not result.can_write and not result.fully_verified


@pytest.mark.parametrize("mutation", ["selection", "suggestions", "member_parameter", "bool_to_int", "extra_page"])
def test_fake_readback_cannot_ignore_widget_or_typed_content_changes(mutation):
    base = synthetic_scenario()
    observed = deepcopy(base.candidate)
    if mutation == "selection":
        observed[1][0].pop("userSelectedElementIdentifier")
    elif mutation == "suggestions":
        observed[1][0]["allowsSuggestions"] = False
    elif mutation == "member_parameter":
        observed[1][0]["elements"][0]["futureParameters"] = b"unexpected"
    elif mutation == "bool_to_int":
        observed[1][1]["opaque"]["flag"] = 1
    else:
        observed.append([])
    result = simulate(replace(base, readbacks=(Observation("snapshot", observed),)))
    assert result.status is Status.MISMATCH
    assert result.differences
    assert result.send_attempts == 1 and result.rollback_attempts == 0
    assert not result.can_write and not result.fully_verified


def test_failure_after_a_mismatch_retains_uncertainty_without_writing_again():
    base = synthetic_scenario()
    observed = deepcopy(base.candidate)
    observed[1][0]["elements"].reverse()
    result = simulate(replace(base, readbacks=(Observation("snapshot", observed), Observation("failure"))))
    assert result.status is Status.UNCERTAIN
    assert result.differences and result.send_attempts == 1
    assert result.rollback_attempts == 0


@pytest.mark.parametrize("case", ["identity", "stale", "backup", "inventory_failed", "inventory_partial", "placeholders"])
def test_fake_pre_send_failures_have_zero_send_attempts(case):
    base = synthetic_scenario()
    if case == "identity":
        scenario = replace(base, current_identity="another-synthetic-device")
    elif case == "stale":
        scenario = replace(base, current=deepcopy(base.candidate))
    elif case == "backup":
        scenario = replace(base, backup_result="corrupt")
    elif case == "inventory_failed":
        scenario = replace(base, inventory=replace(base.inventory, user=InventoryQuery("failed", (), True)))
    elif case == "inventory_partial":
        scenario = replace(base, inventory=replace(base.inventory, system=replace(base.inventory.system, complete=False)))
    else:
        scenario = replace(base, inventory=replace(base.inventory, placeholders_requested=1))
    result = simulate(scenario)
    assert result.status is Status.BLOCKED
    assert result.send_attempts == result.read_attempts == result.rollback_attempts == 0
    assert not result.can_write


def test_simulator_cannot_accept_a_device_adapter_or_transport_subclass():
    class DeviceTrap:
        def send(self, *_):
            raise AssertionError("A real-looking adapter must not be invoked")

    with pytest.raises(TypeError):
        simulate(DeviceTrap())
    with pytest.raises(TypeError):
        class ForbiddenTransport(FakeTransport):
            pass


def test_every_builtin_scenario_keeps_production_duo_write_guard():
    for scenario in builtin_scenarios():
        result = simulate(scenario)
        assert result.send_attempts <= 1 and result.rollback_attempts == 0
        assert result.can_write is False and result.fully_verified is False
        assert write_block_reason(scenario.candidate, product_type="iPhone19,4")


def test_simulator_summary_does_not_expose_fabricated_app_identities():
    text = json.dumps(simulate(synthetic_scenario()).to_dict())
    assert "example.user" not in text and "example.member" not in text
    assert "synthetic-phone" not in text


def evidence_state():
    return deepcopy(synthetic_scenario().origin)


class FakeEvidenceReader:
    def __init__(self, fail_part=None, *, empty_inventory=False, close_failure=False):
        self.calls = []
        self.closed = 0
        self.fail_part = fail_part
        self.empty_inventory = empty_inventory
        self.close_failure = close_failure

    async def read(self, part):
        self.calls.append(part)
        if part == self.fail_part:
            raise RuntimeError("private-error-details-must-not-be-exported")
        if part.startswith("identity_"):
            return {"device_key": PHONE_A, "product_type": "iPhone19,4", "ios_version": "27.3",
                    "build_version": "synthetic-build-a", "transport": "USB"}
        if part.startswith("layout_v2"):
            return evidence_state()
        if part == "metrics":
            return {"homeScreenIconColumns": 4, "homeScreenIconRows": 6,
                    "homeScreenIconDockMaxCount": 4, "homeScreenIconFolderColumns": 3,
                    "homeScreenIconFolderRows": 3}
        if part == "apps_user":
            if self.empty_inventory:
                return {}
            return {ident: {"CFBundleIdentifier": ident, "ApplicationType": "User", "IsDemotedApp": False}
                    for ident in ("example.user.a", "example.user.b", "example.library")}
        if part == "apps_system":
            if self.empty_inventory:
                return {}
            return {"example.system.dock": {"CFBundleIdentifier": "example.system.dock", "ApplicationType": "System"}}
        if part == "layout_v3":
            return {"reference": "synthetic-only", "iconLists": evidence_state()}
        raise AssertionError("Unexpected query")

    async def close(self):
        self.closed += 1
        if self.close_failure:
            raise RuntimeError("private-close-details")


def collected_bundle(*, fail_part=None, empty_inventory=False, close_failure=False):
    from ipsm.evidence import collect_evidence
    adapter = FakeEvidenceReader(fail_part, empty_inventory=empty_inventory, close_failure=close_failure)
    bundle = asyncio.run(collect_evidence(adapter, source="synthetic", timeout=0.1))
    return bundle, adapter


def changed_draft():
    draft = OfflineDraft(evidence_state())
    draft.swap(1, 1, 2)
    return draft


def checks(report):
    return {item["code"]: item for item in report["checks"]}


def usb_labeled_bundle(*, age_seconds=0, empty_inventory=False):
    """A deliberately synthetic record carrying a USB source label, not authenticity."""
    from ipsm.evidence import EvidenceBundle
    bundle, _ = collected_bundle(empty_inventory=empty_inventory)
    record = bundle.record
    now = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
    stamp = (now - timedelta(seconds=age_seconds)).isoformat()
    record["source"] = "usb_readonly"
    record["started_at"] = record["finished_at"] = stamp
    for receipt in record["receipts"].values():
        if receipt["status"] in ("observed", "failed"):
            receipt["started_at"] = receipt["finished_at"] = stamp
    return EvidenceBundle.from_record(record), now


@pytest.mark.parametrize("failed", ["identity_before", "layout_v2_before", "metrics", "apps_user",
                                   "apps_system", "layout_v2_after", "identity_after", "layout_v3"])
def test_collector_stops_at_first_failed_query_and_closes_without_retry(failed):
    from ipsm.evidence import PARTS
    bundle, adapter = collected_bundle(fail_part=failed)
    index = PARTS.index(failed)
    assert adapter.calls == list(PARTS[:index + 1])
    assert adapter.closed == 1
    assert bundle.receipts[failed]["status"] == "failed"
    assert bundle.receipts[failed]["error_code"] == "query_failed"
    assert bundle.data(failed) is None
    assert all(bundle.receipts[p]["status"] == "not_collected" for p in PARTS[index + 1:])
    assert not bundle.collection_succeeded and not bundle.can_write
    assert "private-error-details" not in json.dumps(bundle.record, default=str)


def test_successful_empty_query_is_observed_but_never_means_full_library_coverage():
    from ipsm.preflight import build_preflight_report
    bundle, adapter = collected_bundle(empty_inventory=True)
    assert bundle.collection_succeeded and adapter.closed == 1
    assert bundle.receipts["apps_user"]["status"] == "observed" and bundle.data("apps_user") == {}
    report = build_preflight_report(changed_draft(), bundle)
    assert checks(report)["apps_user"]["status"] == "pass"
    assert checks(report)["hidden_webclips"]["status"] == "unknown"
    assert report["can_write"] is False and report["status"] == "blocked"


def test_empty_observed_inventory_that_omits_visible_apps_is_a_reported_contradiction():
    from ipsm.preflight import build_preflight_report
    bundle, now = usb_labeled_bundle(empty_inventory=True)
    report = build_preflight_report(changed_draft(), bundle, now=now)
    assert checks(report)["visible_inventory_coverage"]["status"] == "failed"


def test_close_failure_is_not_hidden_by_successful_observations():
    from ipsm.preflight import build_preflight_report
    bundle, adapter = collected_bundle(close_failure=True)
    assert adapter.closed == 1 and not bundle.collection_succeeded
    assert bundle.record["close_error_code"] == "close_failed"
    report = build_preflight_report(changed_draft(), bundle)
    assert checks(report)["collection_completion"]["status"] == "failed"


def test_importing_a_backup_cannot_invent_identity_inventory_or_new_device_reads():
    from ipsm.evidence import EvidenceBundle, PARTS
    from ipsm.preflight import build_preflight_report
    raw = evidence_state()
    before = binary(raw)
    bundle = EvidenceBundle.from_backup(raw, source_file_sha256=hashlib.sha256(before).hexdigest())
    assert binary(bundle.data("layout_v2_before")) == before
    for part in PARTS:
        if part != "layout_v2_before":
            assert bundle.receipts[part]["status"] == "missing" and bundle.data(part) is None
    assert not bundle.collection_succeeded and not bundle.can_write
    report = build_preflight_report(changed_draft(), bundle)
    c = checks(report)
    assert c["evidence_source"]["status"] == "blocked"
    assert c["freshness"]["status"] == "missing"
    assert c["snapshot_stability"]["status"] == "missing"
    assert c["device_identity"]["status"] == "missing"
    assert report["can_write"] is False


@pytest.mark.parametrize("field", ["geometry", "hidden_pages", "widget_settings", "hidden_webclips"])
def test_evidence_cannot_promote_unobservable_state_to_verified(field):
    from ipsm.evidence import EvidenceBundle, EvidenceError
    bundle, _ = collected_bundle()
    record = bundle.record
    record["unknown"][field] = "verified"
    with pytest.raises(EvidenceError):
        EvidenceBundle.from_record(record)


@pytest.mark.parametrize("mutation", ["boolean_option", "false_status_data", "extra_private_identity", "mixed_scope"])
def test_receipt_type_and_scope_tampering_is_rejected(mutation):
    from ipsm.evidence import EvidenceBundle, EvidenceError
    bundle, _ = collected_bundle()
    record = bundle.record
    if mutation == "boolean_option":
        record["receipts"]["apps_user"]["options"]["show_placeholders"] = 1
    elif mutation == "false_status_data":
        receipt = record["receipts"]["apps_user"]
        receipt.update(status="failed", error_code="query_failed")  # Data must not survive a failure label.
    elif mutation == "extra_private_identity":
        record["receipts"]["identity_before"]["data"]["udid"] = "not-allowed"
    else:
        record["receipts"]["apps_user"]["data"]["example.user.a"]["ApplicationType"] = "System"
    with pytest.raises(EvidenceError):
        EvidenceBundle.from_record(record)


@pytest.mark.parametrize("age,expected", [(0, "pass"), (301, "failed"), (-6, "failed")])
def test_freshness_reports_age_and_future_timestamps_without_granting_writes(age, expected):
    from ipsm.preflight import build_preflight_report
    bundle, now = usb_labeled_bundle(age_seconds=age)
    report = build_preflight_report(changed_draft(), bundle, now=now)
    assert checks(report)["freshness"]["status"] == expected
    assert report["status"] == "blocked" and report["can_write"] is False


@pytest.mark.parametrize("kind", ["baseline", "layout_after", "device", "model", "ios", "build"])
def test_stale_snapshot_or_identity_changes_are_explicit_preflight_failures(kind):
    from ipsm.evidence import EvidenceBundle
    from ipsm.preflight import build_preflight_report
    bundle, now = usb_labeled_bundle()
    record = bundle.record
    if kind == "baseline":
        record["receipts"]["layout_v2_before"]["data"][1][1]["opaque"]["flag"] = 1
        code = "baseline"
    elif kind == "layout_after":
        record["receipts"]["layout_v2_after"]["data"][1][0]["allowsSuggestions"] = False
        code = "snapshot_stability"
    else:
        field, value = {"device": ("device_key", PHONE_B), "model": ("product_type", "iPhone18,1"),
                        "ios": ("ios_version", "27.4"), "build": ("build_version", "synthetic-build-b")}[kind]
        record["receipts"]["identity_after"]["data"][field] = value
        code = "device_identity"
    report = build_preflight_report(changed_draft(), EvidenceBundle.from_record(record), now=now)
    assert checks(report)[code]["status"] == "failed"
    assert report["can_write"] is False


def test_perfect_export_receipts_are_still_not_full_verification():
    from ipsm.preflight import build_preflight_report
    bundle, now = usb_labeled_bundle()
    draft = changed_draft()
    before = binary(draft.current_state)
    report = build_preflight_report(draft, bundle, now=now)
    c = checks(report)
    for code in ("geometry", "hidden_pages", "widget_settings", "hidden_webclips", "wire_protocol"):
        assert c[code]["status"] == "unknown" and code in report["blockers"]
    assert c["write_policy"]["status"] == "blocked"
    assert report["device_requests"] == 0 and report["can_write"] is False
    assert binary(draft.current_state) == before
    assert write_block_reason(draft.current_state, product_type="iPhone19,4")


def test_report_replays_history_instead_of_trusting_forged_draft_state():
    from ipsm.preflight import build_preflight_report
    draft = changed_draft()
    forged = draft.current_state
    forged[1][0]["allowsSuggestions"] = False
    draft._states[draft._cursor] = binary(forged)
    with pytest.raises(ValueError):
        build_preflight_report(draft)


@pytest.mark.parametrize("field,value", [("schema_version", True), ("schema_version", 2),
                                        ("can_write", 0), ("can_write", True),
                                        ("record_sha256", "0" * 64)])
def test_evidence_file_rejects_header_or_integrity_tampering(tmp_path, field, value):
    from ipsm.evidence import EvidenceBundle, EvidenceError
    bundle, _ = collected_bundle()
    path = bundle.save(tmp_path / "receipt.hsevidence")
    envelope = plistlib.loads(path.read_bytes())
    envelope[field] = value
    path.write_bytes(binary(envelope))
    with pytest.raises(EvidenceError):
        EvidenceBundle.load(path)


def test_evidence_record_and_loaded_data_are_detached(tmp_path):
    from ipsm.evidence import EvidenceBundle
    bundle, _ = collected_bundle()
    first = bundle.data("layout_v2_before")
    first[1].clear()
    second = bundle.record
    second["receipts"]["apps_user"]["data"].clear()
    assert bundle.data("layout_v2_before")[1]
    assert bundle.data("apps_user")
    path = bundle.save(tmp_path / "receipt.hsevidence")
    loaded = EvidenceBundle.load(path)
    assert binary(bundle.record) == binary(loaded.record)
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_evidence_and_report_files_cannot_enter_phone_restoration(tmp_path):
    from ipsm.preflight import build_preflight_report, save_preflight_report
    bundle, _ = collected_bundle()
    evidence_path = bundle.save(tmp_path / "receipt.hsevidence")
    report_path = save_preflight_report(tmp_path / "report.hspreflight", build_preflight_report(changed_draft(), bundle))
    store = BackupStore(tmp_path / "app", PHONE_A)

    class FakePhone:
        device_key = PHONE_A
        reads = 0
        writes = 0

        async def get_icon_state(self):
            self.reads += 1
            raise AssertionError("Invalid artifacts must be refused before querying a phone")

        async def set_icon_state(self, _):
            self.writes += 1
            raise AssertionError("Evidence/report artifacts cannot be written")

    phone = FakePhone()
    for index, source in enumerate((evidence_path, report_path)):
        payload = source.read_bytes()
        target = store.dir / f"forged{index}.plist"
        target.write_bytes(payload)
        target.with_suffix(".meta.json").write_text(json.dumps({"schema": 1, "device_key": PHONE_A,
                                                              "sha256": hashlib.sha256(payload).hexdigest()}))
        with pytest.raises(BackupError):
            asyncio.run(restore(phone, store, target))
    assert phone.reads == phone.writes == 0


def test_report_save_refuses_original_backup_and_disguised_nonreport(tmp_path):
    from ipsm.preflight import build_preflight_report, save_preflight_report
    report = build_preflight_report(changed_draft())
    original = binary(evidence_state())
    for suffix in (".plist", ".hspreflight"):
        path = tmp_path / ("original" + suffix)
        path.write_bytes(original)
        with pytest.raises((ValueError, OSError)):
            save_preflight_report(path, report, replace=True)
        assert path.read_bytes() == original


def test_report_save_never_accepts_a_write_enabled_header(tmp_path):
    from ipsm.preflight import build_preflight_report, save_preflight_report
    report = build_preflight_report(changed_draft())
    for flag in (True, 0, 1):
        forged = deepcopy(report)
        forged["can_write"] = flag
        with pytest.raises(ValueError):
            save_preflight_report(tmp_path / "invalid.hspreflight", forged)
    path = save_preflight_report(tmp_path / "blocked.hspreflight", report)
    assert json.loads(path.read_text())["can_write"] is False
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_evidence_cli_help_and_missing_scope_cannot_construct_a_device(tmp_path, monkeypatch):
    import sys
    import types
    from ipsm import evidence_collect

    trap = MagicMock(side_effect=AssertionError("No device construction in help or refused collection"))
    fake_module = types.ModuleType("ipsm.device")
    fake_module.ReadOnlyEvidenceAdapter = trap
    monkeypatch.setitem(sys.modules, "ipsm.device", fake_module)
    with pytest.raises(SystemExit) as exc:
        evidence_collect.main(["--help"])
    assert exc.value.code == 0
    # This exercises the CLI refusal only; the adapter module is a trap, not an SDK.
    with pytest.raises(SystemExit) as exc:
        evidence_collect.main(["--collect-usb", "--output", str(tmp_path / "refused.hsevidence")])
    assert exc.value.code == 2
    trap.assert_not_called()
    assert not (tmp_path / "refused.hsevidence").exists()


def test_local_backup_import_cli_does_not_construct_a_device(tmp_path, monkeypatch):
    import sys
    import types
    from ipsm import evidence_collect
    from ipsm.evidence import EvidenceBundle

    monkeypatch.setenv("HOMESPREAD_DATA_DIR", str(tmp_path / "app-data"))
    trap = MagicMock(side_effect=AssertionError("A local import must not instantiate a device"))
    fake_module = types.ModuleType("ipsm.device")
    fake_module.ReadOnlyEvidenceAdapter = trap
    monkeypatch.setitem(sys.modules, "ipsm.device", fake_module)
    path = tmp_path / "input.plist"
    before = binary(evidence_state())
    path.write_bytes(before)
    output = tmp_path / "local.hsevidence"
    assert evidence_collect.main(["--from-backup", str(path), "--output", str(output)]) == 0
    trap.assert_not_called()
    result = EvidenceBundle.load(output)
    assert result.source == "imported_backup" and not result.collection_succeeded
    assert result.record["source_file_sha256"] == hashlib.sha256(before).hexdigest()
    assert path.read_bytes() == before


def test_readonly_adapter_rejects_unknown_actions_before_connecting(monkeypatch):
    from ipsm.device import ReadOnlyEvidenceAdapter

    adapter = ReadOnlyEvidenceAdapter()
    ready = MagicMock(side_effect=AssertionError("Unsupported actions must not connect"))
    monkeypatch.setattr(adapter, "_ready", ready)
    for name in ("set_icon_state", "reload_icon_state", "restore", "install", "get_icon_pngdata"):
        with pytest.raises(ValueError):
            asyncio.run(adapter.read(name))
    ready.assert_not_called()


def test_readonly_adapter_queries_minimal_inventory_including_placeholders(monkeypatch):
    from ipsm import device

    calls = []

    class FakeProxy:
        def __init__(self, **kwargs):
            calls.append(("create", kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def lookup(self, options):
            calls.append(("lookup", options))
            kind = options["ApplicationType"]
            return {"example.visible": {"CFBundleIdentifier": "example.visible", "ApplicationType": kind,
                                        "IsDemotedApp": True, "CFBundleDisplayName": "Example",
                                        "PrivateContainerPath": "not-requested-not-exported"}}

    adapter = device.ReadOnlyEvidenceAdapter()
    sentinel = object()
    adapter._lockdown = sentinel  # Inject a fake already-created session; never call its factory.
    monkeypatch.setattr(device, "InstallationProxyService", FakeProxy)
    for part, expected in (("apps_user", "User"), ("apps_system", "System")):
        result = asyncio.run(adapter.read(part))
        options = calls[-1][1]
        assert options["ApplicationType"] == expected and options["ShowPlaceholders"] is True
        assert set(options["ReturnAttributes"]) == set(adapter._ATTRIBUTES)
        assert result["example.visible"]["IsDemotedApp"] is True
        assert "PrivateContainerPath" not in result["example.visible"]


def test_readonly_adapter_fresh_identity_is_whitelisted_and_hashed():
    from ipsm.device import ReadOnlyEvidenceAdapter

    class FakeLockdown:
        calls = []
        async def get_value(self, *, key):
            self.calls.append(key)
            return {"UniqueDeviceID": "00000000-1111111111111111", "ProductType": "iPhone19,4",
                    "ProductVersion": "27.3", "BuildVersion": "synthetic-build"}[key]

    adapter = ReadOnlyEvidenceAdapter()
    fake = FakeLockdown()
    adapter._lockdown = fake
    one = asyncio.run(adapter.read("identity_before"))
    two = asyncio.run(adapter.read("identity_after"))
    assert len(fake.calls) == 8
    assert set(one) == {"device_key", "product_type", "ios_version", "build_version", "transport"}
    assert one == two and one["transport"] == "USB"
    assert one["device_key"] == hashlib.sha256(b"000000001111111111111111").hexdigest()
    assert "11111111" not in json.dumps(one)


@pytest.fixture(scope="session")
def preflight_qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def preflight_window(preflight_qt_app, tmp_path, monkeypatch):
    import socket
    from PySide6.QtCore import QCoreApplication, QEvent
    from ipsm import apple_devices, i18n
    from ipsm.ui import main_window, worker

    monkeypatch.setenv("HOMESPREAD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOMESPREAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(worker.DeviceWorker, "start", lambda self: None)
    monkeypatch.setattr(worker.DeviceWorker, "shutdown", lambda self: None)
    guards = []
    for owner, name in ((socket, "socket"), (apple_devices, "look"), (worker, "DeviceBridge")):
        guard = MagicMock(side_effect=AssertionError("Offline preflight must not access a device or network"))
        monkeypatch.setattr(owner, name, guard)
        guards.append(guard)
    window = main_window.MainWindow(tmp_path / "app", offline=True)
    for name in ("load", "fetch_icons", "apply", "check_compatibility", "restore_backup"):
        guard = MagicMock(side_effect=AssertionError("Preflight must not submit device work"))
        monkeypatch.setattr(window.worker, name, guard)
        guards.append(guard)
    source = tmp_path / "source.plist"
    source.write_bytes(binary(evidence_state()))
    assert window.open_preview(source) and window.start_draft()
    window.draft.swap(1, 1, 2)
    window._render_draft()
    yield window, source
    for guard in guards:
        guard.assert_not_called()
    monkeypatch.setattr(window, "_confirm_draft_transition", lambda: True)
    window.close()
    i18n.off_language_changed(window.retranslate)
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    preflight_qt_app.processEvents()


def test_ui_preflight_import_export_is_offline_and_preserves_the_draft(preflight_window, tmp_path):
    from PySide6.QtCore import QCoreApplication, QEvent
    from ipsm.evidence import EvidenceBundle
    from ipsm.ui.preflight_dialog import PreflightDialog

    window, source = preflight_window
    original_file = source.read_bytes()
    candidate = binary(window.draft.current_state)
    report = window.create_preflight_report()
    assert report["can_write"] is False and report["device_requests"] == 0
    dialog = PreflightDialog(window.draft, tmp_path, window)
    try:
        assert dialog.text.isReadOnly()
        path = EvidenceBundle.from_backup(window.draft.origin).save(tmp_path / "local.hsevidence")
        dialog.load_evidence(path)
        assert dialog.report["evidence_source"] == "imported_backup"
        exported = dialog.export_report(tmp_path / "local.hspreflight")
        assert json.loads(exported.read_text())["can_write"] is False
        assert not window.act_load.isEnabled() and not window.act_apply.isEnabled()
        assert not window.act_restore.isEnabled() and not window.act_compatibility.isEnabled()
        assert binary(window.draft.current_state) == candidate and source.read_bytes() == original_file
        assert window.draft.dirty
    finally:
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_ui_report_snapshot_is_detached_from_later_draft_edits(preflight_window, tmp_path):
    from PySide6.QtCore import QCoreApplication, QEvent
    from ipsm.ui.preflight_dialog import PreflightDialog

    window, _ = preflight_window
    dialog = PreflightDialog(window.draft, tmp_path, window)
    try:
        before = binary(dialog.draft.current_state)
        window.draft.undo()
        assert binary(window.draft.current_state) != before
        dialog.refresh_report()
        assert binary(dialog.draft.current_state) == before and len(dialog.report["changes"]) == 2
    finally:
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_dialog_refuses_inconsistent_current_state_instead_of_repairing_it(preflight_window, tmp_path):
    from ipsm.ui.preflight_dialog import PreflightDialog

    window, _ = preflight_window
    altered = window.draft.current_state
    altered[1][0]["allowsSuggestions"] = False
    window.draft._states[window.draft._cursor] = binary(altered)
    with pytest.raises(ValueError):
        PreflightDialog(window.draft, tmp_path, window)


def test_preflight_ui_action_does_not_start_collection(preflight_window, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QEvent
    from ipsm.ui.preflight_dialog import PreflightDialog

    window, _ = preflight_window
    seen = []
    monkeypatch.setattr(PreflightDialog, "exec", lambda self: seen.append(self.report) or 0)
    assert window.act_preflight.isEnabled()
    window._preflight_report()
    assert len(seen) == 1 and seen[0]["can_write"] is False
    # Dialog is parent-owned; destroy while the QApplication is alive.
    for child in window.findChildren(PreflightDialog):
        child.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_dialog_uses_plain_text_for_draft_app_names(preflight_window, tmp_path):
    from PySide6.QtCore import QCoreApplication, QEvent
    from ipsm.ui.preflight_dialog import PreflightDialog

    window, _ = preflight_window
    raw = evidence_state()
    raw[1][1]["displayName"] = '<img src="https://example.invalid/no-network">'
    draft = OfflineDraft(raw)
    draft.swap(1, 1, 2)
    dialog = PreflightDialog(draft, tmp_path, window)
    try:
        assert '<img src="https://example.invalid/no-network">' in dialog.text.toPlainText()
        assert dialog.report["can_write"] is False
    finally:
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_real_evidence_adapter_has_no_write_or_pairing_calls():
    """Inspect the adapter without constructing or running its real USB path."""
    tree = ast.parse((ROOT / "src/ipsm/device.py").read_text())
    adapter = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == "ReadOnlyEvidenceAdapter")
    forbidden = {"set_icon_state", "reload_icon_state", "pair", "unpair", "install", "uninstall",
                 "restore", "set_value", "remove_value", "send_plist", "send_recv_plist", "sendall"}
    factories = []
    for node in ast.walk(adapter):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden
        elif isinstance(node.func, ast.Name):
            assert node.func.id not in {"DeviceBridge", "eval", "exec", "__import__"}
            if node.func.id == "create_using_usbmux":
                factories.append(node)
                keywords = {kw.arg: kw.value for kw in node.keywords}
                assert isinstance(keywords.get("autopair"), ast.Constant)
                assert keywords["autopair"].value is False
                assert isinstance(keywords.get("connection_type"), ast.Constant)
                assert keywords["connection_type"].value == "USB"
    assert len(factories) == 1


def test_preflight_ui_never_imports_the_real_collector():
    for relative in ("src/ipsm/preflight.py", "src/ipsm/ui/preflight_dialog.py", "src/ipsm/ui/main_window.py"):
        tree = ast.parse((ROOT / relative).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not name.name.endswith(("evidence_collect", ".device"))
                           and not name.name.startswith("pymobiledevice3") for name in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.module not in {"device", "evidence_collect", "ipsm.device", "ipsm.evidence_collect"}
                assert not (node.module or "").startswith("pymobiledevice3")
                assert all(alias.name != "ReadOnlyEvidenceAdapter" for alias in node.names)


@pytest.mark.parametrize("platform,endpoint", [("darwin", "/var/run/usbmuxd"),
                                               ("win32", "127.0.0.1:27015")])
def test_evidence_adapter_ignores_remote_mux_environment_override(tmp_path, monkeypatch, platform, endpoint):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from ipsm import device

    monkeypatch.setenv("USBMUXD_SOCKET_ADDRESS", "198.51.100.10:27015")
    monkeypatch.setattr(device.sys, "platform", platform)
    monkeypatch.setattr(device, "data_root", lambda: tmp_path)
    listing = AsyncMock(return_value=[SimpleNamespace(serial="synthetic-usb-device", connection_type="USB")])
    session = SimpleNamespace(paired=True, close=AsyncMock())
    factory = AsyncMock(return_value=session)
    monkeypatch.setattr(device.usbmux, "list_devices", listing)
    monkeypatch.setattr(device, "create_using_usbmux", factory)
    adapter = device.ReadOnlyEvidenceAdapter()
    asyncio.run(adapter._ready())
    listing.assert_awaited_once_with(usbmux_address=endpoint)
    assert factory.await_args.kwargs["usbmux_address"] == endpoint
    assert factory.await_args.kwargs["autopair"] is False
    assert factory.await_args.kwargs["connection_type"] == "USB"
    asyncio.run(adapter.close())
    session.close.assert_awaited_once()


def test_export_picker_sets_native_default_suffix(preflight_window, tmp_path, monkeypatch):
    """A native save panel must not require manually retyping the report suffix."""
    from ipsm.ui import preflight_dialog as module
    from PySide6.QtCore import QCoreApplication, QEvent
    window = preflight_window[0]
    real_picker = module.QFileDialog
    seen = {}

    class Picker:
        AcceptMode = real_picker.AcceptMode
        FileMode = real_picker.FileMode
        def __init__(self, *args): pass
        def setAcceptMode(self, value): seen["mode"] = value
        def setFileMode(self, value): pass
        def setNameFilter(self, value): pass
        def setDefaultSuffix(self, value): seen["suffix"] = value
        def selectFile(self, value): seen["name"] = value
        def exec(self): return module.QDialog.DialogCode.Rejected
        def deleteLater(self): seen["disposed"] = True

    monkeypatch.setattr(module, "QFileDialog", Picker)
    dialog = module.PreflightDialog(window.draft, tmp_path, window)
    try:
        dialog._export()
        assert seen["suffix"] == "hspreflight"
        assert seen["name"].endswith(".hspreflight")
        assert seen["mode"] == real_picker.AcceptMode.AcceptSave
        assert seen["disposed"]
        assert not list((tmp_path / "preflight_reports").glob("*.hspreflight"))
    finally:
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
