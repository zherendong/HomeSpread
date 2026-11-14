"""Read-only observation receipts, never permission to send a layout.

A successful query is distinct from complete knowledge of the Home Screen.
Files have integrity checks, not authenticated provenance. No SDK is imported
here; collection accepts only an explicitly supplied read/close adapter.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import math
from pathlib import Path
import plistlib
import re
from typing import Any, Protocol

from .i18n import tr
from .safeio import atomic_private_write

FORMAT = "ipsm.readonly-evidence"
SCHEMA_VERSION = 1
MAX_FILE_BYTES = 64 * 1024 * 1024
PARTS = ("identity_before", "layout_v2_before", "metrics", "apps_user", "apps_system",
         "layout_v2_after", "identity_after", "layout_v3")
SOURCES = frozenset({"usb_readonly", "imported_backup", "synthetic"})
STATUSES = frozenset({"observed", "failed", "missing", "not_collected"})
UNKNOWN_FIELDS = ("geometry", "hidden_pages", "widget_settings", "hidden_webclips")
APP_ATTRIBUTES = ("CFBundleIdentifier", "ApplicationType", "CFBundleDisplayName",
                  "CFBundleName", "IsDemotedApp", "SBAppTags")
PART_OPTIONS = {
    "identity_before": {}, "layout_v2_before": {"format_version": "2"},
    "metrics": {},
    "apps_user": {"application_type": "User", "show_placeholders": True,
                  "return_attributes": list(APP_ATTRIBUTES)},
    "apps_system": {"application_type": "System", "show_placeholders": True,
                    "return_attributes": list(APP_ATTRIBUTES)},
    "layout_v2_after": {"format_version": "2"}, "identity_after": {},
    "layout_v3": {"format_version": "3"},
}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RECEIPT_KEYS = frozenset({"status", "data", "started_at", "finished_at", "error_code", "options"})
_RECORD_KEYS = frozenset({"source", "started_at", "finished_at", "receipts", "unknown",
                         "source_file_sha256", "close_error_code"})
_FILE_KEYS = frozenset({"format", "schema_version", "can_write", "record", "record_sha256"})


class EvidenceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class ReadOnlyAdapter(Protocol):
    async def read(self, part: str) -> Any: ...
    async def close(self) -> None: ...


def _error() -> EvidenceError:
    return EvidenceError("invalid_evidence", tr("This is not a valid read-only evidence bundle."))


def _binary(value: Any) -> bytes:
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY, sort_keys=True)


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date(value: Any) -> datetime:
    if not isinstance(value, str):
        raise _error()
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset() is None:
            raise _error()
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise _error() from exc


def _plist_values(value: Any, seen: set[int] | None = None, depth: int = 0) -> None:
    if depth > 40:
        raise _error()
    seen = seen if seen is not None else set()
    if type(value) in (dict, list):
        if id(value) in seen:
            raise _error()
        seen.add(id(value))
        try:
            if isinstance(value, dict) and not all(type(k) is str for k in value):
                raise _error()
            for child in value.values() if isinstance(value, dict) else value:
                _plist_values(child, seen, depth + 1)
        finally:
            seen.remove(id(value))
    elif value is not None and type(value) not in (str, bool, int, float, bytes, datetime, plistlib.UID):
        raise _error()
    elif isinstance(value, float) and not math.isfinite(value):
        raise _error()


def _check_data(part: str, data: Any) -> None:
    _plist_values(data)
    if part.startswith("identity_"):
        keys = {"device_key", "product_type", "ios_version", "build_version", "transport"}
        if (type(data) is not dict or set(data) != keys
                or any(type(data[key]) is not str or not data[key] for key in keys)
                or not _SHA.fullmatch(data["device_key"]) or data["transport"] != "USB"):
            raise _error()
    elif part.startswith("layout_v2"):
        if (type(data) is not list or not data or len(data) > 256
                or any(type(page) is not list or len(page) > 1024 for page in data)):
            raise _error()
    elif part == "layout_v3":
        if type(data) not in (dict, list):
            raise _error()
    elif part == "metrics":
        if type(data) is not dict or any(type(v) not in (int, float) for v in data.values()):
            raise _error()
    elif part in ("apps_user", "apps_system"):
        if type(data) is not dict or len(data) > 20000:
            raise _error()
        expected_type = PART_OPTIONS[part]["application_type"]
        for identifier, info in data.items():
            if (type(identifier) is not str or not identifier or type(info) is not dict
                    or not set(info).issubset(APP_ATTRIBUTES)):
                raise _error()
            for key in ("CFBundleIdentifier", "ApplicationType"):
                if key in info and (type(info[key]) is not str or not info[key]):
                    raise _error()
            for key in ("CFBundleDisplayName", "CFBundleName"):
                if key in info and type(info[key]) is not str:
                    raise _error()
            if "CFBundleIdentifier" in info and info["CFBundleIdentifier"] != identifier:
                raise _error()
            if "ApplicationType" in info and info["ApplicationType"] != expected_type:
                raise _error()
            if "IsDemotedApp" in info and type(info["IsDemotedApp"]) is not bool:
                raise _error()
            if "SBAppTags" in info and (type(info["SBAppTags"]) is not list
                    or any(type(tag) is not str for tag in info["SBAppTags"])):
                raise _error()


def _receipt(part: str, status: str = "not_collected") -> dict:
    return {"status": status, "data": None, "started_at": "", "finished_at": "",
            "error_code": "", "options": deepcopy(PART_OPTIONS[part])}


def _check_record(record: Any) -> None:
    _plist_values(record)
    if (type(record) is not dict or set(record) != _RECORD_KEYS
            or type(record.get("source")) is not str or record["source"] not in SOURCES):
        raise _error()
    start, finish = _date(record["started_at"]), _date(record["finished_at"])
    if finish < start:
        raise _error()
    if record["unknown"] != dict.fromkeys(UNKNOWN_FIELDS, "unknown"):
        raise _error()
    if record["close_error_code"] not in ("", "close_failed", "timeout"):
        raise _error()
    digest = record["source_file_sha256"]
    if type(digest) is not str or (digest and not _SHA.fullmatch(digest)):
        raise _error()
    receipts = record["receipts"]
    if type(receipts) is not dict or set(receipts) != set(PARTS):
        raise _error()
    last_finished = start
    stopped = False
    for part in PARTS:
        receipt = receipts[part]
        if (type(receipt) is not dict or set(receipt) != _RECEIPT_KEYS
                or type(receipt.get("status")) is not str or receipt["status"] not in STATUSES
                or _binary(receipt["options"]) != _binary(PART_OPTIONS[part])):
            raise _error()
        status = receipt["status"]
        if status in ("observed", "failed"):
            if stopped:
                raise _error()
            a, b = _date(receipt["started_at"]), _date(receipt["finished_at"])
            if not start <= a <= b <= finish or a < last_finished:
                raise _error()
            last_finished = b
        elif any(type(receipt[key]) is not str or receipt[key] != ""
                 for key in ("started_at", "finished_at", "error_code")):
            raise _error()
        if status == "observed":
            if receipt["error_code"] != "":
                raise _error()
            _check_data(part, receipt["data"])
        elif receipt["data"] is not None:
            raise _error()
        if status == "failed":
            if receipt["error_code"] not in ("timeout", "query_failed", "invalid_response"):
                raise _error()
            stopped = True
        if record["source"] == "imported_backup" and status == "observed" and part != "layout_v2_before":
            raise _error()
    if record["source"] == "imported_backup":
        if receipts["layout_v2_before"]["status"] != "observed":
            raise _error()
        if any(receipts[part]["status"] != "missing" for part in PARTS if part != "layout_v2_before"):
            raise _error()


class EvidenceBundle:
    """Immutable, typed observation record; source labels are not authentication."""
    def __init__(self, record: dict) -> None:
        _check_record(record)
        encoded = _binary(record)
        if len(encoded) > MAX_FILE_BYTES:
            raise EvidenceError("evidence_too_large", tr("The evidence bundle exceeds the 64 MiB file limit."))
        self._record_bytes = encoded

    @classmethod
    def from_record(cls, record: dict) -> "EvidenceBundle":
        try:
            return cls(record)
        except EvidenceError:
            raise
        except (ValueError, TypeError, OverflowError, RecursionError, KeyError) as exc:
            raise _error() from exc

    @classmethod
    def from_backup(cls, raw: Any, source_file_sha256: str | None = None) -> "EvidenceBundle":
        now = _stamp()
        receipts = {part: _receipt(part, "missing") for part in PARTS}
        receipts["layout_v2_before"].update(status="observed", data=deepcopy(raw), started_at=now, finished_at=now)
        return cls.from_record({"source": "imported_backup", "started_at": now, "finished_at": now,
                               "receipts": receipts, "unknown": dict.fromkeys(UNKNOWN_FIELDS, "unknown"),
                               "source_file_sha256": "" if source_file_sha256 is None else source_file_sha256,
                               "close_error_code": ""})

    @property
    def record(self) -> dict:
        return plistlib.loads(self._record_bytes)

    def to_dict(self) -> dict:
        return self.record

    @property
    def receipts(self) -> dict:
        return self.record["receipts"]

    @property
    def source(self) -> str:
        return self.record["source"]

    @property
    def can_write(self) -> bool:
        return False

    @property
    def collection_succeeded(self) -> bool:
        record = self.record
        required = PARTS[:-1]
        return (record["source"] != "imported_backup" and not record["close_error_code"]
                and all(record["receipts"][part]["status"] == "observed" for part in required)
                and record["receipts"]["layout_v3"]["status"] in ("observed", "not_collected"))

    def data(self, part: str) -> Any:
        if part not in PARTS:
            raise KeyError(part)
        receipt = self.receipts[part]
        return receipt["data"] if receipt["status"] == "observed" else None

    @staticmethod
    def _path(path: Path) -> Path:
        path = Path(path)
        if path.suffix.lower() != ".hsevidence":
            raise EvidenceError("evidence_extension", tr("Read-only evidence must use the .hsevidence extension."))
        return path

    def save(self, path: Path, *, replace: bool = False) -> Path:
        path = self._path(path)
        if path.is_symlink():
            raise EvidenceError("invalid_evidence_path", tr("Evidence cannot be saved through a symbolic link."))
        if path.exists() and replace:
            self.load(path)  # Never overwrite a different file disguised by its extension.
        envelope = {"format": FORMAT, "schema_version": SCHEMA_VERSION, "can_write": False,
                    "record": self.record, "record_sha256": sha256(self._record_bytes).hexdigest()}
        payload = _binary(envelope)
        if len(payload) > MAX_FILE_BYTES:
            raise EvidenceError("evidence_too_large", tr("The evidence bundle exceeds the 64 MiB file limit."))
        atomic_private_write(path, payload, replace=replace)
        saved = self.load(path)
        if saved._record_bytes != self._record_bytes:
            raise EvidenceError("evidence_integrity", tr("The saved evidence did not match when read back."))
        return path

    @classmethod
    def load(cls, path: Path) -> "EvidenceBundle":
        path = cls._path(path)
        try:
            with path.open("rb") as handle:
                payload = handle.read(MAX_FILE_BYTES + 1)
            if len(payload) > MAX_FILE_BYTES:
                raise EvidenceError("evidence_too_large", tr("The evidence bundle exceeds the 64 MiB file limit."))
            if not payload.startswith(b"bplist00"):
                raise _error()
            envelope = plistlib.loads(payload)
            if (type(envelope) is not dict or set(envelope) != _FILE_KEYS
                    or envelope["format"] != FORMAT or type(envelope["schema_version"]) is not int
                    or envelope["schema_version"] != SCHEMA_VERSION or envelope["can_write"] is not False):
                raise _error()
            bundle = cls.from_record(envelope["record"])
            if envelope["record_sha256"] != sha256(bundle._record_bytes).hexdigest():
                raise EvidenceError("evidence_integrity", tr("The evidence integrity check failed."))
            return bundle
        except EvidenceError:
            raise
        except (OSError, ValueError, TypeError, OverflowError, RecursionError, KeyError) as exc:
            raise _error() from exc


async def collect_evidence(adapter: ReadOnlyAdapter, *, source: str = "synthetic",
                           timeout: float = 10.0, include_layout_v3: bool = True) -> EvidenceBundle:
    """Collect once in order, stop on first failure, then close the adapter.

    Empty successful queries remain observed. Errors carry only a stable code,
    never exception strings that could contain identifiers or credentials.
    This coroutine does not instantiate an adapter or import device libraries.
    """
    if source not in ("synthetic", "usb_readonly") or type(include_layout_v3) is not bool:
        raise _error()
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise ValueError("Evidence timeout must be positive and at most 60 seconds")
    started = _stamp()
    receipts = {part: _receipt(part) for part in PARTS}
    close_error = ""
    observed_bytes = 4096  # Reserve room for fixed receipt metadata.
    try:
        for part in PARTS if include_layout_v3 else PARTS[:-1]:
            receipt = receipts[part]
            receipt["started_at"] = _stamp()
            try:
                data = await asyncio.wait_for(adapter.read(part), timeout=timeout)
                try:
                    _check_data(part, data)
                    data_bytes = len(_binary(data))
                    if observed_bytes + data_bytes > MAX_FILE_BYTES:
                        raise _error()
                except (EvidenceError, ValueError, TypeError, OverflowError, RecursionError):
                    receipt.update(status="failed", error_code="invalid_response")
                    break
                receipt.update(status="observed", data=deepcopy(data))
                observed_bytes += data_bytes
            except TimeoutError:
                receipt.update(status="failed", error_code="timeout")
                break
            except Exception:
                receipt.update(status="failed", error_code="query_failed")
                break
            finally:
                receipt["finished_at"] = _stamp()
    finally:
        try:
            await asyncio.wait_for(adapter.close(), timeout=min(timeout, 5))
        except TimeoutError:
            close_error = "timeout"
        except Exception:
            close_error = "close_failed"
    return EvidenceBundle.from_record({"source": source, "started_at": started, "finished_at": _stamp(),
                                      "receipts": receipts, "unknown": dict.fromkeys(UNKNOWN_FIELDS, "unknown"),
                                      "source_file_sha256": "", "close_error_code": close_error})
