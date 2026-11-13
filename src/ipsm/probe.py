"""기기 프로브 — 이 프로젝트의 첫 관문 (REQ-001 · 002 · 003 · 004 · 005).

이 도구가 하는 일:
  1. 연결된 iPhone을 찾아 연결한다
  2. 홈화면 레이아웃 원본을 그대로 덤프한다
  3. 그리드 메트릭을 덤프한다
  4. (선택) **항등 왕복 안전 시험** — 읽은 그대로 다시 써서 아무것도 변하지 않는지 확인한다
  5. 전 과정을 로그 파일과 산출물로 남기고 zip으로 묶는다

기본은 **읽기 전용**이다. 기기에 쓰는 것은 `--roundtrip` 을 붙이고 확인 질문에 답했을
때뿐이다. 항등 왕복은 값이 바뀌지 않는 쓰기지만, 그래도 쓰기다 — 이 프로젝트에서
기기에 쓰는 일은 언제나 명시적 동의를 거친다.

항등 왕복이 실패하면 그것이 곧 결론이다: 이 기기·이 iOS 버전에서는 홈화면을 쓰는 방식이
성립하지 않으므로, 편집 기능을 만들면 안 된다. 실패하는 편이 낫다 — 사용자의 홈화면이
망가진 뒤에 알게 되는 것보다.

사용법:
    python -m ipsm.probe                # 읽기 전용 (권장: 이것부터)
    python -m ipsm.probe --roundtrip    # 항등 왕복 안전 시험까지
    python -m ipsm.probe --icons        # 앱 아이콘 이미지도 내려받기
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Optional

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ipsm import i18n
from ipsm.i18n import tr
from ipsm.paths import data_root  # noqa: E402

# exe 로 묶으면 소스 위치와 자료 위치가 달라진다. 자세한 이유는 `ipsm/paths.py`.
PROJECT_ROOT = data_root()

from ipsm.backup import BackupError, BackupStore, guarded_write  # noqa: E402
from ipsm.device import DeviceBridge, DeviceError  # noqa: E402
from ipsm.iconstate import IconState, compare_after_write  # noqa: E402
from ipsm.logging_setup import (  # noqa: E402
    DASH,
    MARK_FAIL,
    MARK_INFO,
    MARK_OK,
    MARK_WARN,
    RULE_CHAR,
    current_session,
    start_session,
)

log = logging.getLogger("probe")


def hr(title: str = "") -> None:
    log.info("")
    log.info(RULE_CHAR * 62)
    if title:
        log.info("  %s", title)
        log.info(RULE_CHAR * 62)


def confirm(question: str) -> bool:
    """기기에 쓰기 직전의 마지막 관문. 비대화형 실행에서는 '아니오'로 취급한다."""
    if not sys.stdin or not sys.stdin.isatty():
        log.warning(tr("대화형 입력이 불가능하여 쓰기를 건너뜁니다."))
        return False
    try:
        answer = input(f"{question} [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        log.warning(tr("사용자가 입력을 취소했습니다."))
        return False
    return answer in ("y", "yes")


# --------------------------------------------------------------------- 단계들


async def probe_read(bridge: DeviceBridge) -> tuple[list[Any], dict[str, Any]]:
    hr(tr("2. 홈화면 레이아웃 읽기"))
    state = await bridge.get_icon_state(artifact_name="icon_state_before")
    parsed = IconState.parse(state)
    for line in parsed.describe().splitlines():
        log.info("   %s", line)

    unknown = parsed.counts()["unknown"]
    if unknown:
        # 우리가 해석하지 못하는 요소가 있다는 것은 오류가 아니라 정보다.
        # 다만 그 원본은 반드시 남겨야 형식 해석을 고칠 수 있다.
        log.info("")
        log.info(tr("   %s 해석하지 못한 항목이 %d개 있습니다 (위젯 등일 수 있습니다)."), MARK_INFO, unknown)
        log.info(tr("     원본 표본을 산출물로 저장합니다 — 형식을 보완하는 근거가 됩니다."))
        current_session().save_artifact("unknown_items", parsed.unknown_samples(limit=20))

    hr(tr("3. 그리드 메트릭 읽기"))
    metrics = await bridge.get_homescreen_icon_metrics()
    if metrics:
        for key in sorted(metrics):
            log.info("   %s: %s", key, metrics[key])
    else:
        log.info(tr("   (이 기기에서는 메트릭을 제공하지 않습니다 — 치명적이지 않습니다)"))

    orientation = await bridge.get_orientation()
    log.info(tr("   화면 방향: %s"), orientation if orientation is not None else tr("조회 불가"))

    return state, metrics


async def probe_icons(bridge: DeviceBridge, state: list[Any], limit: int) -> None:
    hr(tr("3b. Fetch app icons (up to {limit})").format(limit=limit))
    parsed = IconState.parse(state)
    bundle_ids = sorted(parsed.bundle_ids())[:limit]
    session = current_session()
    icon_dir_name = "icons"
    saved = failed = 0
    for bundle_id in bundle_ids:
        data = await bridge.get_icon_png(bundle_id)
        if data:
            session.save_artifact(f"{icon_dir_name}_{bundle_id}.png", data, fmt="bytes")
            saved += 1
        else:
            failed += 1
    log.info(tr("   성공 %d개 / 실패 %d개"), saved, failed)


async def probe_roundtrip(bridge: DeviceBridge, store: BackupStore, before: list[Any]) -> bool:
    """항등 왕복 안전 시험 (REQ-003).

    읽은 상태를 **한 글자도 바꾸지 않고** 그대로 되돌려 쓴 뒤 다시 읽는다.
    같으면: 쓰기 경로가 성립하고, 우리가 원본을 온전히 왕복시킬 수 있다는 뜻이다.
    다르면: 쓰기 기능을 만들면 안 된다. 무엇이 유실되는지 산출물로 남긴다.
    """
    hr(tr("5. 항등 왕복 안전 시험 (기기에 씁니다)"))
    log.info(tr("   읽은 레이아웃을 그대로 다시 써서, 아무것도 변하지 않는지 확인합니다."))
    log.info(tr("   값이 바뀌지 않는 쓰기지만, 실제로 기기에 전송됩니다."))
    log.info(tr("   직전 상태는 이미 백업되어 있으므로 되돌릴 수 있습니다."))
    log.info("")

    log.warning(tr("   Apps kept only in the App Library may reappear on the Home Screen. Restoring a backup cannot undo this iOS behavior."))
    if not confirm(tr("   진행할까요?")):
        log.info(tr("   -> 건너뜁니다. 기기에 아무것도 쓰지 않았습니다."))
        return False

    log.info("")
    log.info(tr("   %s 시험이 끝날 때까지 iPhone을 분리하지 말고 잠금 해제 상태로 두세요."), MARK_WARN)
    await guarded_write(bridge, store, before, "roundtrip", expected_state=before)

    # SpringBoard가 배치를 반영하고 안정될 시간을 준다. 즉시 다시 읽으면
    # '적용 중'인 상태를 읽고 불일치로 오판할 수 있다.
    await asyncio.sleep(2.0)

    after = await bridge.get_icon_state(artifact_name="icon_state_after")

    hr(tr("6. 결과 대조"))
    result = compare_after_write(before, after)
    current_session().save_artifact(
        "roundtrip_diff",
        {"lost": result.lost, "moved": result.moved, "changed": result.changed, "added": result.added},
    )

    if not result.safe:
        # 배치가 훼손됐다. 이 경우에만 편집 기능을 만들지 않는다.
        log.error(tr("   %s 실패 %s 사용자의 배치가 보존되지 않았습니다."), MARK_FAIL, DASH)
        for note in result.lost:
            log.error(tr("     사라짐: %s"), note)
        for note in result.moved:
            log.error(tr("     이동:   %s"), note)
        for note in result.changed:
            log.error(tr("     Changed content: %s"), note)
        log.error("")
        log.error(tr("   이 기기에서는 홈화면 쓰기 기능을 활성화하면 안 됩니다."))
        log.error(tr("   되돌리려면 backups/ 의 가장 최근 파일로 복원하세요."))
        return False

    if result.identical:
        log.info(tr("   %s 통과 %s 쓰기 전후가 완전히 동일합니다."), MARK_OK, DASH)
        log.info(tr("     이 기기에서 홈화면 편집 기능을 만들어도 안전합니다."))
        return True

    # 사라지거나 움직인 것은 없고, 늘어나기만 했다.
    # 홈화면에 없던 앱(앱 라이브러리에만 있던 앱)을 iOS 가 마지막 페이지 끝에 붙인 것이다.
    log.info(tr("   %s 통과 %s 사라지거나 움직인 항목이 없습니다 (%d개 항목 보존)."),
             MARK_OK, DASH, sum(1 for _ in IconState.parse(before).iter_items()))
    log.info("")
    log.info(tr("   %s 다만 iPhone이 앱 %d개를 홈화면 끝에 새로 붙였습니다:"), MARK_WARN, len(result.added))
    for note in result.added:
        log.info("       %s", note)
    log.info("")
    log.info(tr("     홈화면에 없던 앱(앱 라이브러리에만 있던 앱)입니다. iOS 는 홈화면 배치를"))
    log.info(tr("     통째로 받으면, 그 안에 없는 설치된 앱을 끝에 되붙입니다. 우리가 빠뜨린 것이"))
    log.info(tr("     아니라 iOS 의 동작이며, 쓰기를 할 때마다 일어납니다."))
    log.info(tr("     원치 않으면 iPhone에서 해당 아이콘을 길게 눌러 '홈 화면에서 제거'를 선택하세요"))
    log.info(tr("     (앱은 지워지지 않고 앱 라이브러리에 남습니다)."))
    return True


# ------------------------------------------------------------------------ main


async def run(args: argparse.Namespace) -> int:
    session = start_session(PROJECT_ROOT, name="probe")
    log.info(tr("iPhone 홈화면 진단 (%s)"), session.id)
    log.info(tr("모든 기록: %s"), session.log_path)

    bridge = DeviceBridge()
    store = BackupStore(PROJECT_ROOT)
    passed: Optional[bool] = None

    try:
        hr(tr("1. 기기 연결"))
        devices = await DeviceBridge.list_devices()
        if not devices:
            log.error(tr("   연결된 iPhone이 없습니다."))
            log.error(tr("   USB 케이블로 연결하고, iPhone 화면에서 '신뢰'를 눌러 주세요."))
            log.error(tr("   (충전 전용 케이블은 데이터 통신이 되지 않습니다)"))
            return 2
        # `list_devices` 는 같은 기기의 여러 연결 경로를 이미 한 줄로 묶어 돌려준다.
        # Wi-Fi 동기화가 켜져 있으면 USB 와 Network 로 함께 잡히는데, '2대'라고 알리면
        # 사용자가 없는 문제를 찾게 된다.
        transports = {t for d in devices for t in d["connection_types"]}
        if len(transports) > 1:
            log.info(tr("   같은 기기가 %s 로 잡힙니다. USB 를 사용합니다."), " · ".join(sorted(transports)))
        if len(devices) > 1:
            log.info(tr("   기기가 %d대 있습니다. 첫 번째 기기를 사용합니다."), len(devices))

        info = await bridge.connect(serial=args.udid)
        store.bind_device(bridge.device_key)
        log.info("   %s", info.summary())

        state, _metrics = await probe_read(bridge)

        if args.icons:
            await probe_icons(bridge, state, limit=args.icon_limit)

        hr(tr("4. 백업"))
        # 읽기만 하더라도 백업은 남긴다. 이 시점의 홈화면이 '원래대로'의 기준이 된다.
        backup = store.save(state, reason="probe")
        log.info("   %s", backup.label)
        log.info(tr("   파일: %s"), backup.path)

        if args.roundtrip:
            passed = await probe_roundtrip(bridge, store, state)
        else:
            hr(tr("5. 항등 왕복 안전 시험"))
            log.info(tr("   건너뜀 (읽기 전용 실행)."))
            log.info(tr("   위 결과가 정상으로 보이면 --roundtrip 을 붙여 다시 실행하세요."))

    except DeviceError as exc:
        log.error("")
        log.error("%s %s", MARK_FAIL, exc.message)
        log.error("  -> %s", exc.action)
        log.debug(tr("원인"), exc_info=exc.cause)
        return 2
    except BackupError as exc:
        log.error("")
        log.error(tr("%s 백업을 만들지 못해 중단했습니다: %s"), MARK_FAIL, exc)
        log.error(tr("  -> 백업 없이는 기기에 아무것도 쓰지 않습니다."))
        return 3
    except KeyboardInterrupt:
        log.warning("")
        log.warning(tr("사용자가 중단했습니다."))
        return 130
    except Exception:
        log.exception(tr("예상치 못한 오류로 중단했습니다."))
        return 1
    finally:
        await bridge.close()
        hr(tr("진단 보고서"))
        try:
            report = session.export_zip()
            log.info(tr("   문제가 있었다면 이 파일 하나만 전달하면 됩니다:"))
            log.info("   %s", report)
        except Exception:
            log.exception(tr("보고서를 만들지 못했습니다. 로그 파일은 그대로 남아 있습니다."))
        log.info("")

    if passed is False:
        return 4
    return 0


def main() -> int:
    i18n.start()
    parser = argparse.ArgumentParser(
        prog="ipsm.probe",
        description=tr("iPhone 홈화면 진단 프로브 — 기본은 읽기 전용입니다."),
    )
    parser.add_argument("--udid", help=tr("특정 기기를 지정 (생략하면 첫 번째 기기)"))
    parser.add_argument(
        "--roundtrip",
        action="store_true",
        help=tr("항등 왕복 안전 시험을 수행한다 (기기에 씁니다 · 확인 질문 있음)"),
    )
    parser.add_argument("--icons", action="store_true", help=tr("앱 아이콘 이미지도 내려받는다"))
    parser.add_argument("--icon-limit", type=int, default=30, help=tr("내려받을 아이콘 수 (기본 30)"))
    args = parser.parse_args()

    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
