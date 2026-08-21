# -*- coding: utf-8 -*-
r"""딸려 오는 라이브러리의 라이선스를 모아 적는다.

**왜 손으로 적지 않는가:** 목록은 `pip install` 한 번에 바뀐다. 손으로 적은 목록은
바뀐 줄 아무도 모르는 채 낡고, 낡은 라이선스 고지는 고지하지 않은 것과 같다. 그래서
설치된 것을 그대로 읽어 적는다 — 사람이 고칠 곳은 아래 `BUILD_ONLY` 뿐이다.

**무엇을 적는가:** 이름·판·라이선스·원산지, 그리고 각 꾸러미가 함께 넣어 둔 라이선스
원문. 원문은 `third_party_licenses/` 로 복사한다. MIT·BSD·Apache 는 모두 "저작권
고지와 허가문을 함께 전달하라"고 요구하므로, 이름만 적어서는 지킨 것이 아니다.

    .\.venv\Scripts\python.exe scripts\gen_notices.py
"""

from __future__ import annotations

import shutil
from importlib.metadata import distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTICES = ROOT / "THIRD-PARTY-NOTICES.md"
TEXTS = ROOT / "third_party_licenses"

#: exe 를 만드는 데만 쓰이고 exe 안에는 들어가지 않는 것들. 여기에 적힌 것만 빠진다.
BUILD_ONLY = {
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "altgraph",
    "pefile",
    "setuptools",
    "pip",
    "wheel",
}


def _license_of(meta) -> str:
    """SPDX 표기를 먼저 보고, 없으면 분류자에서 캐낸다."""
    spdx = meta.get("License-Expression")
    if spdx:
        return spdx
    marks = [
        value.split("::")[-1].strip()
        for key, value in meta.items()
        if key == "Classifier" and value.startswith("License ::")
    ]
    if marks:
        return " / ".join(dict.fromkeys(marks))
    words = (meta.get("License") or "").strip().splitlines()
    # 어떤 꾸러미는 License 칸에 원문을 통째로 넣는다 — 첫 줄만 쓴다.
    return words[0][:60] if words else "(표기 없음)"


def _home_of(meta) -> str:
    home = meta.get("Home-page")
    if home:
        return home
    for key, value in meta.items():
        if key == "Project-URL" and value.lower().startswith(("source", "homepage", "repository")):
            return value.split(",", 1)[-1].strip()
    return ""


def _copy_text(dist, name: str, version: str) -> str:
    """꾸러미가 넣어 둔 라이선스 원문을 옮겨 온다. 없으면 빈 문자열."""
    for file in dist.files or []:
        parts = [p.lower() for p in file.parts]
        if not any(p.startswith(("license", "copying", "notice")) for p in parts[-1:]):
            continue
        source = Path(dist.locate_file(file))
        if not source.is_file():
            continue
        target = TEXTS / f"{name}-{version}{source.suffix or '.txt'}"
        shutil.copyfile(source, target)
        return target.name
    return ""


def main() -> None:
    TEXTS.mkdir(exist_ok=True)
    for stale in TEXTS.glob("*"):
        stale.unlink()

    rows = []
    for dist in distributions():
        meta = dist.metadata
        name = meta["Name"]
        if not name or name.lower() in BUILD_ONLY:
            continue
        version = meta["Version"] or "?"
        rows.append(
            (
                name,
                version,
                _license_of(meta),
                _home_of(meta),
                _copy_text(dist, name, version),
            )
        )
    rows.sort(key=lambda row: row[0].lower())

    lines = [
        "# 함께 실려 오는 것들",
        "",
        "HomeBoard 는 아래 라이브러리 위에 서 있다. 이 파일은 손으로 적지 않는다 —",
        "`scripts/gen_notices.py` 가 설치된 것을 그대로 읽어 다시 쓴다.",
        "",
        f"꾸러미 {len(rows)}개. 각 줄의 **원문**은 `third_party_licenses/` 안의 파일이다.",
        "",
        "> **GPL 이 이 앱 전체의 라이선스를 정한다.** `pymobiledevice3` 가",
        "> GPL-3.0-or-later 이고 우리는 그것을 함께 실어 배포하므로, HomeBoard 자체도",
        "> GPL-3.0-or-later 로 공개한다. 자세한 것은 `LICENSE` 와 README 의 라이선스 절.",
        "",
        "| 꾸러미 | 판 | 라이선스 | 원문 | 원산지 |",
        "|--------|----|----------|------|--------|",
    ]
    for name, version, spdx, home, text in rows:
        link = f"[{text}](third_party_licenses/{text})" if text else "—"
        where = f"[{home}]({home})" if home.startswith("http") else "—"
        lines.append(f"| {name} | {version} | {spdx} | {link} | {where} |")
    lines.append("")
    lines.append(
        "exe 를 만드는 데만 쓰고 exe 안에는 들어가지 않는 것("
        + ", ".join(sorted(BUILD_ONLY))
        + ")은 뺐다."
    )
    lines.append("")

    NOTICES.write_text("\n".join(lines), encoding="utf-8")
    missing = [row[0] for row in rows if not row[4]]
    print(f"{len(rows)}개 기록 · 원문 {len(rows) - len(missing)}개 복사")
    if missing:
        print("원문을 함께 넣지 않은 꾸러미: " + ", ".join(missing))


if __name__ == "__main__":
    main()
