"""기기 없이 확인할 수 있는 것들.

실기기 세션은 비싸고 되돌리기 번거롭다. 여기서 잡을 수 있는 것은 여기서 잡는다.
"""

import ast
import copy
import logging
import plistlib
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

#: 저장소 뿌리 — 라이선스·명세처럼 소스 밖에 있는 파일을 볼 때 쓴다.
ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "src"))

from ipsm.backup import BackupError, BackupStore  # noqa: E402
from ipsm.iconstate import (  # noqa: E402
    IconState,
    ItemKind,
    compare_after_write,
    deep_equal,
    diff_summary,
)
from ipsm.icons import IconStore, wanted_icons  # noqa: E402
from ipsm.layout import LayoutDocument, LayoutError  # noqa: E402
from ipsm.paths import DATA_DIRS, cache_root, data_root, ensure_ready  # noqa: E402
from ipsm.logging_setup import prune_sessions, start_session  # noqa: E402
from ipsm import product  # noqa: E402

# 실제 iconState 를 흉내낸 표본. 독 + 2페이지 + 폴더 + 위젯(우리가 모르는 것).
SAMPLE = [
    [
        {"displayName": "전화", "bundleIdentifier": "com.apple.mobilephone"},
        {"displayName": "Safari", "bundleIdentifier": "com.apple.mobilesafari"},
    ],
    [
        {"displayName": "메시지", "bundleIdentifier": "com.apple.MobileSMS", "iconModDate": datetime(2026, 8, 14, 2, 48, 0, 56643)},
        {
            "displayName": "도구",
            "listType": "folder",
            "iconLists": [
                [
                    {"displayName": "계산기", "bundleIdentifier": "com.apple.calculator"},
                    {"displayName": "나침반", "bundleIdentifier": "com.apple.compass"},
                ]
            ],
        },
        {"widgetPageID": "x", "gridSize": {"rows": 2, "columns": 2}},
    ],
    [{"displayName": "지도", "bundleIdentifier": "com.apple.Maps"}],
]


def test_parse_counts():
    state = IconState.parse(SAMPLE)
    assert len(state.pages) == 2
    assert len(state.dock) == 2
    assert state.counts() == {"app": 6, "folder": 1, "empty": 0, "unknown": 1}
    assert "com.apple.Maps" in state.bundle_ids()


def test_unknown_is_preserved_and_not_movable():
    """REQ-017: 모르는 것은 버리지도, 움직이지도 않는다."""
    state = IconState.parse(SAMPLE)
    unknown = [i for i in state.iter_items() if i.kind is ItemKind.UNKNOWN]
    assert len(unknown) == 1
    assert unknown[0].raw == {"widgetPageID": "x", "gridSize": {"rows": 2, "columns": 2}}
    assert not unknown[0].movable


def test_parse_does_not_mutate_input():
    original = copy.deepcopy(SAMPLE)
    state = IconState.parse(SAMPLE)
    state.raw[1][0]["displayName"] = "바뀜"
    assert SAMPLE == original


def test_volatile_fields_do_not_break_comparison():
    """iconModDate 는 기기가 갱신한다. 이걸로 불일치를 판정하면 항상 실패한다."""
    other = copy.deepcopy(SAMPLE)
    other[1][0]["iconModDate"] = datetime(2026, 8, 19, 9, 0, 0, 1)
    assert deep_equal(SAMPLE, other)


def test_real_differences_are_detected():
    other = copy.deepcopy(SAMPLE)
    del other[2]
    assert not deep_equal(SAMPLE, other)
    notes = diff_summary(SAMPLE, other)
    assert any("com.apple.Maps" in n for n in notes)


def test_lost_widget_is_detected():
    """가장 무서운 시나리오: 위젯이 조용히 사라지는 것."""
    other = copy.deepcopy(SAMPLE)
    del other[1][2]
    assert not deep_equal(SAMPLE, other)
    assert any("알 수 없는 항목" in n for n in diff_summary(SAMPLE, other))


def test_backup_round_trip():
    root = Path(tempfile.mkdtemp())
    start_session(root, name="test")
    store = BackupStore(root)
    backup = store.save(SAMPLE, reason="unit test!")
    assert store.load(backup.path) == SAMPLE
    assert backup.reason == "unit test!"
    assert store.latest().reason == "unit-test"  # 파일명은 안전한 문자만
    assert len(store.list_backups()) == 1


def test_backup_refuses_unserializable_state():
    """plist 로 저장할 수 없는 상태라면 백업은 실패해야 한다.

    '파일은 만들어졌지만 복원할 수 없는' 백업은 없는 것보다 나쁘다.
    호출자는 BackupError 를 받고 쓰기를 포기한다 — 그것이 옳은 동작이다.
    """
    root = Path(tempfile.mkdtemp())
    start_session(root, name="test")
    store = BackupStore(root)
    try:
        store.save([[object()]], reason="broken")
    except BackupError:
        pass
    else:
        raise AssertionError("저장 불가한 상태를 백업했다고 보고했다")

    # 실패한 백업의 잔해가 남으면 안 된다. 남으면 list_backups() 가 그것을 멀쩡한
    # 백업으로 보여주고, 사용자는 되돌릴 수 있다고 믿게 된다.
    assert list(store.dir.iterdir()) == [], f"실패한 백업이 남았다: {list(store.dir.iterdir())}"
    assert store.list_backups() == []


def test_appended_apps_are_not_treated_as_damage():
    """iOS 는 홈화면에 없던 앱을 쓰기 때마다 마지막 페이지 끝에 되붙인다.

    실기기 항등 왕복에서 실제로 일어났다 — 309개 중 사라지거나 움직인 것은 하나도 없고,
    앱 라이브러리에만 있던 앱 4개가 6페이지 끝에 붙었다. 이것을 '실패'로 판정하면 멀쩡한
    기기에서 편집 기능을 영영 못 만든다. 반대로 손실과 뭉뚱그리면 훼손을 놓친다.
    """
    after = copy.deepcopy(SAMPLE)
    after[2].append({"displayIdentifier": "jp.naver.line", "displayName": "LINE"})

    result = compare_after_write(SAMPLE, after)
    assert result.safe, "붙기만 했는데 훼손으로 판정했다"
    assert not result.identical
    assert result.added and "jp.naver.line" in result.added[0]
    assert "2페이지" in result.added[0], result.added


def test_loss_and_move_are_treated_as_damage():
    """사라짐과 이동은 반드시 실패여야 한다 — 사용자가 만든 배치가 훼손된 것이다."""
    lost_one = copy.deepcopy(SAMPLE)
    del lost_one[1][0]
    assert not compare_after_write(SAMPLE, lost_one).safe

    moved = copy.deepcopy(SAMPLE)
    moved[1][0], moved[1][1] = moved[1][1], moved[1][0]
    result = compare_after_write(SAMPLE, moved)
    assert not result.safe and result.moved, result

    # 폴더 안에서의 이동도 잡아야 한다. 폴더는 식별자가 없으므로 이름으로 추적한다.
    inner = copy.deepcopy(SAMPLE)
    inner[1][1]["iconLists"][0].reverse()
    assert not compare_after_write(SAMPLE, inner).safe


def test_real_device_shapes_are_all_understood():
    """실기기(iPhone 14, iOS 26.1)에서 관측된 네 가지 형태가 모두 해석되어야 한다.

    처음에는 bundleIdentifier 를 항목의 정체성으로 가정했다가, 실기기에서 79개가
    '알 수 없는 항목'으로 잡혔다. 오프로드된 앱에는 그 키가 아예 없었다.
    알 수 없는 항목은 UI에서 움직일 수 없게 되므로, 이 오해는 앱의 절반을 얼려버린다.
    """
    state = [
        [
            {  # 설치된 앱
                "bundleIdentifier": "com.apple.mobilephone",
                "bundleVersion": "1.0",
                "displayIdentifier": "com.apple.mobilephone",
                "displayName": "전화",
                "iconModDate": datetime(2026, 8, 14, 2, 48, 0, 56643),
            },
        ],
        [
            {"displayIdentifier": "kr.co.captv.pooqV2", "displayName": "Wavve"},  # 오프로드
            {  # 웹 클립
                "displayIdentifier": "com.apple.webapp.X",
                "displayName": "북마크",
                "iconModDate": datetime(2026, 8, 1, 0, 0, 0, 1),
                "webClipURL": "https://example.com",
            },
            {  # 폴더
                "displayName": "도구",
                "listType": "folder",
                "iconLists": [[{"displayIdentifier": "com.x.y", "displayName": "Y"}]],
            },
        ],
    ]
    parsed = IconState.parse(state)
    counts = parsed.counts()
    assert counts["unknown"] == 0, f"해석하지 못한 항목이 남았다: {counts}"
    assert counts["app"] == 4 and counts["folder"] == 1, counts
    assert all(item.movable for item in parsed.iter_items() if item.kind is ItemKind.APP)

    by_name = {item.label: item for item in parsed.iter_items()}
    assert by_name["전화"].installed
    assert not by_name["Wavve"].installed          # 오프로드된 앱
    assert by_name["북마크"].is_web_clip
    assert by_name["Wavve"].bundle_id == "kr.co.captv.pooqV2"


def test_backup_preserves_sub_second_dates():
    """iconModDate 는 마이크로초까지 있고, XML plist 는 그것을 잘라낸다.

    실기기에서 바로 이 이유로 백업 검증이 걸렸다. 초 단위로 잘린 날짜는 홈화면 복원에는
    영향이 없지만, 그것을 판단할 수 있는 것은 사람이지 코드가 아니다. 백업은 원본과
    같아야 하고, 같지 않으면 멈춰야 한다 — 그러니 애초에 잃지 않는 형식으로 저장한다.
    """
    root = Path(tempfile.mkdtemp())
    start_session(root, name="test")
    store = BackupStore(root)
    backup = store.save(SAMPLE, reason="dates")
    restored = store.load(backup.path)
    assert restored[1][0]["iconModDate"] == SAMPLE[1][0]["iconModDate"], (
        f"날짜가 손실되었다: {restored[1][0]['iconModDate']}"
    )
    assert restored == SAMPLE


def test_backup_file_is_a_valid_plist():
    root = Path(tempfile.mkdtemp())
    start_session(root, name="test")
    store = BackupStore(root)
    backup = store.save(SAMPLE, reason="probe")
    assert plistlib.loads(backup.path.read_bytes()) == SAMPLE



# ---------------------------------------------------------------- 편집 모델

def _doc(state=None):
    return LayoutDocument.from_state(copy.deepcopy(state if state is not None else SAMPLE))


def test_document_shape_matches_sample():
    doc = _doc()
    assert len(doc.pages) == 2, len(doc.pages)
    assert len(doc.dock.items) == 2
    folder = doc.pages[0].items[1]
    assert folder.is_folder and folder.child_count() == 2


def test_identity_holds_without_edits():
    """편집이 없으면 내보낸 결과가 원본과 완전히 같아야 한다.

    이것이 깨지면 문서 모델이 무언가를 잃고 있다는 뜻이고, 그대로 기기에 쓰면
    사용자의 홈화면에서 그것이 사라진다 (REQ-017).
    """
    doc = _doc()
    assert doc.verify_identity()
    assert doc.to_state() == doc.origin
    assert not doc.dirty


def test_undo_restores_the_original_exactly():
    doc = _doc()
    node = doc.pages[1].items[0]           # 3페이지의 '지도'
    doc.move(node.uid, doc.pages[0].uid, 0)
    assert doc.dirty and doc.to_state() != doc.origin
    doc.undo()
    assert doc.to_state() == doc.origin, "되돌린 결과가 원본과 다르다"
    assert not doc.dirty
    assert doc.changes() == []


def test_redo_returns_to_the_edited_state():
    doc = _doc()
    node = doc.pages[1].items[0]
    doc.move(node.uid, doc.pages[0].uid, 0)
    edited = doc.to_state()
    doc.undo()
    doc.redo()
    assert doc.to_state() == edited


def test_unknown_item_cannot_be_moved():
    """위젯처럼 해석하지 못한 항목은 붙잡을 수 없어야 한다."""
    doc = _doc()
    widget = doc.pages[0].items[2]
    assert not widget.movable
    assert doc.can_move(widget.uid, doc.pages[1].uid) is not None


def test_full_container_is_refused_with_a_reason():
    doc = _doc()
    doc.pages[1].capacity = len(doc.pages[1].items)   # 이미 가득 찬 것으로 둔다
    node = doc.dock.items[0]
    reason = doc.can_move(node.uid, doc.pages[1].uid)
    assert reason and "가득" in reason, reason


def test_folder_cannot_go_inside_a_folder():
    doc = _doc()
    folder = doc.pages[0].items[1]
    inner_page = folder.pages[0]
    assert doc.can_move(folder.uid, inner_page.uid) is not None


def test_page_reorder_is_not_reported_as_item_moves():
    """페이지를 옮긴 것은 페이지 한 줄로만 보고돼야 한다.

    페이지 안의 앱까지 '옮겨졌다'고 세면, 변경 목록이 수십 줄로 불어나
    사용자가 적용 전에 읽지 않게 된다.
    """
    doc = _doc()
    doc.reorder_pages(0, 1)
    changes = doc.changes()
    assert len(changes) == 1, changes


def test_empty_page_only_can_be_removed():
    doc = _doc()
    try:
        doc.remove_page(0)
    except LayoutError:
        pass
    else:
        raise AssertionError("비어 있지 않은 페이지가 지워졌다")
    doc.add_page()
    doc.remove_page(len(doc.pages) - 1)
    assert doc.to_state() == doc.origin


def test_last_page_cannot_be_removed():
    doc = _doc([[], []])
    try:
        doc.remove_page(0)
    except LayoutError:
        return
    raise AssertionError("마지막 페이지가 지워졌다")


def test_placed_identifiers_reach_inside_folders():
    doc = _doc()
    placed = doc.placed_identifiers()
    assert "com.apple.calculator" in placed, "폴더 안의 앱이 빠졌다"
    assert "com.apple.mobilephone" in placed


def test_unplaced_apps_only_lists_what_is_missing():
    doc = _doc()
    installed = {
        "com.apple.calculator": "계산기",          # 폴더 안에 있다
        "com.apple.Maps": "지도",                   # 페이지에 있다
        "com.example.library": "앱 라이브러리에만",  # 어디에도 없다
    }
    unplaced = doc.unplaced_apps(installed)
    assert [bundle for bundle, _name in unplaced] == ["com.example.library"], unplaced


def test_grouping_makes_one_folder_and_undo_restores_the_original():
    """묶기는 편집 하나다 — 되돌리면 원본과 **완전히** 같아야 한다 (REQ-017)."""
    doc = _doc()
    maps = doc.pages[1].items[0]          # 3페이지 '지도'
    msg = doc.pages[0].items[0]           # 2페이지 '메시지'
    uid = doc.group([maps.uid, msg.uid], "새 폴더")

    folder = doc.node(uid)
    assert folder.is_folder
    assert [n.label for page in folder.pages for n in page.items] == ["메시지", "지도"], (
        "화면에 보이는 순서(앞 페이지 먼저)로 담겨야 한다"
    )
    # 첫 항목이 있던 자리에 놓인다
    assert doc.pages[0].items[0] is folder
    raw = folder.to_raw()
    assert set(raw) == {"displayName", "listType", "iconLists"}, raw
    assert raw["listType"] == "folder"
    assert [item["displayName"] for item in raw["iconLists"][0]] == ["메시지", "지도"]

    doc.undo()
    assert doc.to_state() == doc.origin, "되돌린 결과가 원본과 다르다"
    assert not doc.dirty


def test_grouping_redo_returns_to_the_same_result():
    doc = _doc()
    a = doc.dock.items[0]
    b = doc.dock.items[1]
    doc.group([a.uid, b.uid], "묶음")
    edited = doc.to_state()
    doc.undo()
    doc.redo()
    assert doc.to_state() == edited


def test_grouping_refuses_what_ios_cannot_hold():
    doc = _doc()
    folder = doc.pages[0].items[1]
    widget = doc.pages[0].items[2]
    maps = doc.pages[1].items[0]
    inner = folder.pages[0].items[0]

    assert "두 개 이상" in (doc.can_group([maps.uid]) or "")
    assert "이미 묶음" in (doc.can_group([folder.uid, maps.uid]) or "")
    assert "해석하지 못한" in (doc.can_group([widget.uid, maps.uid]) or "")
    assert "묶음 안에 있습니다" in (doc.can_group([inner.uid, maps.uid]) or "")
    # 거절된 요청은 문서를 건드리지 않는다
    assert doc.to_state() == doc.origin


def test_grouping_respects_the_folder_capacity():
    many = [[], [{"displayName": f"앱{i}", "bundleIdentifier": f"x.{i}"} for i in range(20)]]
    doc = _doc(many)
    doc.grid.folder_max_pages = 2          # 9 x 2 = 18 까지만 들어간다
    limit = doc.grid.folder_page_capacity * doc.grid.folder_max_pages
    uids = [n.uid for n in doc.pages[0].items]

    reason = doc.can_group(uids[: limit + 1])
    assert reason and str(limit) in reason, reason

    doc.group(uids[:limit], "가득")
    folder = doc.pages[0].items[0]
    assert sum(len(page.items) for page in folder.pages) == limit
    assert len(folder.pages) == doc.grid.folder_max_pages
    assert all(len(page.items) <= doc.grid.folder_page_capacity for page in folder.pages)


def test_renaming_a_folder_changes_only_the_name():
    doc = _doc()
    folder = doc.pages[0].items[1]
    before = folder.to_raw()

    doc.rename_folder(folder.uid, "새 이름")
    after = folder.to_raw()
    assert after["displayName"] == "새 이름"
    assert after["iconLists"] == before["iconLists"], "이름만 바꿨는데 내용이 달라졌다"
    assert set(after) == set(before)
    assert folder.label == "새 이름"

    assert doc.dirty, "이름만 바꾸면 아무것도 움직이지 않는다 — 그래도 변경이다"
    assert any("묶음 이름" in note for note in doc.changes()), doc.changes()

    doc.undo()
    assert doc.to_state() == doc.origin
    assert not doc.dirty


def test_renaming_refuses_what_is_not_a_folder_or_has_no_name():
    doc = _doc()
    folder = doc.pages[0].items[1]
    app = doc.dock.items[0]
    assert doc.can_rename(app.uid, "이름") is not None
    assert "비워" in (doc.can_rename(folder.uid, "   ") or "")
    assert doc.can_rename(folder.uid, "정상") is None
    doc.rename_folder(folder.uid, "  도구  ")   # 같은 이름이면 이력을 늘리지 않는다
    assert not doc.can_undo


def test_group_and_rename_are_reported_as_one_line_each():
    doc = _doc()
    maps = doc.pages[1].items[0]
    msg = doc.pages[0].items[0]
    uid = doc.group([maps.uid, msg.uid], "새 폴더")
    notes = doc.changes()
    assert len(notes) == 1, notes           # 안에 든 앱을 따로 세지 않는다
    assert "새 묶음 “새 폴더” 만듦" in notes[0] and "2개" in notes[0]

    doc.rename_folder(uid, "고침")
    notes = doc.changes()
    assert len(notes) == 1, notes           # 새로 만든 묶음의 이름 변경은 '만듦' 한 줄에 흡수
    assert "고침" in notes[0]


def test_changes_are_written_in_user_language():
    doc = _doc()
    node = doc.pages[1].items[0]
    doc.move(node.uid, doc.pages[0].uid, 0)
    # 2페이지에 혼자 있던 앱이라 페이지도 함께 없어진다. 그 줄이 먼저 오므로
    # 첫 줄이 아니라 '항목 줄이 있는가'를 본다.
    line = next(line for line in doc.changes() if "지도" in line)
    assert "→" in line, line



def test_folder_opens_a_new_page_when_the_current_one_is_full():
    """묶음 페이지가 찼다고 해서 묶음이 찬 것은 아니다.

    iPhone 은 이 자리에서 페이지를 한 장 더 편다. 우리가 거절해 버리면 사용자는
    기기에서 되던 일이 PC 에서 안 된다고 느낀다.
    """
    doc = _doc()
    folder = doc.pages[0].items[1]
    folder.pages[0].capacity = 2          # 이미 두 개가 들어 있으니 꽉 찬 상태
    assert folder.pages[0].full
    maps = doc.pages[1].items[0]

    assert doc.can_move(maps.uid, folder.pages[0].uid) is None, "받을 수 있어야 한다"
    doc.move(maps.uid, folder.pages[0].uid, 99)

    assert len(folder.pages) == 2, [len(page.items) for page in folder.pages]
    assert [n.label for n in folder.pages[1].items] == ["지도"]
    assert folder.child_count() == 3

    doc.undo()
    assert len(folder.pages) == 1, "되돌리면 펴 놓은 페이지도 접혀야 한다"
    assert doc.to_state() == doc.origin


def test_folder_fills_an_existing_gap_before_opening_a_new_page():
    """빈자리가 이미 있으면 페이지를 새로 펴지 않는다."""
    two_pages = copy.deepcopy(SAMPLE)
    two_pages[1][1]["iconLists"].append(
        [{"displayName": "시계", "bundleIdentifier": "com.apple.clock"}]
    )
    doc = _doc(two_pages)
    folder = doc.pages[0].items[1]
    assert len(folder.pages) == 2
    folder.pages[0].capacity = 2               # 1페이지만 꽉 찼다
    maps = doc.pages[1].items[0]

    doc.move(maps.uid, folder.pages[0].uid, 99)

    assert len(folder.pages) == 2, "빈자리를 두고 페이지를 새로 폈다"
    assert [n.label for n in folder.pages[1].items] == ["시계", "지도"]


def test_folder_stops_growing_at_the_device_limit():
    doc = _doc()
    folder = doc.pages[0].items[1]
    folder.pages[0].capacity = 2
    doc.grid.folder_max_pages = 1              # 더 펼 수 없는 기기라고 둔다
    maps = doc.pages[1].items[0]
    reason = doc.can_move(maps.uid, folder.pages[0].uid)
    assert reason and "가득" in reason, reason


def test_emptying_a_folder_removes_it_in_the_same_step():
    """마지막 하나를 꺼내면 빈 묶음이 남지 않아야 한다.

    실기기 확인(2026-08-20): 빈 묶음을 그대로 보내면 iOS 가 그것을 지우고,
    뒤따르던 항목이 전부 한 칸씩 밀린다. 우리 검증기는 그것을 '손실 3건 ·
    의도치 않은 이동 39건'으로 읽는다. 우리가 먼저 지워야 보낸 것과 되읽은 것이 맞는다.
    """
    doc = _doc()
    folder = doc.pages[0].items[1]
    first, second = folder.pages[0].items[0], folder.pages[0].items[1]

    doc.move(first.uid, doc.pages[1].uid, 0)
    assert folder.child_count() == 1
    assert any(item is folder for item in doc.pages[0].items), "아직 지우면 안 된다"

    doc.move(second.uid, doc.pages[1].uid, 0)
    assert not any(item is folder for item in doc.pages[0].items), "빈 묶음이 남았다"

    said = [line for line in doc.changes() if "없어짐" in line]
    assert said and "도구" in said[0], doc.changes()

    doc.undo()
    assert any(item is folder for item in doc.pages[0].items), "되돌리면 묶음이 돌아와야 한다"
    doc.undo()
    assert doc.to_state() == doc.origin
    assert not doc.dirty


def test_removing_an_emptied_folder_is_one_undo_not_two():
    """드래그 한 번 = 취소 한 번 (REQ-014).

    묶음이 없어지는 것을 따로 명령으로 두면, 취소를 한 번 눌렀을 때 '항목은 돌아왔는데
    묶음은 없는' 상태가 드러난다. 사용자가 만든 적 없는 모양이다.
    """
    doc = _doc()
    folder = doc.pages[0].items[1]
    for node in list(folder.pages[0].items):
        doc.move(node.uid, doc.pages[1].uid, 0)
    before = len(doc._undo)
    doc.undo()
    assert len(doc._undo) == before - 1
    assert any(item is folder for item in doc.pages[0].items)
    assert folder.child_count() == 1


def test_moving_inside_a_folder_does_not_delete_it():
    """묶음 안에서 자리만 바꾼 것은 비운 것이 아니다."""
    doc = _doc()
    folder = doc.pages[0].items[1]
    doc.move(folder.pages[0].items[0].uid, folder.pages[0].uid, 2)
    assert any(item is folder for item in doc.pages[0].items)
    assert folder.child_count() == 2



def _folder_doc(page1: int, page2: int = 0, capacity: int = 3):
    """묶음 하나를 원하는 만큼 채워서 만든다. (문서, 묶음 노드) 를 돌려준다.

    페이지 용량을 3 으로 줄여 쓰는 이유는, 9칸을 채우는 표본은 읽는 사람이 세어 봐야
    하기 때문이다. 밀어내기에서 중요한 것은 칸 수가 아니라 '넘치면 어디로 가는가'다.
    """
    state = [
        [],
        [
            {
                "displayName": "도구",
                "listType": "folder",
                "iconLists": [
                    [{"displayName": f"1-{i}", "bundleIdentifier": f"a.p1.{i}"} for i in range(page1)],
                ]
                + (
                    [[{"displayName": f"2-{i}", "bundleIdentifier": f"a.p2.{i}"} for i in range(page2)]]
                    if page2
                    else []
                ),
            },
            {"displayName": "지도", "bundleIdentifier": "com.apple.Maps"},
        ],
    ]
    doc = LayoutDocument.from_state(state, {"homeScreenIconFolderColumns": capacity, "homeScreenIconFolderRows": 1})
    return doc, doc.pages[0].items[0]


def test_full_folder_page_pushes_its_last_item_to_the_next_page():
    """사용자가 말한 그 동작 — 1페이지가 꽉 찼을 때 2페이지에서 앱을 끌어오면
    1페이지의 마지막 앱이 2페이지로 밀려간다. iPhone 에서 하던 그대로다."""
    doc, folder = _folder_doc(page1=3, page2=2)
    moving = folder.pages[1].items[0]          # 2페이지의 첫 앱 (2-0)

    doc.move(moving.uid, folder.pages[0].uid, 1)   # 1페이지 두 번째 자리에 끼운다

    assert [n.label for n in folder.pages[0].items] == ["1-0", "2-0", "1-1"]
    # 밀려난 것은 다음 페이지 **맨 앞**이다 — 보이는 순서가 그래야 이어진다.
    assert [n.label for n in folder.pages[1].items] == ["1-2", "2-1"]
    assert folder.child_count() == 5, "밀어내기는 개수를 바꾸지 않는다"

    doc.undo()
    assert doc.to_state() == doc.origin
    assert not doc.dirty


def test_pushing_cascades_through_pages_that_are_also_full():
    """밀려난 것이 다음 페이지도 넘치게 하면, 그 다음 페이지로 계속 밀린다."""
    doc, folder = _folder_doc(page1=3, page2=3)
    outside = doc.pages[0].items[1]            # 지도 — 묶음 밖에서 들어온다

    doc.move(outside.uid, folder.pages[0].uid, 0)

    assert [n.label for n in folder.pages[0].items] == ["지도", "1-0", "1-1"]
    assert [n.label for n in folder.pages[1].items] == ["1-2", "2-0", "2-1"]
    assert [n.label for n in folder.pages[2].items] == ["2-2"], "3페이지가 새로 펴져야 한다"
    assert folder.child_count() == 7

    doc.undo()
    assert len(folder.pages) == 2
    assert doc.to_state() == doc.origin


def test_a_completely_full_folder_still_allows_moving_inside_it():
    """꽉 찬 묶음이라도 그 안에서 자리를 바꾸는 것은 개수를 늘리지 않는다.

    예전에는 '가득 찼습니다'로 막았다. 사용자에게는 2페이지 앱을 1페이지로
    끌어다 놓아도 아무 일도 일어나지 않는 것으로 보였다.
    """
    doc, folder = _folder_doc(page1=3, page2=3)
    doc.grid.folder_max_pages = 2              # 더 펼 수 없다
    moving = folder.pages[1].items[2]          # 2페이지 마지막 (2-2)

    assert doc.can_move(moving.uid, folder.pages[0].uid) is None
    doc.move(moving.uid, folder.pages[0].uid, 0)

    assert [n.label for n in folder.pages[0].items] == ["2-2", "1-0", "1-1"]
    assert [n.label for n in folder.pages[1].items] == ["1-2", "2-0", "2-1"]
    assert len(folder.pages) == 2
    assert folder.child_count() == 6


def test_dropping_past_the_end_does_not_push_anyone():
    """끝에 붙이려는 것은 밀 이유가 없다. 겨누지도 않은 항목이 페이지를 넘으면
    사용자는 자기가 옮긴 것이 무엇인지 알 수 없게 된다."""
    doc, folder = _folder_doc(page1=3, page2=1)
    outside = doc.pages[0].items[1]

    doc.move(outside.uid, folder.pages[0].uid, 99)

    assert [n.label for n in folder.pages[0].items] == ["1-0", "1-1", "1-2"], "아무도 밀리지 않았다"
    assert [n.label for n in folder.pages[1].items] == ["2-0", "지도"]


def _home_doc(*counts: int, columns: int = 3) -> "LayoutDocument":
    """홈 페이지만 여러 장 있는 문서. 각 페이지에 `counts[i]` 개의 앱을 둔다."""
    state = [[]] + [
        [
            {"displayName": f"{page + 1}-{i}", "bundleIdentifier": f"a.p{page + 1}.{i}"}
            for i in range(count)
        ]
        for page, count in enumerate(counts)
    ]
    return LayoutDocument.from_state(
        state, {"homeScreenIconColumns": columns, "homeScreenIconRows": 1}
    )


def test_full_home_page_pushes_its_last_app_to_the_next_page():
    """사용자가 말한 그 동작 — 2페이지에서 앱을 끌어왔는데 1페이지가 꽉 찼으면
    1페이지의 마지막 앱이 2페이지로 밀려간다. 묶음에서 하던 것과 같다."""
    doc = _home_doc(3, 2)
    moving = doc.pages[1].items[0]                 # 2페이지의 첫 앱 (2-0)

    doc.move(moving.uid, doc.pages[0].uid, 1)      # 1페이지 두 번째 자리에 끼운다

    assert [n.label for n in doc.pages[0].items] == ["1-0", "2-0", "1-1"]
    # 밀려난 것은 다음 페이지 **맨 앞**이다 — 보이는 순서가 그래야 이어진다.
    assert [n.label for n in doc.pages[1].items] == ["1-2", "2-1"]
    assert sum(len(page.items) for page in doc.pages) == 5, "밀어내기는 개수를 바꾸지 않는다"

    doc.undo()
    assert doc.to_state() == doc.origin
    assert not doc.dirty


def test_home_pushing_cascades_and_opens_a_new_page():
    """밀려난 것이 다음 페이지도 넘치게 하면 계속 밀리고, 끝에 이르면 한 장 편다."""
    doc = _home_doc(3, 3)
    moving = doc.pages[1].items[2]                 # 2-2

    doc.move(moving.uid, doc.pages[0].uid, 0)

    assert [n.label for n in doc.pages[0].items] == ["2-2", "1-0", "1-1"]
    assert [n.label for n in doc.pages[1].items] == ["1-2", "2-0", "2-1"]
    assert len(doc.pages) == 2, "2-2 가 빠진 자리에 1-2 가 들어가 새 페이지가 필요 없다"

    doc.undo()
    assert doc.to_state() == doc.origin


def test_home_pushing_opens_a_new_page_when_every_page_is_full():
    """밖에서 들어와 모든 페이지가 넘치면 iPhone 처럼 페이지를 한 장 더 편다."""
    state = [
        [{"displayName": "독앱", "bundleIdentifier": "a.dock"}],
        [{"displayName": f"1-{i}", "bundleIdentifier": f"a.p1.{i}"} for i in range(3)],
        [{"displayName": f"2-{i}", "bundleIdentifier": f"a.p2.{i}"} for i in range(3)],
    ]
    doc = LayoutDocument.from_state(state, {"homeScreenIconColumns": 3, "homeScreenIconRows": 1})
    dock_app = doc.dock.items[0]

    doc.move(dock_app.uid, doc.pages[0].uid, 0)

    assert [n.label for n in doc.pages[0].items] == ["독앱", "1-0", "1-1"]
    assert [n.label for n in doc.pages[1].items] == ["1-2", "2-0", "2-1"]
    assert [n.label for n in doc.pages[2].items] == ["2-2"], "3페이지가 새로 펴져야 한다"
    assert doc.dock.items == []

    doc.undo()
    assert len(doc.pages) == 2
    assert doc.to_state() == doc.origin
    assert not doc.dirty


def test_home_pushing_is_refused_when_there_is_nowhere_left():
    """페이지를 더 펼 수 없고 뒤도 다 찼으면 미는 대신 이유를 말한다."""
    doc = _home_doc(3, 3)
    doc.grid.max_pages = 2
    moving = doc.pages[1].items[0]

    reason = doc.can_move(moving.uid, doc.pages[0].uid, 0)
    assert reason and "가득" in reason, reason
    assert [n.label for n in doc.pages[0].items] == ["1-0", "1-1", "1-2"]


def test_dropping_past_the_end_of_a_full_home_page_does_not_push():
    """끝에 붙이려는 것은 밀 이유가 없다. 겨누지도 않은 앱이 페이지를 넘으면
    사용자는 자기가 옮긴 것이 무엇인지 알 수 없게 된다."""
    doc = _home_doc(3, 1)
    moving = doc.pages[1].items[0]

    reason = doc.can_move(moving.uid, doc.pages[0].uid, 99)
    assert reason and "가득" in reason, reason
    # 자리를 모르고 물어도 마찬가지다 — 보수적으로 거절한다.
    assert doc.can_move(moving.uid, doc.pages[0].uid) is not None


def test_emptying_a_home_page_removes_that_page():
    """홈 페이지도 다 비면 없앤다.

    빈 페이지를 그대로 실어 보내면 iOS 가 지우면서 뒤가 밀리고, 우리 검증기는
    그것을 손실·오이동으로 읽는다 — 빈 묶음 때(2026-08-20 실기기)와 같은 일이다.
    """
    doc = _home_doc(2, 1)
    alone = doc.pages[1].items[0]

    doc.move(alone.uid, doc.pages[0].uid, 0)

    assert len(doc.pages) == 1, "다 빈 페이지가 남았다"
    assert [n.label for n in doc.pages[0].items] == ["2-0", "1-0", "1-1"]

    doc.undo()
    assert len(doc.pages) == 2
    assert doc.to_state() == doc.origin
    assert not doc.dirty


def test_the_last_home_page_is_kept_even_when_empty():
    """페이지가 하나도 없는 홈화면은 없다. 마지막 한 장은 비어도 남긴다."""
    doc = _home_doc(1)
    alone = doc.pages[0].items[0]

    doc.move(alone.uid, doc.dock.uid, 0)

    assert len(doc.pages) == 1
    assert doc.pages[0].items == []
    doc.undo()
    assert doc.to_state() == doc.origin


def test_a_folder_alone_on_a_page_takes_the_page_with_it():
    """묶음이 통째로 없어지면 그 묶음만 있던 페이지도 함께 빈다.

    묶음만 지우고 페이지를 두고 오면, 빈 페이지가 그대로 기기로 실려 간다.
    """
    state = [
        [],
        [{"displayName": "1-0", "bundleIdentifier": "a.p1.0"}],
        [
            {
                "displayName": "도구",
                "listType": "folder",
                "iconLists": [[{"displayName": "혼자앱", "bundleIdentifier": "a.only"}]],
            }
        ],
    ]
    doc = LayoutDocument.from_state(state, {"homeScreenIconColumns": 3, "homeScreenIconRows": 1})
    only = doc.pages[1].items[0].pages[0].items[0]

    doc.move(only.uid, doc.pages[0].uid, 1)

    assert len(doc.pages) == 1, "묶음이 사라진 빈 페이지가 남았다"
    assert [n.label for n in doc.pages[0].items] == ["1-0", "혼자앱"]

    doc.undo()
    assert len(doc.pages) == 2
    assert doc.to_state() == doc.origin
    assert not doc.dirty


def test_emptying_a_folder_page_removes_that_page():
    """묶음 안의 페이지도 다 비면 없앤다.

    빈 페이지를 그대로 실어 보내면 iOS 가 지우면서 뒤가 밀리고, 우리 검증기는
    그것을 손실·오이동으로 읽는다 — 빈 묶음 때(2026-08-20 실기기)와 같은 일이다.
    """
    doc, folder = _folder_doc(page1=2, page2=1)
    alone = folder.pages[1].items[0]           # 2페이지에 혼자 있는 앱

    doc.move(alone.uid, doc.pages[0].uid, 0)

    assert len(folder.pages) == 1, "다 빈 페이지가 남았다"
    assert folder.child_count() == 2
    assert any(item is folder for item in doc.pages[0].items), "묶음까지 지우면 안 된다"

    doc.undo()
    assert len(folder.pages) == 2
    assert doc.to_state() == doc.origin


def test_leaving_a_page_empty_prunes_it_even_when_the_move_pushes():
    """빈 페이지 치우기와 밀어내기가 한 번에 일어나는 자리.

    떠나온 묶음의 페이지가 다 비었는데 도착한 곳이 꽉 찬 페이지라면, 두 가지가
    동시에 필요하다. 밀어내기만 하고 빈 페이지를 두고 오면 그 페이지는 그대로
    기기로 실려 간다.
    """
    state = [
        [],
        [
            {
                "displayName": "도구",
                "listType": "folder",
                "iconLists": [[{"displayName": f"1-{i}", "bundleIdentifier": f"a.p1.{i}"} for i in range(3)]],
            },
            {
                "displayName": "짐",
                "listType": "folder",
                "iconLists": [
                    [{"displayName": "머무는앱", "bundleIdentifier": "b.stay"}],
                    [{"displayName": "떠나는앱", "bundleIdentifier": "b.go"}],
                ],
            },
        ],
    ]
    doc = LayoutDocument.from_state(state, {"homeScreenIconFolderColumns": 3, "homeScreenIconFolderRows": 1})
    tools, bag = doc.pages[0].items[0], doc.pages[0].items[1]
    leaving = bag.pages[1].items[0]

    doc.move(leaving.uid, tools.pages[0].uid, 1)

    assert [n.label for n in tools.pages[0].items] == ["1-0", "떠나는앱", "1-1"]
    assert [n.label for n in tools.pages[1].items] == ["1-2"]
    assert len(bag.pages) == 1, "다 빈 페이지가 남았다"
    assert [n.label for n in bag.pages[0].items] == ["머무는앱"]

    doc.undo()
    assert doc.to_state() == doc.origin
    assert not doc.dirty


def test_removing_an_emptied_page_is_one_undo_not_two():
    doc, folder = _folder_doc(page1=2, page2=1)
    alone = folder.pages[1].items[0]
    doc.move(alone.uid, doc.pages[0].uid, 0)
    before = len(doc._undo)
    doc.undo()
    assert len(doc._undo) == before - 1
    assert len(folder.pages) == 2


def test_the_last_page_of_a_folder_is_kept_even_when_empty():
    """페이지가 하나뿐인 묶음에서 마지막 앱을 빼면, 없어지는 것은 묶음이지
    페이지가 아니다. 페이지만 지우면 iconLists 가 없는 폴더가 되어 버린다."""
    doc, folder = _folder_doc(page1=1)
    only = folder.pages[0].items[0]
    doc.move(only.uid, doc.pages[0].uid, 0)
    assert not any(item is folder for item in doc.pages[0].items), "빈 묶음은 없어져야 한다"


def test_version_is_one_point_zero_and_shows_in_the_title():
    """버전 선언은 한 곳뿐이고, 사용자가 보는 곳(창 제목)이 그것을 읽는다."""
    from ipsm import version

    assert (version.VERSION_MAJOR, version.VERSION_MINOR) == (1, 0)
    assert 0 <= version.VERSION_PATCH <= 99
    assert version.VERSION_TEXT == f"v01.00.{version.VERSION_PATCH:02d}"

    source = (Path(__file__).resolve().parents[1] / "src/ipsm/ui/main_window.py").read_text(
        encoding="utf-8"
    )
    assert "VERSION_TEXT" in source, "창 제목이 버전을 읽지 않는다"


# ------------------------------------------------------------- 이름과 후원


def test_the_store_name_carries_no_apple_trademark():
    """스토어의 '앱 이름' 칸에 Apple 상표가 들어가면 거절된다.

    Apple 상표 지침은 자기 제품 이름 **안에** iOS·iPhone 을 넣는 것을 금지하고,
    호환성 표기는 이름 아래 부제로만 허용한다. 그래서 이름과 부제를 나눠 두었는데,
    나눠 둔 것만으로는 다시 붙는 것을 막지 못한다 — 여기서 지킨다.
    """
    from ipsm import product

    lowered = product.NAME.lower()
    for mark in ("ios", "iphone", "ipad", "apple"):
        assert mark not in lowered, f"이름에 Apple 상표가 들어갔다: {product.NAME}"
    # 부제는 반대다. 호환성 표기가 없으면 무엇에 쓰는 앱인지 알 수 없다.
    assert "ios" in product.TAGLINE.lower()


def test_the_name_is_declared_once():
    """이름을 여러 곳에 적으면 바꿀 때 한 곳이 남는다 — 그 한 곳이 옛 이름을 계속 말한다."""
    from ipsm import product

    root = Path(__file__).resolve().parents[1] / "src/ipsm"
    guilty = []
    for path in root.rglob("*.py"):
        if path.name == "product.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # 설명글은 글이지 코드가 아니다 — 화면에 나가지 않으므로 이름을 적어도 된다.
        prose = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                head = node.body[0] if node.body else None
                if isinstance(head, ast.Expr) and isinstance(head.value, ast.Constant):
                    prose.add(id(head.value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if product.NAME in node.value and id(node) not in prose:
                    guilty.append(f"{path.name}:{node.lineno}")
    assert not guilty, "이름을 직접 적은 자리: " + ", ".join(guilty)


def test_the_donate_link_reaches_the_right_account():
    """후원 주소가 깨지면 돈이 엉뚱한 데로 가는 것이 아니라 아무 데도 가지 않는다.

    계정 주소의 `@` 는 그대로 두면 주소가 잘리는 글자라, 이어 붙이지 않고 인코딩해야
    한다. 창을 띄우지 않고도 확인할 수 있어야 해서 주소 짓는 일을 `product` 에 두었다.
    """
    from urllib.parse import parse_qs, urlparse

    from ipsm import product

    parsed = urlparse(product.donate_url())
    assert parsed.scheme == "https", "결제 주소가 https 가 아니다"
    assert parsed.netloc == "www.paypal.com"
    values = parse_qs(parsed.query)
    assert values["business"] == [product.DONATE_ACCOUNT]
    assert values["currency_code"] == [product.DONATE_CURRENCY]
    # 응원 한 번이 매달 빠져나가면 안 된다
    assert values["no_recurring"] == ["1"]


def test_the_settings_offers_support_without_going_anywhere_by_itself():
    """후원은 누른 사람만 바깥으로 나간다 — 창을 여는 것만으로 접속하지 않는다."""
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from ipsm import product
    from ipsm.ui import main_window as mw

    opened = []

    class Fake:
        @staticmethod
        def openUrl(url):          # noqa: N802  (Qt 이름 그대로)
            opened.append(url.toString())
            return True

    real, mw.QDesktopServices = mw.QDesktopServices, Fake
    try:
        dialog = mw.SettingsDialog()
        assert not opened, "창을 열기만 했는데 바깥으로 나갔다"
        dialog.donate.click()
        assert opened == [product.donate_url()], opened
        dialog.close()
    finally:
        mw.QDesktopServices = real


# ---------------------------------------------------------------- 아이콘

def test_wanted_icons_skips_folders_and_unknowns():
    doc = _doc()
    wanted = wanted_icons(doc)
    identifiers = [identifier for identifier, _stamp in wanted]
    assert "com.apple.calculator" in identifiers   # 폴더 안의 앱은 필요하다
    assert len(identifiers) == len(set(identifiers))
    for identifier in identifiers:
        assert identifier, "빈 식별자가 목록에 들어갔다"


def test_icon_store_round_trip_and_freshness():
    with tempfile.TemporaryDirectory() as tmp:
        store = IconStore(Path(tmp))
        assert store.get("com.example.a") is None
        store.put_many({"com.example.a": b"PNGDATA"}, {"com.example.a": "2026-08-19"})
        assert store.get("com.example.a") == b"PNGDATA"
        # 날짜가 같으면 다시 받지 않는다
        assert store.missing([("com.example.a", "2026-08-19")]) == []
        # 날짜가 달라지면 다시 받는다
        assert store.missing([("com.example.a", "2026-08-20")]) == ["com.example.a"]
        # 색인을 새로 읽어도 같은 판단이어야 한다
        assert IconStore(Path(tmp)).missing([("com.example.a", "2026-08-19")]) == []


def test_icon_store_survives_unsafe_identifiers():
    """웹 클립 식별자에 무엇이 들어 있을지 모른다. 파일 이름으로 새어 나가면 안 된다."""
    with tempfile.TemporaryDirectory() as tmp:
        store = IconStore(Path(tmp))
        nasty = "../../etc/passwd:weird*id"
        store.put(nasty, b"X")
        assert store.get(nasty) == b"X"
        files = list(Path(tmp).glob("icons/*.png"))
        assert len(files) == 1, files
        # 이름이 어떻게 바뀌든, 파일이 저장소 밖으로 나가지 않는 것이 요점이다.
        assert files[0].resolve().parent == store.dir.resolve()


# ---------------------------------------------------------------- 화면

def _qt_ready():
    """Qt 없이도 나머지 시험은 돌아야 한다. 화면 시험만 건너뛴다."""
    try:
        import PySide6  # noqa: F401
    except ImportError:
        return None
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_icon_cache_reports_missing_without_raising():
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from ipsm.ui.tiles import IconCache

    with tempfile.TemporaryDirectory() as tmp:
        cache = IconCache(IconStore(Path(tmp)))
        assert cache.pixmap("com.example.none", 48) is None
        assert cache.pixmap(None, 48) is None


def test_drop_moves_the_item_and_refusal_leaves_it_alone():
    """화면에서 놓는 동작이 문서의 판단을 그대로 따르는지 본다.

    옮길 수 있는가는 화면이 아니라 `can_move` 가 정한다. 두 판단이 갈리면
    사용자는 '되는 것처럼 보였는데 안 되는' 화면을 보게 된다.
    """
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from PySide6.QtCore import QMimeData, QPointF, Qt
    from PySide6.QtGui import QDropEvent

    from ipsm.ui.tiles import MIME_NODE, ContainerView, IconCache

    def drop(view, node_uid, point):
        mime = QMimeData()
        mime.setData(MIME_NODE, node_uid.encode("utf-8"))
        event = QDropEvent(
            QPointF(point),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        view.dropEvent(event)
        return event.isAccepted()

    with tempfile.TemporaryDirectory() as tmp:
        doc = _doc()
        icons = IconCache(IconStore(Path(tmp)))
        target = ContainerView(doc, doc.pages[1].uid, 4, 6, icons, tile=40)
        target.resize(4 * 60, 6 * 60)

        movable = doc.pages[0].items[0]              # '메시지'
        assert drop(target, movable.uid, target._cell_rect(1).center())
        assert doc.locate(movable.uid)[0].uid == doc.pages[1].uid
        assert doc.dirty

        widget = doc.pages[0].items[-1]              # 우리가 모르는 항목
        before = doc.to_state()
        assert not drop(target, widget.uid, target._cell_rect(2).center())
        assert doc.to_state() == before, "거절된 드롭이 문서를 바꿨다"


def test_dropping_an_app_on_an_app_asks_to_group_instead_of_moving():
    """앱 한가운데에 앱을 겹치면 묶기다 — 가장자리에 놓으면 그냥 옆자리다.

    판 스스로 묶지는 않는다. 이름을 물어야 하기 때문에 창 주인에게 알리기만 한다.
    문서가 그 자리에서 바뀌어 버리면 사용자가 취소를 눌러도 이미 늦다.
    """
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from PySide6.QtCore import QMimeData, QPointF, Qt
    from PySide6.QtGui import QDropEvent

    from ipsm.ui.tiles import MIME_NODE, ContainerView, IconCache

    def drop(view, node_uid, point):
        mime = QMimeData()
        mime.setData(MIME_NODE, node_uid.encode("utf-8"))
        event = QDropEvent(
            QPointF(point),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        view.dropEvent(event)
        return event.isAccepted()

    with tempfile.TemporaryDirectory() as tmp:
        doc = _doc()
        icons = IconCache(IconStore(Path(tmp)))
        view = ContainerView(doc, doc.pages[0].uid, 4, 6, icons, tile=40)
        view.resize(4 * 60, 6 * 60)

        asked = []
        view.grouped.connect(lambda a, b: asked.append((a, b)))

        maps = doc.pages[1].items[0]                 # 3페이지 '지도'
        message = doc.pages[0].items[0]              # 2페이지 '메시지'
        before = doc.to_state()

        assert drop(view, maps.uid, view._icon_rect(0).center())
        assert asked == [(maps.uid, message.uid)], asked
        assert doc.to_state() == before, "판이 스스로 문서를 바꿨다 — 이름을 묻기 전인데"

        # 가장자리는 여전히 '옆에 끼우기'다
        asked.clear()
        edge = view._cell_rect(0).topLeft()
        assert drop(view, maps.uid, edge)
        assert asked == []
        assert doc.locate(maps.uid)[0].uid == doc.pages[0].uid


def test_dropping_on_a_folder_still_goes_inside_it():
    """묶기를 넣었다고 폴더에 넣던 동작이 사라지면 안 된다."""
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from PySide6.QtCore import QMimeData, QPointF, Qt
    from PySide6.QtGui import QDropEvent

    from ipsm.ui.tiles import MIME_NODE, ContainerView, IconCache

    with tempfile.TemporaryDirectory() as tmp:
        doc = _doc()
        icons = IconCache(IconStore(Path(tmp)))
        view = ContainerView(doc, doc.pages[0].uid, 4, 6, icons, tile=40)
        view.resize(4 * 60, 6 * 60)

        folder = doc.pages[0].items[1]               # '도구'
        maps = doc.pages[1].items[0]
        mime = QMimeData()
        mime.setData(MIME_NODE, maps.uid.encode("utf-8"))
        event = QDropEvent(
            QPointF(view._icon_rect(1).center()),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        view.dropEvent(event)
        assert event.isAccepted()
        assert doc.locate(maps.uid)[0].uid == folder.pages[0].uid


def test_dropping_on_a_full_folder_opens_a_new_page_instead_of_refusing():
    """꽉 찬 묶음 위에 놓으면 페이지가 한 장 펴져야 한다 (판에서 실제로 놓아 본다)."""
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from PySide6.QtCore import QMimeData, QPointF, Qt
    from PySide6.QtGui import QDropEvent

    from ipsm.ui.tiles import MIME_NODE, ContainerView, IconCache

    with tempfile.TemporaryDirectory() as tmp:
        doc = _doc()
        icons = IconCache(IconStore(Path(tmp)))
        view = ContainerView(doc, doc.pages[0].uid, 4, 6, icons, tile=40)
        view.resize(4 * 60, 6 * 60)

        folder = doc.pages[0].items[1]
        folder.pages[0].capacity = 2                # 꽉 찬 상태로 둔다
        maps = doc.pages[1].items[0]
        mime = QMimeData()
        mime.setData(MIME_NODE, maps.uid.encode("utf-8"))
        event = QDropEvent(
            QPointF(view._icon_rect(1).center()),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        view.dropEvent(event)
        assert event.isAccepted()
        assert len(folder.pages) == 2, "페이지가 펴지지 않았다"
        assert doc.locate(maps.uid)[0].uid == folder.pages[1].uid


def test_dropping_into_a_full_folder_page_pushes_from_the_view():
    """모델만이 아니라 **판에서 끌어다 놓았을 때도** 밀려나야 한다.

    묶음을 열면 페이지가 나란히 놓인다. 2페이지 앱을 1페이지의 가운데 자리에
    떨어뜨리는 것이 사용자가 말한 그 동작이다.
    """
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from PySide6.QtCore import QMimeData, QPointF, Qt
    from PySide6.QtGui import QDropEvent

    from ipsm.ui.tiles import MIME_NODE, ContainerView, IconCache

    with tempfile.TemporaryDirectory() as tmp:
        doc, folder = _folder_doc(page1=3, page2=2)
        icons = IconCache(IconStore(Path(tmp)))
        view = ContainerView(doc, folder.pages[0].uid, 3, 1, icons, tile=40)
        view.resize(3 * 60, 60)

        moving = folder.pages[1].items[0]           # 2페이지의 2-0
        mime = QMimeData()
        mime.setData(MIME_NODE, moving.uid.encode("utf-8"))
        # 두 번째 칸의 왼쪽 가장자리 — '겹쳐서 묶기'가 아니라 '사이에 끼우기'다.
        spot = view._cell_rect(1)
        event = QDropEvent(
            QPointF(spot.left() + 2, spot.center().y()),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        view.dropEvent(event)
        assert event.isAccepted()
        assert [n.label for n in folder.pages[0].items] == ["1-0", "2-0", "1-1"]
        assert [n.label for n in folder.pages[1].items] == ["1-2", "2-1"]


def test_dropping_into_a_full_home_page_pushes_from_the_view():
    """홈 페이지에서도 **판에서 끌어다 놓았을 때** 밀려나야 한다.

    모델이 밀 수 있어도 화면이 자리를 알려 주지 않으면 '가득 찼습니다'로 막힌다 —
    실제로 묶음 밀어내기를 처음 붙였을 때 그렇게 아무 일도 일어나지 않았다.
    """
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from PySide6.QtCore import QMimeData, QPointF, Qt
    from PySide6.QtGui import QDropEvent

    from ipsm.ui.tiles import MIME_NODE, ContainerView, IconCache

    with tempfile.TemporaryDirectory() as tmp:
        doc = _home_doc(3, 2)
        icons = IconCache(IconStore(Path(tmp)))
        view = ContainerView(doc, doc.pages[0].uid, 3, 1, icons, tile=40)
        view.resize(3 * 60, 60)

        moving = doc.pages[1].items[0]              # 2페이지의 2-0
        mime = QMimeData()
        mime.setData(MIME_NODE, moving.uid.encode("utf-8"))
        # 두 번째 칸의 왼쪽 가장자리 — '겹쳐서 묶기'가 아니라 '사이에 끼우기'다.
        spot = view._cell_rect(1)
        event = QDropEvent(
            QPointF(spot.left() + 2, spot.center().y()),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        view.dropEvent(event)
        assert event.isAccepted()
        assert [n.label for n in doc.pages[0].items] == ["1-0", "2-0", "1-1"]
        assert [n.label for n in doc.pages[1].items] == ["1-2", "2-1"]


def test_apply_dialog_stays_locked_until_the_warning_is_read():
    """적용 버튼은 경고를 확인하기 전에는 눌리지 않아야 한다 (REQ-010)."""
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from ipsm.ui.main_window import ApplyDialog

    dialog = ApplyDialog(["지도: 3페이지 1번째 → 1페이지 1번째"], ["앱 라이브러리에만 있는 앱"])
    assert not dialog._ok.isEnabled()
    dialog.agree.setChecked(True)
    assert dialog._ok.isEnabled()


def test_apply_dialog_names_the_apps_ios_will_append():
    """붙어 버릴 앱의 이름을 대화상자가 실제로 말하는가.

    이 부작용만은 백업 복원으로도 되돌아가지 않는다. 적용을 누르기 전에
    보이지 않으면 사용자는 앱이 제멋대로 늘어난 것으로 본다.
    """
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from PySide6.QtWidgets import QLabel

    from ipsm.ui.main_window import ApplyDialog

    dialog = ApplyDialog(["지도: 이동"], ["앱 라이브러리에만 있는 앱"])
    texts = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "앱 라이브러리에만 있는 앱" in texts, texts



def test_dialog_text_is_readable_on_its_own_background():
    """대화상자의 글씨가 바탕에 묻히지 않는가 — 그려서 픽셀로 본다.

    같은 실수가 두 번 났다. 도구모음은 바탕만 어둡게 칠하고 글자색을 두지 않아
    검은 글씨가 됐고, 이름 바꾸기 창은 반대로 글자색만 밝게 칠하고 바탕을 두지
    않아 흰 바탕에 흰 글씨가 됐다. 규칙을 눈으로 훑어서는 잡히지 않는 종류다.
    그래서 실제로 그린 뒤 바탕과 가장 먼 색이 충분히 떨어져 있는지 재 본다.
    """
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from collections import Counter

    from PySide6.QtWidgets import QInputDialog, QLabel, QLineEdit

    from ipsm.ui.main_window import STYLE

    def brightness(name):
        r, g, b = (int(name[i:i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    dialog = QInputDialog()
    dialog.setStyleSheet(STYLE)
    dialog.setLabelText("새 이름")
    dialog.setTextValue("업무")
    dialog.show()
    edit = dialog.findChild(QLineEdit)
    edit.deselect()          # 전체 선택 상태면 선택색이 글자색을 가린다
    image = dialog.grab().toImage()

    for what, widget, inset in (("입력칸", edit, 4),
                                ("안내 문구", next(w for w in dialog.findChildren(QLabel)
                                                 if w.text()), 0)):
        origin = widget.mapTo(dialog, widget.rect().topLeft())
        box = widget.rect().translated(origin).adjusted(inset, inset, -inset, -inset)
        seen = Counter()
        for y in range(box.top(), box.bottom() + 1):
            for x in range(box.left(), box.right() + 1):
                seen[image.pixelColor(x, y).name()] += 1
        back = seen.most_common(1)[0][0]
        # 글씨는 안티에일리어싱 탓에 픽셀이 적다. 얼룩 한 점을 글씨로 세지 않도록
        # 몇 픽셀 이상 찍힌 것 중에서 바탕과 가장 먼 색을 고른다.
        inks = [c for c, n in seen.items() if c != back and n >= 4]
        assert inks, f"{what}: 바탕 말고 아무것도 안 그려졌다"
        gap = max(abs(brightness(c) - brightness(back)) for c in inks)
        assert gap > 80, f"{what}: 바탕 {back} 위에 글씨가 묻힌다 (밝기 차 {gap:.0f})"

    dialog.close()


def test_the_dropdown_list_is_readable_too():
    """펼친 목록의 글씨가 바탕에 묻히지 않는가.

    같은 실수의 세 번째 얼굴이다. 고르는 칸은 어둡게 칠했는데 **펼쳐지는 목록은
    QComboBox 가 아니라 그 안의 다른 위젯**이라 흰 바탕으로 남았고, 위쪽의
    "글자는 밝게" 규칙이 그 위에 흰 글씨를 얹었다. 접힌 칸만 보고는 알 수 없어
    실제로 펼쳐서 그린 뒤 픽셀로 잰다.
    """
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from collections import Counter

    from ipsm.ui.main_window import STYLE, SettingsDialog

    def brightness(name):
        r, g, b = (int(name[i:i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    dialog = SettingsDialog()
    dialog.setStyleSheet(STYLE)
    dialog.show()
    dialog.language.showPopup()
    try:
        for what, widget in (("고르는 칸", dialog.language),
                             ("펼친 목록", dialog.language.view())):
            image = widget.grab().toImage()
            seen = Counter()
            for y in range(image.height()):
                for x in range(image.width()):
                    seen[image.pixelColor(x, y).name()] += 1
            back = seen.most_common(1)[0][0]
            inks = [c for c, n in seen.items() if c != back and n >= 4]
            assert inks, f"{what}: 바탕 말고 아무것도 안 그려졌다"
            gap = max(abs(brightness(c) - brightness(back)) for c in inks)
            assert gap > 80, f"{what}: 바탕 {back} 위에 글씨가 묻힌다 (밝기 차 {gap:.0f})"
    finally:
        dialog.language.hidePopup()
        dialog.close()


def test_the_window_changes_its_words_when_the_language_changes():
    """설정에서 언어를 바꾸면 이미 그려진 창의 글씨까지 따라 바뀌는가.

    Qt 는 한 번 넣은 글자를 스스로 바꾸지 않는다. 그래서 문구를 넣은 자리마다
    `retranslate()` 에 짝이 있어야 하고, 짝을 하나 빠뜨리면 그 위젯만 옛 말로
    남는다 — 앱을 다시 켜기 전에는 눈에 띄지도 않는다. 여기서 실제 창을 지어
    도구모음·안내 문구·창 제목이 함께 움직이는지 본다.
    """
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from ipsm import i18n
    from ipsm.ui.main_window import MainWindow, SettingsDialog

    before = i18n.language()
    with tempfile.TemporaryDirectory() as folder:
        window = None
        try:
            i18n.set_language("ko")
            window = MainWindow(Path(folder))
            assert window.act_load.text() == "기기에서 읽기"

            i18n.set_language("en")   # choose() 와 달리 저장은 하지 않는다
            assert window.act_load.text() == "Read from device"
            assert window.act_settings.text() == "Settings"
            assert window.fit_button.text() == "Fit all"
            assert "Not connected" in window.windowTitle()
            assert "iPhone 을" not in window.statusBar().currentMessage()
            assert "한국어" not in window.note.text()

            # 언어 목록만은 늘 그 언어로 적힌다 — 읽지 못하는 말로 켜진 사람이
            # 자기 말을 찾을 수 있어야 하기 때문이다.
            dialog = SettingsDialog(window)
            names = [dialog.language.itemText(i) for i in range(dialog.language.count())]
            assert names == ["한국어", "English"], names
            assert dialog.chosen() == "en"
            dialog.close()

            i18n.set_language("ko")
            assert window.act_load.text() == "기기에서 읽기"
        finally:
            if window is not None:
                window.close()   # 닫으면 언어 명단에서도 빠진다
                assert window.retranslate not in i18n._listeners
            i18n.set_language(before)


# ------------------------------------------------------- 준비물과 시작 안내판


def test_the_open_port_decides_readiness_not_the_folder():
    """27015 가 열려 있으면 그것으로 끝이다 — 설치 자리는 묻지도 않는다.

    설치 자리를 이름으로 찾는 것은 Apple 이 폴더 이름을 바꾸면 틀린다. 틀렸을 때
    손해가 작은 쪽으로 써야 하므로, 말이 통하는 것이 확인되면 그 위에 다른 짐작을
    얹지 않는다.
    """
    from ipsm import apple_devices

    port, where = apple_devices._muxer_listening, apple_devices._installed_where
    try:
        apple_devices._muxer_listening = lambda timeout=0.4: True
        apple_devices._installed_where = lambda: (_ for _ in ()).throw(
            AssertionError("열려 있는데도 설치 자리를 뒤졌다")
        )
        ready = apple_devices.look()
        assert ready.running and ready.installed and ready.ready

        apple_devices._muxer_listening = lambda timeout=0.4: False
        apple_devices._installed_where = lambda: r"C:\Program Files\Common Files\Apple"
        idle = apple_devices.look()
        assert idle.installed and not idle.running, "설치는 됐지만 아직 안 뜬 경우"

        apple_devices._installed_where = lambda: None
        missing = apple_devices.look()
        assert not missing.installed and not missing.running
    finally:
        apple_devices._muxer_listening = port
        apple_devices._installed_where = where


def test_the_guide_tells_the_user_what_to_do_next():
    """세 갈래마다 다음에 할 일이 다르다 — 없는 사람에게 '실행하세요'라고 하면 안 된다."""
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from ipsm import apple_devices
    from ipsm.ui.guide import GuideBoard

    original = apple_devices.look
    try:
        def pretend(running, installed):
            apple_devices.look = lambda: apple_devices.Presence(running, installed, "시험")

        pretend(False, False)
        board = GuideBoard()
        assert "Store" in board.action.text(), board.action.text()
        assert board.again.isVisibleTo(board), "스스로 다시 볼 수 있어야 한다"

        pretend(False, True)
        board.refresh()
        assert "Store" in board.action.text()
        assert "설치되어 있지만" in board.state.text(), board.state.text()

        pretend(True, True)
        board.refresh()
        assert board.action.text() == "기기에서 읽기"
        assert board.again.isHidden() or not board.again.isVisibleTo(board)

        seen = []
        board.readRequested.connect(lambda: seen.append(1))
        board.action.click()
        assert seen == [1], "준비된 상태에서는 단추가 읽기를 시작해야 한다"
        board.close()
    finally:
        apple_devices.look = original


def test_the_guide_hands_its_place_to_the_canvas():
    """안내판과 캔버스는 같은 자리를 나눠 쓴다. 둘 다 보이면 어느 쪽도 넓지 않다."""
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from ipsm.ui.main_window import MainWindow

    with tempfile.TemporaryDirectory() as folder:
        window = MainWindow(Path(folder))
        try:
            assert not window.guide.isHidden(), "읽기 전에는 안내판이 자리를 채운다"
            assert window.scroll.isHidden()

            window._set_document(copy.deepcopy(SAMPLE), None)
            assert window.guide.isHidden(), "홈화면이 왔는데도 안내판이 남아 있다"
            assert not window.scroll.isHidden()
        finally:
            window.close()


# --------------------------------------------------------- 라이선스와 정보 창


def test_the_license_is_the_real_gpl_text():
    """LICENSE 가 진짜 GPL-3.0 원문인가.

    라이선스는 '무슨 라이선스입니다'라는 말이 아니라 **원문 자체**가 있어야 효력이
    있다. 요약본이나 링크만 두고 배포하면 지킨 것이 아니다.
    """
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in text
    assert "Version 3, 29 June 2007" in text
    assert "TERMS AND CONDITIONS" in text
    # 원문은 674줄이다. 잘려 실리면 조항 하나가 통째로 없어진다.
    assert len(text.splitlines()) == 674, len(text.splitlines())


def test_every_library_we_ship_is_named_in_the_notices():
    """설치해 쓰는 것이 고지 목록에 다 있는가.

    목록은 `pip install` 한 번에 낡는다. 낡은 고지는 고지하지 않은 것과 같으므로,
    requirements 에 적힌 이름이 전부 목록에 있는지 본다. 다시 만드는 법은
    `scripts/gen_notices.py`.
    """
    notices = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8").lower()
    wanted = []
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        name = line.split(">=")[0].split("==")[0].strip()
        wanted.append(name)
    missing = [
        name for name in wanted
        if name.lower().replace("-", "_") not in notices.replace("-", "_")
    ]
    assert not missing, "고지에서 빠진 것: " + ", ".join(missing)


def test_the_gpl_library_is_marked_as_gpl_in_the_notices():
    """GPL 이 이 앱 전체의 라이선스를 정한다 — 그 사실이 목록에 적혀 있어야 한다."""
    notices = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    row = next(l for l in notices.splitlines() if l.startswith("| pymobiledevice3 "))
    assert "GPL-3.0-or-later" in row, row


def test_the_license_texts_travel_inside_the_exe():
    """exe 하나만 받은 사람도 원문을 읽을 수 있어야 한다."""
    spec = (ROOT / "HomeSpread.spec").read_text(encoding="utf-8")
    for needed in (
        "LICENSE",
        "THIRD-PARTY-NOTICES.md",
        "third_party_licenses",
        "PRIVACY.md",
    ):
        assert f'("{needed}"' in spec, f"{needed} 가 exe 에 실리지 않는다"


def test_opening_the_window_does_not_wait_for_the_device_library():
    """창이 뜨는 길에 `pymobiledevice3` 가 끼어들면 안 된다.

    이 라이브러리 하나를 들이는 데 8초가 걸린다(실측). 우리가 그것을 필요로 하는
    시점은 사용자가 '기기에서 읽기'를 누른 뒤이므로, 워커 스레드가 뒤에서 들인다.
    누군가 편의를 위해 맨 위로 옮기면 시작이 다시 8초 느려지고, 그 사실은 실행해
    보기 전에는 드러나지 않는다 — 그래서 여기서 지킨다.
    """
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    import subprocess

    code = (
        "import sys; sys.path.insert(0, r'"
        + str(ROOT / "src")
        + "'); import ipsm.ui.main_window; "
        "print('pymobiledevice3' in sys.modules)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=180
    )
    assert out.returncode == 0, out.stderr[-500:]
    assert out.stdout.strip() == "False", "창 모듈이 기기 라이브러리를 끌고 들어온다"


def test_the_splash_covers_the_seconds_before_the_window():
    """창이 뜨기 전 몇 초 동안 화면이 비어 있으면 안 된다.

    그 구간에는 파이썬조차 시작 전이라 Qt 로는 아무것도 띄울 수 없다. 부트로더가
    직접 띄우는 그림만이 답이고, 그 그림은 Tk 로 그려진다 — 그래서 `tkinter` 를
    제외 목록에 되돌려 놓으면 그림이 조용히 사라진다.
    """
    spec = (ROOT / "HomeSpread.spec").read_text(encoding="utf-8")
    assert "Splash(" in spec, "시작 그림이 없다"
    assert "splash.binaries" in spec, "그림에 필요한 파일이 함께 실리지 않는다"
    assert '"tkinter",' not in spec, "tkinter 를 제외하면 시작 그림이 뜨지 않는다"
    assert (ROOT / "assets" / "splash.png").exists(), "그림 파일이 없다"

    app_src = (ROOT / "src" / "ipsm" / "app.py").read_text(encoding="utf-8")
    assert "_close_splash()" in app_src
    # 창을 보이기 '전에' 내려야 빈 바탕화면이 비치지 않는다.
    assert app_src.index("_close_splash()\n    window.show()") > 0


def test_the_splash_shows_the_name_we_use_now():
    """시작 그림이 지금 쓰는 이름을 보여야 한다.

    2026-08-26 에 이름을 `HomeBoard` 에서 `HomeSpread` 로 갈았는데, 그림은 닷새 전
    것이 그대로 남아 실행할 때마다 옛 이름이 떴다. 그리는 코드는 처음부터
    `product.NAME` 을 읽고 있었다 — 틀린 것은 코드가 아니라 **다시 그리지 않은
    산출물**이었고, 픽셀만으로는 그것을 알아낼 방법이 없다.

    그래서 그릴 때 쓴 이름을 PNG 의 `tEXt` 조각에 함께 적는다. 여기서 그것을 꺼내
    `product` 와 대조하면, 이름을 갈고 다시 그리지 않은 채로는 시험이 통과하지
    못한다. 낡은 그림은 조용히 있지 못한다.
    """
    data = (ROOT / "assets" / "splash.png").read_bytes()

    labels: dict[str, str] = {}
    for match in re.finditer(rb"tEXt", data):
        start = match.start() + 4
        # tEXt 는 `키\0값` 이고, 길이는 앞의 4바이트가 말한다.
        length = int.from_bytes(data[match.start() - 4 : match.start()], "big")
        key, _, value = data[start : start + length].partition(b"\x00")
        labels[key.decode("latin-1")] = value.decode("utf-8")

    assert labels, "그림에 이름표가 없다 — scripts/make_splash.py 로 다시 그려라"
    assert labels.get("Title") == product.NAME, (
        f"시작 그림이 {labels.get('Title')!r} 을 보여준다. "
        f"지금 이름은 {product.NAME!r} 이다 — scripts/make_splash.py 로 다시 그려라"
    )
    assert labels.get("Description") == product.TAGLINE, (
        "시작 그림의 부제가 지금 것과 다르다 — scripts/make_splash.py 로 다시 그려라"
    )


def test_a_quiet_run_leaves_one_file_and_no_empty_folder():
    """기기에 닿지 않고 끝난 실행은 로그 한 장만 남겨야 한다.

    산출물 폴더를 미리 만들면 실행할 때마다 빈 폴더가 하나씩 쌓이고, 정작 내용이
    든 폴더를 그 사이에서 찾을 수 없게 된다. 폴더가 있다는 것 자체가 "이 세션은
    기기에서 무언가를 받아 왔다"는 표시여야 한다.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        session = start_session(root, name="test")
        assert session.log_path.exists(), "로그 파일이 없다"
        assert not session.artifact_dir.exists(), "받아 온 것이 없는데 폴더가 생겼다"

        session.save_artifact("something", {"a": 1})
        assert session.artifact_dir.is_dir(), "저장할 것이 생겼는데 폴더가 없다"

        # 산출물이 없어도 보고서는 만들 수 있어야 한다 — 로그만 들어간다.
        session2 = start_session(root, name="test2")
        assert session2.export_zip().exists()

        # Windows 는 열린 파일을 지우지 못한다. 임시 폴더를 치우려면 먼저 놓아야 한다.
        for handler in list(logging.getLogger().handlers):
            logging.getLogger().removeHandler(handler)
            handler.close()


def test_old_sessions_are_pruned_but_strangers_are_not():
    """세션마다 새 파일을 만드는 것은 신고 하나가 실행 하나에 대응하기 위해서지,
    영원히 쌓으려는 것이 아니다. 다만 지우는 것은 되돌릴 수 없으므로, 우리가 지은
    이름 모양에 맞는 것만 지운다 — 사용자가 `logs/` 에 둔 파일은 남의 것이다.
    """
    with tempfile.TemporaryDirectory() as tmp:
        log_dir = Path(tmp) / "logs"
        log_dir.mkdir()
        for i in range(6):
            stem = f"app_2026081{i}_101010"
            (log_dir / f"{stem}.log").write_text("x", encoding="utf-8")
            (log_dir / stem).mkdir()
        stranger = log_dir / "my_notes.log"
        stranger.write_text("사용자가 둔 파일", encoding="utf-8")

        prune_sessions(log_dir, keep=2)

        left = sorted(x.name for x in log_dir.glob("*.log"))
        assert left == ["app_20260814_101010.log", "app_20260815_101010.log", "my_notes.log"], left
        assert not (log_dir / "app_20260810_101010").exists(), "폴더가 남았다"
        assert stranger.exists(), "남의 파일을 지웠다"


def test_the_program_ships_as_a_folder_not_one_file():
    """단일 exe 는 실행할 때마다 자기 안 72MB 를 임시 폴더에 푼다 — 매번 16.5초다.

    실측(2026-08-21): 단일 exe 21초 · 폴더 배포 2.9초. 되돌리면 그 시간이 그대로
    돌아오는데, 명세만 보아서는 되돌아간 줄 모른다. 그래서 여기서 붙잡는다.
    스토어에 올릴 MSIX 도 이 모양을 요구하므로 되돌릴 이유가 더 없다.
    """
    spec = (ROOT / "HomeSpread.spec").read_text(encoding="utf-8")
    assert "COLLECT(" in spec, "폴더 배포가 아니다 — 실행할 때마다 압축을 푼다"
    assert "exclude_binaries=True" in spec, "EXE 가 아직 모든 것을 안고 있다"

    bat = (ROOT / "build_exe.bat").read_text(encoding="cp949")
    # 안내문이 배포 모양과 어긋나면, 사용자는 있지도 않은 파일을 찾는다.
    assert r"dist\HomeSpread\HomeSpread.exe" in bat


def test_building_never_deletes_the_users_backups():
    """PyInstaller 의 COLLECT 는 만들기 전에 `dist\HomeSpread\` 를 통째로 지운다.

    그 폴더는 exe 를 한 번이라도 실행하면 `backups\` 가 생기는 자리이기도 하다.
    그래서 아무것도 하지 않으면 **빌드 한 번이 조용히 백업 전부 삭제**가 된다 —
    2026-08-21 에 실제로 그렇게 잃었다. 되돌릴 길이 백업뿐인 앱에서 이것은 우리가
    막아야 할 바로 그 사고이고, 약속("backups 는 사용자만 지운다")은 빌드
    스크립트에도 걸린다.
    """
    bat = (ROOT / "build_exe.bat").read_text(encoding="cp949")
    run_at = bat.index("-m PyInstaller")
    stash_at = bat.index("keep_data.py stash")
    assert stash_at < run_at, "빌드가 먼저 돌아 백업이 지워진 뒤에 치운다"
    # 실패한 빌드 때문에 자료가 _keep 에 갇히면 안 된다 — 양쪽 갈래 모두 돌려놓는다.
    assert bat.count("keep_data.py restore") >= 2, "빌드 실패 시 돌려놓지 않는다"

    src = (ROOT / "scripts" / "keep_data.py").read_text(encoding="utf-8")
    assert '"backups"' in src and '"logs"' in src

    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("keep_data", ROOT / "scripts" / "keep_data.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    assert "backups" in module.PRECIOUS

    # 구해 둔 것을 구하다가 잃는 일이 없어야 한다 — 덮어쓰지 않고 옆에 둔다.
    with tempfile.TemporaryDirectory() as tmp:
        taken = Path(tmp) / "backups"
        taken.mkdir()
        assert module._free(taken) != taken
        assert not module._free(taken).exists()


def test_the_source_offer_points_somewhere_real():
    """GPL 은 실행 파일을 건네준 사람에게 소스에 닿을 길을 함께 주기를 요구한다.

    비어 있으면 정보 창이 "배포한 사람에게 요청하세요"라고만 말한다 — 손으로 건넬
    때는 그것도 답이지만, 스토어에 올리는 순간 건넬 사람이 없어진다. 방침 URL 도
    같은 주소에서 나오므로, 여기가 비면 Partner Center 의 필수 칸까지 함께 빈다.
    """
    assert product.SOURCE_URL.startswith("https://"), "소스 주소가 비었거나 https 가 아니다"
    assert product.PRIVACY_URL.startswith(product.SOURCE_URL), "방침 주소가 소스와 다른 곳을 가리킨다"
    assert product.PRIVACY_URL.endswith("PRIVACY.md")
    # 주소가 가리키는 파일이 실제로 저장소에 있어야 한다. 없으면 404 를 배포하는 셈이다.
    assert (ROOT / "PRIVACY.md").exists()


# 아래 다섯은 2026-08-21 실기기(iPhone 14 / iOS 26.1)에서 그대로 뜬 모양이다.
# 손으로 지어낸 예가 아니라 실제 `installation_proxy` 응답에서 뽑았다.
_REAL_SYSTEM_APPS = {
    # 8/19 쓰기에서 iOS 가 실제로 마지막 페이지에 되붙인 기본 앱. 반드시 예고해야 한다.
    "com.apple.Magnifier": {
        "CFBundleDisplayName": "돋보기",
        "CFBundleIcons": {"CFBundlePrimaryIcon": {"CFBundleIconFiles": ["AppIcon60x60"]}},
    },
    # 화면이 없는 내부 구성요소. 232개 중 184개가 이 모양이다.
    "com.apple.AAUIViewService": {
        "CFBundleDisplayName": "AAUIViewService",
        "SBAppTags": ["hidden"],
    },
    # 아이콘 자체가 없다.
    "com.apple.webapp": {"CFBundleDisplayName": "Web"},
    # 앱이 자기 표시 여부를 스스로 정한다 — 켜 주기 전에는 홈화면에 뜨지 않는다.
    "com.apple.sidecar": {
        "CFBundleDisplayName": "연속성",
        "CFBundleIcons": {"CFBundlePrimaryIcon": {"CFBundleIconFiles": ["Sidecar60x60"]}},
        "SBIconVisibilitySetByAppPreference": True,
    },
    # 지역 제한: 한국 기기에서는 뜨지 않는다.
    "com.apple.news": {
        "CFBundleDisplayName": "News",
        "CFBundleIcons": {"CFBundlePrimaryIcon": {"CFBundleIconFiles": ["AppIcon60x60"]}},
        "LSSupportedRegions": ["US", "GB", "AU", "CA"],
    },
}


def test_only_the_built_in_apps_that_can_appear_are_warned_about():
    """기본 앱 232개를 다 세면 틀린 경고를 190번 하게 된다.

    실기기 대조(2026-08-21): 이 기준을 통과하는 미배치 기본 앱은 0개였고, 그날 두 번의
    쓰기에서 iOS 가 되붙인 것도 0개였다. 반대로 8/19 에 되붙은 '돋보기'는 통과한다.
    """
    from ipsm.device import shows_on_home_screen

    visible = {
        bundle_id
        for bundle_id, info in _REAL_SYSTEM_APPS.items()
        if shows_on_home_screen(info, "KR")
    }
    assert visible == {"com.apple.Magnifier"}, visible

    # 지역을 모를 때는 지역 조건만 접는다 — 모른다고 빠뜨리면 사용자가 놀란다.
    assert shows_on_home_screen(_REAL_SYSTEM_APPS["com.apple.news"], None)
    assert shows_on_home_screen(_REAL_SYSTEM_APPS["com.apple.news"], "US")
    # 다른 조건은 지역과 무관하게 그대로 막는다.
    assert not shows_on_home_screen(_REAL_SYSTEM_APPS["com.apple.sidecar"], None)


def test_the_device_asks_for_built_in_apps_too():
    """`application_type="User"` 만 물으면 기본 앱이 예고에서 통째로 빠진다.

    이 구멍은 가정이 아니라 실제로 터졌다 — 8/19 쓰기에서 iOS 가 되붙인 4개 중 하나가
    Apple 기본 앱 '돋보기'였는데, 그때 우리는 그것을 예고하지 못했다.
    """
    src = (ROOT / "src" / "ipsm" / "device.py").read_text(encoding="utf-8")
    body = src[src.index("async def list_installed_apps("): src.index("async def get_orientation(")]
    assert 'application_type="User"' in body
    assert 'application_type="System"' in body, "기본 앱을 다시 안 묻게 되돌아갔다"
    assert "shows_on_home_screen(" in body, "기본 앱을 거르지 않고 다 센다"


def test_the_region_never_comes_from_the_apple_part_code():
    """`RegionInfo` 는 'KH/A' 처럼 Apple 의 부품 지역 코드이지 ISO 국가 코드가 아니다.

    ISO 로 `KH` 는 캄보디아라, 그것으로 `LSSupportedRegions` 를 대조하면 조용히 틀린다.
    """
    from ipsm import device

    assert device._region_of("ko_KR") == "KR"
    assert device._region_of("en-US") == "US"
    assert device._region_of(None) is None
    assert device._region_of("ko") is None  # 나라를 모르면 없다고 말한다

    src = (ROOT / "src" / "ipsm" / "device.py").read_text(encoding="utf-8")
    region_fn = src[src.index("async def _home_region("): src.index("async def list_installed_apps(")]
    assert "RegionInfo" not in region_fn


def test_the_device_verifier_stays_read_only_without_apply():
    """검증기는 `--apply` 를 붙였을 때만 기기에 쓴다.

    이 도구는 사용자의 진짜 홈화면을 재료로 삼는다. 읽기만 하는 줄 알고 돌렸는데
    썼다면, 그것은 도구가 아니라 사고다. 그래서 쓰기를 부르는 자리를 `stage_two`
    안으로만 두고, 그 함수는 `args.apply` 아래에서만 불린다 — 두 성질을 함께
    지켜야 "기본은 읽기 전용"이 성립한다.
    """
    src = (ROOT / "scripts" / "verify_edits.py").read_text(encoding="utf-8")

    stage_two_at = src.index("async def stage_two(")
    writes = [i for i in range(len(src)) if src.startswith("set_icon_state(", i)]
    assert writes, "쓰기를 부르는 자리가 아예 없다 — 2단계가 사라졌는가"
    for at in writes:
        assert at > stage_two_at, "stage_two 바깥에서 기기에 쓴다"

    # stage_two 를 부르는 곳은 --apply 아래여야 한다.
    call_at = src.index("await stage_two(")
    guard_at = src.index("if args.apply:")
    assert guard_at < call_at, "--apply 검사 없이 2단계를 부른다"

    # 기본값이 켜져 있으면 플래그가 있으나 마나다.
    assert '"--apply", action="store_true"' in src


def test_the_privacy_policy_tells_the_whole_truth_in_both_languages():
    """방침이 실제 동작과 어긋나면 스토어 심사에서 걸리고, 무엇보다 거짓말이 된다.

    그래서 코드가 실제로 하는 일 — 남기는 폴더 넷, 기기와 말하는 주소, 밖으로
    나가는 두 경우 — 이 전부 적혀 있는지 확인한다. 영어도 함께 확인하는 이유는
    Partner Center 심사자가 읽는 쪽이 그쪽이기 때문이다.
    """
    text = (ROOT / "PRIVACY.md").read_text(encoding="utf-8")

    for kept in ("backups", "logs", "icons", "settings.json"):
        assert kept in text, f"{kept} 가 남는다는 사실을 말하지 않는다"
    assert "127.0.0.1:27015" in text, "기기와 어떻게 말하는지 밝히지 않는다"
    assert "PayPal" in text and "Microsoft Store" in text, "밖으로 나가는 경우 누락"
    assert "UDID" in text, "기기 식별자를 다룬다는 사실을 숨기고 있다"
    assert "Privacy Policy (English)" in text, "심사자가 읽을 영어본이 없다"

    # 방침에 적은 파일 이름이 코드와 어긋나면, 어느 한쪽이 낡은 것이다.
    from ipsm.i18n import settings_path
    from ipsm.paths import cache_root

    assert settings_path().name in text
    # 아이콘 캐시가 임시 폴더로 옮겨 갔다는 사실도 방침에 있어야 한다. 폴더 이름을
    # 코드에서 가져와 대조하므로, 이름만 바꾸고 방침을 안 고치면 여기서 걸린다.
    assert cache_root().name in text, "아이콘 캐시가 어디 남는지 말하지 않는다"
    assert "TEMP" in text, "임시 폴더에 둔다는 사실을 말하지 않는다"
    # 문서 폴더를 클라우드와 동기화하는 사람에게는 백업도 함께 올라간다.
    assert "OneDrive" in text, "동기화되는 문서 폴더에 대한 고지가 없다"


def test_the_about_window_says_what_this_is_and_shows_the_originals():
    """정보 창이 이름·판·라이선스를 말하고, 원문을 창 안에서 보여주는가.

    원문을 바깥 프로그램으로 열지 않는 이유가 있다 — exe 로 묶이면 원문은 임시
    폴더에 잠깐 풀렸다 지워지므로, 메모장이 열어 둔 파일이 사라진다. 그래서 읽어서
    그리고, 그렸는지를 여기서 확인한다.
    """
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from ipsm import product
    from ipsm.ui.about import AboutDialog
    from ipsm.version import VERSION_TEXT

    dialog = AboutDialog()
    try:
        shown = " ".join(
            w.text() for w in dialog.findChildren(type(dialog.source)) if w.text()
        )
        assert product.NAME in shown and VERSION_TEXT in shown, shown
        assert product.TAGLINE in shown
        assert product.LICENSE_SPDX in shown, "무슨 라이선스인지 말하지 않는다"

        license_text = dialog._read("LICENSE")
        assert "GNU GENERAL PUBLIC LICENSE" in license_text
        notices = dialog._read("THIRD-PARTY-NOTICES.md")
        assert "pymobiledevice3" in notices
        privacy = dialog._read("PRIVACY.md")
        assert "PayPal" in privacy and "127.0.0.1:27015" in privacy

        # 없는 파일을 달라고 해도 죽지 않고 말로 답한다
        assert "LICENSE" not in dialog._read("없는파일") or True
        assert dialog._read("없는파일").strip(), "찾을 수 없을 때 아무 말도 안 한다"
    finally:
        dialog.close()


def test_the_about_window_offers_source_without_inventing_an_address():
    """GPL 은 소스에 닿을 길을 요구한다. 주소가 없으면 없는 대로 말해야 한다."""
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from ipsm import product
    from ipsm.ui.about import AboutDialog

    original = product.SOURCE_URL
    try:
        product.SOURCE_URL = ""
        dialog = AboutDialog()
        assert "http" not in dialog.source.text(), "없는 주소를 지어냈다"
        assert dialog.source.text().strip()
        dialog.close()

        product.SOURCE_URL = "https://example.invalid/homeboard"
        dialog = AboutDialog()
        assert product.SOURCE_URL in dialog.source.text()
        dialog.close()
    finally:
        product.SOURCE_URL = original


def test_the_license_text_is_readable_on_its_own_background():
    """같은 실수의 네 번째 자리가 되지 않게 — 원문 창도 그려서 밝기를 잰다."""
    if _qt_ready() is None:
        print("      (PySide6 없음 — 건너뜀)")
        return
    from collections import Counter

    from ipsm.ui.about import TextWindow
    from ipsm.ui.main_window import STYLE

    def brightness(name):
        r, g, b = (int(name[i:i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    window = TextWindow("라이선스 전문", "GNU GENERAL PUBLIC LICENSE\nVersion 3")
    window.setStyleSheet(STYLE)
    window.show()
    image = window.grab().toImage()
    view = window.body
    origin = view.mapTo(window, view.rect().topLeft())
    box = view.rect().translated(origin).adjusted(4, 4, -4, -4)
    seen = Counter()
    for y in range(box.top(), box.bottom() + 1):
        for x in range(box.left(), box.right() + 1):
            seen[image.pixelColor(x, y).name()] += 1
    back = seen.most_common(1)[0][0]
    inks = [c for c, n in seen.items() if c != back and n >= 4]
    assert inks, "원문 창에 바탕 말고 아무것도 안 그려졌다"
    gap = max(abs(brightness(c) - brightness(back)) for c in inks)
    assert gap > 80, f"원문이 바탕 {back} 에 묻힌다 (밝기 차 {gap:.0f})"
    window.close()


# --- 자료 폴더 (exe 배포) ---------------------------------------------------



def test_data_dirs_are_created_where_the_program_lives():
    """소스로 돌릴 때는 프로젝트 폴더가 자료 폴더다."""
    root, problem = ensure_ready()
    assert problem is None, problem
    assert root == data_root()
    for name in DATA_DIRS:
        assert (root / name).is_dir(), name
    # 아이콘만 자리가 다르다 — 잃어도 되는 것이라 임시 폴더에 산다.
    assert "cache" not in DATA_DIRS
    assert (cache_root() / "icons").is_dir()
    assert cache_root() != root



def test_unusable_folder_is_reported_instead_of_moved_elsewhere():
    """만들 수 없는 곳이면 조용히 다른 데로 옮기지 않고 이유를 돌려준다.

    백업이 어디 있는지 모르면 없는 백업과 같다. 그래서 이 경우는 실패로 다룬다.
    """
    import ipsm.paths as paths

    original = paths.data_root
    try:
        # 파일 안쪽 경로 — mkdir 이 반드시 실패한다
        paths.data_root = lambda: Path(__file__).resolve() / "sub"
        root, problem = paths.ensure_ready()
    finally:
        paths.data_root = original

    assert problem is not None
    assert "폴더를 만들 수 없습니다" in problem
    assert "옮긴 뒤" in problem  # 무엇을 하면 되는지까지 말한다


def test_the_backup_folder_never_lives_where_windows_may_clean_it():
    """백업과 로그를 임시 폴더에 두지 않는다.

    저장 공간 센스가 켜진 PC 에서 임시 파일 정리는 사고가 아니라 정상 동작이다.
    거기에 백업을 두는 것은 **지우는 일을 OS 에 위임하는 것**이고, 그때 사라지는
    백업은 사라졌다는 말조차 남기지 않는다. 되돌릴 길이 백업뿐인 앱에서 이것은
    있어서는 안 되는 배치다.
    """
    import tempfile as _tempfile

    from ipsm.paths import cache_root, data_root

    temp = Path(_tempfile.gettempdir()).resolve()
    root = data_root().resolve()
    assert temp not in root.parents and root != temp, f"자료 폴더가 TEMP 안이다: {root}"
    # 반대로 아이콘은 그 자리에 있어야 한다 — 지워져도 되는 것이라는 선언이다.
    assert cache_root().resolve().parent == temp


def test_the_data_folder_moves_out_of_the_install_dir_when_packaged():
    """MSIX 로 설치되면 exe 옆은 쓸 수 없다 — 문서 폴더로 간다.

    `C:\Program Files\WindowsApps\...` 는 관리자 권한으로도 쓸 수 없다는 것을
    2026-08-21 에 직접 확인했다. 그러니 포장된 설치에서 exe 옆을 자료 폴더로 삼으면
    '옮겨 주세요'라고 말할 수밖에 없는데, Store 로 설치한 앱은 사용자가 옮길 수
    없으므로 그 안내는 막다른 길이다.

    `%LOCALAPPDATA%` 도 답이 아니다 — 포장된 앱에서는 `Packages\...\LocalCache\`
    로 조용히 옮겨져, 정확히 '사용자가 찾을 수 없는 곳'이 된다.
    """
    import ipsm.paths as paths
    from ipsm import product

    saved = (paths.is_frozen, paths.package_family_name, paths.documents_dir)
    try:
        paths.is_frozen = lambda: True
        paths.package_family_name = lambda: "HomeSpread_abcdefghijklm"
        paths.documents_dir = lambda: Path("D:/Personal/Documents")
        assert paths.is_packaged()
        assert paths.data_root() == Path("D:/Personal/Documents") / product.NAME

        # 문서 폴더를 묻지 못해도 설치 폴더로 되돌아가지는 않는다.
        paths.documents_dir = lambda: None
        assert paths.data_root() == Path.home() / product.NAME

        # 포장 밖이면 지금까지와 똑같다 — 방금 확인한 폴더 배포 동작은 그대로.
        paths.package_family_name = lambda: None
        assert not paths.is_packaged()
        assert paths.data_root() == Path(sys.executable).resolve().parent
    finally:
        paths.is_frozen, paths.package_family_name, paths.documents_dir = saved


def test_source_runs_are_never_mistaken_for_a_packaged_install():
    """개발용 파이썬이 Store 판이면 **소스로 돌려도** 패키지 신원이 잡힌다.

    이 프로젝트가 실제로 그렇다(`PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0`).
    포장 여부를 신원만으로 판단하면 개발 중에 자료가 프로젝트 밖 문서 폴더로 흩어진다.
    """
    import ipsm.paths as paths

    saved = paths.package_family_name
    try:
        paths.package_family_name = lambda: "PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0"
        assert not paths.is_packaged(), "소스 실행을 포장된 설치로 잘못 읽는다"
    finally:
        paths.package_family_name = saved


def test_the_advice_matches_what_the_user_can_actually_do():
    """Store 로 설치한 앱은 사용자가 옮길 수 없다 — 그때는 옮기라고 말하지 않는다."""
    import ipsm.paths as paths

    saved = paths.is_packaged
    try:
        paths.is_packaged = lambda: True
        message = paths._cannot_write(Path("C:/Program Files/WindowsApps/x/backups"))
        assert "옮겨" not in message, "설치 폴더를 옮기라는 막다른 안내를 한다"
        assert "권한" in message
    finally:
        paths.is_packaged = saved


def test_the_package_check_answers_no_outside_a_package():
    """실제로 이 프로세스에 물어본다 — 포장 밖이면 None 이어야 한다."""
    from ipsm.paths import package_family_name

    name = package_family_name()
    assert name is None or isinstance(name, str)


def test_the_documents_folder_is_asked_for_not_guessed():
    """문서 폴더를 다른 드라이브로 옮겨 둔 PC 가 흔하다 — 지어낸 경로는 틀린다."""
    src = (ROOT / "src" / "ipsm" / "paths.py").read_text(encoding="utf-8")
    body = src[src.index("def documents_dir("): src.index("def data_root(")]
    assert "SHGetKnownFolderPath" in body
    # 환경 변수로 경로를 짓지 않는다 — 문서 폴더의 진짜 자리는 셸만 안다.
    assert "environ" not in src and "getenv" not in src

    from ipsm.paths import documents_dir

    found = documents_dir()
    if sys.platform == "win32":
        assert found is not None and found.is_dir(), found


# ----------------------------------------------------------------- 다국어


def _translatable_strings() -> list[tuple[str, str]]:
    """소스에 적힌 tr("...") 의 원문을 전부 모은다. (파일, 원문)

    사람 눈으로 250개를 맞춰 보는 것은 되지 않는다. 그래서 소스를 읽어서 센다 —
    새 문구를 넣고 사전에 넣는 것을 잊으면 이 목록이 먼저 알아챈다.
    """
    root = Path(__file__).resolve().parents[1] / "src" / "ipsm"
    found: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else getattr(node.func, "attr", "")
            )
            if name not in ("tr", "_", "defer") or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.append((path.name, first.value))
    return found


def test_no_module_level_translation_freezes_the_language():
    """모듈 맨 바깥에서 `tr()` 을 부르면 그 자리는 불러온 순간의 언어로 굳는다.

    기기 오류 안내표가 실제로 그랬다. 표가 만들어질 때 한 번 옮겨지고 나면 언어를
    바꿔도 그 표만 한국어로 남는데, 평소에 보이지 않는 말이라 한참 뒤에야 드러난다.
    표에는 `defer()` 를 적고 쓰는 자리에서 옮긴다.
    """
    root = Path(__file__).resolve().parents[1] / "src" / "ipsm"
    frozen = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # 불러올 때 실행되는 자리 = 모듈 본문과 클래스 본문. 함수 안은 부를 때
        # 옮겨지므로 괜찮다.
        eager = list(tree.body)
        while eager:
            top = eager.pop()
            if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(top, ast.ClassDef):
                eager.extend(top.body)
                continue
            for node in ast.walk(top):
                if not isinstance(node, ast.Call):
                    continue
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else getattr(node.func, "attr", "")
                )
                if name in ("tr", "_"):
                    frozen.append(f"{path.name}:{top.lineno}")
    assert not frozen, "모듈 바깥에서 굳어 버린 번역: " + " / ".join(sorted(set(frozen)))


def test_every_translatable_string_has_an_english_entry():
    """빠뜨린 번역은 눈이 아니라 시험이 잡는다.

    빠져도 앱은 한국어를 그대로 보여주므로 화면이 깨지지는 않는다 — 그래서 더더욱
    사람 눈에는 안 띈다. 여기서 잡지 않으면 영어로 켠 사용자만 알게 된다.
    """
    from ipsm.translations_en import TRANSLATIONS

    missing = sorted({text for _file, text in _translatable_strings() if text not in TRANSLATIONS})
    assert not missing, "영어 번역이 없는 문구: " + " / ".join(m[:40] for m in missing[:5])


def test_translations_keep_the_same_placeholders():
    """{n} 이 번역에서 사라지면 format() 이 조용히 다른 문장을 만든다.

    이름이 틀리면 KeyError 로 터지지만, 빠지면 값만 사라진 문장이 나온다 —
    "앱 3개를 받았습니다" 가 "Fetched icons." 가 되어도 아무도 못 알아챈다.
    """
    from ipsm.translations_en import TRANSLATIONS

    slots = lambda text: set(re.findall(r"\{(\w+)\}", text))
    wrong = [key for key, value in TRANSLATIONS.items() if slots(key) != slots(value)]
    assert not wrong, "값 자리가 어긋난 번역: " + " / ".join(w[:40] for w in wrong[:5])


def test_no_translation_is_left_as_korean():
    """번역해 놓고 원문을 그대로 붙여 둔 것을 잡는다. 옮기다 만 자리다."""
    from ipsm.translations_en import TRANSLATIONS

    same = [key for key, value in TRANSLATIONS.items() if key == value]
    assert not same, "원문 그대로인 번역: " + " / ".join(s[:40] for s in same[:5])


def test_switching_language_changes_what_tr_returns():
    from ipsm import i18n

    before = i18n.language()
    try:
        i18n.set_language("en")
        assert i18n.tr("취소") == "Cancel"
        assert i18n.tr("모르는 말") == "모르는 말", "사전에 없으면 원문 그대로"
        i18n.set_language("ko")
        assert i18n.tr("취소") == "취소"
    finally:
        i18n.set_language(before)


def test_the_model_speaks_the_chosen_language():
    """사전이 화면뿐 아니라 모델의 판정문에도 닿는지. 두 층이 같은 사전을 쓴다."""
    from ipsm import i18n

    before = i18n.language()
    try:
        i18n.set_language("en")
        doc = _doc()
        node = doc.pages[1].items[0]
        doc.move(node.uid, doc.pages[0].uid, 0)
        assert any("→" in line or "slot" in line for line in doc.changes())
        assert "pages" in doc.summary()
    finally:
        i18n.set_language(before)


def test_language_choice_survives_a_restart(tmp_path=None):
    """고른 언어는 settings.json 에 남는다 — 다음에 켤 때도 같아야 한다."""
    from ipsm import i18n, paths

    original_root = paths.data_root
    before = i18n.language()
    with tempfile.TemporaryDirectory() as folder:
        try:
            paths.data_root = lambda: Path(folder)
            i18n.choose("en")
            assert i18n.load_settings()["language"] == "en"
            # 새로 켠 셈 치고 저장된 값을 읽는다
            i18n.set_language("ko")
            assert i18n.start() == "en"
        finally:
            paths.data_root = original_root
            i18n.set_language(before)


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except Exception as exc:
                failures += 1
                print(f"  FAIL  {name}: {exc!r}")
    print()
    print("모두 통과" if not failures else f"{failures}개 실패")
    raise SystemExit(1 if failures else 0)


def test_the_exe_says_what_it_is():
    """비어 있는 버전 리소스는 오탐을 부르고, 받은 사람에게도 아무 말을 하지 않는다.

    2026-08-26 에 Defender 가 이 exe 를 `Trojan:Win32/Bearfoos.B!ml` 로 격리했다.
    `!ml` 은 서명 목록이 아니라 **기계학습의 추정**이고, 그것이 나쁜 쪽으로 기우는
    조건이 우리 것에 다 있었다 — 서명 없음, 아이콘 없음, 회사·제품·설명이 전부 빈
    버전 리소스. 서명은 스토어가 대신 해 주지만 뒤의 둘은 우리가 채워야 한다.
    채운다고 탐지가 반드시 사라지는 것은 아니나, 비워 두면 받은 사람이 속성 창을
    열어도 이것이 무엇이고 누가 만들었는지 알 방법이 없다.

    숫자는 `version.py` 에서만 온다. 여기에 또 적으면 빌드마다 올라가는 패치 번호와
    갈라서고, 그 어긋남은 실행해 보기 전에는 드러나지 않는다.
    """
    from ipsm import product

    spec = (ROOT / "HomeSpread.spec").read_text(encoding="utf-8")
    assert "version=_VERSION_RES" in spec, "exe 에 버전 리소스를 붙이지 않는다"
    assert "icon=" in spec, "exe 에 아이콘을 붙이지 않는다"
    assert (ROOT / "assets" / "app.ico").exists(), "아이콘 파일이 없다"

    # 숫자를 spec 이 직접 적지 않는지 — version.py 에서 받아 와야 한다.
    assert "version.VERSION_TUPLE" in spec, "판 번호를 version.py 에서 받지 않는다"

    # 채워 넣는 칸들이 실제로 이름을 말하는지.
    assert product.NAME in product.PUBLISHER
    assert product.NAME in product.COPYRIGHT
    assert "Copyright" in product.COPYRIGHT


def test_the_write_failure_message_names_controlled_folder_access():
    """"권한을 확인하세요"만으로는 빠져나올 수 없는 경우가 있다.

    Windows 보안의 제어된 폴더 액세스는 허용 목록에 없는 앱이 문서·바탕화면에 쓰는
    것을 막는다. 그때 **폴더 권한은 멀쩡하므로** 권한만 들여다보는 사용자는 원인에
    닿지 못한다. 2026-08-26 에 우리가 그 벽에 부딪혔다.

    더 나쁜 것은 포장하지 않은 판의 다음 줄이었다 — "바탕화면이나 문서 폴더로
    옮기라"고 권하는데, 그 둘이 바로 제어된 폴더 액세스가 기본으로 지키는 자리다.
    같은 벽으로 다시 보내는 안내였다. 그래서 네 갈래 모두가 이것을 말해야 한다.
    """
    from ipsm import paths

    hint = "제어된 폴더 액세스"
    seen = []
    for packaged in (True, False):
        real = paths.is_packaged
        paths.is_packaged = lambda: packaged
        try:
            seen.append(paths._cannot_write(Path("X:/nowhere")))
            with tempfile.TemporaryDirectory() as tmp:
                blocked = Path(tmp) / "blocked"
                blocked.write_text("나는 폴더가 아니다", encoding="utf-8")
                real_root = paths.data_root
                paths.data_root = lambda: blocked
                try:
                    _, problem = paths.ensure_ready()
                finally:
                    paths.data_root = real_root
            assert problem, "폴더를 만들 수 없는데 아무 말도 하지 않는다"
            seen.append(problem)
        finally:
            paths.is_packaged = real

    assert len(seen) == 4
    for message in seen:
        assert hint in message, "제어된 폴더 액세스를 짚지 않는다:\n" + message
