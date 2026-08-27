# -*- coding: utf-8 -*-
r"""MSIX 포장 — 매니페스트를 짓고, 담을 것만 모아 놓고, 필요하면 등록한다.

**왜 `dist\HomeSpread\` 를 그대로 싸지 않는가:** 그 폴더는 실행하면 자기 옆에
`logs\`·`backups\`·`settings.json` 을 만든다. 전부 **이 PC 에서 나온 사용자
자료**다. 그대로 싸면 남의 기기 기록이 스토어에 올라간다. 그래서 담을 것만
`dist\msix\` 로 옮겨 놓고 거기서 싼다.

**왜 판 번호 끝자리가 0 인가:** 스토어는 마지막 자리를 자기가 쓴다고 못박고
있어서 0 이 아닌 판을 거부한다. `version.py` 의 세 자리 뒤에 0 을 붙인다.

    .venv/Scripts/python.exe scripts/make_msix.py stage           # 담을 것만 모은다
    .venv/Scripts/python.exe scripts/make_msix.py stage --dev     # 시험용 신원으로
    .venv/Scripts/python.exe scripts/make_msix.py register        # 느슨한 등록(A단계)
    .venv/Scripts/python.exe scripts/make_msix.py unregister
    .venv/Scripts/python.exe scripts/make_msix.py pack            # .msix 로 싼다(B단계)
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ipsm import product, version  # noqa: E402

BUILD = ROOT / "dist" / "HomeSpread"
STAGE = ROOT / "dist" / "msix"
LOGOS = ROOT / "assets" / "logo"
PACKAGES = ROOT / "dist" / "packages"

#: 실행하면 생기는 것들. 사용자 자료이므로 포장에 넣지 않는다.
RUNTIME_LEAVINGS = {"logs", "backups", "cache", "settings.json"}

#: 판이 서로 다른 두 자리에서 선언되지 않도록 여기서만 짓는다.
MSIX_VERSION = (
    f"{version.VERSION_MAJOR}.{version.VERSION_MINOR}.{version.VERSION_PATCH}.0"
)

MANIFEST = r"""<?xml version="1.0" encoding="utf-8"?>
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
  IgnorableNamespaces="uap rescap">

  <Identity
    Name="{name}"
    Publisher="{publisher}"
    Version="{version}"
    ProcessorArchitecture="x64" />

  <Properties>
    <DisplayName>{display}</DisplayName>
    <PublisherDisplayName>{publisher_display}</PublisherDisplayName>
    <Logo>Assets\StoreLogo.png</Logo>
    <Description>{description}</Description>
  </Properties>

  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop"
                        MinVersion="10.0.17763.0"
                        MaxVersionTested="10.0.26100.0" />
  </Dependencies>

  <Resources>
    <Resource Language="ko-KR" />
    <Resource Language="en-US" />
  </Resources>

  <Applications>
    <Application Id="App"
                 Executable="{executable}"
                 EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements
        DisplayName="{display}"
        Description="{description}"
        BackgroundColor="#1b1e26"
        Square150x150Logo="Assets\Square150x150Logo.png"
        Square44x44Logo="Assets\Square44x44Logo.png">
        <uap:DefaultTile
          Wide310x150Logo="Assets\Wide310x150Logo.png"
          Square71x71Logo="Assets\Square71x71Logo.png"
          Square310x310Logo="Assets\Square310x310Logo.png" />
      </uap:VisualElements>
    </Application>
  </Applications>

  <Capabilities>
    <!-- 데스크톱 앱을 AppContainer 밖에서 돌린다. 이것이 없으면 우리 프로그램은
         127.0.0.1:27015 로 Apple 구성요소와 말할 수 없고, 문서 폴더에도 쓸 수 없다. -->
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
</Package>
"""


def identity(dev: bool) -> dict[str, str]:
    path = ROOT / "packaging" / ("identity.dev.json" if dev else "identity.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in ("Name", "Publisher", "PublisherDisplayName") if k not in data]
    if missing:
        raise SystemExit(f"{path.name} 에 {missing} 가 없다")
    if any("PUT-" in str(v) for v in data.values()):
        raise SystemExit(
            f"{path.name} 이 아직 채워지지 않았다 — Partner Center 의 [패키지] 에 적힌\n"
            "Name · Publisher · PublisherDisplayName 을 그대로 옮겨 적어야 한다."
        )
    return data


def write_manifest(target: Path, dev: bool) -> Path:
    who = identity(dev)
    text = MANIFEST.format(
        name=escape(who["Name"]),
        publisher=escape(who["Publisher"], {'"': "&quot;"}),
        publisher_display=escape(who["PublisherDisplayName"]),
        version=MSIX_VERSION,
        display=escape(product.NAME),
        description=escape(f"{product.NAME} — {product.TAGLINE}"),
        executable=f"{product.NAME}.exe",
    )
    path = target / "AppxManifest.xml"
    path.write_text(text, encoding="utf-8")
    return path


def stage(dev: bool) -> Path:
    if not (BUILD / f"{product.NAME}.exe").exists():
        raise SystemExit(f"{BUILD} 에 exe 가 없다 — build_exe.bat 을 먼저 돌린다")

    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    for item in BUILD.iterdir():
        if item.name in RUNTIME_LEAVINGS:
            continue
        if item.is_dir():
            shutil.copytree(item, STAGE / item.name)
        else:
            shutil.copy2(item, STAGE / item.name)

    assets = STAGE / "Assets"
    assets.mkdir()
    for logo in sorted(LOGOS.glob("*.png")):
        shutil.copy2(logo, assets / logo.name)

    write_manifest(STAGE, dev)
    return STAGE


def _powershell(script: str) -> int:
    done = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        text=True,
    )
    return done.returncode


def register(dev: bool) -> int:
    path = stage(dev)
    print(f"등록: {path}")
    # 느슨한 등록은 서명을 요구하지 않는다. 대신 개발자 모드가 켜져 있어야 한다.
    return _powershell(f'Add-AppxPackage -Register "{path / "AppxManifest.xml"}"')


def unregister(dev: bool) -> int:
    name = identity(dev)["Name"]
    return _powershell(
        f'Get-AppxPackage "{name}" | Remove-AppxPackage; if (-not $?) {{ exit 0 }}'
    )


def _find_makeappx() -> Path | None:
    roots = [
        Path("C:/Program Files (x86)/Windows Kits/10/bin"),
        Path("C:/Program Files/Windows Kits/10/bin"),
        ROOT / "tools",
    ]
    found: list[Path] = []
    for base in roots:
        if base.exists():
            found.extend(base.rglob("x64/makeappx.exe"))
    # 여러 판이 깔려 있으면 가장 새것을 쓴다.
    return sorted(found)[-1] if found else None


def pack(dev: bool) -> int:
    tool = _find_makeappx()
    if tool is None:
        raise SystemExit(
            "makeappx.exe 를 찾지 못했다. Windows SDK 또는\n"
            "Microsoft.Windows.SDK.BuildTools 를 tools 아래에 풀어야 한다."
        )
    path = stage(dev)
    PACKAGES.mkdir(parents=True, exist_ok=True)
    out = PACKAGES / f"{product.NAME}_{MSIX_VERSION}_x64.msix"
    print(f"makeappx: {tool}")
    done = subprocess.run(
        [str(tool), "pack", "/o", "/d", str(path), "/p", str(out)], text=True
    )
    if done.returncode == 0:
        print(f"만들었다: {out} ({out.stat().st_size / 1_048_576:.1f} MB)")
    return done.returncode


def main(argv: list[str]) -> int:
    action = argv[1] if len(argv) > 1 else "stage"
    dev = "--dev" in argv
    if action == "stage":
        print(f"모았다: {stage(dev)}  (판 {MSIX_VERSION})")
        return 0
    if action == "register":
        return register(dev)
    if action == "unregister":
        return unregister(dev)
    if action == "pack":
        return pack(dev)
    raise SystemExit(f"모르는 명령: {action}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
