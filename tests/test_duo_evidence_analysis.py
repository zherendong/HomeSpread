"""Synthetic reference formats, inventories and local-only CLI tests."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import plistlib
import socket
import sys

import pytest

from ipsm.evidence import EvidenceBundle, PART_OPTIONS
from research.duo_evidence_analysis import analyze_observations, render_analysis
from scripts.analyze_duo_evidence import main


def app(n, **extra):
    return {"displayIdentifier": f"example.study.{n}", "displayName": f"Private name {n}",
            "unknown": {"flag": True, "bytes": b"secret data"}, **extra}


def standalone(**extra):
    return {"displayIdentifier": "private-widget-id", "iconType": "custom", "elementType": "widget",
            "widgetIdentifier": "example.widget", "gridSize": "medium", **extra}


def snapshot():
    return [[app(0)], [standalone(userSelectedElementIdentifier="private-selection"),
                       {"listType": "folder", "displayName": "Private folder", "iconLists": [[app(2)]]},
                       app(1)]]


def reference(raw):
    return [[[deepcopy(raw[0][0]), False, False, False]], [[False, False, deepcopy(raw[1][2]), False]]]


def inventories():
    return {f"example.study.{n}": {"ApplicationType": "User", "IsDemotedApp": n == 3}
            for n in range(4)}, {"example.hidden": {"ApplicationType": "System", "SBAppTags": ["hidden"]},
                                "example.emptytags": {"SBAppTags": []}, "example.missingtags": {}}


def binary(value):
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY, sort_keys=True)


def completed_bundle(raw=None, *, mutation=None):
    raw = raw or snapshot()
    user, system = inventories()
    now = datetime.now(timezone.utc).isoformat()
    identity = {"device_key": "a" * 64, "product_type": "SyntheticPhone", "ios_version": "test",
                "build_version": "test-build", "transport": "USB"}
    values = {"identity_before": identity, "identity_after": identity, "layout_v2_before": raw,
              "layout_v2_after": raw, "layout_v3": reference(raw), "metrics": {},
              "apps_user": user, "apps_system": system}
    record = {"source": "usb_readonly", "started_at": now, "finished_at": now,
              "source_file_sha256": "", "close_error_code": "",
              "unknown": dict.fromkeys(("geometry", "hidden_pages", "widget_settings", "hidden_webclips"), "unknown"),
              "receipts": {part: {"status": "observed", "data": deepcopy(value), "started_at": now,
                                  "finished_at": now, "error_code": "", "options": deepcopy(PART_OPTIONS[part])}
                           for part, value in values.items()}}
    if mutation:
        mutation(record)
    return EvidenceBundle.from_record(record)


def test_projection_explains_false_without_claiming_coordinates_or_write_safety():
    raw = snapshot()
    report = analyze_observations(raw, format3=reference(raw), apps_user=inventories()[0], apps_system=inventories()[1])
    assert report["format3"]["compact_projection_matches"]
    assert report["format3"]["top_level_apps_exact_order"]
    assert report["format3"]["cell_kinds"] == {"app": 2, "folder": 0, "widget": 0, "false": 6, "other": 0}
    assert report["format3"]["explained_non_app_cells"] == 2
    assert report["format3"]["explained_padding_cells"] == 4
    assert report["folder_app_occurrences"] == 1
    assert not report["format3"]["geometry_verified"] and not report["format3"]["false_means_empty"]
    assert report["can_write"] is report["payload_generated"] is False
    assert report["device_requests"] == 0


@pytest.mark.parametrize("change", ["false_to_zero", "true", "change_content", "remove_page", "extra_row", "move_app"])
def test_projection_rejects_near_matches(change):
    raw = snapshot()
    ref = reference(raw)
    if change == "false_to_zero": ref[0][0][1] = 0
    elif change == "true": ref[0][0][1] = True
    elif change == "change_content": ref[0][0][0]["unknown"]["flag"] = 1
    elif change == "remove_page": ref.pop()
    elif change == "extra_row": ref[0].append([False] * 4)
    elif change == "move_app": ref[0][0][0], ref[1][0][2] = ref[1][0][2], ref[0][0][0]
    report = analyze_observations(raw, format3=ref)
    assert not report["format3"]["compact_projection_matches"]
    assert report["format3"]["explained_padding_cells"] is None


@pytest.mark.parametrize("reference_value", [None, {}, [], [True], [[{}]]])
def test_missing_or_unrecognized_reference_never_claims_empty_geometry(reference_value):
    report = analyze_observations(snapshot(), format3=reference_value)
    assert not report["format3"]["row_shape_recognized"]
    assert not report["format3"]["geometry_verified"]


def test_inventory_counts_do_not_conflate_missing_tags_empty_tags_and_hidden():
    user, system = inventories()
    report = analyze_observations(snapshot(), apps_user=user, apps_system=system)
    inv = report["inventory"]
    assert inv["visible_coverage"] == "pass"
    assert inv["user"]["matched_visible_alias"] == 3
    assert inv["user"]["offloaded_unmatched"] == 1
    assert inv["user"]["tags_absent"] == 4
    assert inv["system"]["unmatched_hidden"] == 1
    assert inv["system"]["unmatched_tags_absent"] == 1
    assert inv["system"]["unmatched_explicit_tags_without_hidden"] == 1
    assert not inv["exclusion_list_complete"]


def test_missing_queries_differ_from_successful_empty_queries():
    missing = analyze_observations(snapshot())["inventory"]
    empty = analyze_observations(snapshot(), apps_user={}, apps_system={})["inventory"]
    assert missing["user"]["status"] == "missing" and missing["visible_coverage"] == "missing"
    assert empty["user"]["status"] == "observed" and empty["visible_coverage"] == "failed"
    assert empty["unmatched_visible_occurrences"] == 3


@pytest.mark.parametrize("value", [False, [], {"x": None}, {"x": {"IsDemotedApp": 1}},
                                   {"x": {"SBAppTags": "hidden"}}, {"x": {"ApplicationType": "System"}},
                                   {"x": {"CFBundleIdentifier": "y"}}])
def test_malformed_or_conflicting_inventory_is_rejected(value):
    with pytest.raises(ValueError):
        analyze_observations(snapshot(), apps_user=value)


@pytest.mark.parametrize("extra,status", [({}, "selected_identifier_missing"),
    ({"userSelectedElementIdentifier": "selected"}, "source_field_available_unverified"),
    ({"userSelectedElementIdentifier": "selected", "uniqueIdentifier": "selected"}, "already_equal"),
    ({"userSelectedElementIdentifier": "selected", "uniqueIdentifier": "other"}, "conflicting_identifiers"),
    ({"userSelectedElementIdentifier": "selected", "uniqueIdentifier": False}, "invalid_unique_identifier")])
def test_widget_alias_assessment_is_field_analysis_and_does_not_patch_input(extra, status):
    raw = [[], [standalone(**extra), app(1)]]
    before = binary(raw)
    widget = analyze_observations(raw)["widgets"][0]
    assert widget["standalone_alias_assessment"] == status
    assert not widget["configuration_verified"]
    assert binary(raw) == before


def test_reports_do_not_expose_private_input_strings_or_mutate_inputs():
    raw = snapshot()
    ref = reference(raw)
    user, system = inventories()
    before = binary([raw, ref, user, system])
    report = analyze_observations(raw, format3=ref, apps_user=user, apps_system=system)
    assert binary([raw, ref, user, system]) == before
    rendered = json.dumps(report) + render_analysis(report)
    for secret in ("example.", "private-selection", "Private name", "Private folder", "secret data", "private-widget-id"):
        assert secret not in rendered


@pytest.mark.parametrize("suffix", [".json", ".txt"])
def test_cli_reads_only_local_bundle_and_roundtrips_private_report(tmp_path, monkeypatch, suffix):
    source = tmp_path / "sample.hsevidence"
    completed_bundle().save(source)
    digest = source.read_bytes()
    def forbidden(*a, **k): raise AssertionError("No device/network operations allowed")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setitem(sys.modules, "ipsm.device", None)
    monkeypatch.setitem(sys.modules, "pymobiledevice3", None)
    target = tmp_path / ("report" + suffix)
    assert main(["--evidence", str(source), "--output", str(target)]) == 0
    assert source.read_bytes() == digest
    assert target.stat().st_mode & 0o777 == 0o600
    assert b"private-selection" not in target.read_bytes()
    assert "ipsm.device" not in {k for k,v in sys.modules.items() if v is not None}


@pytest.mark.parametrize("part", ["layout_v2_after", "identity_after"])
def test_cli_rejects_unstable_observations_before_writing(tmp_path, part):
    def mutate(record):
        data = record["receipts"][part]["data"]
        if part == "layout_v2_after": data[0][0]["displayName"] = "Changed"
        else: data["build_version"] = "Changed"
    source = tmp_path / "unstable.hsevidence"
    completed_bundle(mutation=mutate).save(source)
    target = tmp_path / "report.json"
    assert main(["--evidence", str(source), "--output", str(target)]) == 2
    assert not target.exists()


def test_cli_cannot_overwrite_inputs_or_existing_reports(tmp_path):
    source = tmp_path / "input.hsevidence"
    completed_bundle().save(source)
    existing = tmp_path / "existing.json"
    existing.write_bytes(b"keep")
    with pytest.raises(SystemExit): main(["--evidence", str(source), "--output", str(existing)])
    assert existing.read_bytes() == b"keep"
    with pytest.raises(SystemExit): main(["--evidence", str(source), "--output", str(source)])


def test_cli_does_not_promote_imported_backup_to_device_observation(tmp_path):
    source = tmp_path / "imported.hsevidence"
    EvidenceBundle.from_backup(snapshot()).save(source)
    target = tmp_path / "report.json"
    assert main(["--evidence", str(source), "--output", str(target)]) == 2
    assert not target.exists()
