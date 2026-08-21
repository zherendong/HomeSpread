# -*- coding: utf-8 -*-
"""빌드할 때마다 패치 숫자를 하나 올리고 빌드 시각을 적는다.

전역 규칙(2026-08-09)의 pre-build 훅에 해당한다. 왜 필요한가: 고쳤는데 그대로인 것
같을 때, 화면의 패치 숫자가 방금 만든 숫자와 다르면 **낡은 exe 를 실행한 것**이다.
이 한 가지를 가려내려고 매 빌드마다 숫자를 올린다. 99 다음은 0 으로 돌아간다.

파일 시각(mtime)은 건드리지 않는다. 그 규칙은 git 이 같은 크기의 변경을 놓치는 것을
막으려는 것인데, 이 프로젝트는 git 저장소가 아니고 PyInstaller 는 mtime 으로 캐시를
판단하므로 과거 시각을 심으면 오히려 낡은 것을 다시 쓸 수 있다.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "src" / "ipsm" / "version.py"


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")

    match = re.search(r"^VERSION_PATCH = (\d+)$", text, re.MULTILINE)
    if match is None:
        print("[!] VERSION_PATCH 를 찾지 못했습니다:", TARGET)
        return 1
    patch = (int(match.group(1)) + 1) % 100
    text = text[: match.start()] + f"VERSION_PATCH = {patch}" + text[match.end() :]

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = re.sub(r'^BUILD_STAMP = ".*"$', f'BUILD_STAMP = "{stamp}"', text, count=1, flags=re.MULTILINE)

    TARGET.write_text(text, encoding="utf-8")

    major = re.search(r"^VERSION_MAJOR = (\d+)$", text, re.MULTILINE).group(1)
    minor = re.search(r"^VERSION_MINOR = (\d+)$", text, re.MULTILINE).group(1)
    print(f"버전 v{int(major):02d}.{int(minor):02d}.{patch:02d} (빌드 {stamp})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
