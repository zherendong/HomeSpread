# -*- mode: python ; coding: utf-8 -*-
"""Self-contained native .app, ad-hoc signed for local use on this Mac."""
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH)
resources = root / "build" / "macos-resources"
datas = copy_metadata("pymobiledevice3")
datas += [(str(root / name), ".") for name in
          ("LICENSE", "LICENSE.zh-CN.md", "PRIVACY.md", "PRIVACY.zh-CN.md", "README.md", "README.zh-CN.md", "DOCUMENTATION.zh-CN.md", "PROVENANCE.zh-CN.md", "SECURITY_AUDIT.zh-CN.md")]
datas += [(str(resources / name), ".") for name in
          ("THIRD-PARTY-NOTICES.md", "HomeSpread-source.zip", "dependency-inventory.json")]
datas += [(str(resources / "third_party_licenses"), "third_party_licenses")]
datas += [(str(root / "_workspace/04_macos-qa_final-report.md"), "_workspace")]
datas += [(str(root / "_workspace/05_widget-duo-qa.md"), "_workspace")]
datas += [(str(root / "_workspace/06_offline-draft-qa.md"), "_workspace")]

a = Analysis(
    [str(root / "src/ipsm/app.py")], pathex=[str(root / "src")],
    datas=datas, binaries=[],
    hiddenimports=["ipsm.translations_en", "ipsm.translations_zh", "ipsm.device"],
    # No firmware tooling, web servers, shell, or Windows bootstrap in this app.
    excludes=["tkinter", "IPython", "pytest", "pip", "pip_audit", "setuptools",
              "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore",
              "PySide6.QtWebEngineWidgets", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="HomeSpread",
          debug=False, strip=False, upx=False, console=False,
          argv_emulation=False, target_arch="arm64", codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="HomeSpread")
app = BUNDLE(coll, name="HomeSpread.app", icon=str(resources / "HomeSpread.icns"),
             bundle_identifier="local.homespread.macos.zh",
             info_plist={"CFBundleName": "HomeSpread", "CFBundleDisplayName": "HomeSpread",
                         "CFBundleShortVersionString": "1.0.22", "CFBundleVersion": "1.0.22.3",
                         "CFBundleDevelopmentRegion": "zh_CN",
                         "CFBundleLocalizations": ["zh_CN", "en", "ko"],
                         "LSMinimumSystemVersion": "14.0", "NSHighResolutionCapable": True,
                         "NSHumanReadableCopyright": "GPL-3.0-or-later; HomeSpread contributors"})
