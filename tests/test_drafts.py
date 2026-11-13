"""Offline draft workflow tests using fabricated apps and widget data."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import plistlib
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ipsm.draft_rules import DraftError
from ipsm.drafts import OfflineDraft, Swap
from ipsm import drafts


def app(index):
    return {"displayIdentifier": f"example.draft.app{index}", "displayName": f"App {index}",
            "iconModDate": datetime(2026, 1, 2, 3, 4, 5, 987654),
            "futureField": {"opaque": b"\x00\xff\x01", "enabled": True, "number": 1}}


def snapshot():
    stack = {"iconType": "custom", "displayIdentifier": "example.draft.stack",
             "gridSize": "medium", "iconLists": [], "allowsSuggestions": False,
             "userSelectedElementIdentifier": "example-member-1",
             "elements": [{"elementType": "widget", "widgetIdentifier": f"example.widget{i}",
                           "uniqueIdentifier": f"example-member-{i}", "opaque": b"\x00\x80"}
                          for i in range(3)]}
    folder = {"listType": "folder", "displayName": "示例文件夹", "iconLists": [[app(6)]]}
    return [[app(9)], [stack, app(1), app(2), app(3), folder], [app(4), app(5)]]


def binary(value):
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY)


def test_snapshot_access_is_detached_from_caller_and_other_snapshots():
    original = snapshot()
    before = binary(original)
    draft = OfflineDraft(original)
    original[1][0]["elements"].clear()
    first = draft.origin
    first[1][1]["futureField"]["opaque"] = b"changed"
    current = draft.current_state
    current[0].clear()
    assert binary(draft.origin) == before
    assert binary(draft.current) == before
    assert not draft.device_write_allowed


def test_swap_and_final_diff_preserve_widgets_folder_and_dock():
    raw = snapshot()
    draft = OfflineDraft(raw)
    draft.swap(1, 1, 2)
    assert draft.operations == (Swap(1, 1, 2),)
    assert [(c.page, c.index, c.before_label, c.after_label) for c in draft.diff()] == [
        (1, 1, "App 1", "App 2"), (1, 2, "App 2", "App 1")]
    assert binary(draft.current[1][0]) == binary(raw[1][0])
    assert binary(draft.current[1][4]) == binary(raw[1][4])
    assert binary(draft.current[0]) == binary(raw[0])
    assert binary(draft.current[2]) == binary(raw[2])
    assert draft.has_changes and draft.dirty


def test_multiple_swaps_undo_redo_and_saved_state_tracking(tmp_path):
    draft = OfflineDraft(snapshot())
    baseline = binary(draft.current)
    assert not draft.undo() and not draft.redo()
    draft.swap(1, 1, 2)
    first = binary(draft.current)
    draft.save(tmp_path / "first.hsdraft")
    assert not draft.dirty
    draft.swap(1, 2, 3)
    second = binary(draft.current)
    assert draft.dirty and draft.can_undo and not draft.can_redo
    assert draft.undo() and binary(draft.current) == first and not draft.dirty
    assert draft.undo() and binary(draft.current) == baseline and draft.dirty
    assert draft.redo() and binary(draft.current) == first and not draft.dirty
    assert draft.redo() and binary(draft.current) == second and draft.dirty


def test_invalid_new_swap_does_not_destroy_redo_history():
    draft = OfflineDraft(snapshot())
    draft.swap(1, 1, 2)
    swapped = binary(draft.current)
    draft.undo()
    with pytest.raises(DraftError):
        draft.swap(1, 0, 1)  # A widget must not become an endpoint.
    assert draft.can_redo and not draft.can_undo
    draft.redo()
    assert binary(draft.current) == swapped


def test_valid_branch_replaces_only_redo_tail():
    draft = OfflineDraft(snapshot())
    draft.swap(1, 1, 2)
    draft.swap(1, 2, 3)
    draft.undo()
    draft.swap(2, 0, 1)
    assert draft.operations == (Swap(1, 1, 2), Swap(2, 0, 1))
    assert not draft.can_redo
    assert draft.current[1][1]["displayName"] == "App 2"
    assert draft.current[2][0]["displayName"] == "App 5"


def test_inverse_operation_has_history_but_no_final_changes():
    draft = OfflineDraft(snapshot())
    draft.swap(1, 1, 2)
    draft.swap(1, 1, 2)
    assert draft.can_undo and len(draft.operations) == 2
    assert not draft.has_changes and not draft.dirty
    assert draft.diff() == ()


def test_save_reopen_replays_history_and_can_undo(tmp_path):
    draft = OfflineDraft(snapshot())
    draft.swap(1, 1, 2)
    draft.swap(2, 0, 1)
    path = tmp_path / "计划.hsdraft"
    assert draft.save(path) == path
    loaded = OfflineDraft.load(path)
    assert loaded.path == path
    assert not loaded.dirty and loaded.has_changes
    assert loaded.operations == draft.operations
    assert binary(loaded.origin) == binary(draft.origin)
    assert binary(loaded.current) == binary(draft.current)
    assert loaded.undo() and loaded.undo()
    assert binary(loaded.current) == binary(draft.origin)


def test_save_persists_active_history_without_discarding_in_memory_redo(tmp_path):
    draft = OfflineDraft(snapshot())
    draft.swap(1, 1, 2)
    draft.swap(2, 0, 1)
    draft.undo()
    path = tmp_path / "active.hsdraft"
    draft.save(path)
    assert draft.can_redo
    loaded = OfflineDraft.load(path)
    assert loaded.operations == (Swap(1, 1, 2),)
    assert loaded.can_undo and not loaded.can_redo
    assert binary(loaded.current) == binary(draft.current)


def test_unswapped_draft_can_be_saved_and_reopened(tmp_path):
    draft = OfflineDraft(snapshot())
    path = tmp_path / "baseline.hsdraft"
    draft.save(path)
    loaded = OfflineDraft.load(path)
    assert not loaded.has_changes and not loaded.dirty
    assert not loaded.can_undo and not loaded.can_redo
    assert binary(loaded.origin) == binary(snapshot())


def test_explicit_replace_of_valid_draft_updates_saved_marker(tmp_path):
    draft = OfflineDraft(snapshot())
    path = tmp_path / "plan.hsdraft"
    draft.save(path)
    draft.swap(1, 1, 2)
    previous = path.read_bytes()
    with pytest.raises(DraftError):
        draft.save(path)
    assert path.read_bytes() == previous and draft.dirty
    draft.save(path, replace=True)
    assert not draft.dirty
    assert OfflineDraft.load(path).operations == (Swap(1, 1, 2),)


def test_original_backup_not_replaced_even_if_renamed_as_draft(tmp_path):
    original = binary(snapshot())
    plist_path = tmp_path / "original.plist"
    disguised = tmp_path / "original.hsdraft"
    plist_path.write_bytes(original)
    disguised.write_bytes(original)
    draft = OfflineDraft(snapshot())
    draft.swap(1, 1, 2)
    for path in (plist_path, disguised):
        with pytest.raises(DraftError):
            draft.save(path, replace=True)
        assert path.read_bytes() == original
    assert draft.path is None and draft.dirty


def test_snapshot_memory_limit_refuses_without_losing_current_state(monkeypatch):
    draft = OfflineDraft(snapshot())
    before = binary(draft.current)
    monkeypatch.setattr(drafts, "MAX_HISTORY_BYTES", len(before) + 10)
    with pytest.raises(DraftError) as exc:
        draft.swap(1, 1, 2)
    assert exc.value.code == "draft_history_limit"
    assert binary(draft.current) == before
    assert not draft.can_undo and not draft.dirty


def test_saved_history_memory_budget_is_checked_before_replay(tmp_path, monkeypatch):
    draft = OfflineDraft(snapshot())
    draft.swap(1, 1, 2)
    path = tmp_path / "memory.hsdraft"
    draft.save(path)
    monkeypatch.setattr(drafts, "MAX_HISTORY_BYTES", len(binary(draft.origin)) + 10)
    with pytest.raises(DraftError) as exc:
        OfflineDraft.load(path)
    assert exc.value.code == "draft_history_limit"
