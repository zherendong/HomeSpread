"""Windows 쪽 준비물(Apple Devices / iTunes)이 있는지 본다.

iPhone 과 말을 주고받는 일은 우리가 직접 하지 않는다. Apple 이 만든 구성요소(Apple
Devices 앱이나 iTunes 에 딸려 오는 Apple Mobile Device Support)가 USB 를 맡고, 우리는
그것이 열어 둔 **127.0.0.1:27015** 로 이야기한다. 그래서 이 하나가 없으면 다른 모든
것이 갖춰져 있어도 아무 일도 일어나지 않는다.

여기서 보는 것은 두 가지이고, 둘은 다르다.

* **지금 말이 통하는가** — 27015 가 열려 있는가. 이것이 진짜 답이다. 무엇이 열었든
  상관없다.
* **설치는 되어 있는가** — 자리를 보고 짐작한다. 설치는 됐는데 아직 안 뜬 경우와,
  아예 없는 경우에 사용자에게 할 말이 다르기 때문이다. 앞의 사람에게 "스토어에서
  받으세요"라고 하면 없는 길을 다시 걷게 만든다.

설치 여부를 자리로 짐작하는 것은 정확하지 않을 수 있다 — Apple 이 폴더 이름을 바꾸면
못 찾는다. 그래서 **틀렸을 때 손해가 작은 쪽으로** 쓴다. 27015 가 열려 있으면 설치
여부는 묻지도 않고 통과시키고, 못 찾았을 때도 막지 않고 안내만 한다.
"""

from __future__ import annotations

import logging
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger("apple")

#: Store 에서 이 앱을 가리키는 이름. 딥링크와 설치 자리 이름에 함께 쓰인다.
STORE_PACKAGE = "AppleInc.AppleDevices_nzyj5cx40ttqa"
STORE_LINK = f"ms-windows-store://pdp/?PFN={STORE_PACKAGE}"
#: 딥링크가 듣지 않을 때(지역·버전에 따라 그렇다) 검색으로라도 데려다 준다.
STORE_SEARCH = "ms-windows-store://search/?query=Apple%20Devices"

MUX_HOST = "127.0.0.1"
MUX_PORT = 27015


@dataclass(frozen=True)
class Presence:
    """지금 PC 가 iPhone 과 말할 준비가 되어 있는가."""

    running: bool
    installed: bool
    where: str  # 무엇을 보고 그렇게 판단했는지 — 로그용이라 옮기지 않는다

    @property
    def ready(self) -> bool:
        return self.running


def _muxer_listening(timeout: float = 0.4) -> bool:
    """27015 가 열려 있는가. 열려 있으면 곧바로, 없으면 곧바로 거절당한다.

    같은 PC 안이라 기다릴 일이 거의 없지만, 방화벽이 응답을 삼키는 드문 경우가 있어
    시간 제한을 둔다. 화면을 그리는 실타래에서 부르므로 오래 잡고 있으면 안 된다.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((MUX_HOST, MUX_PORT)) == 0
    except OSError as exc:  # 지역 설정이 깨졌거나 소켓 자체를 못 만드는 PC
        log.debug("27015 확인 중 예외: %r", exc)
        return False


def _folder(*parts: str) -> Optional[Path]:
    root = os.environ.get(parts[0])
    if not root:
        return None
    path = Path(root).joinpath(*parts[1:])
    return path if path.exists() else None


def _installed_where() -> Optional[str]:
    """설치 자리를 하나라도 찾으면 그 자리 이름을 돌려준다."""
    candidates = [
        ("LOCALAPPDATA", "Packages", STORE_PACKAGE),          # Store 로 받은 Apple Devices
        ("ProgramFiles", "Common Files", "Apple", "Mobile Device Support"),
        ("ProgramFiles(x86)", "Common Files", "Apple", "Mobile Device Support"),
        ("CommonProgramFiles", "Apple", "Mobile Device Support"),  # iTunes 에 딸려 오는 쪽
    ]
    for parts in candidates:
        found = _folder(*parts)
        if found is not None:
            return str(found)
    return None


def look() -> Presence:
    """지금 상태를 본다. 부를 때마다 새로 본다 — 사용자가 방금 설치했을 수 있다."""
    if _muxer_listening():
        return Presence(running=True, installed=True, where=f"{MUX_HOST}:{MUX_PORT}")
    where = _installed_where()
    return Presence(running=False, installed=where is not None, where=where or "-")
