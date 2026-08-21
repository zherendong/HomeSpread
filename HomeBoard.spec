# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 명세 — 파이썬이 없는 PC 에서도 실행되는 단일 exe.

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

5. `Splash(...)` 와 `tkinter` 를 지우지 않는 것
   단일 exe 는 실행할 때마다 자기 안(약 74MB)을 임시 폴더에 푼다. 그 구간에는
   우리 파이썬 코드가 아직 시작조차 하지 않으므로 Qt 로는 아무것도 띄울 수 없다.
   부트로더가 직접 띄우는 이 그림만이 그 몇 초를 채운다. 그림은 Tk 로 그려지므로
   위 제외 목록에서 `tkinter` 를 빼면 안 된다 — 빼는 순간 그림이 조용히 사라진다.

4. 라이선스 원문 싣기
   이 프로그램은 GPL 이고, 함께 실려 오는 라이브러리들도 저마다 "고지를 함께
   전달하라"고 요구한다. exe 하나만 건네받은 사람도 그 글을 읽을 수 있어야 하므로
   원문을 exe 안에 넣고, 정보 창이 꺼내 보여준다. 읽기만 하니 `_MEIPASS` 가
   끝날 때 지워지는 것은 문제가 되지 않는다 — 지워져서 곤란한 것은 백업뿐이다.
"""

from PyInstaller.utils.hooks import collect_all

pmd_datas, pmd_binaries, pmd_hidden = collect_all("pymobiledevice3")

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

# 압축을 푸는 동안 사용자가 보는 유일한 것. `scripts/make_splash.py` 가 그린다.
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
    a.binaries,
    a.datas,
    splash,
    splash.binaries,
    [],
    name="HomeBoard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX 로 줄인 exe 는 백신이 자주 막는다. 크기보다 실행되는 것이 낫다
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
