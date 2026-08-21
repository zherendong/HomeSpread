"""기기 브리지 — 외부 라이브러리를 감싸는 유일한 계층.

다른 모듈은 pymobiledevice3 를 직접 import 하지 않는다. 그래야 라이브러리를 교체하거나,
기기 없이 나머지를 개발·테스트할 수 있다.

여기서 하는 일은 두 가지뿐이다.
  1. 연결 실패를 '사용자가 무엇을 해야 하는지'로 번역한다.
  2. SpringBoard 명령을 감싸고, 오간 원본을 세션 산출물로 남긴다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pymobiledevice3 import exceptions as pmd_exc
from pymobiledevice3 import usbmux
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.installation_proxy import InstallationProxyService
from pymobiledevice3.services.springboard import SpringBoardServicesService

from . import product
from .i18n import defer, tr
from .logging_setup import current_session, mask, step

log = logging.getLogger("device")


class DeviceError(Exception):
    """사용자에게 보여줄 수 있는 형태로 번역된 기기 오류.

    message 는 화면에 그대로 띄울 수 있어야 한다. 내부 용어(lockdownd, usbmux 등)를
    담지 않는다. 원인 추적용 정보는 로그에 남는다.
    """

    def __init__(self, message: str, action: str, *, cause: Optional[BaseException] = None) -> None:
        super().__init__(message)
        self.message = message
        self.action = action
        self.cause = cause

    def __str__(self) -> str:
        return f"{self.message} → {self.action}"


# 예외를 사용자 언어로 옮기는 표. 새 실패 유형을 만나면 여기에 추가한다 —
# 분기를 코드 곳곳에 흩뿌리면 어떤 실패가 안내 없이 새는지 알 수 없게 된다.
_TRANSLATIONS: list[tuple[type[BaseException], str, str]] = [
    (
        pmd_exc.ConnectionFailedToUsbmuxdError,
        defer("iPhone과 통신하는 Windows 구성요소를 찾을 수 없습니다."),
        defer("Apple 기기(Apple Devices) 앱 또는 iTunes를 설치한 뒤 PC를 다시 시작해 주세요."),
    ),
    (
        pmd_exc.NoDeviceConnectedError,
        defer("연결된 iPhone이 없습니다."),
        defer("USB 케이블로 iPhone을 연결해 주세요. 충전 전용 케이블은 동작하지 않습니다."),
    ),
    (
        pmd_exc.DeviceNotFoundError,
        defer("지정한 iPhone을 찾을 수 없습니다."),
        defer("케이블을 다시 연결하고 시도해 주세요."),
    ),
    (
        pmd_exc.PairingDialogResponsePendingError,
        defer("iPhone에서 아직 신뢰 여부를 선택하지 않았습니다."),
        defer("iPhone 화면의 '이 컴퓨터를 신뢰하시겠습니까?'에서 '신뢰'를 눌러 주세요."),
    ),
    (
        pmd_exc.UserDeniedPairingError,
        defer("iPhone에서 이 PC를 신뢰하지 않도록 선택했습니다."),
        defer("케이블을 다시 연결한 뒤 '신뢰'를 선택해 주세요."),
    ),
    (
        pmd_exc.PasswordRequiredError,
        defer("iPhone이 잠겨 있어 연결할 수 없습니다."),
        defer("iPhone 잠금을 해제한 상태로 두고 다시 시도해 주세요."),
    ),
    (
        pmd_exc.PasscodeRequiredError,
        defer("iPhone이 잠겨 있어 연결할 수 없습니다."),
        defer("iPhone 잠금을 해제한 상태로 두고 다시 시도해 주세요."),
    ),
    (
        pmd_exc.NotPairedError,
        defer("이 PC가 iPhone과 아직 연결 설정되지 않았습니다."),
        defer("iPhone 잠금을 해제하고, 화면에 나타나는 '신뢰'를 눌러 주세요."),
    ),
    (
        pmd_exc.NotTrustedError,
        defer("iPhone이 이 PC를 신뢰하지 않습니다."),
        defer("iPhone 잠금을 해제하고 '신뢰'를 눌러 주세요."),
    ),
    (
        pmd_exc.SetProhibitedError,
        defer("iPhone이 홈화면 변경 요청을 거부했습니다."),
        defer("iPhone 잠금을 해제한 상태로 다시 시도해 주세요. 계속 실패하면 진단 보고서를 저장해 주세요."),
    ),
    (
        pmd_exc.StartServiceError,
        defer("iPhone의 홈화면 서비스를 시작하지 못했습니다."),
        defer("iPhone 잠금을 해제하고 다시 시도해 주세요. 계속 실패하면 iPhone을 재시동해 주세요."),
    ),
    (
        pmd_exc.InvalidServiceError,
        defer("이 iPhone에서는 홈화면 서비스를 사용할 수 없습니다."),
        defer("진단 보고서를 저장해 주세요. iOS 버전에 따라 지원되지 않을 수 있습니다."),
    ),
]


def translate(exc: BaseException) -> DeviceError:
    """라이브러리 예외를 사용자 언어로 옮긴다. 모르는 예외도 안내 없이 새지 않게 한다."""
    for exc_type, message, action in _TRANSLATIONS:
        if isinstance(exc, exc_type):
            return DeviceError(tr(message), tr(action), cause=exc)
    return DeviceError(
        tr("iPhone과 통신하는 중 예상치 못한 문제가 발생했습니다."),
        tr("iPhone 잠금을 해제하고 케이블을 다시 연결해 주세요. 반복되면 진단 보고서를 저장해 주세요."),
        cause=exc,
    )


#: 기기에게 우리를 소개하는 이름. 짝짓기 기록에 남으므로 제품 이름을 그대로 쓴다.
_LABEL = product.NAME


async def _create_lockdown(serial: Optional[str]):
    """USB 를 먼저 시도한다.

    Wi-Fi 동기화가 켜져 있으면 같은 iPhone 이 usbmux 목록에 USB 와 Network 로 두 번 나타난다.
    Wi-Fi 경로는 느리고 기기가 잠들면 끊긴다. 홈화면 plist 는 100KB 에 가깝고, 무엇보다
    쓰기 도중 끊기는 것은 이 프로젝트에서 가장 피하고 싶은 상황이다.

    '기기가 없다' 계열 실패일 때만 전체 대상으로 되시도한다. 잠김·미신뢰 같은 실패는
    경로를 바꿔도 똑같이 실패하므로, 같은 오류를 두 번 내지 않고 그대로 올려보낸다.
    """
    try:
        return await create_using_usbmux(serial=serial, label=_LABEL, connection_type="USB")
    except (
        pmd_exc.NoDeviceConnectedError,
        pmd_exc.DeviceNotFoundError,
        pmd_exc.ConnectionFailedError,
    ) as exc:
        log.debug("USB 경로에 기기가 없다. 전체 대상으로 재시도한다: %r", exc)
        return await create_using_usbmux(serial=serial, label=_LABEL)


@dataclass
class DeviceInfo:
    """진단에 필요한 최소 정보. 개인 식별 정보는 마스킹된 상태로만 보관한다."""

    udid_masked: str
    device_name: str
    product_type: str
    ios_version: str
    build_version: str
    connection_type: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def summary(self) -> str:
        return (
            f"{self.device_name} ({self.product_type}), iOS {self.ios_version} "
            f"[{self.build_version}], {self.connection_type} 연결, UDID {self.udid_masked}"
        )


# 로그에 남길 lockdown 값. 전화번호·계정·일련번호 전체는 의도적으로 제외한다.
_SAFE_KEYS = (
    "DeviceName",
    "ProductType",
    "ProductVersion",
    "BuildVersion",
    "DeviceClass",
    "HardwareModel",
    "CPUArchitecture",
    "PasswordProtected",
    "TimeZone",
    "ProductName",
)


class DeviceBridge:
    """USB로 연결된 iPhone 하나에 대한 세션."""

    def __init__(self) -> None:
        self._lockdown = None
        self.info: Optional[DeviceInfo] = None

    # ------------------------------------------------------------- discovery

    @staticmethod
    async def list_devices() -> list[dict[str, Any]]:
        with step(log, "연결된 기기 검색") as ctx:
            try:
                devices = await usbmux.list_devices()
            except Exception as exc:
                raise translate(exc) from exc
            # Wi-Fi 동기화가 켜져 있으면 같은 iPhone 이 USB 와 Network 로 두 번 나온다.
            # 그대로 세면 "2대 발견"이 되어, 기기가 하나뿐인 사용자가 무엇이 잘못됐나
            # 생각하게 된다. 실제 UDID 로 묶어 한 대로 세고 경로만 나열한다.
            # 묶는 기준은 마스킹 전의 값이다 — 마스킹된 값은 앞 4글자뿐이라
            # 서로 다른 기기도 같아 보인다.
            grouped: dict[str, dict[str, Any]] = {}
            for d in devices:
                serial = str(getattr(d, "serial", "") or "")
                entry = grouped.setdefault(
                    serial,
                    {
                        "udid_masked": mask(serial or None),
                        "connection_types": [],
                        "device_ids": [],
                    },
                )
                entry["connection_types"].append(str(getattr(d, "connection_type", "?")))
                entry["device_ids"].append(getattr(d, "devid", None))

            found = list(grouped.values())
            paths = sum(len(entry["connection_types"]) for entry in found)
            ctx["result"] = f"{len(found)}대 발견"
            if paths > len(found):
                ctx["result"] += f" (연결 경로 {paths}개 — USB 와 Wi-Fi 로 함께 보인다)"
            for entry in found:
                log.debug("  기기: %s", entry)
            return found

    async def connect(self, serial: Optional[str] = None) -> DeviceInfo:
        with step(log, "iPhone 연결") as ctx:
            try:
                self._lockdown = await _create_lockdown(serial)
            except Exception as exc:
                raise translate(exc) from exc

            values = dict(getattr(self._lockdown, "all_values", None) or {})
            safe = {k: values.get(k) for k in _SAFE_KEYS if k in values}

            self.info = DeviceInfo(
                udid_masked=mask(getattr(self._lockdown, "udid", None)),
                device_name=str(values.get("DeviceName", tr("알 수 없음"))),
                product_type=str(values.get("ProductType", tr("알 수 없음"))),
                ios_version=str(values.get("ProductVersion", tr("알 수 없음"))),
                build_version=str(values.get("BuildVersion", tr("알 수 없음"))),
                connection_type=str(getattr(self._lockdown, "connection_type", "USB")),
                raw=safe,
            )
            current_session().save_artifact("device_info", safe)
            ctx["result"] = self.info.summary()
            return self.info

    # ----------------------------------------------------------- springboard

    def _springboard(self) -> SpringBoardServicesService:
        if self._lockdown is None:
            raise DeviceError(
                tr("iPhone에 연결되지 않았습니다."),
                tr("먼저 iPhone을 연결해 주세요."),
            )
        return SpringBoardServicesService(lockdown=self._lockdown)

    async def get_icon_state(self, *, artifact_name: Optional[str] = None) -> list[Any]:
        """홈화면 레이아웃 원본을 그대로 가져온다 (REQ-002).

        해석하지 않은 원본을 반환한다. 형식 해석이 틀렸다고 나중에 밝혀져도 원본이 있으면
        다시 파싱할 수 있다.
        """
        with step(log, "홈화면 레이아웃 조회") as ctx:
            try:
                async with self._springboard() as sb:
                    state = await sb.get_icon_state()
            except Exception as exc:
                raise translate(exc) from exc
            if artifact_name:
                current_session().save_artifact(artifact_name, state, fmt="plist")
                current_session().save_artifact(f"{artifact_name}_readable", state)
            ctx["result"] = f"{len(state)}개 리스트 (독 포함)"
            return state

    async def set_icon_state(self, state: list[Any]) -> None:
        """홈화면 레이아웃을 통째로 덮어쓴다.

        부분 갱신이 아니라 전체 교체다. 보내지 않은 것은 사라진다 — 호출자는 원본에서
        해석하지 못한 요소까지 모두 포함한 상태를 넘겨야 한다 (REQ-017).
        """
        with step(log, "홈화면 레이아웃 적용") as ctx:
            current_session().save_artifact("icon_state_sent", state, fmt="plist")
            try:
                async with self._springboard() as sb:
                    await sb.set_icon_state(state)
            except Exception as exc:
                raise translate(exc) from exc
            ctx["result"] = "전송 완료"

    async def get_homescreen_icon_metrics(self) -> dict[str, Any]:
        """그리드 배치 수치 (REQ-005). 지원하지 않는 기기가 있을 수 있으므로 실패를 허용한다."""
        with step(log, "홈화면 그리드 메트릭 조회") as ctx:
            try:
                async with self._springboard() as sb:
                    metrics = await sb.get_homescreen_icon_metrics()
            except Exception as exc:
                log.warning("메트릭을 가져오지 못했다 (치명적이지 않음): %r", exc)
                ctx["result"] = "미지원"
                return {}
            current_session().save_artifact("icon_metrics", metrics)
            ctx["result"] = f"{len(metrics)}개 항목"
            return metrics

    async def get_icon_png(self, bundle_id: str) -> Optional[bytes]:
        """앱 아이콘 이미지. 한 앱의 실패가 전체를 막지 않도록 None을 반환한다."""
        try:
            async with self._springboard() as sb:
                return await sb.get_icon_pngdata(bundle_id)
        except Exception as exc:
            log.debug("아이콘을 가져오지 못했다: %s (%r)", bundle_id, exc)
            return None

    async def get_icon_pngs(
        self,
        identifiers: list[str],
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict[str, bytes]:
        """여러 아이콘을 연결 하나로 받아온다.

        `get_icon_png` 을 반복 호출하면 앱 하나마다 서비스를 새로 열고 닫는다. 300개면
        연결도 300번이고, 실제로 그렇게 하면 몇 분이 걸린다. 여기서는 서비스를 한 번만
        열고 그 안에서 전부 받는다.

        하나가 실패해도 멈추지 않는다 — 웹 클립처럼 애초에 아이콘을 줄 수 없는 항목이
        섞여 있는 것이 정상이기 때문이다. 결과 dict 에 없는 식별자가 곧 실패한 것이다.
        """
        icons: dict[str, bytes] = {}
        if not identifiers:
            return icons
        with step(log, f"앱 아이콘 {len(identifiers)}개 내려받기") as ctx:
            try:
                async with self._springboard() as sb:
                    for index, identifier in enumerate(identifiers, start=1):
                        try:
                            data = await sb.get_icon_pngdata(identifier)
                        except Exception as exc:
                            log.debug("아이콘 실패: %s (%r)", identifier, exc)
                            data = None
                        if data:
                            icons[identifier] = bytes(data)
                        if on_progress is not None:
                            on_progress(index, len(identifiers), identifier)
            except Exception as exc:
                # 서비스 자체가 끊긴 경우. 여기까지 받은 것은 그대로 살려서 돌려준다.
                log.warning("아이콘 내려받기가 중단되었다: %r", exc)
            ctx["result"] = f"성공 {len(icons)}개 / 요청 {len(identifiers)}개"
        return icons

    async def list_installed_apps(self) -> dict[str, str]:
        """설치된 사용자 앱: 번들 ID -> 표시 이름.

        홈화면 배치(iconState)에는 **홈화면에 놓인 것만** 들어 있다. 앱 라이브러리에만
        있는 앱은 흔적조차 없다 — `setIconState` 에 "설치됐지만 홈화면에 없음"을
        표현할 방법이 없기 때문이다. 그래서 쓰기를 하면 iOS 가 그런 앱들을 마지막
        페이지 끝에 되붙인다. 실기기에서 확인된 이 동작은 백업 복원으로도 되돌지 않는다.

        여기서 설치 목록을 따로 받아 두면, 적용 전에 "이 앱들이 끝에 붙습니다"를
        이름까지 대며 말할 수 있다. 놀라게 하지 않는 것이 이 조회의 전부다.

        실패해도 빈 dict 를 돌려준다 — 이것은 부가 정보이며, 없다고 편집을 막을 이유가 없다.
        """
        if self._lockdown is None:
            return {}
        try:
            async with InstallationProxyService(lockdown=self._lockdown) as proxy:
                apps = await proxy.get_apps(application_type="User")
        except Exception as exc:
            log.warning("설치된 앱 목록을 받지 못했다(치명적이지 않음): %r", exc)
            return {}
        found = {
            str(bundle_id): str(
                info.get("CFBundleDisplayName") or info.get("CFBundleName") or bundle_id
            )
            for bundle_id, info in (apps or {}).items()
        }
        log.info("설치된 사용자 앱 %d개", len(found))
        return found

    async def get_orientation(self) -> Optional[str]:
        try:
            async with self._springboard() as sb:
                return str(await sb.get_interface_orientation())
        except Exception as exc:
            log.debug("화면 방향 조회 실패: %r", exc)
            return None

    # ---------------------------------------------------------------- close

    async def close(self) -> None:
        if self._lockdown is not None:
            try:
                close = getattr(self._lockdown, "aclose", None) or getattr(
                    self._lockdown, "close", None
                )
                if close is not None:
                    result = close()
                    if hasattr(result, "__await__"):
                        await result
            except Exception as exc:  # 종료 실패는 진단 정보로만 남긴다
                log.debug("연결 종료 중 예외: %r", exc)
            self._lockdown = None
