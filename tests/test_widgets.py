"""Widget preview fixtures are synthetic; no device identifiers or app inventory."""
import copy
import plistlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ipsm.iconstate import IconState, ItemKind, compare_after_write, parse_item
from ipsm.layout import Grid, LayoutDocument, LayoutError
from ipsm.placement import place_items


def app(number):
    return {"displayIdentifier": f"example.preview.app{number}", "displayName": f"App {number}"}


def widget(size="medium", members=0):
    raw = {
        "displayIdentifier": "example.preview.widget-position",
        "iconType": "custom", "gridSize": size, "iconLists": [],
        "allowsSuggestions": True, "futureMetadata": {"payload": b"keep this exactly"},
    }
    if members:
        raw["elements"] = [
            {"elementType": "widget", "widgetIdentifier": f"example.preview.member{index}",
             "uniqueIdentifier": f"synthetic-member-{index}"}
            for index in range(members)
        ]
        raw["userSelectedElementIdentifier"] = "synthetic-member-2"
    else:
        raw.update(elementType="widget", widgetIdentifier="example.preview.single")
    return raw


@pytest.mark.parametrize("members", [0, 7])
def test_widgets_with_icon_lists_are_never_folders(members):
    raw = widget(members=members)
    item = parse_item(raw)
    assert item.kind is ItemKind.WIDGET
    assert not item.movable
    assert item.children == []
    doc = LayoutDocument([[], [raw, app(1)]], Grid())
    node = doc.pages[0].items[0]
    assert node.is_widget and not node.is_folder and not node.movable
    assert node.widget_span == (4, 2)
    assert node.widget_member_count == (members or 1)
    assert node.identifier not in node.label


def test_widget_counts_do_not_count_stack_members_as_apps_or_folders():
    raw = [[], [widget(members=7), widget("small"), app(1),
                {"listType": "folder", "displayName": "Folder", "iconLists": [[app(2)]]}]]
    parsed = IconState.parse(raw)
    assert parsed.counts() == {"app": 2, "folder": 1, "widget": 2, "unknown": 0, "empty": 0}
    assert parsed.bundle_ids() == {"example.preview.app1", "example.preview.app2"}


def test_all_widget_metadata_survives_parse_preview_and_serialization():
    raw = [[app(0)], [widget(members=7), app(1)], [widget("small")]]
    original = copy.deepcopy(raw)
    doc = LayoutDocument(raw, Grid())
    for page in doc.pages:
        assert place_items(page.items, 4, 6).complete
    assert doc.verify_identity() and doc.to_state() == original and raw == original
    assert plistlib.dumps(doc.to_state(), fmt=plistlib.FMT_BINARY) == plistlib.dumps(original, fmt=plistlib.FMT_BINARY)
    exported = doc.to_state()
    exported[1][0]["futureMetadata"]["payload"] = b"changed outside document"
    assert doc.to_state() == original


@pytest.mark.parametrize("opaque", [None, {"iconLists": []}, {"displayIdentifier": "future", "iconType": "future-shape"}, {"unrecognized": True}])
def test_unsupported_shapes_are_not_reclassified_as_editable_apps(opaque):
    expected = ItemKind.EMPTY if opaque is None else ItemKind.UNKNOWN
    assert parse_item(opaque).kind is expected
    doc = LayoutDocument([[], [opaque, app(1)]], Grid())
    assert doc.readonly_reason and doc.to_state() == doc.origin
    assert doc.can_move(doc.pages[0].items[1].uid, doc.dock.uid, 0)


def test_whole_widget_layout_rejects_neighbor_and_page_edits():
    raw = [[], [widget(), app(1), app(2),
                {"listType": "folder", "displayName": "Folder", "iconLists": [[app(3)]]}], []]
    doc = LayoutDocument(raw, Grid())
    one, two, folder = doc.pages[0].items[1:]
    operations = [
        lambda: doc.move(one.uid, doc.dock.uid, 0),
        lambda: doc.group([one.uid, two.uid], "New"),
        lambda: doc.rename_folder(folder.uid, "Changed"),
        lambda: doc.reorder_pages(0, 1),
        doc.add_page,
        lambda: doc.remove_page(1),
        doc.undo,
        doc.redo,
    ]
    for operation in operations:
        with pytest.raises(LayoutError):
            operation()
        assert doc.to_state() == raw and not doc.dirty


@pytest.mark.parametrize("app_count,occupied", [(8, 16), (16, 24)])
def test_medium_widget_reserves_two_full_rows(app_count, occupied):
    entries = [widget(members=7)] + [app(index) for index in range(app_count)]
    result = place_items(entries, 4, 6)
    assert result.complete and result.occupied_cells == occupied
    assert (result.cells[0].row, result.cells[0].column, result.cells[0].width, result.cells[0].height) == (0, 0, 4, 2)
    assert (result.cells[1].row, result.cells[1].column) == (2, 0)
    assert [cell.index for cell in result.cells] == list(range(len(entries)))


def test_small_widget_and_neighbor_cells_never_overlap():
    entries = [app(index) for index in range(10)] + [widget("small")] + [app(index) for index in range(10, 18)]
    result = place_items(entries, 4, 6)
    assert result.complete and result.occupied_cells == 22
    cell = result.cells[10]
    assert (cell.row, cell.column, cell.width, cell.height) == (2, 2, 2, 2)
    actual = [(r, c) for p in result.cells for r in range(p.row, p.row+p.height) for c in range(p.column, p.column+p.width)]
    assert len(set(actual)) == len(actual)


def test_unknown_widget_size_does_not_guess_positions_after_it():
    result = place_items([app(0), widget("futureSize"), app(1)], 4, 6)
    assert not result.complete and result.unsupported_indices == (1, 2)
    assert [cell.index for cell in result.cells] == [0]


def test_overflow_is_reported_without_losing_raw_indices():
    result = place_items([widget()] + [app(index) for index in range(18)], 4, 6)
    assert not result.complete and result.occupied_cells == 24
    assert result.overflow_indices == (17, 18)
    assert len(result.cells) == 17


@pytest.mark.parametrize("dimensions", [(0, 6), (4, -1), (100, 100), (True, 6)])
def test_invalid_grid_does_not_invent_a_preview(dimensions):
    result = place_items([app(0)], *dimensions)
    assert not result.complete and result.error == "invalid_grid"
    assert result.cells == ()


def test_widget_payload_comparison_preserves_icon_lists_and_stack_members():
    before = [[], [widget(members=7)]]
    for mutate in (
        lambda item: item["iconLists"].append([app(0)]),
        lambda item: item["elements"].reverse(),
        lambda item: item["futureMetadata"].update(payload=b"changed"),
    ):
        after = copy.deepcopy(before)
        mutate(after[1][0])
        result = compare_after_write(before, after)
        assert not result.safe and result.changed
