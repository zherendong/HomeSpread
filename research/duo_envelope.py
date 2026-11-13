"""Offline study of a proposed plist envelope, never a transport implementation.

The dictionary shape is reported by third-party implementations. Serialization
tests cannot prove device acceptance or completeness of an App Library inventory.
No installed applications are queried, no file is saved, and nothing is sent.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import plistlib
from typing import Any


class EvidenceMissing(ValueError):
    """The caller has not supplied even the explicit candidate exclusion list."""


@dataclass(frozen=True)
class PayloadStudy:
    payload: dict[str, Any]
    source_sha256: str

    @property
    def can_send(self) -> bool:
        # This is a research artifact, never a capability grant.
        return False


def _visible_app_ids(pages: list[list[Any]]) -> set[str]:
    visible: set[str] = set()
    for page in pages:
        for item in page:
            if isinstance(item, str):
                visible.add(item)
            elif isinstance(item, dict):
                if item.get("elementType") == "widget" or any(
                    key in item for key in ("widgetIdentifier", "elements", "gridSize", "webClipURL")
                ):
                    continue
                if item.get("listType") == "folder":
                    children = item.get("iconLists")
                    if not isinstance(children, list) or not all(isinstance(p, list) for p in children):
                        raise ValueError("Malformed folder")
                    visible.update(_visible_app_ids(children))
                else:
                    for field in ("displayIdentifier", "bundleIdentifier"):
                        ident = item.get(field)
                        if isinstance(ident, str) and ident:
                            visible.add(ident)
    return visible


def simulate_dictionary_payload(raw: list[Any], *, excluded_app_ids: list[str] | None) -> PayloadStudy:
    """Model only the envelope shape using an explicitly supplied candidate list.

    An empty list is meaningful only for a synthetic complete-inventory case.
    This function cannot establish inventory completeness, placeholder coverage,
    hidden web-clip coverage, widget-setting preservation, or device acceptance.
    Its result always has ``can_send == False``.
    """
    if excluded_app_ids is None:
        raise EvidenceMissing("Raw layout has no complete App Library exclusion inventory")
    if (not isinstance(raw, list) or not raw
            or not all(isinstance(page, list) for page in raw)):
        raise ValueError("Expected the unmodified list-form snapshot, Dock first")
    if (not isinstance(excluded_app_ids, list)
            or any(not isinstance(i, str) or not i for i in excluded_app_ids)
            or len(set(excluded_app_ids)) != len(excluded_app_ids)):
        raise ValueError("Exclusion identifiers must be unique non-empty strings")
    if _visible_app_ids(raw) & set(excluded_app_ids):
        raise ValueError("A displayed app cannot simultaneously be excluded")
    original = plistlib.dumps(raw, fmt=plistlib.FMT_BINARY, sort_keys=True)
    payload = {
        "buttonBar": deepcopy(raw[0]),
        "iconLists": deepcopy(raw[1:]),
        "ignored": sorted(excluded_app_ids),
    }
    # No field normalization: prove only that wrapping and binary serialization
    # preserve every value from the returned layout.
    decoded = plistlib.loads(plistlib.dumps(payload, fmt=plistlib.FMT_BINARY))
    unwrapped = [decoded["buttonBar"], *decoded["iconLists"]]
    if plistlib.dumps(unwrapped, fmt=plistlib.FMT_BINARY, sort_keys=True) != original:
        raise ValueError("The candidate envelope changed snapshot data")
    return PayloadStudy(payload, hashlib.sha256(original).hexdigest())
