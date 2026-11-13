"""Synthetic offline experiments; no personal layout or device transport imports."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import plistlib
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.duo_planner import DraftError, analyze_layout, plan_swap, validate_swap


def app(index, *, installed=True):
    result = {
        "displayIdentifier": f"example.research.app{index}",
        "displayName": f"Synthetic App {index}",
        "opaqueFutureField": {"blob": b"\x00\xff\x01", "flag": True, "integer": 1},
        "iconModDate": datetime(2026, 1, 1, 2, 3, 4, 56789),
    }
    if installed:
        result["bundleIdentifier"] = result["displayIdentifier"]
        result["bundleVersion"] = "1.2.3"
    return result


def widget(size="medium", members=0):
    result = {
        "displayIdentifier": f"example.research.widget-{size}-{members}",
        "iconType": "custom", "gridSize": size, "iconLists": [],
        "allowsSuggestions": False, "allowsExternalSuggestions": True,
        "opaqueWidgetData": {"bytes": b"\x10\x00", "date": datetime(2026, 1, 1)},
    }
    if members:
        result["elements"] = [
            {"elementType": "widget", "widgetIdentifier": f"example.research.member{number}",
             "uniqueIdentifier": f"synthetic-member-{number}",
             "futureMemberData": {"number": number, "bytes": b"member"}}
            for number in range(members)
        ]
        result["userSelectedElementIdentifier"] = "synthetic-member-2"
    else:
        result.update(elementType="widget", widgetIdentifier="example.research.standalone")
    return result


def folder():
    return {"listType": "folder", "displayName": "Synthetic Folder",
            "iconLists": [[app(90), app(91, installed=False)]], "futureFolderData": b"opaque"}


def snapshot():
    return [
        [app(100), app(101), app(102)],
        [widget(members=7)] + [app(number) for number in range(8)],
        [widget()] + [app(number) for number in range(10, 26)],
        [widget("small"), folder(), app(30, installed=False), app(31)],
    ]


def binary(value):
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY, sort_keys=True)


def test_analysis_counts_and_modeled_footprints_are_explicit():
    raw = snapshot()
    before = binary(raw)
    result = analyze_layout(raw)
    assert result["counts"] == {"apps": 31, "folders": 1, "widget_blocks": 3, "widget_members": 9}
    assert result["home_page_count"] == 3 and result["dock_item_count"] == 3
    assert [page["occupied_cells"] for page in result["pages"]] == [16, 24, 7]
    assert result["pages"][0]["candidate_indices"] == list(range(1, 9))
    assert result["pages"][0]["placements"][1] == {
        "index": 1, "row": 2, "column": 0, "width": 1, "height": 1, "kind": "app"}
    assert result["device_write_supported"] is False
    assert result["geometry_evidence"] == "modeled_not_device_verified"
    # The report may be public; it must not contain app or widget identifiers.
    assert "example.research" not in json.dumps(result)
    assert binary(raw) == before


def test_swap_preserves_every_other_slot_and_all_nested_opaque_data():
    raw = snapshot()
    before = binary(raw)
    candidate = plan_swap(raw, 2, 1, 16)
    verdict = validate_swap(raw, candidate, 2, 1, 16)
    assert verdict["changed_paths"] == [[2, 1], [2, 16]]
    assert verdict["valid"] and verdict["device_write_supported"] is False
    assert binary(candidate[2][1]) == binary(raw[2][16])
    assert binary(candidate[2][16]) == binary(raw[2][1])
    for p, items in enumerate(raw):
        for index, item in enumerate(items):
            if (p, index) not in {(2, 1), (2, 16)}:
                assert binary(candidate[p][index]) == binary(item)
    assert binary(raw) == before
    assert binary(plistlib.loads(binary(candidate))) == binary(candidate)
    candidate[1][0]["elements"][0]["futureMemberData"]["bytes"] = b"changed externally"
    assert binary(raw) == before


def test_all_enumerated_pairs_validate_and_swap_back_exactly():
    raw = snapshot()
    before = binary(raw)
    result = analyze_layout(raw)
    attempted = 0
    for page in result["pages"]:
        for left, right in page["candidate_pairs"]:
            candidate = plan_swap(raw, page["page"], left, right)
            validate_swap(raw, candidate, page["page"], left, right)
            restored = plan_swap(candidate, page["page"], left, right)
            assert binary(restored) == before
            attempted += 1
    assert attempted == 149  # C(8,2) + C(16,2) + C(2,2).


@pytest.mark.parametrize("intent", [
    (0, 0, 1), (-1, 0, 1), (4, 0, 1), (True, 1, 2),
    (1, -1, 2), (1, 1, 99), (1, True, 2), (1, (1, 1), (2, 2)),
    (1, 1, 1), (1, 0, 1), (3, 1, 2),
])
def test_only_two_ordinary_app_occurrences_on_one_non_dock_page_are_accepted(intent):
    raw = snapshot()
    before = binary(raw)
    with pytest.raises(DraftError):
        plan_swap(raw, *intent)
    assert binary(raw) == before


@pytest.mark.parametrize("bad", [None, "legacy.app", {}, {"displayIdentifier": "unknown", "iconType": "future"},
                                  {"displayIdentifier": "spacer", "gridSize": "small"},
                                  {"iconLists": []}, {"displayIdentifier": 123},
                                  {"displayIdentifier": "web", "webClipURL": "https://example.invalid"}])
def test_unknown_empty_legacy_and_webclip_items_block_the_entire_experiment(bad):
    raw = snapshot()
    raw.append([bad])
    with pytest.raises(DraftError):
        plan_swap(raw, 1, 1, 2)


@pytest.mark.parametrize("size", ["extraLarge", "future", None, 2, [2, 2]])
def test_unknown_widget_spans_are_not_guessed(size):
    raw = snapshot()
    raw[1][0]["gridSize"] = size
    with pytest.raises(DraftError) as error:
        analyze_layout(raw)
    assert error.value.code == "unsupported_span"


def test_page_and_folder_overflow_are_rejected():
    raw = snapshot()
    raw[2].append(app(500))
    with pytest.raises(DraftError) as error:
        analyze_layout(raw)
    assert error.value.code == "overflow"
    raw = snapshot()
    raw[3][1]["iconLists"][0] = [app(index) for index in range(10)]
    with pytest.raises(DraftError):
        analyze_layout(raw)


@pytest.mark.parametrize("mutation", [
    lambda item: item["elements"].__setitem__(1, deepcopy(item["elements"][0])),
    lambda item: item.update(userSelectedElementIdentifier="absent"),
    lambda item: item["elements"][0].update(elementType="unknown"),
    lambda item: item.update(iconLists=[[app(80)]]),
    lambda item: item.update(listType="folder"),
])
def test_malformed_or_ambiguous_stacks_are_rejected(mutation):
    raw = snapshot()
    mutation(raw[1][0])
    with pytest.raises(DraftError):
        analyze_layout(raw)


@pytest.mark.parametrize("mutation", [
    lambda value: value[0].reverse(),
    lambda value: value[3][1].update(displayName="Renamed"),
    lambda value: value[3][1]["iconLists"][0].reverse(),
    lambda value: value[1][0].update(allowsSuggestions=True),
    lambda value: value[1][0].update(userSelectedElementIdentifier="synthetic-member-3"),
    lambda value: value[1][0]["elements"].reverse(),
    lambda value: value[1][0]["opaqueWidgetData"].update(bytes=b"forged"),
    lambda value: value[2][1]["opaqueFutureField"].update(flag=1),
    lambda value: value[2][2].update(iconModDate=datetime(2026, 1, 1)),
    lambda value: value[2].pop(),
    lambda value: value[2].append(app(999)),
    lambda value: value.append([]),
])
def test_independent_validator_rejects_extra_mutations_including_bool_int_changes(mutation):
    raw = snapshot()
    candidate = plan_swap(raw, 2, 1, 2)
    mutation(candidate)
    with pytest.raises(DraftError):
        validate_swap(raw, candidate, 2, 1, 2)


def test_noop_payloads_are_rejected_but_duplicate_identifiers_are_occurrence_safe():
    repeated = app(1)
    raw = [[], [deepcopy(repeated), deepcopy(repeated), app(2)]]
    analysis = analyze_layout(raw)
    assert analysis["pages"][0]["candidate_pairs"] == [[0, 2], [1, 2]]
    with pytest.raises(DraftError) as error:
        plan_swap(raw, 1, 0, 1)
    assert error.value.code == "no_op"
    raw[1][1]["opaqueFutureField"]["integer"] = 2
    candidate = plan_swap(raw, 1, 0, 1)
    assert candidate[1][0]["displayIdentifier"] == candidate[1][1]["displayIdentifier"]
    assert candidate[1][0]["opaqueFutureField"]["integer"] == 2
    assert candidate[1][1]["opaqueFutureField"]["integer"] == 1
    assert validate_swap(raw, candidate, 1, 0, 1)["changed_paths"] == [[1, 0], [1, 1]]


def test_wrong_occurrence_cannot_be_hidden_by_equal_app_identifiers():
    raw = [[], [app(1), app(1), app(2)]]
    candidate = plan_swap(raw, 1, 1, 2)
    with pytest.raises(DraftError):
        validate_swap(raw, candidate, 1, 0, 2)


@pytest.mark.parametrize("raw", [{"buttonBar": [], "iconLists": []}, [], [[]], [[], {}],
                                  [[app(i) for i in range(5)], [app(1), app(2)]],
                                  [[], [folder(), {"listType": "folder", "iconLists": [[]]}]]])
def test_unsupported_top_level_and_container_shapes_are_rejected(raw):
    with pytest.raises(DraftError):
        analyze_layout(raw)


def test_non_plist_and_cyclic_opaque_metadata_fail_closed():
    for opaque in ({1, 2}, (1, 2), object()):
        raw = [[], [app(1), app(2)]]
        raw[1][0]["opaqueFutureField"] = opaque
        with pytest.raises(DraftError):
            analyze_layout(raw)
    raw = [[], [app(1), app(2)]]
    raw[1][0]["cycle"] = raw
    with pytest.raises(DraftError):
        analyze_layout(raw)
