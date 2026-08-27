# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 명세 — 파이썬이 없는 PC 에서도 실행되는 폴더 하나.

왜 명세 파일인가: 명령줄 옵션으로 하면 옵션이 어딘가의 배치 파일에만 남고,
왜 그 옵션을 넣었는지는 아무 데도 남지 않는다. 아래 세 가지는 이유를 알아야
나중에 지우지 않는다.

1. `collect_all("pymobiledevice3")`
   이 라이브러리는 기기와 말하는 데 쓰는 자료 파일(플러그인·프로토콜 정의)을
   패키지 안에 두고, 일부 모듈을 실행 중에 이름으로 찾아 불러온다. 정적 분석만으로는
   따라오지 않아, 묶은 exe 가 "기기를 못 찾음"으로 실패한다.

2. `console=False`
   창이 있는 앱이다. 진단은 화면이 아니라 `logs/` 에 남기기로 되어 있으므로
   (`app.py` 머리말) 검은 콘솔 창을 함께 띄울 이유가 없다.

3. Qt 모듈 제외 목록
   PySide6-Essentials 를 써도 이 앱이 쓰지 않는 모듈이 딸려 온다. 지운 만큼
   내려받을 파일이 작아진다. 지운 것을 쓰는 곳이 생기면 exe 만 실패하고
   소스 실행은 멀쩡하므로, 여기 목록은 늘리기보다 줄이는 쪽으로 손댄다.

5. `COLLECT(...)` — 단일 exe 가 아니라 폴더로 낸다
   단일 exe 는 실행할 때마다 자기 안(72MB)을 임시 폴더에 푼다. 그 시간이 **매번**
   붙는다. 실측(2026-08-21): 단일 exe 21초, 그중 16.5초가 압축 해제 — 우리 파이썬
   코드는 그동안 시작조차 하지 않는다. 폴더로 내면 풀 것이 없어 **2.9초**다.
   대가는 두 가지다. 건네줄 것이 파일 하나가 아니라 폴더 하나가 되고(zip 이나
   설치본으로 감싼다), 펼친 크기가 72MB → 169MB 로 늘어난다. 시작 시간 7배를
   주고 사기에 싼 값이고, 스토어(MSIX)도 어차피 이 모양을 요구한다.

6. `Splash(...)` 와 `tkinter` 를 지우지 않는 것
   폴더 배포에서도 **첫 실행**은 8.4초 걸린다 — 파일 수백 개를 처음 읽어 들이고
   백신이 그것을 훑는 시간이다. 그 구간에는 Qt 가 아직 없으므로 우리가 창을 띄울
   방법이 없다. 부트로더가 직접 띄우는 이 그림만이 그 자리를 채운다(0.3초에 뜬다).
   그림은 Tk 로 그려지므로 위 제외 목록에서 `tkinter` 를 빼면 안 된다 — 빼는 순간
   그림이 조용히 사라진다.

7. 라이선스 원문 싣기
   이 프로그램은 GPL 이고, 함께 실려 오는 라이브러리들도 저마다 "고지를 함께
   전달하라"고 요구한다. exe 하나만 건네받은 사람도 그 글을 읽을 수 있어야 하므로
   원문을 함께 싣고, 정보 창이 꺼내 보여준다. 폴더 배포에서는 `_MEIPASS` 가 곧
   그 폴더라 지워지지 않는다.

8. `version=` 와 `icon=` — exe 가 자기가 무엇인지 말하게 한다
   2026-08-26 에 Defender 가 이 exe 를 `Trojan:Win32/Bearfoos.B!ml` 로 격리했다.
   `!ml` 은 서명 목록에 걸린 것이 아니라 **기계학습의 추정**이고, 그 추정이 나쁜 쪽으로
   기우는 조건이 우리 것에 다 있었다 — 서명 없음, 아이콘 없음, 회사·제품·설명이 전부
   비어 있는 버전 리소스, 그리고 PyInstaller 부트로더. 서명은 스토어가 대신 해 주고
   부트로더는 우리가 고를 수 없지만, **뒤의 둘은 우리가 채울 수 있다.** 채운다고 탐지가
   반드시 사라진다는 보장은 없다. 다만 비워 두는 것은 사용자에게도 손해다 — 받은 사람이
   속성 창을 열어도 이것이 무엇이고 누가 만들었는지 알 방법이 없다.

   버전 리소스는 손으로 적지 않고 `ipsm.version` 과 `ipsm.product` 에서 **빌드할 때
   짓는다.** 전역 규칙(2026-08-09)이 지키려는 것은 선언이 한 곳이라는 것이고, 여기에
   숫자를 또 적으면 빌드마다 올라가는 패치 번호와 갈라선다.
"""

import os
import sys

from PyInstaller.utils.hooks import collect_all

sys.path.insert(0, os.path.join(SPECPATH, "src"))  # noqa: F821 — PyInstaller 가 준다
from ipsm import product, version  # noqa: E402

pmd_datas, pmd_binaries, pmd_hidden = collect_all("pymobiledevice3")

# --- exe 의 버전 리소스 -------------------------------------------------------
# Windows 가 속성 창에 보여주는 칸들. 숫자는 `version.py` 에서만 온다.
# 네 자리를 요구하므로 세 자리 뒤에 0 을 붙인다 — MSIX 판 번호와 같은 모양이다.
_VER = version.VERSION_TUPLE + (0,)
_VER_TEXT = ".".join(str(n) for n in _VER)
_VERSION_RES = os.path.join(SPECPATH, "build", "file_version_info.txt")  # noqa: F821
os.makedirs(os.path.dirname(_VERSION_RES), exist_ok=True)
with open(_VERSION_RES, "w", encoding="utf-8") as fp:
    fp.write(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={_VER}, prodvers={_VER},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', {product.PUBLISHER!r}),
         StringStruct('FileDescription', {f"{product.NAME} — {product.TAGLINE}"!r}),
         StringStruct('FileVersion', {_VER_TEXT!r}),
         StringStruct('InternalName', {product.NAME!r}),
         StringStruct('LegalCopyright', {product.COPYRIGHT!r}),
         StringStruct('OriginalFilename', {f"{product.NAME}.exe"!r}),
         StringStruct('ProductName', {product.NAME!r}),
         StringStruct('ProductVersion', {_VER_TEXT!r})]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    )

a = Analysis(
    ["src/ipsm/app.py"],
    pathex=["src"],
    binaries=pmd_binaries,
    datas=pmd_datas
    + [
        ("LICENSE", "."),
        ("THIRD-PARTY-NOTICES.md", "."),
        ("PRIVACY.md", "."),
        ("third_party_licenses", "third_party_licenses"),
    ],
    hiddenimports=pmd_hidden
    + [
        "ipsm.ui.main_window",
        "ipsm.ui.canvas",
        "ipsm.ui.tiles",
        "ipsm.ui.worker",
        "ipsm.ui.guide",
        "ipsm.apple_devices",
        "ipsm.i18n",
        "ipsm.translations_en",
        "ipsm.device",
        "ipsm.iconstate",
        "ipsm.layout",
        "ipsm.backup",
        "ipsm.icons",
        "ipsm.paths",
        "ipsm.version",
        "ipsm.product",
        "ipsm.ui.about",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # tkinter 는 제외하지 않는다 — 시작 그림(Splash)이 Tk 로 그려진다.
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        "PySide6.Qt3DCore",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtBluetooth",
        "PySide6.QtPositioning",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtDesigner",
        "PySide6.QtHelp",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# 창이 뜨기 전 몇 초 동안 사용자가 보는 유일한 것. `scripts/make_splash.py` 가 그린다.
splash = Splash(
    "assets/splash.png",
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,  # 그림 자체는 exe 안에 — 부트로더가 폴더를 읽기 전에 띄워야 한다
    [],
    exclude_binaries=True,  # 나머지는 COLLECT 가 `_internal\` 로 모은다
    name="HomeSpread",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX 로 줄인 exe 는 백신이 자주 막는다. 크기보다 실행되는 것이 낫다
    runtime_tmpdir=None,
    console=False,
    version=_VERSION_RES,  # 위 8번 — 비어 있는 버전 리소스는 오탐을 부른다
    icon=os.path.join(SPECPATH, "assets", "app.ico"),  # noqa: F821
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    splash.binaries,
    strip=False,
    upx=False,
    name="HomeSpread",
)
