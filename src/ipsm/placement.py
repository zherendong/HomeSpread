"""Span-aware, read-only grid preview. No layout payloads are rewritten here.

The input array supplies ordering, not screenshot coordinates. Known widget spans
are packed into the next available rectangle in row-major order. This provides a
deterministic preview, not evidence that iOS accepts a reconstructed placement.
If geometry is unknown, later items are left unplaced instead of guessing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .iconstate import ItemKind, parse_item, widget_span


@dataclass(frozen=True)
class Placement:
    index: int
    row: int
    column: int
    width: int
    height: int


@dataclass(frozen=True)
class PagePlacement:
    cells: tuple[Placement, ...]
    occupied_cells: int
    unsupported_indices: tuple[int, ...] = ()
    overflow_indices: tuple[int, ...] = ()
    error: str | None = None

    @property
    def complete(self) -> bool:
        return not self.unsupported_indices and not self.overflow_indices and self.error is None


def place_items(items: Iterable[Any], columns: int, rows: int) -> PagePlacement:
    """Place raw items, parsed Items, or Nodes, retaining each input's index."""
    entries = tuple(items)
    if (type(columns) is not int or type(rows) is not int
            or columns <= 0 or rows <= 0 or columns * rows > 4096):
        return PagePlacement((), 0, tuple(range(len(entries))), error="invalid_grid")
    reserved: set[tuple[int, int]] = set()
    placements: list[Placement] = []
    occupied = 0
    for index, entry in enumerate(entries):
        raw = getattr(entry, "raw", entry)
        item = parse_item(raw)
        if item.kind is ItemKind.WIDGET:
            span = widget_span(raw)
        elif item.kind in (ItemKind.APP, ItemKind.FOLDER, ItemKind.EMPTY):
            span = (1, 1)
        else:
            span = None
        if span is None:
            return PagePlacement(tuple(placements), occupied, tuple(range(index, len(entries))))
        width, height = span
        location = next(((row, column)
                         for row in range(rows - height + 1)
                         for column in range(columns - width + 1)
                         if all((r, c) not in reserved
                                for r in range(row, row + height)
                                for c in range(column, column + width))), None)
        if location is None:
            return PagePlacement(tuple(placements), occupied, overflow_indices=tuple(range(index, len(entries))))
        row, column = location
        placements.append(Placement(index, row, column, width, height))
        reserved.update((r, c) for r in range(row, row + height) for c in range(column, column + width))
        if item.kind is not ItemKind.EMPTY:
            occupied += width * height
    return PagePlacement(tuple(placements), occupied)
