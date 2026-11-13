"""버전 한 곳.

전역 규칙(2026-08-09)은 버전을 `shared_vars.h` 에 두라고 정한다. 그 규칙이 지키려는
것은 파일 이름이 아니라 **선언이 한 곳뿐이라는 것**이므로, 파이썬 프로젝트인 여기서는
이 모듈이 그 자리다. 창 제목·로그·`__version__` 이 모두 여기만 읽는다.

패치 숫자는 빌드할 때마다 `scripts/bump_build.py` 이 하나 올린다 (99 다음은 0).
목적은 화면에 보이는 것이 방금 만든 그 exe 가 맞는지 확인하는 것이다 — 고쳤는데
그대로인 것 같을 때, 패치 숫자와 빌드 시각을 보면 낡은 exe 를 실행했는지 알 수 있다.
"""

from __future__ import annotations

from .product import NAME

VERSION_MAJOR = 1
VERSION_MINOR = 0
VERSION_PATCH = 22

# 빌드 시각. 소스에서 바로 실행하면 빌드한 적이 없으므로 비어 있다.
BUILD_STAMP = "2026-11-13 macOS Chinese port"

VERSION_TEXT = f"v{VERSION_MAJOR:02d}.{VERSION_MINOR:02d}.{VERSION_PATCH:02d}-mac.zh.1"
VERSION_TUPLE = (VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH)


def version_line() -> str:
    """로그와 정보 창에 쓰는 한 줄."""
    return f"{NAME} {VERSION_TEXT}" + (f" (빌드 {BUILD_STAMP})" if BUILD_STAMP else "")
