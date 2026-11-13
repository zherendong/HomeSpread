"""Pure-data experiment for a constrained edit on a Duo layout snapshot.

The only supported draft operation is exchanging two distinguishable, ordinary
1x1 application occurrences on the same logical Home Screen page. Dock entries,
folders, widgets, stack members, page boundaries and all other payloads remain
exactly unchanged. The functions have no file, device, network or GUI access.

The assumed geometry is a 4x6 logical page, a four-entry Dock, and 3x3 folder
pages. Row-major packing is a *model*, not a measurement of iOS coordinates.
Passing this validator proves only the stated local invariants. It does not
authorize sending its result to a phone or establish that iOS accepts it.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from itertools import combinations
import plistlib
from typing import Any

_SPANS = {"small": (2, 2), "medium": (4, 2), "large": (4, 4)}
_MAX_BYTES = 16 * 1024 * 1024
_MAX_PAGES = 15


class DraftError(ValueError):
    """The proposed local experiment cannot establish its required invariants."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _fail(code: str, message: str) -> None:
    raise DraftError(code, message)


def _canonical(value: Any) -> bytes:
    """Typed equality: unlike Python ==, binary plist distinguishes True and 1."""
    try:
        return plistlib.dumps(value, fmt=plistlib.FMT_BINARY, sort_keys=True)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise DraftError("invalid_plist", "The snapshot contains unsupported plist values.") from exc


def _check_value(value: Any, active: set[int], depth: int = 0) -> None:
    if depth > 40:
        _fail("invalid_plist", "The snapshot exceeds the supported nesting depth.")
    if type(value) in (dict, list):
        identity = id(value)
        if identity in active:
            _fail("invalid_plist", "Cyclic objects cannot be a layout snapshot.")
        active.add(identity)
        try:
            if type(value) is dict:
                if not all(type(key) is str for key in value):
                    _fail("invalid_plist", "Plist dictionary keys must be strings.")
                children = value.values()
            else:
                children = value
            for child in children:
                _check_value(child, active, depth + 1)
        finally:
            active.remove(identity)
    elif value is not None and type(value) not in (str, bool, int, float, bytes, datetime, plistlib.UID):
        _fail("invalid_plist", "Only raw plist values are supported; no type coercion is performed.")


def _text(value: Any) -> bool:
    return type(value) is str and bool(value)


def _widget_member(raw: Any) -> bool:
    return (type(raw) is dict and raw.get("elementType") == "widget"
            and _text(raw.get("widgetIdentifier")))


def _classify(raw: Any, counts: Counter, *, location: str) -> tuple[str, tuple[int, int]]:
    if type(raw) is not dict:
        _fail("unsupported_item", "Unknown, empty and legacy string items are outside this draft scope.")

    widget_markers = (raw.get("iconType") == "custom"
                      or raw.get("elementType") == "widget"
                      or "widgetIdentifier" in raw or "elements" in raw)
    if widget_markers:
        if location != "page":
            _fail("unsupported_widget", "Widgets inside the Dock or a folder are outside this model.")
        if raw.get("listType") is not None:
            _fail("unsupported_widget", "An item has conflicting widget and list discriminants.")
        if raw.get("iconType") != "custom" or not _text(raw.get("displayIdentifier")):
            _fail("unsupported_widget", "Widget identity and its explicit custom type are required.")
        size = raw.get("gridSize")
        if type(size) is not str or size not in _SPANS:
            _fail("unsupported_span", "The widget size has no validated offline span mapping.")
        if "iconLists" in raw and (type(raw["iconLists"]) is not list or raw["iconLists"]):
            _fail("unsupported_widget", "A widget contains nonempty or malformed folder-like content.")
        if "elements" in raw:
            elements = raw["elements"]
            if type(elements) is not list or not elements or len(elements) > 100:
                _fail("unsupported_widget", "A widget stack requires a bounded nonempty member list.")
            if not all(_widget_member(member) for member in elements):
                _fail("unsupported_widget", "A stack member is not an explicit widget payload.")
            member_ids = [member.get("uniqueIdentifier") for member in elements]
            if not all(_text(identifier) for identifier in member_ids) or len(set(member_ids)) != len(member_ids):
                _fail("unsupported_widget", "Stack member identities must be present and unique.")
            selected = raw.get("userSelectedElementIdentifier")
            if selected is not None and selected not in member_ids:
                _fail("unsupported_widget", "The selected stack member does not exist in the stack.")
            members = len(elements)
        else:
            if not _widget_member(raw):
                _fail("unsupported_widget", "The custom item is not an explicit standalone widget.")
            members = 1
        counts["widget_blocks"] += 1
        counts["widget_members"] += members
        return "widget", _SPANS[size]

    if raw.get("listType") == "folder":
        if location == "folder":
            _fail("unsupported_folder", "Nested folders are outside this draft scope.")
        pages = raw.get("iconLists")
        if type(pages) is not list or not pages or len(pages) > _MAX_PAGES:
            _fail("unsupported_folder", "A folder requires a bounded nonempty page list.")
        counts["folders"] += 1
        for page in pages:
            if type(page) is not list or not page or len(page) > 9:
                _fail("unsupported_folder", "Folder pages must have between one and nine app entries.")
            for child in page:
                kind, _ = _classify(child, counts, location="folder")
                if kind != "app":
                    _fail("unsupported_folder", "Only ordinary app entries are modeled inside folders.")
        return "folder", (1, 1)

    if any(key in raw for key in ("iconLists", "listType", "elementType", "gridSize")):
        _fail("unsupported_item", "An item contains unknown layout discriminants.")
    if raw.get("iconType") not in (None, "app", "application"):
        _fail("unsupported_item", "An item uses an unsupported icon type.")
    if any(key in raw for key in ("webClipURL", "webClipIdentifier", "isWebClip", "isWebApp")):
        _fail("unsupported_item", "Web clips and web apps are outside this draft scope.")
    if not (_text(raw.get("displayIdentifier")) or _text(raw.get("bundleIdentifier"))):
        _fail("unsupported_item", "An ordinary app requires a nonempty string identifier.")
    for key in ("displayIdentifier", "bundleIdentifier"):
        if key in raw and not _text(raw[key]):
            _fail("unsupported_item", "App identifiers must be nonempty strings when present.")
    counts["apps"] += 1
    return "app", (1, 1)


def _placements(kinds: list[tuple[str, tuple[int, int]]]) -> tuple[list[dict], int]:
    occupied: set[tuple[int, int]] = set()
    result = []
    for index, (kind, (width, height)) in enumerate(kinds):
        anchor = None
        for row in range(6 - height + 1):
            for column in range(4 - width + 1):
                area = {(r, c) for r in range(row, row + height) for c in range(column, column + width)}
                if not area & occupied:
                    anchor = row, column, area
                    break
            if anchor is not None:
                break
        if anchor is None:
            _fail("overflow", "Items do not fit in the assumed four-column, six-row logical page.")
        row, column, area = anchor
        occupied.update(area)
        result.append({"index": index, "row": row, "column": column,
                       "width": width, "height": height, "kind": kind})
    return result, len(occupied)


def analyze_layout(raw: Any) -> dict:
    """Validate a snapshot and enumerate occurrence-indexed local swap candidates.

    No names, bundle identifiers or other personal fields are included in the
    returned report. Its hashes identify local snapshot content, not a device.
    """
    if type(raw) is not list or not 2 <= len(raw) <= _MAX_PAGES + 1:
        _fail("unsupported_shape", "Expected a list containing Dock followed by one to fifteen logical pages.")
    _check_value(raw, set())
    encoded = _canonical(raw)
    if len(encoded) > _MAX_BYTES:
        _fail("too_large", "The snapshot exceeds the sixteen MiB research limit.")
    if not all(type(page) is list for page in raw):
        _fail("unsupported_shape", "Every Dock/page container must be a list.")
    if len(raw[0]) > 4:
        _fail("overflow", "The Dock exceeds the four-entry research profile.")
    counts = Counter({"apps": 0, "folders": 0, "widget_blocks": 0, "widget_members": 0})
    for item in raw[0]:
        _classify(item, counts, location="dock")
    pages = []
    for page_number, entries in enumerate(raw[1:], start=1):
        if len(entries) > 24:
            _fail("overflow", "A logical page has more entries than the modeled grid can hold.")
        kinds = [_classify(item, counts, location="page") for item in entries]
        placements, occupied = _placements(kinds)
        candidates = [index for index, (kind, _) in enumerate(kinds) if kind == "app"]
        fingerprints = {index: _canonical(entries[index]) for index in candidates}
        pairs = [[left, right] for left, right in combinations(candidates, 2)
                 if fingerprints[left] != fingerprints[right]]
        pages.append({"page": page_number, "item_count": len(entries), "occupied_cells": occupied,
                      "placements": placements, "candidate_indices": candidates, "candidate_pairs": pairs})
    return {"schema": "dock-first-list", "raw_sha256": sha256(encoded).hexdigest(),
            "device_write_supported": False, "geometry_evidence": "modeled_not_device_verified",
            "assumed_grid": {"columns": 4, "rows": 6, "dock_capacity": 4,
                             "folder_columns": 3, "folder_rows": 3},
            "counts": dict(counts), "home_page_count": len(raw) - 1,
            "dock_item_count": len(raw[0]), "pages": pages}


def _intent(raw: list, analysis: dict, page: int, index_a: int, index_b: int) -> None:
    if type(page) is not int or not 1 <= page < len(raw):
        _fail("invalid_page", "Only one logical Home Screen page may be selected; Dock is excluded.")
    if type(index_a) is not int or type(index_b) is not int:
        _fail("invalid_index", "Occurrence indices must be integers, not booleans or paths.")
    if not 0 <= index_a < len(raw[page]) or not 0 <= index_b < len(raw[page]):
        _fail("invalid_index", "The selected occurrence index is outside the logical page.")
    if index_a == index_b:
        _fail("no_op", "The two selected occurrences are the same position.")
    candidates = analysis["pages"][page - 1]["candidate_indices"]
    if index_a not in candidates or index_b not in candidates:
        _fail("unsupported_endpoint", "Both selected occurrences must be ordinary one-cell apps.")
    if _canonical(raw[page][index_a]) == _canonical(raw[page][index_b]):
        _fail("no_op", "The two payloads are indistinguishable; the proposed exchange has no observable effect.")


def validate_swap(origin: Any, candidate: Any, page: int, index_a: int, index_b: int) -> dict:
    """Independently validate exact endpoints and every unchanged raw slot.

    This does not call plan_swap or trust a caller-supplied success flag. It
    deliberately checks fields the display model does not understand as well.
    """
    before = analyze_layout(origin)
    _intent(origin, before, page, index_a, index_b)
    after = analyze_layout(candidate)
    if len(origin) != len(candidate) or any(len(a) != len(b) for a, b in zip(origin, candidate)):
        _fail("shape_changed", "The draft changed a page boundary, page length or Dock size.")
    changes = []
    for p, (left_page, right_page) in enumerate(zip(origin, candidate)):
        for index, (left, right) in enumerate(zip(left_page, right_page)):
            expected = origin[page][index_b] if (p, index) == (page, index_a) else (
                origin[page][index_a] if (p, index) == (page, index_b) else left)
            if _canonical(right) != _canonical(expected):
                _fail("payload_changed", "The draft changed content outside the two exact app payloads or swapped the wrong occurrence.")
            if _canonical(left) != _canonical(right):
                changes.append([p, index])
    if changes != sorted([[page, index_a], [page, index_b]]):
        _fail("intent_mismatch", "The changed positions do not match the explicit two-occurrence intent.")
    if Counter(_canonical(item) for items in origin for item in items) != Counter(
            _canonical(item) for items in candidate for item in items):
        _fail("inventory_changed", "The exact top-level payload multiset changed.")
    # Placements are indexed by raw occurrence, not by identifier. Exchanging
    # two 1x1 entries must leave all widget and folder anchors unchanged.
    if any(left["placements"] != right["placements"] for left, right in zip(before["pages"], after["pages"])):
        _fail("geometry_changed", "The proposed exchange changed modeled spans or anchors.")
    encoded = _canonical(candidate)
    decoded = plistlib.loads(encoded)
    if _canonical(decoded) != encoded:
        _fail("serialization_changed", "Binary plist serialization did not round-trip exactly.")
    return {"valid": True, "device_write_supported": False,
            "operation": "same_logical_page_app_swap", "changed_paths": changes,
            "origin_sha256": before["raw_sha256"], "candidate_sha256": after["raw_sha256"],
            "unchanged_slots_preserved": True, "payload_multiset_preserved": True,
            "modeled_widget_anchors_preserved": True, "binary_plist_roundtrip": True,
            "geometry_evidence": "modeled_not_device_verified"}


def plan_swap(raw: Any, page: int, index_a: int, index_b: int) -> list:
    """Return an in-memory candidate; never modify the source or contact a device."""
    analysis = analyze_layout(raw)
    _intent(raw, analysis, page, index_a, index_b)
    candidate = deepcopy(raw)
    candidate[page][index_a], candidate[page][index_b] = candidate[page][index_b], candidate[page][index_a]
    validate_swap(raw, candidate, page, index_a, index_b)
    return candidate
