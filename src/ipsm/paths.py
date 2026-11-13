"""로그·백업·아이콘을 어디에 둘 것인가.

자리를 정하는 기준은 하나다. **잃으면 안 되는 것과 다시 만들 수 있는 것을 가른다.**

`backups/` 는 잃으면 안 된다. 이 앱은 홈화면 전체를 한 번에 덮어쓰고, 되돌릴 길은
백업뿐이다(REQ-010). `logs/` 도 같은 편에 둔다 — 사고가 난 뒤에 무슨 일이었는지
묻는 자리라, 사고보다 먼저 지워지면 소용이 없다. 반면 `cache/icons/` 는 다시
받으면 그만이다(287개에 7.4초).

그래서 자리는 셋이다.

1. **소스로 돌릴 때** — 프로젝트 폴더가 곧 자료 폴더다.

2. **폴더로 배포한 exe** — exe 가 놓인 폴더. 들고 다니는 프로그램이라, 옆에
   `logs/` `backups/` 가 함께 보이는 편이 사용자에게 가장 찾기 쉽다.
   (`__file__` 이나 `_MEIPASS` 를 쓰면 안 된다 — 폴더 배포에서는 `_internal/`
   안이고, 단일 exe 였다면 **프로그램이 끝나면 지워지는** 임시 폴더였다.)

3. **MSIX 로 포장했을 때** — exe 는 `C:\\Program Files\\WindowsApps\\...` 에 놓이고
   그 자리는 관리자 권한으로도 쓸 수 없다(2026-08-21 확인). 그러니 옆에 둘 수가
   없다. `%LOCALAPPDATA%` 도 답이 아니다 — 포장된 앱에서는 `Packages\\<이름>\\
   LocalCache\\` 로 조용히 옮겨져, 정확히 "사용자가 찾을 수 없는 곳"이 된다.
   그래서 **문서 폴더**에 우리 이름의 폴더를 만든다. 경로는 지어내지 않고
   `SHGetKnownFolderPath` 로 묻는다 — 문서 폴더를 다른 드라이브로 옮겨 둔 PC 에서
   `%USERPROFILE%\\Documents` 는 틀린 답이다.

`cache/` 만은 어느 경우든 **TEMP** 에 둔다. Windows 가 공간이 부족할 때 치워도
잃는 것이 없고, 백업이 있는 폴더가 아이콘 수백 개로 불어나지 않는다. 반대로
백업을 TEMP 에 두는 것은 **지우는 일을 OS 에 위임하는 것**이라 하지 않는다 —
저장 공간 센스가 켜진 PC 에서 임시 파일 정리는 기본 동작이다.

쓸 수 없는 곳이면 **조용히 다른 데로 옮기지 않는다.** 백업이 어디 있는지는
사용자가 알아야 하는 정보다. 모르는 곳에 남은 백업은 없는 백업과 같으므로,
그 경우에는 옮기지 말고 말해 준다 — `ensure_ready()`.
"""

from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from . import product

# i18n 은 자리를 물어볼 때만 paths 를 들여온다 — 서로 물고 늘어지지 않는다.
from .i18n import tr

#: 프로그램이 스스로 만드는 폴더. 없으면 만든다. 아이콘 캐시는 여기 없다 —
#: 저 둘과 수명이 다르고, 다른 자리(`cache_root`)에 산다.
DATA_DIRS = ("logs", "backups")

#: `GetCurrentPackageFamilyName` 이 "포장 밖"을 뜻할 때 돌려주는 값.
_APPMODEL_ERROR_NO_PACKAGE = 15700

#: FOLDERID_Documents. 문서 폴더의 **실제** 자리를 묻는 열쇠다.
_FOLDERID_DOCUMENTS = "FDD39AD0-238F-46AF-ADB4-6C85480369C7"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(text: str) -> _GUID:
    value = uuid.UUID(text)
    out = _GUID()
    out.Data1 = value.time_low
    out.Data2 = value.time_mid
    out.Data3 = value.time_hi_version
    out.Data4 = (ctypes.c_ubyte * 8)(*value.bytes[8:])
    return out


def package_family_name() -> Optional[str]:
    """이 프로세스가 MSIX 패키지 안에서 돌고 있으면 그 이름, 아니면 None.

    포장 여부를 파일 경로로 짐작하지 않는 이유: 느슨한 등록(개발자 모드)으로 돌리면
    파일은 제자리에 있으면서 신원만 패키지가 된다. 짐작은 그 경우를 틀리게 읽는다.
    """
    if sys.platform != "win32":
        return None
    try:
        fn = ctypes.windll.kernel32.GetCurrentPackageFamilyName
        length = ctypes.c_uint32(0)
        if fn(ctypes.byref(length), None) == _APPMODEL_ERROR_NO_PACKAGE:
            return None
        buffer = ctypes.create_unicode_buffer(length.value)
        if fn(ctypes.byref(length), buffer) != 0:
            return None
        return buffer.value or None
    except Exception:
        # 이 API 가 없는 옛 Windows. 포장이 아니었던 셈 치면 지금까지와 같이 동작한다.
        return None


def is_packaged() -> bool:
    """MSIX 로 설치돼 실행 중인가.

    `is_frozen()` 을 함께 묻는 이유가 있다. 개발용 파이썬이 Microsoft Store 판이면
    **소스로 돌려도** 패키지 신원이 잡힌다(실제로 이 프로젝트가 그렇다). 그때까지
    문서 폴더로 보내면 개발 중에 자료가 프로젝트 밖으로 흩어진다.
    """
    return is_frozen() and package_family_name() is not None


def documents_dir() -> Optional[Path]:
    """문서 폴더의 실제 자리. 묻지 못하면 None.

    `%USERPROFILE%\\Documents` 로 지어내면 안 된다 — 문서 폴더를 다른 드라이브로
    옮겨 둔 PC 가 흔하고, 그때 지어낸 경로는 아무도 보지 않는 빈 폴더가 된다.
    """
    if sys.platform != "win32":
        return None
    try:
        out = ctypes.c_wchar_p()
        rc = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(_guid(_FOLDERID_DOCUMENTS)), 0, None, ctypes.byref(out)
        )
        if rc != 0 or not out.value:
            return None
        try:
            return Path(out.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(out)
    except Exception:
        return None


def data_root() -> Path:
    """logs · backups · settings.json 을 담을 폴더. 잃으면 안 되는 것들의 자리."""
    override = os.environ.get("HOMESPREAD_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / product.NAME
    if is_packaged():
        documents = documents_dir()
        if documents is not None:
            return documents / product.NAME
        # 문서 폴더를 묻지 못한 아주 드문 경우. 사용자 폴더는 언제나 있다.
        return Path.home() / product.NAME
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def cache_root() -> Path:
    """다시 만들 수 있는 것의 자리 — 아이콘 캐시.

    TEMP 에 두는 것은 "지워도 좋다"는 선언이다. 아이콘은 실제로 그렇다. 백업은
    절대 여기 두지 않는다 — 저장 공간 센스가 임시 파일을 치우는 것은 사고가 아니라
    정상 동작이고, 그때 사라지는 백업은 사라졌다는 말조차 남기지 않는다.
    """
    override = os.environ.get("HOMESPREAD_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / product.NAME
    return Path(tempfile.gettempdir()) / f"{product.NAME}-cache"


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


def _cfa_hint() -> str:
    """"권한을 확인하세요"로는 빠져나올 수 없는 경우가 하나 있다.

    Windows 보안의 **제어된 폴더 액세스**(랜섬웨어 방지)는 허용 목록에 없는 앱이
    문서·바탕화면·사진 폴더에 쓰는 것을 막는다. 이때 폴더의 권한은 멀쩡하므로,
    권한을 아무리 들여다봐도 원인이 보이지 않는다. 2026-08-26 에 우리가 그 벽에
    부딪혔다 — `문서\\HomeSpread\\` 를 만들려다 막혔고, 화면에는 권한을 확인하라는
    말만 떴다.

    더 나쁜 것은 그 다음 줄이었다. 포장하지 않은 판에서는 "바탕화면이나 문서 폴더로
    옮기라"고 권했는데, **그 둘이 바로 제어된 폴더 액세스가 기본으로 지키는 자리다.**
    같은 벽으로 다시 보내는 안내였다. 그래서 이 한 줄을 네 갈래 모두에 붙인다.
    """
    if sys.platform != "win32":
        return tr("Check the folder permissions and available disk space in Finder.")
    return tr(
        "폴더 권한과 별개로, Windows 보안의 '제어된 폴더 액세스'가 막고 있을 수도\n"
        "있습니다. Windows 보안 › 바이러스 및 위협 방지 › 랜섬웨어 방지 에서\n"
        "이 앱을 허용해 주세요."
    )


def _cannot_write(where: Path) -> str:
    """쓸 수 없을 때 사용자에게 건넬 말.

    포장된 설치와 폴더 배포는 **할 수 있는 일이 다르다.** Store 로 설치한 앱은
    사용자가 옮길 수 없으므로, 옮기라는 안내는 그 경우 막다른 길이 된다.
    """
    if sys.platform == "darwin":
        return tr("Cannot write to '{where}'. A verified backup is required before changing the Home Screen. Check this folder's permissions in Finder.").format(where=where)
    if is_packaged():
        return tr(
            "'{where}' 에 파일을 쓸 수 없습니다.\n"
            "이 앱은 홈화면을 바꾸기 전에 반드시 백업을 남깁니다. 백업을 쓸 수 없으면\n"
            "적용도 하지 않습니다. 이 폴더의 쓰기 권한을 확인해 주세요."
        ).format(where=where) + "\n" + _cfa_hint()
    return tr(
        "'{where}' 에 파일을 쓸 수 없습니다.\n"
        "이 앱은 홈화면을 바꾸기 전에 반드시 백업을 남깁니다. 백업을 쓸 수 없으면\n"
        "적용도 하지 않습니다. 쓰기 권한이 있는 폴더로 프로그램을 옮겨 주세요."
    ).format(where=where) + "\n" + _cfa_hint()


def ensure_ready() -> tuple[Path, str | None]:
    """자료 폴더를 만들어 두고, 못 만들었으면 사람이 읽을 이유를 함께 돌려준다.

    창이 뜬 뒤에 백업을 만들려다 실패하는 것보다, 시작할 때 한 번에 확인하는 편이
    낫다. 그때는 아직 기기에 아무것도 쓰지 않은 상태이기 때문이다.

    아이콘 캐시를 못 만드는 것은 **막을 이유가 아니다.** 아이콘 없이도 편집은 되고,
    TEMP 는 언제 치워질지 모르는 자리라 실행 중에 없어질 수도 있다.

    돌려주는 것: (자료 폴더, 문제가 있으면 그 설명 / 없으면 None)
    """
    root = data_root()
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for name in DATA_DIRS:
            (root / name).mkdir(mode=0o700, exist_ok=True)
    except Exception as exc:
        if sys.platform == "darwin":
            return root, tr("Cannot create the data folder '{where}' ({why}). Check folder permissions and disk space in Finder.").format(where=root, why=exc.__class__.__name__)
        if is_packaged():
            return root, tr(
                "'{where}' 에 폴더를 만들 수 없습니다 ({why}).\n"
                "이 폴더의 쓰기 권한을 확인해 주세요."
            ).format(where=root, why=exc.__class__.__name__) + "\n" + _cfa_hint()
        return root, tr(
            "'{where}' 에 폴더를 만들 수 없습니다 ({why}).\n"
            "쓰기 권한이 있는 폴더(예: 바탕화면, 문서)로 프로그램을 옮긴 뒤 다시 실행해 주세요."
        ).format(where=root, why=exc.__class__.__name__) + "\n" + _cfa_hint()

    if not _writable(root / "backups"):
        return root, _cannot_write(root / "backups")

    try:
        (cache_root() / "icons").mkdir(mode=0o700, parents=True, exist_ok=True)
    except Exception as exc:
        # 아이콘은 다시 받으면 그만이다. 여기서 앱을 막지 않는다.
        del exc

    return root, None


def bundled(name: str) -> Optional[Path]:
    """함께 실려 온 읽기 전용 파일(라이선스 원문 등)의 자리.

    자료 폴더(`data_root`)와 일부러 나눠 둔다. 이쪽은 **우리가 넣어 준 것**이고
    저쪽은 **프로그램이 만드는 것**이다. 얼어붙은 실행에서 이쪽은 `_MEIPASS`(폴더
    배포에서는 `_internal/`) 안이고, 읽기만 하므로 그 안에 있어도 상관없다 —
    남아야 하는 것은 백업뿐이다.

    없으면 `None` 을 준다. 라이선스 파일이 빠진 채 묶여도 프로그램이 죽지는 않아야
    하고, 대신 화면이 "찾을 수 없습니다"라고 말한다.
    """
    if is_frozen():
        here = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        here = Path(__file__).resolve().parents[2]
    found = here / name
    return found if found.exists() else None
