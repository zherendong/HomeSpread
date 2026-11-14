"""Independent synthetic checks; no personal observations or device calls."""
from __future__ import annotations

import builtins
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import plistlib
import socket
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.duo_evidence_analysis import analyze_observations, render_analysis


def app(number):
    return {"displayIdentifier": f"SENSITIVE-ID-{number}",
            "bundleIdentifier": f"SENSITIVE-ID-{number}",
            "displayName": f"SENSITIVE-NAME-{number}",
            "iconModDate": datetime(2026, 1, 2, 3, 4, 5, 123456),
            "opaque": {"flag": True, "blob": b"SENSITIVE-BLOB"}}


def sample():
    standalone = {"displayIdentifier": "SENSITIVE-WIDGET-ID", "iconType": "custom",
                  "elementType": "widget", "widgetIdentifier": "SENSITIVE-EXTENSION-ID",
                  "gridSize": "small", "iconLists": [],
                  "userSelectedElementIdentifier": "SENSITIVE-SELECTED-ID"}
    stack = {"displayIdentifier": "SENSITIVE-STACK-ID", "iconType": "custom",
             "gridSize": "small", "iconLists": [],
             "elements": [{"elementType": "widget", "widgetIdentifier": f"SENSITIVE-EXT-{i}",
                           "uniqueIdentifier": f"SENSITIVE-MEMBER-{i}"} for i in range(2)],
             "userSelectedElementIdentifier": "SENSITIVE-MEMBER-1"}
    folder = {"listType": "folder", "displayName": "SENSITIVE-FOLDER-NAME",
              "iconLists": [[app(4), app(5)]]}
    raw = [[app(0)], [standalone, folder, app(1), app(2)], [stack, app(3)]]
    reference = [[[app(0), False, False, False]],
                 [[False, False, app(1), app(2)]],
                 [[False, app(3), False, False]]]
    return raw, reference


def binary(value):
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY, sort_keys=True)


def test_lossy_reference_never_claims_complete_layout_or_geometry():
    raw, reference = sample()
    report = analyze_observations(raw, format3=reference)
    assert report["counts"] == {"apps": 6, "folders": 1, "widget_blocks": 2, "widget_members": 3}
    assert report["top_level_apps"] == 4 and report["folder_app_occurrences"] == 2
    ref = report["format3"]
    assert ref["compact_projection_matches"] is True
    assert ref["explained_non_app_cells"] == 3 and ref["explained_padding_cells"] == 5
    assert ref["geometry_verified"] is False and ref["false_means_empty"] is False
    assert report["can_write"] is False and report["payload_generated"] is False
    assert report["inventory"]["exclusion_list_complete"] is False


@pytest.mark.parametrize("replacement", [0, 0.0, True, None, "", b""])
def test_false_placeholder_cannot_be_replaced_by_equal_or_empty_values(replacement):
    raw, reference = sample()
    reference[1][0][0] = replacement
    ref = analyze_observations(raw, format3=reference)["format3"]
    assert ref["compact_projection_matches"] is False
    assert ref["cell_kinds"]["other"] == 1
    assert ref["explained_non_app_cells"] is None and ref["explained_padding_cells"] is None


@pytest.mark.parametrize("mutation", ["bool_to_int", "date", "blob", "name", "extra_field"])
def test_full_app_payload_changes_are_not_hidden_by_identifier_matching(mutation):
    raw, reference = sample()
    item = reference[1][0][2]
    if mutation == "bool_to_int": item["opaque"]["flag"] = 1
    elif mutation == "date": item["iconModDate"] = item["iconModDate"].replace(microsecond=0)
    elif mutation == "blob": item["opaque"]["blob"] = b"different"
    elif mutation == "name": item["displayName"] = "Changed"
    else: item["futureField"] = "different"
    ref = analyze_observations(raw, format3=reference)["format3"]
    assert not ref["top_level_apps_exact_order"] and not ref["compact_projection_matches"]


@pytest.mark.parametrize("mutation", ["same_page_order", "cross_page", "extra_page", "lost_app", "duplicate_app"])
def test_page_and_occurrence_changes_are_detected(mutation):
    raw, reference = sample()
    if mutation == "same_page_order": reference[1][0][2], reference[1][0][3] = reference[1][0][3], reference[1][0][2]
    elif mutation == "cross_page": reference[1][0][2], reference[2][0][1] = reference[2][0][1], reference[1][0][2]
    elif mutation == "extra_page": reference.append([])
    elif mutation == "lost_app": reference[1][0][2] = False
    else: reference[1][0][3] = deepcopy(reference[1][0][2])
    ref = analyze_observations(raw, format3=reference)["format3"]
    assert not ref["top_level_apps_exact_order"] and not ref["compact_projection_matches"]


def test_row_lengths_and_positions_cannot_be_discarded_for_a_projection_match():
    raw, reference = sample()
    reference[1] = [reference[1][0][:2], reference[1][0][2:]]
    ref = analyze_observations(raw, format3=reference)["format3"]
    assert ref["top_level_apps_exact_order"] is True
    assert ref["all_rows_four_cells"] is False and ref["compact_projection_matches"] is False


@pytest.mark.parametrize("reference", [None, {}, [None], [[False]], "SENSITIVE-RAW"])
def test_unrecognized_reference_never_enables_geometry(reference):
    raw, _ = sample()
    ref = analyze_observations(raw, format3=reference)["format3"]
    assert ref["row_shape_recognized"] is False and ref["geometry_verified"] is False
    assert ref["compact_projection_matches"] is False


@pytest.mark.parametrize("marker,value", [("iconType", "custom"), ("iconType", "future-kind"),
                                         ("webClipIdentifier", "SENSITIVE-WEBCLIP-ID"),
                                         ("isWebClip", True), ("isWebApp", True)])
def test_reference_unknown_or_webclip_item_is_not_counted_as_ordinary_app(marker, value):
    raw, reference = sample()
    reference[0][0][1] = {"displayIdentifier": "SENSITIVE-UNCLASSIFIED-ID", marker: value}
    ref = analyze_observations(raw, format3=reference)["format3"]
    assert ref["cell_kinds"]["app"] == 4
    assert ref["cell_kinds"]["other"] == 1
    assert ref["compact_projection_matches"] is False


def test_missing_tags_and_explicit_empty_tags_remain_distinct():
    raw, reference = sample()
    user = {"SENSITIVE-MISSING": {"IsDemotedApp": True},
            "SENSITIVE-EMPTY": {"SBAppTags": [], "IsDemotedApp": False},
            "SENSITIVE-HIDDEN": {"SBAppTags": ["hidden"], "IsDemotedApp": True}}
    report = analyze_observations(raw, format3=reference, apps_user=user, apps_system={})
    inv = report["inventory"]["user"]
    assert inv["unmatched_tags_absent"] == 1
    assert inv["unmatched_explicit_tags_without_hidden"] == 1
    assert inv["unmatched_hidden"] == 1
    assert inv["offloaded_unmatched"] == 2
    assert report["inventory"]["visible_coverage"] == "failed"
    assert report["inventory"]["exclusion_list_complete"] is False


def test_unobserved_and_successfully_empty_inventories_differ():
    raw, _ = sample()
    missing = analyze_observations(raw)["inventory"]
    empty = analyze_observations(raw, apps_user={}, apps_system={})["inventory"]
    assert missing["user"]["status"] == "missing" and missing["visible_coverage"] == "missing"
    assert empty["user"]["status"] == "observed" and empty["visible_coverage"] == "failed"
    assert empty["unmatched_visible_occurrences"] == 6


def test_two_known_aliases_or_overlapping_queries_do_not_prove_coverage():
    raw, _ = sample()
    raw[0][0]["bundleIdentifier"] = "SENSITIVE-ALTERNATE-ID"
    users = {f"SENSITIVE-ID-{i}": {} for i in range(6)}
    report = analyze_observations(raw, apps_user=users, apps_system={"SENSITIVE-ALTERNATE-ID": {}})
    assert report["inventory"]["ambiguous_visible_occurrences"] == 1
    assert report["inventory"]["visible_coverage"] == "failed"
    report = analyze_observations(raw, apps_user=users, apps_system={"SENSITIVE-ID-1": {}})
    assert report["inventory"]["query_overlap"] == 1
    assert report["inventory"]["visible_coverage"] == "failed"


@pytest.mark.parametrize("value", [1, 0, "true", None])
def test_invalid_placeholder_flags_cannot_be_treated_as_false(value):
    raw, _ = sample()
    with pytest.raises(ValueError):
        analyze_observations(raw, apps_user={"SENSITIVE-ID-1": {"IsDemotedApp": value}})


def test_inputs_preserved_output_detached_and_no_private_values_exported():
    raw, reference = sample()
    user = {"SENSITIVE-ID-0": {"CFBundleDisplayName": "SENSITIVE-INVENTORY-NAME",
                               "opaque": {"secret": "SENSITIVE-INVENTORY-EXTRA"}}}
    before = binary([raw, reference, user])
    report = analyze_observations(raw, format3=reference, apps_user=user, apps_system={})
    assert binary([raw, reference, user]) == before
    assert "SENSITIVE" not in json.dumps(report)
    assert "SENSITIVE" not in render_analysis(report)
    report["widgets"][0]["size"] = "changed-output"
    report["counts"]["apps"] = 999
    assert binary([raw, reference, user]) == before


def test_analysis_has_no_file_network_or_device_effects(monkeypatch):
    raw, reference = sample()
    original_import = builtins.__import__
    def checked_import(name, *args, **kwargs):
        assert not name.startswith(("ipsm.device", "pymobiledevice3")), name
        return original_import(name, *args, **kwargs)
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline analysis attempted external access")
    monkeypatch.setattr(builtins, "__import__", checked_import)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    report = analyze_observations(raw, format3=reference, apps_user={}, apps_system={})
    assert report["device_requests"] == 0
    assert "不连接手机" in render_analysis(report)


def test_missing_standalone_ids_and_stack_ids_are_not_interchangeable():
    raw, _ = sample()
    original = binary(raw)
    standalone, stack = analyze_observations(raw)["widgets"]
    assert standalone["standalone_alias_assessment"] == "source_field_available_unverified"
    assert standalone["configuration_verified"] is False
    assert stack["standalone_alias_assessment"] == "not_applicable_stack"
    assert stack["selected_member_matches"] == 1
    assert binary(raw) == original
    del raw[1][0]["userSelectedElementIdentifier"]
    missing = analyze_observations(raw)["widgets"][0]
    assert missing["standalone_alias_assessment"] == "selected_identifier_missing"


def test_cli_load_failure_stops_without_writing_or_echoing_private_exception(tmp_path, monkeypatch, capsys):
    import scripts.analyze_duo_evidence as cli
    def fail_load(path):
        raise ValueError("SENSITIVE-PRIVATE-DATA in invalid source")
    def must_not_write(*args, **kwargs):
        raise AssertionError("Failed load must not continue to report save")
    monkeypatch.setattr(cli.EvidenceBundle, "load", fail_load)
    monkeypatch.setattr(cli, "atomic_private_write", must_not_write)
    target = tmp_path / "report.json"
    assert cli.main(["--evidence", str(tmp_path / "input.hsevidence"), "--output", str(target)]) == 2
    output = capsys.readouterr().out
    assert "SENSITIVE" not in output
    assert json.loads(output)["status"] == "stopped"
    assert not target.exists()


def test_cli_save_failure_is_not_retried_and_private_error_is_not_echoed(tmp_path, monkeypatch, capsys):
    import scripts.analyze_duo_evidence as cli
    raw, reference = sample()
    values = {"layout_v2_before": raw, "layout_v2_after": raw,
              "identity_before": {"identity": "SENSITIVE-IDENTITY"},
              "identity_after": {"identity": "SENSITIVE-IDENTITY"},
              "layout_v3": reference, "apps_user": {}, "apps_system": {}}
    class ValidatedObservation:
        collection_succeeded = True
        source = "usb_readonly"
        record = {"started_at": "2026-01-02T00:00:00+00:00", "finished_at": "2026-01-02T00:00:01+00:00"}
        def data(self, part): return values[part]
    monkeypatch.setattr(cli.EvidenceBundle, "load", lambda path: ValidatedObservation())
    attempts = []
    def fail_write(*args, **kwargs):
        attempts.append(1)
        raise OSError("SENSITIVE-PRIVATE-PATH could not be written")
    monkeypatch.setattr(cli, "atomic_private_write", fail_write)
    target = tmp_path / "report.json"
    assert cli.main(["--evidence", str(tmp_path / "input.hsevidence"), "--output", str(target)]) == 2
    output = capsys.readouterr().out
    assert "SENSITIVE" not in output and len(attempts) == 1
    assert json.loads(output)["status"] == "stopped"
    assert not target.exists()
