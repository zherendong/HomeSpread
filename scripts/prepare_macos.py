"""为 macOS 应用准备图标、对应依赖的中文清单、许可原文和源码包。"""
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
        license_name = meta.get("License-Expression") or meta.get("License") or "详见附带许可原文"
        license_name = license_name.splitlines()[0][:120].replace("|", "/")
        home = meta.get("Home-page") or next(iter(meta.get_all("Project-URL") or []), "")
        rows.append(f"| {name} | {version} | {license_name} | {', '.join(copied) or home} |")
        inventory.append({"name": name, "version": version, "license": license_name, "license_files": copied})
    (OUT / "THIRD-PARTY-NOTICES.md").write_text(
        "# macOS 版第三方组件\n\n来自 requirements-macos.lock 的运行时依赖。原始许可文件在 third_party_licenses/。\n\n"
        "HomeSpread 修改版遵循 GPL-3.0-or-later，Qt/PySide6 还提供 LGPL/GPL/商业许可选项。\n\n"
        "| 组件 | 版本 | 许可 | 原文 |\n|---|---|---|---|\n" + "\n".join(rows) + "\n", encoding="utf-8")
    (OUT / "dependency-inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2))
    # 使用明确的源码与文档白名单，不把设备布局、缓存、设置、日志或凭据加入分发包。
    source_files = set()
    # Research is corresponding-source material only, never an executable import.
    for folder in ("src", "tests", "scripts", "assets", "research"):
        source_files.update(p for p in (ROOT / folder).rglob("*")
                            if p.is_file() and "__pycache__" not in p.parts)
    for pattern in ("*.md", "*.spec", "*.command", "*.bat", "*.ps1", "requirements*", "LICENSE", ".gitignore"):
        source_files.update(p for p in ROOT.glob(pattern) if p.is_file())
    for folder in ("_workspace", ".claude"):
        source_files.update((ROOT / folder).rglob("*.md"))
    source_files.update((ROOT / "_workspace/screenshots").glob("*.png"))
    source_files.update(p for p in (ROOT / "third_party_licenses").iterdir() if p.is_file())
    source_files.update((ROOT / "packaging").glob("*.json"))
    source_files.add(ROOT / ".github/FUNDING.yml")
    # Drafts are private data even if a user saves one beneath a source directory.
    private_parts = {"drafts", "backups", "logs", "pairing", "cache", "__pycache__", "evidence", "preflight_reports"}
    source_files = {path for path in source_files
                    if path.suffix.lower() not in {".hsdraft", ".hsevidence", ".hspreflight"}
                    and not private_parts.intersection(path.relative_to(ROOT).parts)}
    with zipfile.ZipFile(OUT / "HomeSpread-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_files):
            archive.write(path, "HomeSpread/" + path.relative_to(ROOT).as_posix())
    print(f"已生成 {len(rows)} 个组件的许可说明和包含 {len(source_files)} 个文件的源码包")


if __name__ == "__main__":
    main()
