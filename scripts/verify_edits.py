# -*- coding: utf-8 -*-
"""편집 기능 실기기 검증 — 묶기 · 이름 바꾸기 · 밀어내기 · 빈 자리 정리.

`tests/test_core.py` 는 우리가 지어낸 작은 배치로 규칙을 시험한다. 그것으로 잡히지
않는 것이 하나 있다: **진짜 기기의 자료**다. 항목 수백 개, 폴더 수십 개, 우리가
해석하지 못한 항목, 오프로드된 앱 — 이런 것이 섞인 배치 위에서도 같은 규칙이 서는지는
그 배치를 실제로 받아 보아야 알 수 있다.

그래서 이 도구는 두 겹이다.

  1단계 (언제나, 기기에 쓰지 않는다)
      기기에서 배치를 읽어 와 **메모리 안에서** 편집한다. 묶고, 이름을 바꾸고,
      꽉 찬 페이지에 끼워 밀어내고, 마지막 항목을 빼내 빈 자리를 없앤다. 매 단계마다
      결과가 스스로 모순이 없는지 본다 — 항목이 사라지지 않았는가, 빈 묶음이나 빈
      페이지가 남지 않았는가, 어떤 페이지도 칸 수를 넘지 않았는가. 마지막에 전부
      취소해 원본과 한 글자도 다르지 않은지 확인한다.
      **여기까지는 기기에 한 글자도 쓰지 않는다.** 그런데도 검증의 대부분이 끝난다.

  2단계 (`--apply` 를 붙였을 때만, 기기에 쓴다)
      1단계에서 확인할 수 없는 것이 딱 하나 남는다: "우리가 **지어낸 묶음**을 기기가
      받아들이는가." 그것만을 위해 가장 작은 편집 하나(앱 둘을 묶고 이름을 붙인다)를
      실제로 보내고, 되읽어 대조한 뒤, 백업으로 되돌린다.

되돌릴 수 없는 것이 하나 있다는 것을 먼저 밝힌다. `setIconState` 에는 "설치됐지만
홈화면에 없음"을 표현할 방법이 없어서, **앱 라이브러리에만 있던 앱을 iOS 가 마지막
페이지 끝에 되붙인다.** 백업 복원도 쓰기이므로 이것만은 되돌려지지 않는다.

사용법:
    python scripts/verify_edits.py            # 1단계만 (기기에 쓰지 않는다)
    python scripts/verify_edits.py --apply    # 2단계까지 (기기에 쓴다)
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import logging
import sys
from pathlib import Path
from typing import Any, Optional

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ipsm.backup import BackupStore  # noqa: E402
from ipsm.device import DeviceBridge, DeviceError  # noqa: E402
from ipsm.iconstate import KEY_ICON_LISTS, compare_after_write  # noqa: E402
from ipsm.layout import Container, LayoutDocument, Node  # noqa: E402
from ipsm.logging_setup import start_session  # noqa: E402
from ipsm.paths import data_root  # noqa: E402

PROJECT_ROOT = data_root()
log = logging.getLogger("verify")

PASS = "[통과]"
FAIL = "[실패]"
SKIP = "[건너뜀]"

TEST_FOLDER_NAME = "검증용묶음"


# --------------------------------------------------------------------- 결과 모음


class Report:
    """검사 결과를 모은다. 하나라도 실패하면 종료 코드가 1이 된다."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, mark: str, title: str, detail: str = "") -> None:
        self.rows.append((mark, title, detail))
        line = f"   {mark} {title}"
        if detail:
            line += f" — {detail}"
        (log.error if mark == FAIL else log.info)(line)

    @property
    def failed(self) -> int:
        return sum(1 for mark, _, _ in self.rows if mark == FAIL)

    def summarize(self) -> None:
        passed = sum(1 for mark, _, _ in self.rows if mark == PASS)
        skipped = sum(1 for mark, _, _ in self.rows if mark == SKIP)
        log.info("")
        log.info("검사 %d건 — 통과 %d · 실패 %d · 건너뜀 %d",
                 len(self.rows), passed, self.failed, skipped)


# ----------------------------------------------------------------- 상태 들여다보기


def _is_folder_raw(raw: Any) -> bool:
    return isinstance(raw, dict) and KEY_ICON_LISTS in raw


def leaf_census(state: list[Any]) -> dict[str, int]:
    """폴더가 아닌 항목이 각각 몇 개 있는지 센다.

    손실 검사에 쓴다. `compare_after_write` 는 폴더를 이름으로 식별하므로, 우리가
    묶음을 새로 만들거나 이름을 바꾸면 그것이 손실+추가로 보인다 — 의도한 변경이다.
    항목 자체가 사라졌는지는 폴더를 걷어내고 세어야 알 수 있다.
    """
    counts: dict[str, int] = {}

    def walk(items: list[Any]) -> None:
        for raw in items:
            if _is_folder_raw(raw):
                for page in raw.get(KEY_ICON_LISTS) or []:
                    if isinstance(page, list):
                        walk(page)
                continue
            key = repr(raw)[:200] if not isinstance(raw, dict) else str(
                raw.get("displayIdentifier") or raw.get("bundleIdentifier") or repr(raw)[:200]
            )
            counts[key] = counts.get(key, 0) + 1

    for entries in state:
        if isinstance(entries, list):
            walk(entries)
    return counts


def empty_places(state: list[Any]) -> list[str]:
    """빈 묶음과 빈 페이지를 찾는다. 하나라도 있으면 iOS 가 지우고 뒤를 민다."""
    found: list[str] = []

    def walk_folder(raw: dict, where: str) -> None:
        pages = raw.get(KEY_ICON_LISTS) or []
        name = raw.get("displayName") or "(이름 없음)"
        if not any(isinstance(p, list) and p for p in pages):
            found.append(f"빈 묶음 '{name}' ({where})")
            return
        for index, page in enumerate(pages):
            if isinstance(page, list) and not page:
                found.append(f"묶음 '{name}' 의 빈 {index + 1}페이지 ({where})")

    for list_index, entries in enumerate(state):
        if not isinstance(entries, list):
            continue
        where = "독" if list_index == 0 else f"{list_index}페이지"
        if list_index > 0 and not entries:
            found.append(f"빈 {where}")
        for raw in entries:
            if _is_folder_raw(raw):
                walk_folder(raw, where)
    return found


def over_capacity(doc: LayoutDocument) -> list[str]:
    """칸 수를 넘긴 자리를 찾는다."""
    return [
        f"{container.kind} {container.uid}: {len(container.items)} > {container.capacity}"
        for container in doc.containers()
        if len(container.items) > container.capacity
    ]


def check_consistent(doc: LayoutDocument, origin_leaves: dict[str, int],
                     report: Report, title: str) -> None:
    """편집 결과가 스스로 모순이 없는지 본다 — 손실·빈 자리·칸 넘침."""
    state = doc.to_state()
    problems: list[str] = []

    now = leaf_census(state)
    for key, count in origin_leaves.items():
        if now.get(key, 0) != count:
            problems.append(f"항목 수 달라짐: {key} {count} -> {now.get(key, 0)}")
    for key in now:
        if key not in origin_leaves:
            problems.append(f"없던 항목 생김: {key}")

    problems.extend(empty_places(state))
    problems.extend(over_capacity(doc))

    if problems:
        report.add(FAIL, title, problems[0])
        for extra in problems[1:6]:
            log.error("            %s", extra)
    else:
        report.add(PASS, title, f"항목 {sum(now.values())}개 그대로 · 빈 자리 없음")


# ------------------------------------------------------------------- 대상 고르기


def movable_apps(container: Container) -> list[Node]:
    return [n for n in container.items if n.movable and not n.is_folder]


def find_page_with_apps(doc: LayoutDocument, least: int) -> Optional[Container]:
    for page in doc.pages:
        if len(movable_apps(page)) >= least:
            return page
    return None


def find_full_page(doc: LayoutDocument) -> Optional[Container]:
    """뒤에 이어질 페이지가 있는 꽉 찬 홈 페이지. 밀어낼 곳이 있어야 시험이 된다."""
    for index, page in enumerate(doc.pages[:-1]):
        if page.full:
            return page
    return None


def find_donor(
    doc: LayoutDocument,
    avoid: "set[str]",
    *,
    allow_folder: bool,
) -> Optional[Node]:
    """옮겨 올 항목 하나를 고른다.

    홈 페이지 위의 낱개 앱만 찾으면 금방 바닥난다 — 이 기기가 그랬다. 홈에는 폴더
    35개가 놓여 있고 앱 284개는 대부분 폴더 **안**에 있었다. 그래서 묶음 안까지
    뒤진다. 재료가 없어 시나리오를 건너뛰면 그것은 '통과'가 아니라 '확인 못 함'이다.

    독은 건드리지 않는다. 독은 칸이 적고 사용자가 가장 민감하게 여기는 자리라,
    시험의 재료로 삼을 이유가 없다.
    """
    for container in doc.containers():
        if container.uid in avoid or container.kind == "dock":
            continue
        for node in reversed(container.items):
            if not node.movable:
                continue
            if node.is_folder and not allow_folder:
                continue
            return node
    return None


# ------------------------------------------------------------------ 1단계 시나리오


def scenario_group_and_rename(doc: LayoutDocument, report: Report) -> Optional[str]:
    """앱 둘을 묶고 이름을 바꾼다. 묶음의 raw 는 세 키뿐이어야 한다."""
    page = find_page_with_apps(doc, 2)
    if page is None:
        report.add(SKIP, "묶기", "앱이 둘 이상인 홈 페이지가 없다")
        return None

    first, second = movable_apps(page)[:2]
    names = f"'{first.label}' + '{second.label}'"

    reason = doc.can_group([first.uid, second.uid])
    if reason:
        report.add(FAIL, "묶기", f"묶을 수 없다고 답했다: {reason}")
        return None

    folder_uid = doc.group([first.uid, second.uid], TEST_FOLDER_NAME)
    folder = doc.node(folder_uid)

    if not folder.is_folder or folder.child_count() != 2:
        report.add(FAIL, "묶기", f"묶음에 항목이 {folder.child_count()}개")
        return folder_uid
    raw_keys = set(folder.to_raw().keys())
    expected = {"displayName", KEY_ICON_LISTS, "listType"}
    if raw_keys != expected:
        report.add(FAIL, "묶기", f"묶음의 키가 다르다: {sorted(raw_keys)}")
        return folder_uid
    report.add(PASS, "묶기", f"{names} -> '{folder.label}' (키 3개)")

    # ----- 이름 바꾸기
    new_name = "이름바꿈"
    reason = doc.can_rename(folder_uid, new_name)
    if reason:
        report.add(FAIL, "이름 바꾸기", f"바꿀 수 없다고 답했다: {reason}")
        return folder_uid
    doc.rename_folder(folder_uid, new_name)
    raw = doc.node(folder_uid).to_raw()
    if raw.get("displayName") != new_name:
        report.add(FAIL, "이름 바꾸기", f"raw 의 이름이 '{raw.get('displayName')}'")
    elif set(raw.keys()) != expected:
        report.add(FAIL, "이름 바꾸기", f"키가 늘거나 줄었다: {sorted(raw.keys())}")
    else:
        report.add(PASS, "이름 바꾸기", f"'{TEST_FOLDER_NAME}' -> '{new_name}' (키 3개 그대로)")
    return folder_uid


def scenario_folder_growth_and_spill(doc: LayoutDocument, folder_uid: str,
                                     report: Report) -> None:
    """묶음을 꽉 채워 페이지를 펴고, 꽉 찬 페이지의 자리를 겨눠 밀어낸다."""
    folder = doc.node(folder_uid)
    per_page = doc.grid.folder_page_capacity
    first_page = folder.pages[0]
    # 같은 묶음 안에서 옮기는 것은 개수를 늘리지 않는다. 이 묶음의 페이지는
    # 전부 재료 후보에서 뺀다.
    folder_uids = {p.uid for p in folder.pages}

    # 첫 페이지를 꽉 채운다.
    guard = 0
    while len(first_page.items) < per_page and guard < per_page * 2:
        guard += 1
        donor = find_donor(doc, {p.uid for p in folder.pages}, allow_folder=False)
        if donor is None:
            break
        if doc.can_move(donor.uid, first_page.uid, len(first_page.items)):
            break
        doc.move(donor.uid, first_page.uid, len(first_page.items))

    if len(first_page.items) < per_page:
        report.add(SKIP, "묶음 페이지 늘리기", f"첫 페이지를 채우지 못했다 ({len(first_page.items)}/{per_page})")
        return
    if len(folder.pages) != 1:
        report.add(FAIL, "묶음 페이지 늘리기", f"아직 꽉 찼을 뿐인데 페이지가 {len(folder.pages)}장")
        return

    # 꽉 찬 페이지의 **자리를 겨눠** 하나 더 넣는다 -> 마지막 항목이 다음 장 맨 앞으로.
    donor = find_donor(doc, folder_uids, allow_folder=False)
    if donor is None:
        report.add(SKIP, "묶음 밀어내기", "밀어 넣을 앱이 없다")
        return
    tail_before = first_page.items[-1]
    reason = doc.can_move(donor.uid, first_page.uid, 0)
    if reason:
        report.add(FAIL, "묶음 밀어내기", f"꽉 찬 묶음 페이지의 자리를 거절했다: {reason}")
        return
    doc.move(donor.uid, first_page.uid, 0)

    if len(folder.pages) != 2:
        report.add(FAIL, "묶음 밀어내기", f"페이지가 {len(folder.pages)}장 (2장이어야 한다)")
        return
    if first_page.items[0] is not donor:
        report.add(FAIL, "묶음 밀어내기", "겨눈 자리에 들어가지 않았다")
        return
    if not folder.pages[1].items or folder.pages[1].items[0] is not tail_before:
        report.add(FAIL, "묶음 밀어내기", "넘친 항목이 다음 장 맨 앞에 있지 않다")
        return
    report.add(PASS, "묶음 페이지 늘리기 · 밀어내기",
               f"{per_page}칸을 넘기자 2장이 되고 '{tail_before.label}' 이 다음 장 맨 앞으로")


def scenario_home_spill(doc: LayoutDocument, report: Report) -> None:
    """꽉 찬 홈 페이지의 자리를 겨누면 뒤가 밀리고 마지막이 다음 장 맨 앞으로 간다."""
    page = find_full_page(doc)
    if page is None:
        report.add(SKIP, "홈 밀어내기", "꽉 찬 홈 페이지가 없다")
        return
    index = doc.pages.index(page)
    donor = find_donor(doc, {page.uid}, allow_folder=True)
    if donor is None:
        report.add(SKIP, "홈 밀어내기", "밀어 넣을 앱이 없다")
        return

    tail_before = page.items[-1]
    next_page = doc.pages[index + 1]
    next_head_before = next_page.items[0] if next_page.items else None

    reason = doc.can_move(donor.uid, page.uid, 0)
    if reason:
        report.add(FAIL, "홈 밀어내기", f"꽉 찬 페이지의 자리를 거절했다: {reason}")
        return
    doc.move(donor.uid, page.uid, 0)

    if page.items[0] is not donor:
        report.add(FAIL, "홈 밀어내기", "겨눈 자리에 들어가지 않았다")
        return
    if len(page.items) > page.capacity:
        report.add(FAIL, "홈 밀어내기", f"페이지가 {len(page.items)}칸 (최대 {page.capacity})")
        return
    landed = doc.locate(tail_before.uid)[0]
    if landed is page:
        report.add(FAIL, "홈 밀어내기", "넘쳐야 할 마지막 항목이 그대로 남았다")
        return
    report.add(PASS, "홈 밀어내기",
               f"{index + 1}페이지가 밀리고 '{tail_before.label}' 이 다음 장으로"
               + (f" ('{next_head_before.label}' 앞)" if next_head_before else ""))


def scenario_prune(doc: LayoutDocument, folder_uid: str, report: Report) -> None:
    """마지막 항목이 빠지는 순간 묶음과 페이지가 사라져야 한다."""
    try:
        folder = doc.node(folder_uid)
    except Exception:
        report.add(SKIP, "빈 자리 정리", "시험용 묶음이 이미 없다")
        return

    # 묶음의 마지막 장을 비워 본다 -> 그 장이 사라져야 한다.
    if len(folder.pages) >= 2:
        pages_before = len(folder.pages)
        last = folder.pages[-1]
        target = doc.pages[0]
        while last.items:
            node = last.items[0]
            if doc.can_move(node.uid, target.uid, len(target.items)):
                target = doc.pages[(doc.pages.index(target) + 1) % len(doc.pages)]
                continue
            doc.move(node.uid, target.uid, len(target.items))
        if len(folder.pages) != pages_before - 1:
            report.add(FAIL, "빈 묶음 페이지 치우기", f"{pages_before} -> {len(folder.pages)}장")
        else:
            report.add(PASS, "빈 묶음 페이지 치우기", f"{pages_before}장 -> {len(folder.pages)}장")

    # 묶음을 통째로 비운다 -> 묶음이 사라져야 한다.
    target = doc.pages[0]
    guard = 0
    while folder.child_count() and guard < 60:
        guard += 1
        page = next((p for p in folder.pages if p.items), None)
        if page is None:
            break
        node = page.items[0]
        if doc.can_move(node.uid, target.uid, len(target.items)):
            target = doc.pages[(doc.pages.index(target) + 1) % len(doc.pages)]
            continue
        doc.move(node.uid, target.uid, len(target.items))

    still_there = any(
        n.uid == folder_uid for c in doc.containers() for n in c.items
    )
    if still_there:
        report.add(FAIL, "빈 묶음 치우기", "마지막 항목을 뺐는데도 묶음이 남아 있다")
    else:
        report.add(PASS, "빈 묶음 치우기", "마지막 항목이 빠지는 순간 묶음이 사라졌다")


def scenario_undo_all(doc: LayoutDocument, report: Report) -> None:
    """전부 취소하면 원본과 한 글자도 달라선 안 된다."""
    steps = 0
    while doc.can_undo and steps < 500:
        doc.undo()
        steps += 1
    if doc.can_undo:
        report.add(FAIL, "전부 취소", "취소가 끝나지 않는다")
        return
    if not doc.verify_identity():
        report.add(FAIL, "전부 취소", f"{steps}번 취소했으나 원본과 다르다")
        return
    if doc.dirty:
        report.add(FAIL, "전부 취소", "취소했는데도 '바뀜'으로 남아 있다")
        return
    report.add(PASS, "전부 취소", f"{steps}번 취소하고 원본과 완전히 같아졌다")


# ------------------------------------------------------------------ 2단계 (쓰기)


async def stage_two(bridge: DeviceBridge, store: BackupStore, origin: list[Any],
                    metrics: dict[str, Any], report: Report) -> None:
    """가장 작은 편집 하나를 실제로 보내고, 되읽어 대조한 뒤, 되돌린다."""
    log.info("")
    log.info("=== 2단계 — 기기에 씁니다 ===")

    doc = LayoutDocument.from_state(copy.deepcopy(origin), metrics)
    page = find_page_with_apps(doc, 2)
    if page is None:
        report.add(SKIP, "실기기 쓰기", "묶을 앱이 둘 있는 페이지가 없다")
        return
    first, second = movable_apps(page)[:2]
    folder_uid = doc.group([first.uid, second.uid], TEST_FOLDER_NAME)
    doc.rename_folder(folder_uid, TEST_FOLDER_NAME)
    sent = doc.to_state()

    log.info("   보낼 편집: '%s' 와 '%s' 를 묶어 '%s' 를 만든다",
             first.label, second.label, TEST_FOLDER_NAME)
    for line in doc.changes()[:10]:
        log.info("     - %s", line)

    await bridge.set_icon_state(sent)
    await asyncio.sleep(2.5)
    readback = await bridge.get_icon_state(artifact_name="icon_state_after_group")

    # 우리가 쓴 그대로 기기가 받았는가.
    result = compare_after_write(sent, readback)
    if result.lost or result.moved:
        report.add(FAIL, "지어낸 묶음을 기기가 받는가",
                   f"손실 {len(result.lost)} · 이동 {len(result.moved)}")
        for note in (result.lost + result.moved)[:6]:
            log.error("            %s", note)
    else:
        detail = "보낸 것과 되읽은 것이 같다"
        if result.added:
            detail += f" (iOS 가 되붙인 앱 {len(result.added)}개)"
        report.add(PASS, "지어낸 묶음을 기기가 받는가", detail)

    # 새 묶음이 실제로 기기에 있는가.
    found = [
        raw for entries in readback if isinstance(entries, list)
        for raw in entries
        if _is_folder_raw(raw) and raw.get("displayName") == TEST_FOLDER_NAME
    ]
    if len(found) == 1 and sum(len(p) for p in found[0][KEY_ICON_LISTS]) == 2:
        report.add(PASS, "새 묶음이 기기에 있는가", f"'{TEST_FOLDER_NAME}' 안에 2개")
    else:
        report.add(FAIL, "새 묶음이 기기에 있는가", f"찾은 묶음 {len(found)}개")

    # ----- 되돌린다.
    log.info("")
    log.info("   원래 배치로 되돌립니다.")
    await bridge.set_icon_state(origin)
    await asyncio.sleep(2.5)
    restored = await bridge.get_icon_state(artifact_name="icon_state_restored")
    back = compare_after_write(origin, restored)
    if back.lost or back.moved:
        report.add(FAIL, "되돌리기", f"손실 {len(back.lost)} · 이동 {len(back.moved)}")
        for note in (back.lost + back.moved)[:6]:
            log.error("            %s", note)
        log.error("   backups/ 의 가장 최근 파일로 직접 복원해 주세요.")
    else:
        detail = "원래 배치가 그대로 돌아왔다"
        if back.added:
            detail += f" (iOS 가 되붙인 앱 {len(back.added)}개 — 되돌릴 수 없는 부작용)"
        report.add(PASS, "되돌리기", detail)


# ------------------------------------------------------------------------- 실행


async def run(args: argparse.Namespace) -> int:
    session = start_session(PROJECT_ROOT, name="verify")
    log.info("편집 기능 실기기 검증 (%s)", session.id)
    log.info("기록: %s", session.log_path)

    bridge = DeviceBridge()
    store = BackupStore(PROJECT_ROOT)
    report = Report()

    try:
        log.info("")
        log.info("=== 기기 연결 ===")
        devices = await DeviceBridge.list_devices()
        if not devices:
            log.error("   연결된 iPhone이 없습니다. USB 로 연결하고 '신뢰'를 눌러 주세요.")
            return 2
        info = await bridge.connect(serial=args.udid)
        log.info("   %s", info.summary())

        origin = await bridge.get_icon_state(artifact_name="icon_state_before")
        metrics = await bridge.get_homescreen_icon_metrics()

        log.info("")
        log.info("=== 백업 ===")
        backup = store.save(origin, reason="verify-edits")
        log.info("   %s (항목 %d개 · 페이지 %d장)",
                 backup.path.name, backup.item_count, backup.page_count)

        doc = LayoutDocument.from_state(copy.deepcopy(origin), metrics)
        origin_leaves = leaf_census(origin)
        log.info("")
        log.info("=== 1단계 — 기기에 쓰지 않고 검증 ===")
        log.info("   %s", doc.summary())
        log.info("   한 페이지 %d칸 · 묶음 한 장 %d칸",
                 doc.grid.page_capacity, doc.grid.folder_page_capacity)
        log.info("")

        pre = empty_places(origin)
        if pre:
            report.add(FAIL, "읽어 온 배치에 빈 자리가 없는가", pre[0])
        else:
            report.add(PASS, "읽어 온 배치에 빈 자리가 없는가", "기기 그대로")

        folder_uid = scenario_group_and_rename(doc, report)
        check_consistent(doc, origin_leaves, report, "묶기·이름 바꾸기 뒤 상태")

        if folder_uid:
            scenario_folder_growth_and_spill(doc, folder_uid, report)
            check_consistent(doc, origin_leaves, report, "묶음 밀어내기 뒤 상태")

        scenario_home_spill(doc, report)
        check_consistent(doc, origin_leaves, report, "홈 밀어내기 뒤 상태")

        if folder_uid:
            scenario_prune(doc, folder_uid, report)
            check_consistent(doc, origin_leaves, report, "빈 자리 정리 뒤 상태")

        scenario_undo_all(doc, report)

        if args.apply:
            if report.failed:
                log.warning("")
                log.warning("   1단계에서 실패가 있어 기기에 쓰지 않습니다.")
                report.add(SKIP, "2단계(쓰기)", "1단계 실패")
            else:
                await stage_two(bridge, store, origin, metrics, report)
        else:
            log.info("")
            log.info("   (--apply 없이 실행했으므로 기기에 아무것도 쓰지 않았습니다)")

    except DeviceError as exc:
        log.error("기기 오류: %s", exc)
        return 2
    finally:
        await bridge.close()
        log.info("")
        report.summarize()
        session.export_zip()

    return 1 if report.failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="편집 기능 실기기 검증")
    parser.add_argument("--udid", default=None, help="기기를 지정한다 (여러 대일 때)")
    parser.add_argument("--apply", action="store_true",
                        help="2단계까지 — 실제로 기기에 쓴다 (백업 후 되돌린다)")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("중단했습니다.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
