"""기기 브리지 — 외부 라이브러리를 감싸는 유일한 계층.

다른 모듈은 pymobiledevice3 를 직접 import 하지 않는다. 그래야 라이브러리를 교체하거나,
기기 없이 나머지를 개발·테스트할 수 있다.

여기서 하는 일은 두 가지뿐이다.
  1. 연결 실패를 '사용자가 무엇을 해야 하는지'로 번역한다.
  2. SpringBoard 명령을 감싸고, 오간 원본을 세션 산출물로 남긴다.
"""

from __future__ import annotations

import hashlib
import copy
import logging
import sys
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
from .paths import data_root
from .safeio import private_directory
from .write_policy import write_block_reason

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


class ReadOnlyEvidenceAdapter:
    """Narrow, explicitly invoked evidence reader; no write API is exposed.

    SDK connection initialization reads lockdown metadata internally. Only the
    declared identity whitelist is retained, and fresh per-key identity reads
    bracket collection. Pairing is validated, never newly created by this path.
    Merely constructing/importing this adapter does not connect to a device.
    """

    _PARTS = frozenset({"identity_before", "layout_v2_before", "metrics", "apps_user",
                        "apps_system", "layout_v2_after", "identity_after", "layout_v3"})
    _ATTRIBUTES = ("CFBundleIdentifier", "ApplicationType", "CFBundleDisplayName",
                   "CFBundleName", "IsDemotedApp", "SBAppTags")

    def __init__(self) -> None:
        self._lockdown = None
        self._usbmux_address = "127.0.0.1:27015" if sys.platform == "win32" else "/var/run/usbmuxd"

    async def _ready(self):
        if self._lockdown is not None:
            return self._lockdown
        # Do not use the ordinary bridge helper, whose normal pairing flow may
        # create trust. This evidence path requires an already trusted USB phone.
        # Pin the local service instead of accepting an environment redirect.
        devices = await usbmux.list_devices(usbmux_address=self._usbmux_address)
        serials = {str(d.serial) for d in devices if d.connection_type == "USB" and d.serial}
        if len(serials) != 1:
            raise DeviceError(tr("Evidence collection requires exactly one trusted USB iPhone."),
                              tr("Connect only the intended trusted iPhone and retry the read-only command."))
        pairing_dir = data_root() / "pairing"
        private_directory(pairing_dir)
        lockdown = await create_using_usbmux(
            serial=next(iter(serials)), label=product.NAME, connection_type="USB",
            autopair=False, pairing_records_cache_folder=pairing_dir,
            usbmux_address=self._usbmux_address,
        )
        self._lockdown = lockdown
        if not getattr(lockdown, "paired", False):
            await self.close()
            raise DeviceError(tr("The iPhone does not have an existing trusted session."),
                              tr("Complete trust in Finder before explicitly running evidence collection."))
        return lockdown

    async def read(self, part: str) -> Any:
        if part not in self._PARTS:
            raise ValueError("Read-only evidence query is not on the allowlist")
        lockdown = await self._ready()
        if part.startswith("identity_"):
            # These are fresh requests, not the all_values cache from connect().
            identifier = await lockdown.get_value(key="UniqueDeviceID")
            model = await lockdown.get_value(key="ProductType")
            version = await lockdown.get_value(key="ProductVersion")
            build = await lockdown.get_value(key="BuildVersion")
            if not isinstance(identifier, str) or not identifier:
                raise ValueError("Missing device identity")
            device_key = hashlib.sha256(identifier.replace("-", "").lower().encode("ascii")).hexdigest()
            return {"device_key": device_key, "product_type": model, "ios_version": version,
                    "build_version": build, "transport": "USB"}
        if part in ("apps_user", "apps_system"):
            application_type = "User" if part == "apps_user" else "System"
            async with InstallationProxyService(lockdown=lockdown) as proxy:
                result = await proxy.lookup({"ApplicationType": application_type,
                                             "ShowPlaceholders": True,
                                             "ReturnAttributes": list(self._ATTRIBUTES)})
            if not isinstance(result, dict):
                raise ValueError("Installed-app query did not return LookupResult")
            if any(not isinstance(identifier, str) or not identifier or not isinstance(info, dict)
                   for identifier, info in result.items()):
                raise ValueError("Installed-app query returned a malformed entry")
            # Keep unknown/missing requested values absent, rather than claiming
            # that missing placeholder flags mean an app is fully installed.
            return {identifier: {key: value for key, value in info.items() if key in self._ATTRIBUTES}
                    for identifier, info in result.items()}
        async with SpringBoardServicesService(lockdown=lockdown) as service:
            if part == "metrics":
                return await service.get_homescreen_icon_metrics()
            return await service.get_icon_state(format_version="3" if part == "layout_v3" else "2")

    async def close(self) -> None:
        lockdown, self._lockdown = self._lockdown, None
        if lockdown is not None:
            await lockdown.close()


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
    if isinstance(exc, DeviceError):
        return exc
    if sys.platform == "darwin" and isinstance(exc, pmd_exc.ConnectionFailedToUsbmuxdError):
        return DeviceError(
            tr("The Mac cannot reach Apple's iPhone connection service."),
            tr("Reconnect your iPhone, unlock it and select Trust in Finder and on the iPhone. Restart the Mac if needed."),
            cause=exc,
        )
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
    """Use one explicitly identified USB device; never silently fall back to Wi-Fi."""
    devices = await usbmux.list_devices()
    usb = {str(d.serial): d for d in devices if d.connection_type == "USB" and d.serial}
    if serial is not None:
        matches = [key for key in usb if key.replace("-", "").lower() == serial.replace("-", "").lower()]
        if len(matches) != 1:
            raise DeviceError(
                tr("The selected iPhone is not connected by USB."),
                tr("Connect the intended iPhone with a data cable and try again."),
            )
        selected = matches[0]
    else:
        if not usb:
            raise DeviceError(
                tr("No iPhone is connected by USB."),
                tr("Connect the intended iPhone with a data cable and try again."),
            )
        if len(usb) != 1:
            raise DeviceError(
                tr("More than one iPhone is connected by USB."),
                tr("Disconnect the other devices before reading or changing a layout."),
            )
        selected = next(iter(usb))
    pairing_dir = data_root() / "pairing"
    private_directory(pairing_dir)
    return await create_using_usbmux(
        serial=selected, label=_LABEL, connection_type="USB",
        pairing_records_cache_folder=pairing_dir,
    )


# 기본 앱(System) 232개 중 홈화면에 뜨는 것은 40여 개뿐이다. 나머지는 화면 없는
# 구성요소이거나 자기 자신을 숨기는 앱이라, 그냥 다 세면 "이 앱들이 끝에 붙습니다"라는
# 경고를 190번 틀리게 하게 된다. 아래 네 가지가 실기기에서 확인된 거르는 근거다
# (2026-08-21, iPhone 14 / iOS 26.1 — 이 기준을 통과하는 미배치 기본 앱은 0개였고
#  실제로 되붙은 것도 0개였다. 반대로 8/19 에 iOS 가 되붙인 '돋보기'는 통과한다).


def _has_icon(info: dict[str, Any]) -> bool:
    """홈화면 아이콘이 있는가. 없으면 애초에 홈화면에 놓일 수 없다."""
    icons = info.get("CFBundleIcons")
    if isinstance(icons, dict) and icons.get("CFBundlePrimaryIcon"):
        return True
    return bool(info.get("CFBundleIconFiles") or info.get("CFBundleIconFile"))


def _region_of(locale: Optional[str]) -> Optional[str]:
    """'ko_KR' -> 'KR'.

    lockdown 의 `RegionInfo`('KH/A')를 쓰지 않는 이유: 그것은 Apple 의 부품 지역
    코드이지 ISO 국가 코드가 아니다 — ISO 로 `KH` 는 캄보디아다. 로케일만 쓴다.
    """
    if not locale:
        return None
    parts = str(locale).replace("-", "_").split("_")
    if len(parts) < 2:
        return None  # 'ko' — 말은 알아도 나라는 모른다
    tail = parts[-1].upper()
    return tail if len(tail) == 2 and tail.isalpha() else None


def shows_on_home_screen(info: dict[str, Any], region: Optional[str] = None) -> bool:
    """이 기본 앱이 홈화면에 나타날 수 있는가.

    거르는 순서대로 이유가 다르다.
      1. `SBAppTags` 의 `hidden` — 화면 없는 내부 구성요소. 232개 중 184개가 여기다.
      2. 아이콘 없음 — 그릴 것이 없다.
      3. `SBIconVisibilitySetByAppPreference` — 앱이 자기 표시 여부를 스스로 정한다
         (연속성·피드백·Xcode Previews·필드 테스트). 켜 주기 전에는 뜨지 않는다.
      4. `LSSupportedRegions` 에 이 기기의 지역이 없음 — 예: News 는 US·GB·AU·CA 에서만
         뜬다. **지역을 알아내지 못했으면 거르지 않는다** — 모른다고 빠뜨리는 것보다
         한 번 더 경고하는 편이 낫다. 빠뜨리면 사용자가 놀라고, 더 경고하면 안 붙을 뿐이다.
    """
    if "hidden" in (info.get("SBAppTags") or []):
        return False
    if not _has_icon(info):
        return False
    if info.get("SBIconVisibilitySetByAppPreference"):
        return False
    regions = info.get("LSSupportedRegions")
    if regions and region and region not in {str(r).upper() for r in regions}:
        return False
    return True


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
        return tr("{name} ({model}), iOS {ios} [{build}], {connection} connection, UDID {udid}").format(
            name=self.device_name, model=self.product_type, ios=self.ios_version,
            build=self.build_version, connection=self.connection_type, udid=self.udid_masked,
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
        self.device_key: Optional[str] = None
        self._last_icon_state: Optional[list[Any]] = None

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
                if str(getattr(d, "connection_type", "")) != "USB":
                    continue
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

            udid = str(getattr(self._lockdown, "udid", "") or "")
            if not udid:
                await self.close()
                raise DeviceError(
                    tr("Cannot identify the connected iPhone safely. Reconnect and read it again."),
                    tr("Connect the intended iPhone with a data cable and try again."),
                )
            self.device_key = hashlib.sha256(udid.replace("-", "").lower().encode("ascii")).hexdigest()
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
            self._last_icon_state = copy.deepcopy(state)
            return state

    async def set_icon_state(self, state: list[Any]) -> None:
        """홈화면 레이아웃을 통째로 덮어쓴다.

        부분 갱신이 아니라 전체 교체다. 보내지 않은 것은 사라진다 — 호출자는 원본에서
        해석하지 못한 요소까지 모두 포함한 상태를 넘겨야 한다 (REQ-017).
        """
        for candidate in (self._last_icon_state, state):
            if candidate is not None:
                blocked = write_block_reason(candidate, product_type=getattr(self.info, "product_type", None))
                if blocked:
                    raise DeviceError(blocked, tr("Keep this layout in read-only preview. No device changes were sent."))
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

    async def _home_region(self) -> Optional[str]:
        """이 기기가 어느 나라로 설정돼 있는가 — `LSSupportedRegions` 대조용."""
        if self._lockdown is None:
            return None
        try:
            locale = await self._lockdown.get_value(
                domain="com.apple.international", key="Locale"
            )
        except Exception as exc:  # noqa: BLE001 - 없으면 지역 조건만 건너뛴다
            log.debug("기기 지역을 읽지 못했다: %r", exc)
            return None
        return _region_of(locale if isinstance(locale, str) else None)

    async def list_installed_apps(self) -> dict[str, str]:
        """홈화면에 놓일 수 있는 설치된 앱: 번들 ID -> 표시 이름.

        홈화면 배치(iconState)에는 **홈화면에 놓인 것만** 들어 있다. 앱 라이브러리에만
        있는 앱은 흔적조차 없다 — `setIconState` 에 "설치됐지만 홈화면에 없음"을
        표현할 방법이 없기 때문이다. 그래서 쓰기를 하면 iOS 가 그런 앱들을 마지막
        페이지 끝에 되붙인다. 실기기에서 확인된 이 동작은 백업 복원으로도 되돌지 않는다.

        여기서 설치 목록을 따로 받아 두면, 적용 전에 "이 앱들이 끝에 붙습니다"를
        이름까지 대며 말할 수 있다. 놀라게 하지 않는 것이 이 조회의 전부다.

        **사용자 앱만 세면 구멍이 난다.** 2026-08-19 실기기 쓰기에서 iOS 가 되붙인
        4개 중 하나가 Apple 기본 앱인 '돋보기'(`com.apple.Magnifier`)였다. 기본 앱도
        앱 라이브러리로 치울 수 있으니 당연한 일인데, `application_type="User"` 만
        묻던 우리는 그것을 예고하지 못했다.

        그렇다고 기본 앱을 다 셀 수는 없다 — 232개 중 190개가 홈화면에 결코 뜨지 않는
        것들이라, 그대로 세면 틀린 경고를 190번 하게 된다. `shows_on_home_screen` 이
        그 둘을 가른다. 사용자 앱에는 그 체를 대지 않는다: 두 번의 실기기 쓰기에서
        이미 정확했던 목록이고, 근거 없이 체를 대면 맞던 것을 틀리게 만들 수 있다.

        실패해도 빈 dict 를 돌려준다 — 이것은 부가 정보이며, 없다고 편집을 막을 이유가 없다.
        """
        if self._lockdown is None:
            return {}
        try:
            async with InstallationProxyService(lockdown=self._lockdown) as proxy:
                user_apps = await proxy.get_apps(application_type="User")
                system_apps = await proxy.get_apps(application_type="System")
        except Exception as exc:
            log.warning("설치된 앱 목록을 받지 못했다(치명적이지 않음): %r", exc)
            return {}

        region = await self._home_region()

        def label(bundle_id: str, info: dict[str, Any]) -> str:
            return str(
                info.get("CFBundleDisplayName") or info.get("CFBundleName") or bundle_id
            )

        found = {
            str(bundle_id): label(str(bundle_id), info)
            for bundle_id, info in (user_apps or {}).items()
        }
        visible_system = {
            str(bundle_id): label(str(bundle_id), info)
            for bundle_id, info in (system_apps or {}).items()
            if shows_on_home_screen(info, region)
        }
        found.update(visible_system)
        log.info(
            "설치된 앱 %d개 (사용자 %d · 홈화면에 뜨는 기본 앱 %d/%d, 지역 %s)",
            len(found),
            len(user_apps or {}),
            len(visible_system),
            len(system_apps or {}),
            region or "알 수 없음",
        )
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
            self.device_key = None
