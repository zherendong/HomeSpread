"""기기 작업 스레드 — UI 를 절대로 멈추지 않게 하는 한 겹.

pymobiledevice3 는 전면 async 이고 Qt 는 자기 이벤트 루프를 돈다. 둘을 한 루프에
합치는 대신(`qasync`), 기기 작업만 **독립 스레드 위의 독립 asyncio 루프**로 보낸다
(ADR-001). 이유는 의존성 하나를 줄이는 것보다 훨씬 실질적이다:

    쓰기 도중 UI 가 얼어붙으면 사용자가 케이블을 뽑는다.

응답 없는 창은 사용자에게 "죽었다"로 읽힌다. 홈화면을 덮어쓰는 800ms 동안 창이
하얗게 변하면, 그 순간 케이블을 뽑는 것은 완전히 합리적인 행동이다. 그래서 이
스레드는 편의가 아니라 안전 장치다.

이 안에서만 `DeviceBridge` 를 만들고 쓴다. 메인 스레드는 시그널로 결과만 받는다 —
기기 객체를 두 스레드에서 만지면 언젠가 반드시 깨진다.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import QThread, Signal

from ..backup import Backup, BackupError, BackupStore, guarded_write, restore
from ..i18n import tr
from ..iconstate import compare_after_write
from ..icons import IconStore
from ..paths import cache_root
from ..write_policy import device_write_block_reason, write_block_reason

# 기기 계층은 여기서 들이지 않는다 — `_load_device_layer()` 가 워커 스레드에서 들인다.
DeviceBridge = None  # type: ignore[assignment]
DeviceError = None  # type: ignore[assignment]

log = logging.getLogger("ui.worker")


def _load_device_layer() -> None:
    """`pymobiledevice3` 를 **창이 뜬 뒤에** 들인다.

    이 라이브러리 하나를 import 하는 데 8초쯤 걸린다(실측). 그 8초를 시작 경로에
    두면 사용자는 아무것도 없는 화면을 8초 동안 본다. 우리가 그것을 필요로 하는
    시점은 사용자가 '기기에서 읽기'를 누른 뒤이고, 그 사이에는 워커 스레드가
    이미 돌고 있다 — 그래서 스레드가 시작하자마자 여기서 들인다. 창은 먼저 뜨고,
    라이브러리는 그 뒤에서 준비된다.

    이름을 모듈 전역에 그대로 얹는 이유는 `except DeviceError` 같은 자리를 그대로
    두기 위해서다. 다만 그 자리들은 전부 이 함수가 끝난 뒤에만 실행된다.
    """
    global DeviceBridge, DeviceError
    if DeviceBridge is not None:
        return
    started = time.perf_counter()
    from ..device import DeviceBridge as _Bridge, DeviceError as _Error

    DeviceBridge, DeviceError = _Bridge, _Error
    log.debug("기기 계층 준비 %.1f초", time.perf_counter() - started)

# 쓰기 직후 되읽기까지 두는 시간. iOS 가 아이콘 배치를 반영하고 SpringBoard 가
# 정착하는 데 잠깐 걸린다. 너무 짧으면 '아직 반영 안 된 상태'를 손실로 오해한다.
_SETTLE_SECONDS = 1.5


class DeviceWorker(QThread):
    """기기 작업 하나씩. 결과는 시그널로만 나간다."""

    # 성공 경로
    loaded = Signal(object, object, object)  # state, metrics, DeviceInfo
    iconsUpdated = Signal(int, int)  # 받은 수, 요청한 수
    applied = Signal(object)  # dict(backup, comparison, state)
    compatibilityChecked = Signal(object)
    restoredFrom = Signal(object)  # dict(backup, state)
    backupsListed = Signal(object)  # list[Backup]
    installedListed = Signal(object)  # dict[번들 ID, 표시 이름]

    # 상태
    progressed = Signal(str, int, int)  # 메시지, 진행, 전체
    busyChanged = Signal(bool)
    failed = Signal(str, str)  # 무엇이 잘못됐는가, 무엇을 하면 되는가

    def __init__(self, root: Path, parent: Any = None) -> None:
        super().__init__(parent)
        self.root = Path(root)
        self.backups = BackupStore(self.root)
        # 아이콘만 자리가 다르다 — 잃어도 되는 것이라 임시 폴더에 둔다.
        self.icons = IconStore(cache_root())
        self._bridge: Optional[DeviceBridge] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_ready = threading.Event()
        self._busy = False
        self._startup_error: str | None = None
        self.write_verified = False
        self.offline_mode = False
        self.preview_profile = "pages"
        self._loaded_state: list[Any] | None = None

    def set_offline_mode(self, offline: bool) -> None:
        self.offline_mode = bool(offline)
        self.write_verified = False

    def set_preview_profile(self, profile: str) -> None:
        if profile not in ("pages", "duo"):
            raise ValueError("Unknown preview profile")
        self.preview_profile = profile
        self.write_verified = False

    def _assert_write_allowed(self, state: list[Any] | None = None) -> None:
        if self.offline_mode:
            raise BackupError(tr("Offline preview never connects to or writes to an iPhone."))
        if self.preview_profile == "duo":
            raise BackupError(tr("Duo preview is read-only. Device writes are disabled."))
        model = getattr(getattr(self._bridge, "info", None), "product_type", None)
        blocked = device_write_block_reason(model)
        for candidate in (self._loaded_state, state):
            if candidate is not None:
                blocked = blocked or write_block_reason(candidate, product_type=model)
        if blocked:
            self.write_verified = False
            raise BackupError(blocked)

    # --------------------------------------------------------------- 스레드

    def run(self) -> None:  # QThread 진입점 — 이 아래는 전부 워커 스레드다
        # 루프를 **먼저** 만든다. 그래야 라이브러리를 들이는 동안 창이 닫혀도
        # `shutdown()` 이 올린 정리 작업이 갈 곳이 있다. 반대 순서로 두면 그 몇 초
        # 사이에 닫은 사용자에게는 루프가 없는 스레드가 남아, Qt 가 '아직 도는
        # 스레드를 없앴다'고 경고하며 종료가 지저분해진다.
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        try:
            _load_device_layer()
            self._loop.run_forever()
        except Exception as exc:
            self._startup_error = str(exc)
            log.exception("Device worker startup failed")
            self._busy = False
            self.failed.emit(tr("Cannot load the device connection library."), tr("Reinstall the application dependencies and restart the app."))
            self.busyChanged.emit(False)
        finally:
            try:
                self._loop.close()
            except Exception:  # 종료 경로에서의 실패는 사용자에게 보여줄 것이 없다
                log.debug("워커 루프를 닫는 중 예외", exc_info=True)

    @property
    def busy(self) -> bool:
        return self._busy

    def _submit(self, coro_factory: Callable[[], Any], what: str) -> bool:
        """작업 하나를 워커 루프에 올린다. 이미 작업 중이면 거절한다.

        큐를 두지 않는 이유: 기기 작업은 사용자가 버튼을 눌러 시작하고, 진행 중에는
        그 버튼이 잠긴다. 큐에 쌓인 작업은 사용자가 잊은 뒤에 실행되고, 이 앱에서
        '잊은 뒤에 실행되는 것' 중 하나는 홈화면 덮어쓰기다.
        """
        if self._busy:
            self.failed.emit(tr("이미 다른 작업이 진행 중입니다."), tr("끝날 때까지 기다려 주세요."))
            return False
        self._loop_ready.wait(5.0)
        if self._loop is None or self._loop.is_closed() or self._startup_error:
            self.failed.emit(tr("작업 스레드가 시작되지 않았습니다."), tr("앱을 다시 실행해 주세요."))
            return False

        self._busy = True
        self.busyChanged.emit(True)

        async def guarded() -> None:
            try:
                await coro_factory()
            except DeviceError as exc:
                self.write_verified = False
                log.warning("%s 실패: %s", what, exc)
                self.failed.emit(str(exc.args[0]) if exc.args else str(exc), exc.action)
            except Exception as exc:
                self.write_verified = False
                log.exception("%s 중 예상 못 한 오류", what)
                self.failed.emit(
                    tr("{what} 중 문제가 생겼습니다: {why}").format(what=what, why=exc),
                    tr("로그 파일(logs/)을 확인해 주세요."),
                )
            finally:
                self._busy = False
                self.busyChanged.emit(False)

        asyncio.run_coroutine_threadsafe(guarded(), self._loop)
        return True

    async def _bridge_ready(self) -> DeviceBridge:
        if self.offline_mode:
            raise BackupError(tr("Offline preview never connects to or writes to an iPhone."))
        if self._bridge is None:
            bridge = DeviceBridge()
            await bridge.connect()
            self.backups.bind_device(bridge.device_key)
            self._bridge = bridge
        return self._bridge

    # ----------------------------------------------------------------- 작업

    def load(self) -> bool:
        """연결하고 현재 홈화면과 그리드 규격을 읽어 온다."""

        async def job() -> None:
            self.write_verified = False
            self.progressed.emit(tr("iPhone 을 찾는 중…"), 0, 0)
            bridge = await self._bridge_ready()
            self.progressed.emit(tr("홈화면을 읽는 중…"), 0, 0)
            state = await bridge.get_icon_state(artifact_name="icon_state_loaded")
            self._loaded_state = copy.deepcopy(state)
            metrics = await bridge.get_homescreen_icon_metrics()
            self.loaded.emit(state, metrics, bridge.info)
            # 설치 목록은 부가 정보다. 홈화면을 먼저 띄우고 나서 받는다 —
            # 이것 때문에 화면이 늦게 뜨면 순서가 거꾸로다.
            if write_block_reason(state, product_type=getattr(bridge.info, "product_type", None)):
                self.installedListed.emit({})
            else:
                self.installedListed.emit(await bridge.list_installed_apps())

        return self._submit(job, tr("홈화면 읽기"))

    def fetch_icons(self, wanted: list[tuple[str, Optional[str]]]) -> bool:
        """아직 없거나 낡은 아이콘만 받아 온다."""

        async def job() -> None:
            stamps = dict(wanted)
            missing = self.icons.missing(wanted)
            if not missing:
                self.iconsUpdated.emit(0, 0)
                return
            bridge = await self._bridge_ready()

            def on_progress(done: int, total: int, identifier: str) -> None:
                # 워커 스레드에서 emit 해도 된다 — Qt 가 큐로 넘겨 준다.
                self.progressed.emit(
                    tr("아이콘 받는 중 ({done}/{total})").format(done=done, total=total),
                    done,
                    total,
                )

            icons = await bridge.get_icon_pngs(missing, on_progress=on_progress)
            self.icons.put_many(icons, stamps)
            self.iconsUpdated.emit(len(icons), len(missing))

        return self._submit(job, tr("아이콘 내려받기"))

    def apply(self, state: list[Any], reason: str = "before-edit", *, expected_state: list[Any]) -> bool:
        """백업을 만든 뒤 홈화면을 덮어쓴다 (REQ-010).

        쓰기는 `guarded_write` 로만 나간다. 백업이 실패하면 거기서 멈추고 쓰지 않는다.
        """

        state, expected_state = copy.deepcopy(state), copy.deepcopy(expected_state)

        async def job() -> None:
            self._assert_write_allowed(state)
            if not self.write_verified:
                raise BackupError(tr("Run the write compatibility test before applying edits."))
            bridge = await self._bridge_ready()
            self.progressed.emit(tr("백업을 만드는 중…"), 0, 0)
            backup: Backup = await guarded_write(bridge, self.backups, state, reason, expected_state=expected_state)
            self.progressed.emit(tr("홈화면을 쓰는 중…"), 0, 0)
            await asyncio.sleep(_SETTLE_SECONDS)
            self.progressed.emit(tr("결과를 확인하는 중…"), 0, 0)
            after = await bridge.get_icon_state(artifact_name="icon_state_after_write")
            comparison = compare_after_write(state, after)
            self.write_verified = comparison.safe
            self.applied.emit({"backup": backup, "comparison": comparison, "state": after})

        return self._submit(job, tr("홈화면 적용"))

    def check_compatibility(self, expected_state: list[Any]) -> bool:
        """Explicitly confirmed real identity write; never runs during read/load."""
        expected = copy.deepcopy(expected_state)

        async def job() -> None:
            self.write_verified = False
            self._assert_write_allowed(expected)
            bridge = await self._bridge_ready()
            self.progressed.emit(tr("Checking write compatibility… Keep the iPhone connected."), 0, 0)
            backup = await guarded_write(bridge, self.backups, expected, "compatibility", expected_state=expected)
            await asyncio.sleep(_SETTLE_SECONDS)
            after = await bridge.get_icon_state(artifact_name="icon_state_compatibility")
            comparison = compare_after_write(expected, after)
            self.write_verified = comparison.safe
            self.compatibilityChecked.emit({"backup": backup, "comparison": comparison, "state": after})

        return self._submit(job, tr("Write compatibility test"))

    def restore_backup(self, path: Path) -> bool:
        """백업 시점으로 되돌린다 (REQ-011)."""

        async def job() -> None:
            self._assert_write_allowed()
            bridge = await self._bridge_ready()
            self.progressed.emit(tr("복원하는 중…"), 0, 0)
            expected = self.backups.load(Path(path), for_restore=True)
            backup = await restore(bridge, self.backups, Path(path))
            await asyncio.sleep(_SETTLE_SECONDS)
            after = await bridge.get_icon_state(artifact_name="icon_state_after_restore")
            comparison = compare_after_write(expected, after)
            self.write_verified = comparison.safe
            self.restoredFrom.emit({"backup": backup, "state": after, "comparison": comparison})

        return self._submit(job, tr("백업 복원"))

    def list_backups(self) -> None:
        """디스크만 읽으므로 기기가 없어도 된다. 스레드를 점유하지 않는다."""
        try:
            self.backupsListed.emit(self.backups.list_backups())
        except Exception as exc:
            log.warning("백업 목록을 읽지 못했다: %r", exc)
            self.backupsListed.emit([])

    # ----------------------------------------------------------------- 종료

    def shutdown(self, timeout_ms: int = 5000) -> None:
        """연결을 닫고 루프를 멈춘다. 닫히지 않아도 앱 종료를 막지 않는다.

        두 번 불려도 안전해야 한다. 창을 닫을 때(closeEvent)와 앱을 정리할 때가
        모두 이 함수를 부르는데, 이미 닫힌 루프에 작업을 올리려 하면 예외가 나고
        만들어 둔 코루틴이 대기 상태로 남아 종료 직전에 경고를 뱉는다. 종료 경로에서
        나오는 경고는 실제 문제를 가리는 소음이므로 여기서 막는다.
        """
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        # 기기 계층을 아직 들이는 중이라면(최대 8초) 그 시간을 기다려 준다. 이 경우에만
        # 길게 잡는다 — 평소의 종료는 여전히 즉시 끝나야 한다.
        if DeviceBridge is None:
            timeout_ms = max(timeout_ms, 15000)

        async def closing() -> None:
            if self._bridge is not None:
                try:
                    await self._bridge.close()
                except Exception:
                    log.debug("기기 연결을 닫는 중 예외", exc_info=True)
                self._bridge = None
            loop.stop()

        job = closing()
        try:
            asyncio.run_coroutine_threadsafe(job, loop)
        except Exception:
            job.close()  # 대기 중인 코루틴을 남기지 않는다
            log.debug("종료 작업을 올리지 못했다", exc_info=True)
        if not self.wait(timeout_ms):
            log.warning("워커 스레드가 제때 끝나지 않아 그대로 종료한다.")
