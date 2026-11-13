"""Offline-only layout drafts, separate from phone backups and live editing.

The immutable baseline and every displayed snapshot are binary plist values.
Only the validated same-page app swap rule can build a new state. Saved drafts
contain their explicit history and must replay exactly before they are accepted.
There is no device, worker, transport, or GUI dependency in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import plistlib
from typing import Any

from .draft_rules import DraftError, analyze_layout, plan_swap
from .i18n import tr
from .safeio import atomic_private_write

MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_OPERATIONS = 1000
MAX_HISTORY_BYTES = 128 * 1024 * 1024
FORMAT = "ipsm.offline-draft"
SCHEMA_VERSION = 1
_FILE_KEYS = frozenset({"format", "schema_version", "purpose", "device_write_allowed",
                        "origin", "current", "origin_sha256", "current_sha256", "operations"})
_OP_KEYS = frozenset({"page", "index_a", "index_b"})


def _binary(value: Any) -> bytes:
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY, sort_keys=True)


def _digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def _invalid(message: str | None = None) -> DraftError:
    return DraftError("invalid_draft_file", message or tr("This is not a valid offline draft file."))


def _read_bounded(path: Path) -> bytes:
    with path.open("rb") as handle:
        content = handle.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise DraftError("draft_too_large", tr("The offline draft exceeds the 32 MiB file limit."))
    return content


def _check_extension(path: Path) -> None:
    if path.suffix.lower() != ".hsdraft":
        raise DraftError("draft_extension", tr("Offline drafts must use the .hsdraft extension. Original .plist backups cannot be overwritten."))


def _label(item: Any) -> str:
    if isinstance(item, dict):
        for key in ("displayName", "displayIdentifier", "bundleIdentifier"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
    return tr("Unnamed app")


@dataclass(frozen=True)
class Swap:
    page: int
    index_a: int
    index_b: int


@dataclass(frozen=True)
class DraftChange:
    page: int
    index: int
    before_label: str
    after_label: str


class OfflineDraft:
    """An offline operation history with no permission to write to a phone.

    ``dirty`` compares the current typed state with the last successful save
    (or the baseline for a new draft). ``has_changes`` compares with the baseline.
    Saving persists the active operations only; an undone redo tail is not saved.
    """

    def __init__(self, origin: Any) -> None:
        analyze_layout(origin)
        self._origin_bytes = _binary(origin)
        self._states: list[bytes] = [self._origin_bytes]
        self._history: list[Swap] = []
        self._cursor = 0
        self._saved_digest = _digest(self._origin_bytes)
        self._path: Path | None = None

    @property
    def origin(self) -> list[Any]:
        return plistlib.loads(self._origin_bytes)

    @property
    def current_state(self) -> list[Any]:
        return plistlib.loads(self._states[self._cursor])

    @property
    def current(self) -> list[Any]:
        return self.current_state

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def can_undo(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor < len(self._history)

    @property
    def operations(self) -> tuple[Swap, ...]:
        return tuple(self._history[:self._cursor])

    @property
    def dirty(self) -> bool:
        return _digest(self._states[self._cursor]) != self._saved_digest

    @property
    def has_changes(self) -> bool:
        return self._states[self._cursor] != self._origin_bytes

    @property
    def device_write_allowed(self) -> bool:
        return False

    def swap(self, page: int, index_a: int, index_b: int) -> None:
        if self._cursor >= MAX_OPERATIONS:
            raise DraftError("draft_history_limit", tr("The offline draft has reached its 1000-operation limit."))
        # plan_swap independently validates intent and complete payload retention.
        # Nothing is committed until the entire operation succeeds.
        candidate = plan_swap(self.current_state, page, index_a, index_b)
        encoded = _binary(candidate)
        if sum(len(state) for state in self._states[:self._cursor + 1]) + len(encoded) > MAX_HISTORY_BYTES:
            raise DraftError("draft_history_limit", tr("The offline draft history exceeds its memory limit."))
        self._history = self._history[:self._cursor] + [Swap(page, index_a, index_b)]
        self._states = self._states[:self._cursor + 1] + [encoded]
        self._cursor += 1

    def undo(self) -> bool:
        if not self.can_undo:
            return False
        self._cursor -= 1
        return True

    def redo(self) -> bool:
        if not self.can_redo:
            return False
        self._cursor += 1
        return True

    def diff(self) -> tuple[DraftChange, ...]:
        """Final differences by occurrence, including names only for UI display."""
        result: list[DraftChange] = []
        for page, (before, after) in enumerate(zip(self.origin, self.current_state)):
            for index, (left, right) in enumerate(zip(before, after)):
                if _binary(left) != _binary(right):
                    result.append(DraftChange(page, index, _label(left), _label(right)))
        return tuple(result)

    def _envelope(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "schema_version": SCHEMA_VERSION,
            "purpose": "offline-only",
            "device_write_allowed": False,
            "origin": self.origin,
            "current": self.current_state,
            "origin_sha256": _digest(self._origin_bytes),
            "current_sha256": _digest(self._states[self._cursor]),
            "operations": [{"page": op.page, "index_a": op.index_a, "index_b": op.index_b}
                           for op in self.operations],
        }

    @classmethod
    def _from_envelope(cls, envelope: Any) -> "OfflineDraft":
        if not isinstance(envelope, dict) or set(envelope) != _FILE_KEYS:
            raise _invalid()
        if (envelope.get("format") != FORMAT
                or type(envelope.get("schema_version")) is not int
                or envelope["schema_version"] != SCHEMA_VERSION):
            raise _invalid()
        if envelope.get("purpose") != "offline-only" or envelope.get("device_write_allowed") is not False:
            raise _invalid(tr("This file is not marked as an offline-only draft."))
        operations = envelope.get("operations")
        if not isinstance(operations, list) or len(operations) > MAX_OPERATIONS:
            raise _invalid(tr("The offline draft operation history is invalid or too large."))
        try:
            draft = cls(envelope["origin"])
            if envelope.get("origin_sha256") != _digest(draft._origin_bytes):
                raise _invalid(tr("The offline draft baseline integrity check failed."))
            if len(draft._origin_bytes) * (len(operations) + 1) > MAX_HISTORY_BYTES:
                raise DraftError("draft_history_limit", tr("The offline draft history exceeds its memory limit."))
            for operation in operations:
                if (type(operation) is not dict or set(operation) != _OP_KEYS
                        or any(type(operation[key]) is not int for key in _OP_KEYS)):
                    raise _invalid(tr("The offline draft operation history is invalid or too large."))
                draft.swap(operation["page"], operation["index_a"], operation["index_b"])
            current = _binary(envelope["current"])
            if (current != draft._states[draft._cursor]
                    or envelope.get("current_sha256") != _digest(current)):
                raise _invalid(tr("The offline draft does not match its validated operation history."))
            draft._saved_digest = _digest(current)
            return draft
        except DraftError:
            raise
        except (TypeError, ValueError, OverflowError, RecursionError, KeyError) as exc:
            raise _invalid() from exc

    @classmethod
    def load(cls, path: Path) -> "OfflineDraft":
        path = Path(path)
        _check_extension(path)
        try:
            content = _read_bounded(path)
            if not content.startswith(b"bplist00"):
                raise _invalid(tr("Offline drafts must contain a binary plist envelope."))
            envelope = plistlib.loads(content)
            draft = cls._from_envelope(envelope)
        except DraftError:
            raise
        except (OSError, plistlib.InvalidFileException, TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise _invalid(tr("Could not read the offline draft: {why}").format(why=exc)) from exc
        draft._path = path
        return draft

    def save(self, path: Path, *, replace: bool = False) -> Path:
        path = Path(path)
        _check_extension(path)
        try:
            if path.is_symlink():
                raise _invalid(tr("An offline draft cannot be saved through a symbolic link."))
            if path.exists() and replace:
                # Even with explicit overwrite confirmation, never replace an
                # original layout merely renamed to look like a draft file.
                self.load(path)
            content = _binary(self._envelope())
            if len(content) > MAX_FILE_BYTES:
                raise DraftError("draft_too_large", tr("The offline draft exceeds the 32 MiB file limit."))
            self._from_envelope(plistlib.loads(content))
            atomic_private_write(path, content, replace=replace)
            if _read_bounded(path) != content:
                raise _invalid(tr("The saved offline draft did not match when read back."))
        except DraftError:
            raise
        except (OSError, ValueError, TypeError, OverflowError, RecursionError) as exc:
            raise DraftError("draft_save_failed", tr("Could not save the offline draft: {why}").format(why=exc)) from exc
        self._saved_digest = _digest(self._states[self._cursor])
        self._path = path
        return path
