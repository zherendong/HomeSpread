"""Prepare icon, exact dependency notices, and corresponding source for .app."""
import json
import zipfile
from importlib.metadata import distribution
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "macos-resources"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    Image.open(ROOT / "assets/logo/Square44x44Logo.targetsize-256.png").convert("RGBA").save(
        OUT / "HomeSpread.icns", format="ICNS")
    licenses = OUT / "third_party_licenses"
    licenses.mkdir(exist_ok=True)
    rows, inventory = [], []
    for line in (ROOT / "requirements-macos.lock").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        name, version = line.split("==")
        dist = distribution(name)
        if dist.version != version:
            raise RuntimeError(f"{name}: installed {dist.version}, lock requires {version}")
        meta = dist.metadata
        copied = []
        for file in dist.files or []:
            if file.name.lower().startswith(("license", "copying", "notice")):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    target = f"{name}-{version}-{len(copied)}.txt"
                    (licenses / target).write_bytes(source.read_bytes())
                    copied.append(target)
        license_name = meta.get("License-Expression") or meta.get("License") or "See included license"
        license_name = license_name.splitlines()[0][:120].replace("|", "/")
        home = meta.get("Home-page") or next(iter(meta.get_all("Project-URL") or []), "")
        rows.append(f"| {name} | {version} | {license_name} | {', '.join(copied) or home} |")
        inventory.append({"name": name, "version": version, "license": license_name, "license_files": copied})
    (OUT / "THIRD-PARTY-NOTICES.md").write_text(
        "# macOS 版第三方组件\n\n来自 requirements-macos.lock 的运行时依赖。原始许可文件在 third_party_licenses/。\n\n"
        "HomeSpread 修改版遵循 GPL-3.0-or-later，Qt/PySide6 还提供 LGPL/GPL/商业许可选项。\n\n"
        "| 组件 | 版本 | 许可 | 原文 |\n|---|---|---|---|\n" + "\n".join(rows) + "\n", encoding="utf-8")
    (OUT / "dependency-inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2))
    # Explicit allowlist: never include device layouts, caches, settings, logs,
    # environment files, or credentials in a distributable source archive.
    source_files = set()
    for folder in ("src", "tests", "scripts", "assets"):
        source_files.update(p for p in (ROOT / folder).rglob("*")
                            if p.is_file() and "__pycache__" not in p.parts)
    for pattern in ("*.md", "*.spec", "*.command", "requirements*", "LICENSE"):
        source_files.update(p for p in ROOT.glob(pattern) if p.is_file())
    source_files.update((ROOT / "_workspace/02_contracts").glob("*.md"))
    source_files.add(ROOT / "_workspace/04_macos-qa_final-report.md")
    with zipfile.ZipFile(OUT / "HomeSpread-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_files):
            archive.write(path, "HomeSpread/" + path.relative_to(ROOT).as_posix())
    print(f"Prepared {len(rows)} dependency notices and {len(source_files)} source files")


if __name__ == "__main__":
    main()
