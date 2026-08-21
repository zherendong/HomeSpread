"""로그·백업·아이콘을 어디에 둘 것인가.

파이썬으로 실행할 때는 소스 트리가 곧 작업 폴더다. 그런데 exe 로 묶으면
`__file__` 은 임시 폴더(`_MEIPASS`) 안을 가리키고, 그 폴더는 **프로그램이 끝나면
지워진다.** 거기에 백업을 쓰면 백업이 남지 않는다. 이 앱에서 백업이 남지 않는 것은
단순한 불편이 아니라 안전 장치가 통째로 없어지는 것이므로(REQ-010), 얼어붙은
실행에서는 자료를 **exe 가 놓인 폴더**에 둔다. 들고 다니는 프로그램이라, 옆에
`logs/` `backups/` 가 함께 보이는 편이 사용자에게 가장 찾기 쉽다.

쓸 수 없는 곳에 exe 가 놓였다면(Program Files 등) **조용히 다른 데로 옮기지 않는다.**
백업이 어디 있는지는 사용자가 알아야 하는 정보다. 모르는 곳에 남은 백업은 없는
백업과 같으므로, 그 경우에는 옮기지 말고 말해 준다 — `ensure_ready()`.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Optional

# i18n 은 자리를 물어볼 때만 paths 를 들여온다 — 서로 물고 늘어지지 않는다.
from .i18n import tr

#: 프로그램이 스스로 만드는 폴더. 없으면 만든다.
DATA_DIRS = ("logs", "backups", "cache")


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def data_root() -> Path:
    """logs · backups · cache 를 담을 폴더."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _writable(path: Path) -> bool:
    """실제로 파일을 하나 만들어 본다.

    `os.access` 는 Windows 에서 믿을 것이 못 된다 — 읽기 전용 속성만 보고 ACL 을
    보지 않아, 쓸 수 없는 폴더를 쓸 수 있다고 답하는 경우가 있다.
    """
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix=".wtest", delete=True):
            return True
    except Exception:
        return False


def ensure_ready() -> tuple[Path, str | None]:
    """자료 폴더를 만들어 두고, 못 만들었으면 사람이 읽을 이유를 함께 돌려준다.

    창이 뜬 뒤에 백업을 만들려다 실패하는 것보다, 시작할 때 한 번에 확인하는 편이
    낫다. 그때는 아직 기기에 아무것도 쓰지 않은 상태이기 때문이다.

    돌려주는 것: (자료 폴더, 문제가 있으면 그 설명 / 없으면 None)
    """
    root = data_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
        for name in DATA_DIRS:
            (root / name).mkdir(exist_ok=True)
        (root / "cache" / "icons").mkdir(exist_ok=True)
    except Exception as exc:
        return root, tr(
            "'{where}' 에 폴더를 만들 수 없습니다 ({why}).\n"
            "쓰기 권한이 있는 폴더(예: 바탕화면, 문서)로 프로그램을 옮긴 뒤 다시 실행해 주세요."
        ).format(where=root, why=exc.__class__.__name__)

    if not _writable(root / "backups"):
        return root, tr(
            "'{where}' 에 파일을 쓸 수 없습니다.\n"
            "이 앱은 홈화면을 바꾸기 전에 반드시 백업을 남깁니다. 백업을 쓸 수 없으면\n"
            "적용도 하지 않습니다. 쓰기 권한이 있는 폴더로 프로그램을 옮겨 주세요."
        ).format(where=root / "backups")

    return root, None


def bundled(name: str) -> Optional[Path]:
    """함께 실려 온 읽기 전용 파일(라이선스 원문 등)의 자리.

    자료 폴더(`data_root`)와 일부러 나눠 둔다. 이쪽은 **우리가 넣어 준 것**이고
    저쪽은 **프로그램이 만드는 것**이다. exe 로 묶이면 이쪽은 `_MEIPASS` 안이라
    끝날 때 지워지지만, 읽기만 하므로 상관없다 — 지워져서 곤란한 것은 백업뿐이다.

    없으면 `None` 을 준다. 라이선스 파일이 빠진 채 묶여도 프로그램이 죽지는 않아야
    하고, 대신 화면이 "찾을 수 없습니다"라고 말한다.
    """
    if is_frozen():
        here = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        here = Path(__file__).resolve().parents[2]
    found = here / name
    return found if found.exists() else None
