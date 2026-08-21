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

import json
import logging
import plistlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .i18n import tr
from .iconstate import IconState, value_diff
from .logging_setup import DASH, step

log = logging.getLogger("backup")

_SAFE_REASON = re.compile(r"[^0-9A-Za-z_-]+")


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

    def __init__(self, root: Path) -> None:
        self.dir = root / "backups"
        self.dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ 저장

    def save(self, state: list[Any], reason: str = "auto") -> Backup:
        """현재 레이아웃을 백업한다. 실패하면 BackupError 를 던진다 — 삼키지 않는다.

        저장 직후 되읽어서 원본과 같은지 확인한다. '파일은 만들어졌지만 내용이 깨진'
        백업은 없는 것보다 나쁘다. 복원할 수 있다고 믿게 만들기 때문이다.
        """
        with step(log, f"백업 저장 ({reason})") as ctx:
            safe_reason = _SAFE_REASON.sub("-", reason).strip("-") or "auto"
            created = datetime.now()
            stem = f"{created.strftime('%Y%m%d_%H%M%S')}_{safe_reason}"
            plist_path = self.dir / f"{stem}.plist"
            json_path = self.dir / f"{stem}.json"

            try:
                # 이진 plist 로 쓴다. XML plist 는 날짜를 초 단위로 잘라내기 때문에
                # (iconModDate 의 소수점 이하가 사라진다 — 실기기에서 확인) 저장한 파일이
                # 원본과 달라진다. 기기가 쓰는 형식도 이진이고, 크기도 1/4 이다.
                plist_path.write_bytes(plistlib.dumps(state, fmt=plistlib.FMT_BINARY))
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
                json_path.write_text(
                    json.dumps(state, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8",
                )
            except BackupError:
                _discard(plist_path, json_path)
                raise
            except Exception as exc:
                _discard(plist_path, json_path)
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
        """최신 순으로 백업 목록을 돌려준다. 읽을 수 없는 파일은 건너뛰되 로그에 남긴다."""
        found: list[Backup] = []
        for path in sorted(self.dir.glob("*.plist"), reverse=True):
            try:
                state = plistlib.loads(path.read_bytes())
                parsed = IconState.parse(state)
            except Exception as exc:
                log.warning("백업을 읽을 수 없다: %s (%r)", path.name, exc)
                continue
            # 파일명 규칙: YYYYMMDD_HHMMSS_사유 (앞 15자가 시각)
            stem = path.stem
            reason = stem[16:] if len(stem) > 16 else "?"
            try:
                created = datetime.strptime(stem[:15], "%Y%m%d_%H%M%S")
            except ValueError:
                created = datetime.fromtimestamp(path.stat().st_mtime)
            found.append(
                Backup(
                    path=path,
                    created_at=created,
                    reason=reason or "?",
                    page_count=len(parsed.pages),
                    item_count=sum(1 for _ in parsed.iter_items()),
                )
            )
        return found

    def latest(self) -> Optional[Backup]:
        backups = self.list_backups()
        return backups[0] if backups else None

    def load(self, path: Path) -> list[Any]:
        """백업 파일에서 복원용 원본을 읽는다."""
        with step(log, f"백업 읽기 ({path.name})") as ctx:
            try:
                state = plistlib.loads(Path(path).read_bytes())
            except Exception as exc:
                raise BackupError(
                    tr("백업 파일을 읽지 못했습니다: {why}").format(why=exc)
                ) from exc
            if not isinstance(state, list):
                raise BackupError(tr("백업 파일의 형식이 올바르지 않습니다."))
            ctx["result"] = f"{len(state)}개 리스트"
            return state


async def guarded_write(bridge, store: BackupStore, new_state: list[Any], reason: str) -> Backup:
    """백업을 만든 뒤에만 쓴다 (REQ-010).

    쓰기 경로는 이 함수 하나로 모은다. 여기저기서 `bridge.set_icon_state()` 를 직접 부르면
    언젠가 백업 없는 경로가 하나 생기고, 그 경로에서 사고가 난다.
    """
    current = await bridge.get_icon_state()
    backup = store.save(current, reason=reason)  # 실패하면 여기서 멈춘다 — 쓰지 않는다
    await bridge.set_icon_state(new_state)
    return backup


async def restore(bridge, store: BackupStore, backup_path: Path) -> Backup:
    """백업 시점으로 되돌린다 (REQ-011).

    복원도 쓰기다. 복원 직전 상태를 먼저 백업한다 — 사용자가 '되돌리기를 되돌리고' 싶어질
    수 있고, 잘못된 백업을 골랐을 수도 있다.
    """
    state = store.load(backup_path)
    return await guarded_write(bridge, store, state, reason="before-restore")
