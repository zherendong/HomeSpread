"""Conservative write capability checks, shared by every device write path.

Readable and previewable does not mean writable. This policy is deliberately
independent of UI state, a successful backup, or an earlier compatibility test.
"""
from __future__ import annotations

from typing import Any

from .i18n import tr
from .iconstate import ItemKind, parse_item


def device_write_block_reason(product_type: str | None) -> str | None:
    model = (product_type or "").strip().casefold().replace(" ", "")
    if model in {"iphone19,4", "iphoneduo"}:
        return tr("iPhone Duo is available for read-only preview. Applying, restoring and write compatibility tests are disabled for this device.")
    return None


def write_block_reason(state: Any, *, product_type: str | None = None) -> str | None:
    """Return the reason a whole-layout write must be rejected, or None.

    A widget anywhere blocks the whole operation, including writes of an
    unchanged layout and restores to an older widget-free backup. Callers must
    check both their intended state and the freshly read current state.
    """
    device_reason = device_write_block_reason(product_type)
    if device_reason:
        return device_reason
    malformed = tr("This layout contains an unsupported structure. It can be previewed, but device writes are disabled.")
    if not isinstance(state, list) or not state or len(state) > 256:
        return malformed

    def walk(pages: Any, *, inside_folder: bool = False) -> str | None:
        if not isinstance(pages, list) or len(pages) > 256:
            return malformed
        for page in pages:
            if not isinstance(page, list) or len(page) > 1024:
                return malformed
            for raw in page:
                # Check discriminants before the parser: no broad identifier or
                # iconLists fallback may turn custom content into a writable app.
                if isinstance(raw, dict) and (
                    raw.get("iconType") == "custom"
                    or raw.get("elementType") == "widget"
                    or any(key in raw for key in ("widgetIdentifier", "elements", "gridSize"))
                ):
                    return tr("This layout contains widgets or widget stacks. Preview is read-only; applying, restoring and write compatibility tests are disabled.")
                item = parse_item(raw)
                if item.kind is ItemKind.FOLDER:
                    if inside_folder or not isinstance(raw, dict) or raw.get("listType") != "folder":
                        return malformed
                    reason = walk(raw.get("iconLists"), inside_folder=True)
                    if reason:
                        return reason
                elif item.kind is not ItemKind.APP:
                    return malformed
                elif isinstance(raw, dict):
                    identifier = raw.get("displayIdentifier") or raw.get("bundleIdentifier")
                    if not isinstance(identifier, str) or not identifier:
                        return malformed
                    if raw.get("iconType") not in (None, "app", "application"):
                        return malformed
                elif not isinstance(raw, str) or not raw:
                    return malformed
        return None

    return walk(state)
