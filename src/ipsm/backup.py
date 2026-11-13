"""백업과 복원 (REQ-010, REQ-011).

setIconState 는 전체 덮어쓰기이므로, 직전 상태를 그대로 다시 보내면 완전한 되돌리기가 된다.
이 프로젝트의 안전성은 정교한 검증이 아니라 **백업이 반드시 존재한다**는 사실에 걸려 있다.

그래서 규칙은 하나다: **백업 저장에 실패하면 쓰기를 하지 않는다.** 백업 없이 쓰는 것보다
아무것도 하지 않는 편이 언제나 낫다.

저장 위치:
    backups/{YYYYMMDD_HHMMSS}_{사유}.plist    원본 그대로 (되돌릴 때 이 파일을 보낸다)
    backups/{YYYYMMDD_HHMMSS}_{사유}.json     사람이 확인하는 용도 (복원에는 쓰지 않는다)
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from collections import Counter
import logging
import plistlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .i18n import tr
from .iconstate import IconState, ItemKind, parse_item, value_diff
from .logging_setup import DASH, step
from .safeio import atomic_private_write, private_directory

log = logging.getLogger("backup")

_SAFE_REASON = re.compile(r"[^0-9A-Za-z_-]+")
_DEVICE_KEY = re.compile(r"[0-9a-f]{64}\Z")
MAX_BACKUP_BYTES = 16 * 1024 * 1024


class BackupError(Exception):
    """백업을 만들지 못했다. 호출자는 이 예외를 받으면 쓰기를 포기해야 한다."""


@dataclass
class Backup:
    path: Path
    created_at: datetime
    reason: str
    page_count: int
    item_count: int

    @property
    def label(self) -> str:
        stamp = self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        return tr("{stamp} {dash} {reason} {dash} {pages}페이지 {items}개 항목").format(
            stamp=stamp,
            dash=DASH,
            reason=self.reason,
            pages=self.page_count,
            items=self.item_count,
        )


def _discard(*paths: Path) -> None:
    """검증에 실패한 백업 파일을 지운다.

    남겨두면 list_backups() 가 이것을 멀쩡한 백업으로 보여주고, 사용자는 되돌릴 수 있다고
    믿게 된다. 신뢰할 수 없는 백업은 없는 백업보다 나쁘다 — 이 모듈의 전제 그대로다.
    """
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:  # 지우지 못하면 최소한 알린다
            log.warning("신뢰할 수 없는 백업 파일을 지우지 못했다: %s (%r)", path, exc)


class BackupStore:
    """한 기기(또는 한 프로젝트)의 백업 모음."""

    def __init__(self, root: Path, device_key: Optional[str] = None) -> None:
        self.base_dir = Path(root) / "backups"
        private_directory(self.base_dir)
        self.dir = self.base_dir
        self.device_key: Optional[str] = None
        if device_key is not None:
            self.bind_device(device_key)

    def bind_device(self, device_key: str) -> None:
        """Select one phone using its one-way UDID digest, never a device name."""
        if not isinstance(device_key, str) or not _DEVICE_KEY.fullmatch(device_key):
            raise BackupError(tr("Cannot identify the connected iPhone safely. Reconnect and read it again."))
        target = self.base_dir / device_key
        private_directory(target)
        self.device_key, self.dir = device_key, target

    # ------------------------------------------------------------------ 저장

    def save(self, state: list[Any], reason: str = "auto") -> Backup:
        """현재 레이아웃을 백업한다. 실패하면 BackupError 를 던진다 — 삼키지 않는다.

        저장 직후 되읽어서 원본과 같은지 확인한다. '파일은 만들어졌지만 내용이 깨진'
        백업은 없는 것보다 나쁘다. 복원할 수 있다고 믿게 만들기 때문이다.
        """
        with step(log, f"백업 저장 ({reason})") as ctx:
            safe_reason = _SAFE_REASON.sub("-", reason).strip("-") or "auto"
            created = datetime.now()
            stem = f"{created.strftime('%Y%m%d_%H%M%S_%f')}_{uuid.uuid4().hex[:12]}_{safe_reason}"
            plist_path = self.dir / f"{stem}.plist"
            json_path = self.dir / f"{stem}.json"
            meta_path = self.dir / f"{stem}.meta.json"
            written: list[Path] = []

            try:
                # 이진 plist 로 쓴다. XML plist 는 날짜를 초 단위로 잘라내기 때문에
                # (iconModDate 의 소수점 이하가 사라진다 — 실기기에서 확인) 저장한 파일이
                # 원본과 달라진다. 기기가 쓰는 형식도 이진이고, 크기도 1/4 이다.
                payload = plistlib.dumps(state, fmt=plistlib.FMT_BINARY)
                atomic_private_write(plist_path, payload)
                written.append(plist_path)
                restored = plistlib.loads(plist_path.read_bytes())
                if restored != state:
                    # 어디가 다른지 남긴다. 이 검사가 걸렸다는 것은 우리가 모르는 손실이
                    # 있다는 뜻이고, 그때 필요한 것은 '달랐다'가 아니라 '어디가'다.
                    where = value_diff(state, restored, limit=10)
                    for line in where:
                        log.error("  백업 불일치: %s", line)
                    raise BackupError(
                        tr("백업 파일을 다시 읽었을 때 원본과 달랐습니다. 백업을 신뢰할 수 없습니다.")
                        + (tr(" (예: {sample})").format(sample=where[0]) if where else "")
                    )
                atomic_private_write(
                    json_path,
                    json.dumps(state, indent=2, ensure_ascii=False, default=str).encode("utf-8"),
                )
                written.append(json_path)
                metadata = {
                    "schema": 1,
                    "device_key": self.device_key,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "created_at": created.isoformat(),
                    "reason": safe_reason,
                }
                atomic_private_write(meta_path, json.dumps(metadata).encode("utf-8"))
                written.append(meta_path)
            except BackupError:
                _discard(*written)
                raise
            except Exception as exc:
                _discard(*written)
                raise BackupError(
                    tr("백업을 저장하지 못했습니다: {why}").format(why=exc)
                ) from exc

            parsed = IconState.parse(state)
            backup = Backup(
                path=plist_path,
                created_at=created,
                reason=reason,
                page_count=len(parsed.pages),
                item_count=sum(1 for _ in parsed.iter_items()),
            )
            ctx["result"] = f"{plist_path.name} ({plist_path.stat().st_size} bytes)"
            return backup

    # ------------------------------------------------------------------ 조회

    def list_backups(self) -> list[Backup]:
        """Return only complete, verified backups for the selected phone."""
        found: list[Backup] = []
        for path in sorted(self.dir.glob("*.plist"), reverse=True):
            try:
                state = self.load(path, for_restore=self.device_key is not None)
                parsed = IconState.parse(state)
                meta = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
                created = datetime.fromisoformat(meta["created_at"])
                reason = meta["reason"]
            except Exception as exc:
                log.warning("백업을 읽을 수 없다: %s (%r)", path.name, exc)
                continue
            found.append(Backup(path, created, reason, len(parsed.pages),
                                sum(1 for _ in parsed.iter_items())))
        return sorted(found, key=lambda backup: backup.created_at, reverse=True)

    def latest(self) -> Optional[Backup]:
        backups = self.list_backups()
        return backups[0] if backups else None

    def load(self, path: Path, *, for_restore: bool = False) -> list[Any]:
        """Read a bounded preview, or verify device ownership and integrity to restore.

        Legacy/unbound files remain previewable but cannot be written to a phone.
        The digest detects accidental corruption; it is not a signature against a
        malicious process running as the same macOS user.
        """
        path = Path(path)
        with step(log, f"백업 읽기 ({path.name})") as ctx:
            try:
                if path.stat().st_size > MAX_BACKUP_BYTES:
                    raise ValueError("Backup exceeds the 16 MiB size limit")
                payload = path.read_bytes()
                if for_restore:
                    if (self.device_key is None or path.is_symlink()
                            or path.parent.resolve() != self.dir.resolve()):
                        raise BackupError(tr("This backup does not belong to the connected iPhone."))
                    meta_path = path.with_suffix(".meta.json")
                    if meta_path.is_symlink() or meta_path.stat().st_size > 8192:
                        raise BackupError(tr("The backup integrity record is invalid. Restoration was stopped."))
                    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                    if (metadata.get("schema") != 1
                            or metadata.get("device_key") != self.device_key
                            or metadata.get("sha256") != hashlib.sha256(payload).hexdigest()):
                        raise BackupError(tr("The backup integrity record is invalid. Restoration was stopped."))
                state = plistlib.loads(payload)
                validate_state(state)
            except BackupError:
                raise
            except Exception as exc:
                raise BackupError(tr("백업 파일을 읽지 못했습니다: {why}").format(why=exc)) from exc
            ctx["result"] = f"{len(state)}개 리스트"
            return state


def validate_state(state: Any) -> None:
    """Reject malformed containers without interpreting unknown item payloads."""
    if not isinstance(state, list) or not state or len(state) > 256:
        raise BackupError(tr("The layout has an unsupported structure. No changes were written."))

    def pages(containers: Any, depth: int) -> None:
        if not isinstance(containers, list) or depth > 2 or len(containers) > 256:
            raise BackupError(tr("The layout has an unsupported structure. No changes were written."))
        for page in containers:
            if not isinstance(page, list) or len(page) > 1024:
                raise BackupError(tr("The layout has an unsupported structure. No changes were written."))
            for item in page:
                if isinstance(item, dict) and ("iconLists" in item or item.get("listType") == "folder"):
                    pages(item.get("iconLists"), depth + 1)
    pages(state, 0)


def _edit_contents(state: list[Any]) -> tuple[Counter, dict[tuple, bytes]]:
    leaves: Counter = Counter()
    opaque: dict[tuple, bytes] = {}

    def walk(containers: list[Any], prefix: tuple = ()) -> None:
        for page_index, page in enumerate(containers):
            for index, raw in enumerate(page):
                position = prefix + (page_index, index)
                item = parse_item(raw)
                if item.kind is ItemKind.FOLDER:
                    walk(raw["iconLists"], position)
                else:
                    payload = plistlib.dumps(raw, fmt=plistlib.FMT_BINARY, sort_keys=True)
                    leaves[payload] += 1
                    if item.kind not in (ItemKind.APP,):
                        opaque[position] = payload
    walk(state)
    return leaves, opaque


def _bind_bridge(bridge, store: BackupStore) -> None:
    key = getattr(bridge, "device_key", None)
    if not isinstance(key, str) or not _DEVICE_KEY.fullmatch(key):
        raise BackupError(tr("Cannot identify the connected iPhone safely. Reconnect and read it again."))
    if store.device_key is not None and store.device_key != key:
        raise BackupError(tr("This backup does not belong to the connected iPhone."))
    store.bind_device(key)


async def guarded_write(bridge, store: BackupStore, new_state: list[Any], reason: str,
                        *, expected_state: Optional[list[Any]] = None) -> Backup:
    """Only publish a layout after identity, freshness and durable backup checks."""
    _bind_bridge(bridge, store)
    # Snapshot caller-owned data before the first await; UI mutation cannot change it.
    new_state = copy.deepcopy(new_state)
    expected_state = copy.deepcopy(expected_state)
    validate_state(new_state)
    current = await bridge.get_icon_state()
    validate_state(current)
    if expected_state is not None:
        if current != expected_state:
            raise BackupError(tr("The iPhone layout changed after it was read. Read it again before applying edits."))
        if _edit_contents(current) != _edit_contents(new_state):
            raise BackupError(tr("The edit would lose, duplicate, change or move an unsupported item. No changes were written."))
    backup = store.save(current, reason=reason)
    # A read-back also validates the ownership/integrity record before any device write.
    if store.load(backup.path, for_restore=True) != current:
        raise BackupError(tr("The backup integrity record is invalid. Restoration was stopped."))
    await bridge.set_icon_state(new_state)
    return backup


async def restore(bridge, store: BackupStore, backup_path: Path) -> Backup:
    """Restore only a complete backup from this phone, after backing up its present state."""
    _bind_bridge(bridge, store)
    state = store.load(backup_path, for_restore=True)
    return await guarded_write(bridge, store, state, reason="before-restore")
