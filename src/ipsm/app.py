# HomeSpread — iPhone 홈화면을 PC 한 화면에서 보고 편집한다.
# Copyright (C) 2026 HomeSpread contributors
#
# 이 프로그램은 자유 소프트웨어입니다. 자유 소프트웨어 재단이 발표한 GNU 일반 공중
# 사용 허가서 3판 또는 (선택에 따라) 그 이후 판의 조건에 따라 재배포하거나 수정할
# 수 있습니다.
#
# 이 프로그램은 유용하게 쓰이기를 바라며 배포되지만 **어떠한 보증도 없습니다** —
# 상품성이나 특정 목적 적합성에 대한 묵시적 보증조차 없습니다. 자세한 것은 GNU 일반
# 공중 사용 허가서를 보십시오. 원문은 이 프로그램과 함께 `LICENSE` 로 실려 있고,
# <https://www.gnu.org/licenses/> 에서도 볼 수 있습니다.

"""앱 진입점.

로그를 먼저 연다. 창이 뜨기 전에 실패하는 경우(PySide6 미설치, 드라이버 문제)가
가장 알아내기 어려우므로, 진단은 화면이 아니라 파일에 남는 것이 기본이다 — 사용자는
"안 떠요"라고만 말할 수 있고, 그때 우리가 볼 수 있는 것은 `logs/` 뿐이다.

다만 **로그를 열 자리조차 없는 경우**가 하나 있다. exe 를 쓰기 권한이 없는 폴더에
두고 실행한 경우다. 이때는 로그에 적어도 아무도 볼 수 없으므로, 그 한 가지만은
창으로 말한다.
"""

from __future__ import annotations

import logging
import argparse
import os
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ipsm import i18n  # noqa: E402
from ipsm.i18n import tr  # noqa: E402
from ipsm.paths import cache_root, ensure_ready  # noqa: E402
from ipsm import product  # noqa: E402
from ipsm.version import VERSION_TEXT, version_line  # noqa: E402

log = logging.getLogger("app")


def _close_splash() -> None:
    """시작 그림을 내린다.

    그림은 PyInstaller 부트로더가 띄운 것이라 Qt 가 모른다 — 우리가 닫아 주지
    않으면 창 위에 그대로 남는다. 소스에서 실행할 때는 `pyi_splash` 자체가 없으므로
    조용히 지나간다.
    """
    if sys.platform == "darwin":
        return  # macOS bundle uses Qt directly; PyInstaller Splash is Windows-only here.
    try:
        import pyi_splash  # type: ignore[import-not-found]
    except ImportError:
        return
    try:
        pyi_splash.close()
    except Exception:  # pragma: no cover - 그림 닫기 실패로 앱을 멈출 이유는 없다
        log.debug("시작 그림을 닫는 중 예외", exc_info=True)


def _fatal(message: str) -> int:
    """로그를 쓸 수 없는 상황을 사용자에게 알린다."""
    # 그림을 먼저 내린다. 그림은 늘 맨 위에 뜨므로, 살려 두면 오류 상자가 그 뒤에
    # 숨어 사용자는 멈춘 시작 화면만 보게 된다.
    _close_splash()
    print(message)
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None, tr("시작할 수 없습니다"), message
        )
        del app
    except Exception:  # Qt 조차 없으면 콘솔 출력이 전부다
        pass
    return 3


def main() -> int:
    parser = argparse.ArgumentParser(description=f"{product.NAME} — iPhone 桌面整理工具")
    parser.add_argument("--language", choices=("zh_CN", "en", "ko"))
    parser.add_argument("--smoke-test", action="store_true", help="启动界面并自动退出，不连接 iPhone")
    parser.add_argument("--screenshot", type=Path, help="配合 --smoke-test 保存窗口截图")
    parser.add_argument("--demo", action="store_true", help="打开虚构演示布局，不连接 iPhone")
    parser.add_argument("--preview", type=Path, help="离线预览本地布局备份，不连接 iPhone")
    parser.add_argument("--draft", type=Path, help="打开本地离线草稿，不连接 iPhone")
    parser.add_argument("--profile", choices=("pages", "duo"), default="pages", help="逐页或 Duo 双页预览")
    args = parser.parse_args()
    if sum(bool(value) for value in (args.demo, args.preview, args.draft)) > 1:
        parser.error("--demo、--preview 和 --draft 只能选择一种")
    if os.name == "posix":
        os.umask(0o077)
    # 언어를 가장 먼저 고른다. 시작하다 실패했을 때 뜨는 말도 사용자의 말이어야 한다.
    # 설정을 못 읽어도(자리가 없거나 깨졌어도) PC 언어로 되돌아가므로 여기서 막히지 않는다.
    language = i18n.start(args.language)

    # logs · backups 를 만들어 둔다. 기기에 손대기 전에 확인한다 — 백업을 쓸 수
    # 없는 자리라면 그 사실을 지금 알아야 하고, 아직 아무것도 쓰지 않은 때다.
    root, problem = ensure_ready()
    if problem:
        return _fatal(problem)

    from ipsm.logging_setup import start_session

    session = start_session(root, name="app")
    # 버전을 가장 먼저 적는다. "고쳤는데 그대로예요"의 절반은 낡은 exe 를 실행한
    # 것이고, 그것을 가려낼 수 있는 곳은 이 한 줄뿐이다.
    log.info("%s", version_line())
    log.info("자료 폴더: %s", root)
    log.info("아이콘 캐시: %s", cache_root())
    log.info("언어: %s", language)

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        log.error("PySide6 를 불러올 수 없다: %r", exc)
        print(tr("PySide6 가 설치되어 있지 않습니다. install.bat 을 먼저 실행해 주세요."))
        return 2

    from ipsm.ui.main_window import MainWindow
    from PySide6.QtCore import QLibraryInfo, QLocale, QTimer, QTranslator, QLockFile

    app = QApplication(sys.argv)
    app.setApplicationName(product.NAME)
    app.setApplicationVersion(VERSION_TEXT)
    # Keep two application windows from modifying one device at the same time.
    instance_lock = QLockFile(str(root / ".instance.lock"))
    instance_lock.setStaleLockTime(0)
    if not instance_lock.tryLock(0):
        return _fatal(tr("The application is already running. Switch to its existing window."))
    qt_translator = QTranslator(app)

    def translate_qt() -> None:
        app.removeTranslator(qt_translator)
        code = i18n.language()
        QLocale.setDefault(QLocale(code))
        if qt_translator.load("qtbase_" + code, QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            app.installTranslator(qt_translator)

    translate_qt()
    i18n.on_language_changed(translate_qt)
    window = MainWindow(root, offline=bool(args.demo or args.preview or args.draft))
    window.set_preview_profile(args.profile)
    if args.demo:
        from ipsm.demo import demo_state

        window._device = ("file", tr("Demo layout (fictional apps)"))
        window._set_document(demo_state(), None)
    elif args.preview:
        try:
            preview_ok = window.open_preview(args.preview)
        except Exception as exc:
            window.worker.shutdown()
            return _fatal(tr("Cannot open the preview file: {why}").format(why=exc))
        if not preview_ok:
            window.worker.shutdown()
            return 4
    elif args.draft:
        try:
            draft_ok = window.open_draft(args.draft)
        except Exception as exc:
            window.worker.shutdown()
            return _fatal(tr("Cannot open the offline draft: {why}").format(why=exc))
        if not draft_ok:
            window.worker.shutdown()
            return 4
    # 창을 먼저 만들고, 보이기 직전에 그림을 내린다. 순서를 뒤집으면 그림이 사라진
    # 뒤 창이 뜰 때까지 빈 바탕화면이 남는다.
    _close_splash()
    window.show()
    if args.smoke_test:
        def finish_smoke() -> None:
            if args.screenshot:
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                if not window.grab().save(str(args.screenshot)):
                    log.error("Screenshot save failed")
                    app.exit(4)
                    return
            window.close()
        QTimer.singleShot(2500, finish_smoke)
    log.info("창을 열었다. 로그: %s", session.log_path)
    try:
        return app.exec()
    finally:
        i18n.off_language_changed(translate_qt)
        window.worker.shutdown()
        instance_lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
