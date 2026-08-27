# -*- coding: utf-8 -*-
"""빌드가 사용자의 백업을 지우지 못하게 한다.

PyInstaller 의 `COLLECT` 는 만들기 전에 `dist\\HomeSpread\\` 를 **통째로 지운다.**
그런데 그 폴더는 exe 를 한 번이라도 실행하면 `backups\\` 와 `logs\\` 가 생기는
자리이기도 하다. 그래서 "빌드 한 번"이 조용히 "백업 전부 삭제"가 된다 —
2026-08-21 에 실제로 그렇게 잃었다.

되돌릴 길이 백업뿐인 앱에서 이것은 있어서는 안 되는 일이다. `backups/` 는 사용자가
지우기 전에는 아무도 지우지 않는다는 것이 이 프로젝트의 약속이고, 그 약속은 빌드
스크립트에도 걸린다.

그래서 빌드 앞뒤로 두 번 부른다.

    python scripts/keep_data.py stash     빌드 전 — 옆으로 치워 둔다
    python scripts/keep_data.py restore    빌드 후 — 제자리에 돌려 놓는다

빌드가 실패해도 자료는 `dist\\_keep\\` 에 그대로 남는다. 다음 빌드의 `stash` 는 그
자리가 이미 차 있으면 덮어쓰지 않고 옆에 번호를 붙여 둔다 — 구해 둔 것을 구하는
과정에서 잃는 것이 가장 나쁘다.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "HomeSpread"
KEEP = ROOT / "dist" / "_keep"

#: 빌드가 만들지 않는 것들 — 즉, 지워지면 되찾을 수 없는 것들.
PRECIOUS = ("backups", "logs", "settings.json")


def _free(target: Path) -> Path:
    """`target` 이 이미 있으면 옆자리를 찾아 준다. 덮어쓰지 않는다."""
    if not target.exists():
        return target
    for n in range(1, 1000):
        candidate = target.with_name(f"{target.name}-{n}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"둘 자리를 찾지 못했다: {target}")


def stash() -> int:
    if not DIST.is_dir():
        print("치울 것 없음 (dist\\HomeSpread 가 아직 없다)")
        return 0
    moved = []
    for name in PRECIOUS:
        source = DIST / name
        if not source.exists():
            continue
        KEEP.mkdir(parents=True, exist_ok=True)
        target = _free(KEEP / name)
        shutil.move(str(source), str(target))
        moved.append(target.name)
    if moved:
        print(f"빌드가 지우지 못하게 치워 둔다: {', '.join(moved)} -> dist\\_keep\\")
    else:
        print("치울 것 없음 (아직 실행한 적이 없는 폴더다)")
    return 0


def restore() -> int:
    if not KEEP.is_dir():
        return 0
    DIST.mkdir(parents=True, exist_ok=True)
    returned = []
    for source in sorted(KEEP.iterdir()):
        # 번호가 붙은 것(backups-1 …)은 손대지 않는다. 사람이 보고 정해야 한다.
        if source.name not in PRECIOUS:
            continue
        target = DIST / source.name
        if target.exists():
            # 빌드 사이에 새로 생겼다면 그쪽을 남긴다 — 합치는 판단은 우리 것이 아니다.
            print(f"[!] {target} 가 이미 있어 돌려놓지 않는다. dist\\_keep\\ 에 그대로 있다")
            continue
        shutil.move(str(source), str(target))
        returned.append(source.name)
    if returned:
        print(f"제자리로 돌려놓음: {', '.join(returned)}")
    left = [p.name for p in KEEP.iterdir()] if KEEP.is_dir() else []
    if left:
        print(f"[!] dist\\_keep\\ 에 남은 것: {', '.join(left)} — 직접 확인해 주세요")
    elif KEEP.is_dir():
        KEEP.rmdir()
    return 0


def main() -> int:
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "stash":
        return stash()
    if what == "restore":
        return restore()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
