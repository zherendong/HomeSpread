"""아이콘 이미지 저장소 — 기기에서 한 번 받아 디스크에 둔다.

앱 300개의 아이콘을 매번 기기에서 받으면 앱을 열 때마다 1분 넘게 기다려야 한다.
아이콘은 앱을 업데이트하지 않는 한 바뀌지 않으므로, 받아 둔 것을 다시 쓴다.

무엇을 신선하다고 볼 것인가는 `iconModDate` 가 알려준다. iconState 가 항목마다 그 값을
들고 있으므로, 저장할 때 함께 적어 두고 다음에 그 값이 달라졌을 때만 다시 받는다.
날짜가 없는 항목(오프로드된 앱)은 한 번 받으면 계속 쓴다 — 본체가 없으니 아이콘이
바뀔 일도 없다.

받지 못하는 항목이 정상적으로 존재한다. 웹 클립은 SpringBoard 가 PNG 를 주지 않는다.
그래서 '실패'는 오류가 아니라 상태이며, 화면에는 첫 글자를 딴 대체 타일이 뜬다.
"""

from __future__ import annotations

import json
import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

log = logging.getLogger("icons")

# 파일 이름으로 쓸 수 없는 글자를 걸러낸다. 번들 ID 는 대개 안전하지만 웹 클립
# 식별자에는 무엇이 들어 있을지 모른다.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def _filename(identifier: str) -> str:
    safe = _UNSAFE.sub("_", identifier)[:120]
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:16]
    return f"{safe}-{digest}.png"


class IconStore:
    """아이콘 PNG 를 모아 두는 저장소.

    자리는 `paths.cache_root()` 가 정한다 — 백업·로그와 달리 이것은 **잃어도 되는**
    것이라 임시 폴더에 산다. 통째로 지워져도 다시 받으면 그만이고(287개에 7.4초),
    그 사이에 백업이 있는 폴더가 아이콘 수백 개로 불어나지 않는다.
    """

    def __init__(self, root: Path) -> None:
        self.dir = Path(root) / "icons"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.dir / "index.json"
        self._index: dict[str, str] = self._load_index()
        self._memory: dict[str, bytes] = {}

    def _load_index(self) -> dict[str, str]:
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception as exc:
            # 색인이 깨졌다고 앱이 못 뜨면 안 된다. 아이콘은 다시 받으면 그만이다.
            log.warning("아이콘 색인을 읽지 못해 새로 만든다: %r", exc)
            return {}

    def _save_index(self) -> None:
        try:
            self._index_path.write_text(
                json.dumps(self._index, ensure_ascii=False, indent=1), encoding="utf-8"
            )
        except Exception as exc:
            log.warning("아이콘 색인을 저장하지 못했다: %r", exc)

    # ------------------------------------------------------------------ 읽기

    def get(self, identifier: str) -> Optional[bytes]:
        if identifier in self._memory:
            return self._memory[identifier]
        path = self.dir / _filename(identifier)
        try:
            data = path.read_bytes()
        except OSError:
            return None
        self._memory[identifier] = data
        return data

    def has_fresh(self, identifier: str, stamp: Optional[str]) -> bool:
        """저장된 아이콘이 지금도 쓸 수 있는가."""
        if not (self.dir / _filename(identifier)).exists():
            return False
        recorded = self._index.get(identifier)
        if stamp is None or recorded is None:
            return True  # 날짜를 모르면 있는 것을 믿는다. 틀려도 아이콘 하나가 낡을 뿐이다.
        return recorded == stamp

    def missing(self, wanted: Iterable[tuple[str, Optional[str]]]) -> list[str]:
        """받아야 할 식별자만 추린다. (식별자, iconModDate 문자열) 목록을 받는다."""
        out: list[str] = []
        for identifier, stamp in wanted:
            if identifier and not self.has_fresh(identifier, stamp) and identifier not in out:
                out.append(identifier)
        return out

    # ------------------------------------------------------------------ 쓰기

    def put(self, identifier: str, data: bytes, stamp: Optional[str] = None) -> None:
        path = self.dir / _filename(identifier)
        try:
            path.write_bytes(data)
        except OSError as exc:
            log.warning("아이콘을 저장하지 못했다: %s (%r)", identifier, exc)
            return
        self._memory[identifier] = data
        if stamp is not None:
            self._index[identifier] = stamp

    def put_many(self, icons: dict[str, bytes], stamps: dict[str, Optional[str]]) -> int:
        for identifier, data in icons.items():
            self.put(identifier, data, stamps.get(identifier))
        self._save_index()
        return len(icons)

    def count(self) -> int:
        return sum(1 for path in self.dir.glob("*.png"))


def wanted_icons(document: Any) -> list[tuple[str, Optional[str]]]:
    """문서에서 '아이콘이 필요한 항목'을 뽑는다.

    폴더는 내용물로 그리므로 아이콘이 필요 없고, 알 수 없는 항목은 식별자 자체가 없다.
    """
    out: list[tuple[str, Optional[str]]] = []
    seen: set[str] = set()
    for container in document.containers():
        for node in container.items:
            if node.is_folder or not node.identifier or node.identifier in seen:
                continue
            seen.add(node.identifier)
            stamp = None
            if isinstance(node.raw, dict):
                value = node.raw.get("iconModDate")
                stamp = str(value) if value is not None else None
            out.append((node.identifier, stamp))
    return out


async def refresh(
    bridge: Any,
    store: IconStore,
    document: Any,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> tuple[int, int]:
    """모자란 아이콘만 기기에서 받아 저장소를 채운다. (받은 수, 요청한 수)를 돌려준다."""
    wanted = wanted_icons(document)
    stamps = dict(wanted)
    missing = store.missing(wanted)
    if not missing:
        return 0, 0
    icons = await bridge.get_icon_pngs(missing, on_progress=on_progress)
    store.put_many(icons, stamps)
    # 받지 못한 것도 기록해 둔다 — 다음 실행에서 똑같이 실패할 것을 또 시도하지 않도록.
    for identifier in missing:
        if identifier not in icons:
            log.debug("아이콘 없음(정상일 수 있음): %s", identifier)
    return len(icons), len(missing)
