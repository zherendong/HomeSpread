# -*- coding: utf-8 -*-
r"""从 Windows 构建环境生成第三方许可清单和原文副本。

读取实际安装包的名称、版本、许可及来源，复制其许可原文到
third_party_licenses/。安装依赖后应重新生成，避免清单与分发内容不一致。
本脚本会重写清单并清理旧原文目录；不要用其它环境覆盖上游历史快照。
macOS 构建使用 scripts/prepare_macos.py 和 requirements-macos.lock。

    .\.venv\Scripts\python.exe scripts\gen_notices.py
"""

from __future__ import annotations

import shutil
from importlib.metadata import distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTICES = ROOT / "THIRD-PARTY-NOTICES.md"
TEXTS = ROOT / "third_party_licenses"

#: 仅构建时使用、不进入分发包的工具。只排除此处列出的项目。
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
    """优先读取 SPDX 标识，缺少时使用分类器中的许可字段。"""
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
    # 部分包的 License 字段包含完整原文，表格中只展示首行。
    return words[0][:60] if words else "（未声明）"


def _home_of(meta) -> str:
    home = meta.get("Home-page")
    if home:
        return home
    for key, value in meta.items():
        if key == "Project-URL" and value.lower().startswith(("source", "homepage", "repository")):
            return value.split(",", 1)[-1].strip()
    return ""


def _copy_text(dist, name: str, version: str) -> str:
    """复制发行包所附许可原文；找不到时返回空字符串。"""
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
        "# 第三方组件与许可证",
        "",
        "HomeSpread 使用以下组件。本文件由构建环境自动生成，",
        "`scripts/gen_notices.py` 读取实际安装的版本和许可信息。macOS 使用独立的锁文件及生成脚本。",
        "",
        f"共 {len(rows)} 个组件。各行的许可原文位于 `third_party_licenses/`。",
        "",
        "> HomeSpread 声明采用 GPL-3.0-or-later；设备通信库 `pymobiledevice3` 也采用该许可。",
        "> 第三方组件保留各自许可，原文不因翻译而改写。",
        "> 项目法律文本见 `LICENSE`，中文阅读说明见 `LICENSE.zh-CN.md`。",
        "",
        "| 组件 | 版本 | 许可元数据 | 原文 | 来源 |",
        "|--------|----|----------|------|--------|",
    ]
    for name, version, spdx, home, text in rows:
        link = f"[{text}](third_party_licenses/{text})" if text else "—"
        where = f"[{home}]({home})" if home.startswith("http") else "—"
        lines.append(f"| {name} | {version} | {spdx} | {link} | {where} |")
    lines.append("")
    lines.append(
        "仅用于构建、不进入分发包的工具（"
        + ", ".join(sorted(BUILD_ONLY))
        + "）已排除。"
    )
    lines.append("")

    NOTICES.write_text("\n".join(lines), encoding="utf-8")
    missing = [row[0] for row in rows if not row[4]]
    print(f"已记录 {len(rows)} 个组件，复制 {len(rows) - len(missing)} 份原文")
    if missing:
        print("未随包提供原文的组件：" + ", ".join(missing))


if __name__ == "__main__":
    main()
