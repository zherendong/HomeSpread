"""Synthetic envelope-shape tests; no actual inventory, device, or transport."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import plistlib
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.duo_envelope import EvidenceMissing, simulate_dictionary_payload


def sample():
    return [[{"displayIdentifier": "example.dock"}], [
        {"elementType": "widget", "widgetIdentifier": "example.widget", "gridSize": "medium",
         "bundleIdentifier": "example.widget.extension", "iconLists": [],
         "userSelectedElementIdentifier": "example.selection", "opaque": b"\x00\xff",
         "date": datetime(2026, 1, 2, 3, 4, 5, 123456), "enabled": True},
        {"listType": "folder", "displayName": "示例", "iconLists": [[{"displayIdentifier": "example.inside"}]]},
        {"displayIdentifier": "example.app"},
    ]]


def test_backup_alone_never_implies_empty_exclusion_inventory():
    with pytest.raises(EvidenceMissing):
        simulate_dictionary_payload(sample(), excluded_app_ids=None)


def test_envelope_preserves_exact_typed_raw_fields_and_stays_unsendable():
    raw = sample()
    before = plistlib.dumps(raw, fmt=plistlib.FMT_BINARY)
    result = simulate_dictionary_payload(raw, excluded_app_ids=["example.hidden", "example.library"])
    encoded = plistlib.dumps(result.payload, fmt=plistlib.FMT_BINARY)
    decoded = plistlib.loads(encoded)
    assert set(decoded) == {"buttonBar", "iconLists", "ignored"}
    assert decoded["ignored"] == ["example.hidden", "example.library"]
    assert plistlib.dumps([decoded["buttonBar"], *decoded["iconLists"]], fmt=plistlib.FMT_BINARY) == before
    assert plistlib.dumps(raw, fmt=plistlib.FMT_BINARY) == before
    assert not result.can_send


@pytest.mark.parametrize("excluded", [["example.app"], ["example.dock"], ["example.inside"], ["x", "x"], [""], [1], "x"])
def test_ambiguous_or_conflicting_exclusions_are_refused(excluded):
    with pytest.raises(ValueError):
        simulate_dictionary_payload(sample(), excluded_app_ids=excluded)


def test_widget_extension_is_not_mistaken_for_a_visible_app_icon():
    study = simulate_dictionary_payload(sample(), excluded_app_ids=["example.widget.extension"])
    assert study.payload["ignored"] == ["example.widget.extension"]
    assert not study.can_send  # This classification test is not an inventory policy decision.


def test_result_is_detached_from_caller_snapshot():
    raw = sample()
    expected = deepcopy(raw)
    study = simulate_dictionary_payload(raw, excluded_app_ids=[])
    study.payload["iconLists"][0][0]["opaque"] = b"changed"
    study.payload["buttonBar"].clear()
    assert raw == expected
    assert not study.can_send
