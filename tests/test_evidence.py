"""Synthetic observations only. USB collection is never run by this suite."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import plistlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ipsm import evidence_collect
from ipsm.evidence import EvidenceBundle, EvidenceError, PARTS, collect_evidence


LAYOUT = [[], [{"displayIdentifier": "example.visible", "iconModDate": datetime(2026, 1, 1, 0, 0, 0, 123456)},
               {"iconType": "custom", "elementType": "widget", "widgetIdentifier": "example.widget",
                "gridSize": "medium", "iconLists": [], "opaque": b"\x00\xff", "enabled": True}]]
IDENTITY = {"device_key": "a" * 64, "product_type": "iPhone19,4", "ios_version": "27.3",
            "build_version": "example-build", "transport": "USB"}


def sample(part):
    if part.startswith("identity"):
        return deepcopy(IDENTITY)
    if part.startswith("layout_v2"):
        return deepcopy(LAYOUT)
    if part == "metrics":
        return {"homeScreenIconColumns": 4, "homeScreenIconRows": 6}
    if part == "apps_user":
        return {}  # An observed empty response is not a failure or completeness proof.
    if part == "apps_system":
        return {"example.system": {"CFBundleIdentifier": "example.system", "ApplicationType": "System",
                                   "IsDemotedApp": True}}
    return {"reference": ["example.reference"]}


class FakeReader:
    def __init__(self, failure=None, bad=None, hangs=None):
        self.reads = []
        self.closes = 0
        self.failure, self.bad, self.hangs = failure, bad, hangs

    async def read(self, part):
        self.reads.append(part)
        if part == self.failure:
            raise RuntimeError("DO_NOT_EXPORT_RAW_SECRET")
        if part == self.hangs:
            await asyncio.sleep(60)
        return self.bad[1] if self.bad and part == self.bad[0] else sample(part)

    async def close(self):
        self.closes += 1


def test_collection_reads_exact_allowlist_and_never_grants_writing():
    reader = FakeReader()
    bundle = asyncio.run(collect_evidence(reader))
    assert reader.reads == list(PARTS)
    assert reader.closes == 1
    assert bundle.collection_succeeded
    assert bundle.can_write is False
    assert bundle.data("apps_user") == {}
    assert bundle.receipts["apps_user"]["status"] == "observed"
    assert set(bundle.record["unknown"].values()) == {"unknown"}


@pytest.mark.parametrize("part", PARTS)
def test_failure_stops_all_later_reads_and_retains_partial_receipts(part):
    reader = FakeReader(failure=part)
    bundle = asyncio.run(collect_evidence(reader))
    i = PARTS.index(part)
    assert reader.reads == list(PARTS[:i + 1])
    assert reader.closes == 1
    assert bundle.receipts[part]["status"] == "failed"
    assert bundle.receipts[part]["error_code"] == "query_failed"
    assert all(bundle.receipts[name]["status"] == "not_collected" for name in PARTS[i + 1:])
    assert not bundle.collection_succeeded
    assert "DO_NOT_EXPORT_RAW_SECRET" not in repr(bundle.record)


def test_timeout_stops_and_closes_without_retry():
    reader = FakeReader(hangs="metrics")
    bundle = asyncio.run(collect_evidence(reader, timeout=0.01))
    assert reader.reads == list(PARTS[:3])
    assert reader.closes == 1
    assert bundle.receipts["metrics"]["error_code"] == "timeout"


@pytest.mark.parametrize("part,value", [("apps_user", None), ("apps_user", {"example.x": None}),
                                      ("identity_before", {**IDENTITY, "DeviceName": "private"}),
                                      ("metrics", {"rows": True}), ("layout_v2_before", {})])
def test_invalid_response_is_not_silently_converted_to_empty(part, value):
    reader = FakeReader(bad=(part, value))
    bundle = asyncio.run(collect_evidence(reader))
    assert bundle.receipts[part]["status"] == "failed"
    assert bundle.receipts[part]["error_code"] == "invalid_response"
    assert bundle.data(part) is None


def test_optional_format3_is_explicitly_not_collected():
    reader = FakeReader()
    bundle = asyncio.run(collect_evidence(reader, include_layout_v3=False))
    assert reader.reads == list(PARTS[:-1])
    assert bundle.receipts["layout_v3"]["status"] == "not_collected"
    assert bundle.data("layout_v3") is None
    assert bundle.can_write is False


def test_close_failure_does_not_report_complete_collection():
    reader = FakeReader()
    reader.close = AsyncMock(side_effect=OSError("SECRET"))
    bundle = asyncio.run(collect_evidence(reader))
    assert bundle.record["close_error_code"] == "close_failed"
    assert not bundle.collection_succeeded
    assert "SECRET" not in repr(bundle.record)


def test_backup_import_has_no_fabricated_identity_inventory_or_freshness():
    payload = plistlib.dumps(LAYOUT, fmt=plistlib.FMT_BINARY)
    bundle = EvidenceBundle.from_backup(LAYOUT, sha256(payload).hexdigest())
    assert bundle.source == "imported_backup"
    assert bundle.data("layout_v2_before") == LAYOUT
    assert bundle.data("layout_v2_after") is None
    assert all(bundle.receipts[name]["status"] == "missing" for name in PARTS if name != "layout_v2_before")
    assert not bundle.collection_succeeded
    assert not bundle.can_write


def test_detached_values_and_save_load_typed_integrity(tmp_path):
    bundle = EvidenceBundle.from_backup(LAYOUT)
    record = bundle.record
    record["receipts"]["layout_v2_before"]["data"][1][1]["enabled"] = 1
    assert bundle.data("layout_v2_before")[1][1]["enabled"] is True
    path = tmp_path / "sample.hsevidence"
    bundle.save(path)
    loaded = EvidenceBundle.load(path)
    assert plistlib.dumps(loaded.data("layout_v2_before"), fmt=plistlib.FMT_BINARY) == plistlib.dumps(LAYOUT, fmt=plistlib.FMT_BINARY)
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600
    envelope = plistlib.loads(path.read_bytes())
    envelope["record"]["receipts"]["layout_v2_before"]["data"][1][1]["enabled"] = 1
    path.write_bytes(plistlib.dumps(envelope, fmt=plistlib.FMT_BINARY))
    with pytest.raises(EvidenceError):
        EvidenceBundle.load(path)


@pytest.mark.parametrize("field,value", [("schema_version", True), ("can_write", 0), ("can_write", True)])
def test_typed_header_cannot_be_forged(tmp_path, field, value):
    path = tmp_path / "bad.hsevidence"
    EvidenceBundle.from_backup(LAYOUT).save(path)
    envelope = plistlib.loads(path.read_bytes())
    envelope[field] = value
    path.write_bytes(plistlib.dumps(envelope, fmt=plistlib.FMT_BINARY))
    with pytest.raises(EvidenceError):
        EvidenceBundle.load(path)


@pytest.mark.parametrize("mutation", ["verified_unknown", "placeholder_int", "raw_identity", "invented_after", "naive_date"])
def test_forged_receipts_cannot_be_claimed_as_observations(mutation):
    bundle = asyncio.run(collect_evidence(FakeReader()))
    record = bundle.record
    if mutation == "verified_unknown":
        record["unknown"]["hidden_pages"] = "verified"
    elif mutation == "placeholder_int":
        record["receipts"]["apps_user"]["options"]["show_placeholders"] = 1
    elif mutation == "raw_identity":
        record["receipts"]["identity_before"]["data"]["udid"] = "example.raw"
    elif mutation == "invented_after":
        record["source"] = "imported_backup"
    else:
        record["started_at"] = "2026-11-13T12:00:00"
    with pytest.raises(EvidenceError):
        EvidenceBundle.from_record(record)


def test_evidence_save_refuses_backup_extension_and_disguised_original(tmp_path):
    bundle = EvidenceBundle.from_backup(LAYOUT)
    backup = tmp_path / "original.plist"
    backup.write_bytes(plistlib.dumps(LAYOUT, fmt=plistlib.FMT_BINARY))
    original = backup.read_bytes()
    with pytest.raises(EvidenceError):
        bundle.save(backup, replace=True)
    disguised = tmp_path / "original.hsevidence"
    disguised.write_bytes(original)
    with pytest.raises(EvidenceError):
        bundle.save(disguised, replace=True)
    assert backup.read_bytes() == original == disguised.read_bytes()


def test_local_cli_does_not_import_or_instantiate_device_adapter(tmp_path, monkeypatch, capsys):
    import builtins
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        if name == "device" or name.endswith(".device") or name.startswith("pymobiledevice3"):
            raise AssertionError("No device import in offline command")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    raw = tmp_path / "raw.plist"
    raw.write_bytes(plistlib.dumps(LAYOUT, fmt=plistlib.FMT_BINARY))
    output = tmp_path / "out.hsevidence"
    assert evidence_collect.main(["--from-backup", str(raw), "--output", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["can_write"] is False
    assert EvidenceBundle.load(output).source == "imported_backup"
    with pytest.raises(SystemExit):
        evidence_collect.main(["--collect-usb", "--output", str(tmp_path / "usb.hsevidence")])


def test_readonly_adapter_fresh_identity_and_no_metadata_export(monkeypatch):
    from ipsm.device import ReadOnlyEvidenceAdapter
    adapter = ReadOnlyEvidenceAdapter()
    values = {"UniqueDeviceID": "example-phone", "ProductType": "iPhone19,4",
              "ProductVersion": "27.3", "BuildVersion": "first"}
    client = SimpleNamespace(get_value=AsyncMock(side_effect=lambda *, key: values[key]))
    monkeypatch.setattr(adapter, "_ready", AsyncMock(return_value=client))
    before = asyncio.run(adapter.read("identity_before"))
    values["BuildVersion"] = "second"
    after = asyncio.run(adapter.read("identity_after"))
    assert before["build_version"] == "first" and after["build_version"] == "second"
    assert set(before) == set(IDENTITY)
    assert before["device_key"] == sha256(b"examplephone").hexdigest()
    assert "example-phone" not in repr(before)
    assert client.get_value.await_count == 8


def test_readonly_adapter_rejects_unknown_query_before_connection(monkeypatch):
    from ipsm.device import ReadOnlyEvidenceAdapter
    adapter = ReadOnlyEvidenceAdapter()
    ready = AsyncMock(side_effect=AssertionError("No connection"))
    monkeypatch.setattr(adapter, "_ready", ready)
    with pytest.raises(ValueError):
        asyncio.run(adapter.read("anything_else"))
    ready.assert_not_called()


def test_readonly_adapter_requests_minimal_inventory_and_never_filters_bad_entries(monkeypatch):
    from ipsm import device
    adapter = device.ReadOnlyEvidenceAdapter()
    monkeypatch.setattr(adapter, "_ready", AsyncMock(return_value=object()))
    result = {"example.visible": {"CFBundleIdentifier": "example.visible", "ApplicationType": "User",
                                  "DeviceName": "excluded", "Path": "excluded", "IsDemotedApp": True}}
    lookup = AsyncMock(side_effect=lambda _options: result)
    class Proxy:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return SimpleNamespace(lookup=lookup)
        async def __aexit__(self, *args): pass
    monkeypatch.setattr(device, "InstallationProxyService", Proxy)
    captured = asyncio.run(adapter.read("apps_user"))
    assert captured["example.visible"] == {"CFBundleIdentifier": "example.visible", "ApplicationType": "User", "IsDemotedApp": True}
    options = lookup.await_args.args[0]
    assert options["ApplicationType"] == "User" and options["ShowPlaceholders"] is True
    assert options["ReturnAttributes"] == list(adapter._ATTRIBUTES)
    result["broken"] = None
    with pytest.raises(ValueError):
        asyncio.run(adapter.read("apps_user"))


def test_readonly_adapter_never_creates_pairing(monkeypatch, tmp_path):
    from ipsm import device
    monkeypatch.setattr(device, "data_root", lambda: tmp_path)
    monkeypatch.setattr(device.usbmux, "list_devices", AsyncMock(return_value=[SimpleNamespace(serial="example-phone", connection_type="USB")]))
    client = SimpleNamespace(paired=True, close=AsyncMock())
    factory = AsyncMock(return_value=client)
    monkeypatch.setattr(device, "create_using_usbmux", factory)
    adapter = device.ReadOnlyEvidenceAdapter()
    asyncio.run(adapter._ready())
    assert factory.await_args.kwargs["autopair"] is False
    assert factory.await_args.kwargs["connection_type"] == "USB"
    asyncio.run(adapter.close())
    client.close.assert_awaited_once()
