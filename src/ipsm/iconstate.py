"""iconState 해석 — 원본을 보존하면서 읽는다.

setIconState 는 부분 갱신이 아니라 **전체 덮어쓰기**다. 우리가 이해하지 못해 빠뜨린 요소는
그대로 사라진다. 그래서 이 모듈의 제1 원칙은 하나다:

    해석은 원본 위에 얹는 '뷰'이고, 쓸 때는 언제나 원본을 기반으로 한다.

알 수 없는 항목을 버리고 우리 모델로 재구성해서 쓰면, 위젯이나 새 iOS 기능이 조용히
삭제된다. 되돌릴 수는 있지만(백업), 애초에 일어나면 안 되는 일이다.

형식에 대한 현재 이해는 잠정적이다. 실기기 프로브가 덤프한 원본으로 검증하기 전까지
`ItemKind.UNKNOWN` 이 나오는 것은 정상이며, 오류가 아니다.
"""

from __future__ import annotations

import copy
import hashlib
import plistlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator, Optional

from .i18n import tr

# 실기기(iPhone 14, iOS 26.1)에서 확인한 키들. 관측된 형태는 네 가지뿐이었다:
#
#   설치된 앱   bundleIdentifier · bundleVersion · displayIdentifier · displayName · iconModDate
#   오프로드된 앱                                  displayIdentifier · displayName
#   웹 클립                                        displayIdentifier · displayName · iconModDate · webClipURL
#   폴더        displayName · listType · iconLists
#
# 항목의 정체성은 bundleIdentifier 가 아니라 **displayIdentifier** 다. 오프로드된 앱
# (아이콘만 남기고 본체를 지운 상태)에는 bundleIdentifier 자체가 없기 때문이다.
KEY_DISPLAY_NAME = "displayName"
KEY_BUNDLE_ID = "bundleIdentifier"
KEY_DISPLAY_ID = "displayIdentifier"
KEY_WEB_CLIP_URL = "webClipURL"
KEY_LIST_TYPE = "listType"
KEY_ICON_LISTS = "iconLists"
LIST_TYPE_FOLDER = "folder"


class ItemKind(str, Enum):
    APP = "app"
    FOLDER = "folder"
    WIDGET = "widget"
    EMPTY = "empty"
    UNKNOWN = "unknown"


_WIDGET_SPANS = {"small": (2, 2), "medium": (4, 2), "large": (4, 4)}


def is_widget_payload(raw: Any) -> bool:
    """Recognize explicit widget data before looking at iconLists or bundle IDs.

    Both single widgets and stacks can contain an empty ``iconLists`` field. It
    describes no folder; its presence must never turn a widget into an editable
    folder. Unrecognized custom icon types remain UNKNOWN.
    """
    if not isinstance(raw, dict):
        return False
    if raw.get("elementType") == "widget" or raw.get("widgetIdentifier"):
        return True
    elements = raw.get("elements")
    return bool(isinstance(elements, list) and elements and all(
        isinstance(element, dict)
        and (element.get("elementType") == "widget" or element.get("widgetIdentifier"))
        for element in elements
    ))


def widget_span(raw: Any) -> Optional[tuple[int, int]]:
    """Known preview dimensions as (columns, rows); never guess unknown sizes."""
    if not isinstance(raw, dict):
        return None
    size = raw.get("gridSize")
    return _WIDGET_SPANS.get(size) if isinstance(size, str) else None


def widget_member_count(raw: Any) -> int:
    if not is_widget_payload(raw):
        return 0
    elements = raw.get("elements")
    return len(elements) if isinstance(elements, list) and elements else 1


def widget_label(raw: Any) -> str:
    elements = raw.get("elements") if isinstance(raw, dict) else None
    if isinstance(elements, list) and elements:
        return tr("Widget stack ({n})").format(n=len(elements))
    return tr("Widget")


@dataclass
class Item:
    """홈화면의 항목 하나. `raw` 가 정본이고 나머지는 해석 결과다."""

    kind: ItemKind
    raw: Any
    bundle_id: Optional[str] = None
    display_name: Optional[str] = None
    children: list[list["Item"]] = field(default_factory=list)  # 폴더 내부 페이지들

    @property
    def label(self) -> str:
        if self.kind is ItemKind.WIDGET:
            return widget_label(self.raw)
        if self.display_name:
            return self.display_name
        if self.bundle_id:
            return self.bundle_id
        return {
            ItemKind.EMPTY: tr("(빈칸)"),
            ItemKind.UNKNOWN: tr("(알 수 없는 항목)"),
        }.get(self.kind, tr("(이름 없음)"))

    @property
    def installed(self) -> bool:
        """본체가 기기에 있는가. False 면 오프로드된 앱 — 아이콘만 남아 있다.

        UI에서 구분해 보여줄 값이다. 옮기는 데는 지장이 없다.
        """
        return isinstance(self.raw, dict) and KEY_BUNDLE_ID in self.raw

    @property
    def is_web_clip(self) -> bool:
        """홈화면에 추가한 웹 페이지 바로가기. 앱 아이콘을 받아올 수 없다."""
        return isinstance(self.raw, dict) and KEY_WEB_CLIP_URL in self.raw

    @property
    def movable(self) -> bool:
        """알 수 없는 항목은 움직이지 않는다 — 어떤 제약이 걸려 있는지 모르기 때문이다."""
        return self.kind in (ItemKind.APP, ItemKind.FOLDER)


def parse_item(raw: Any) -> Item:
    if raw is None:
        return Item(kind=ItemKind.EMPTY, raw=None)

    # 오래된 형식은 번들 ID 문자열만 담기도 한다.
    if isinstance(raw, str):
        return Item(kind=ItemKind.APP, raw=raw, bundle_id=raw, display_name=raw)

    if isinstance(raw, dict):
        if is_widget_payload(raw):
            return Item(kind=ItemKind.WIDGET, raw=raw)
        if raw.get(KEY_LIST_TYPE) == LIST_TYPE_FOLDER:
            lists = raw.get(KEY_ICON_LISTS)
            if not isinstance(lists, list) or not all(isinstance(page, list) for page in lists):
                return Item(kind=ItemKind.UNKNOWN, raw=raw)
            pages = [
                [parse_item(entry) for entry in page]
                for page in lists
            ]
            return Item(
                kind=ItemKind.FOLDER,
                raw=raw,
                display_name=raw.get(KEY_DISPLAY_NAME),
                children=pages,
            )
        if (KEY_ICON_LISTS in raw or "iconType" in raw or "elements" in raw
                or raw.get(KEY_LIST_TYPE)):
            return Item(kind=ItemKind.UNKNOWN, raw=raw, display_name=raw.get(KEY_DISPLAY_NAME))
        # displayIdentifier 를 먼저 본다. 오프로드된 앱과 웹 클립에는 그것뿐이고,
        # 설치된 앱에서는 두 값이 같다.
        identifier = raw.get(KEY_DISPLAY_ID) or raw.get(KEY_BUNDLE_ID)
        if identifier:
            return Item(
                kind=ItemKind.APP,
                raw=raw,
                bundle_id=str(identifier),
                display_name=raw.get(KEY_DISPLAY_NAME) or str(identifier),
            )
        # dict 이지만 앱도 폴더도 아니다 — 위젯이거나 우리가 모르는 무언가.
        return Item(
            kind=ItemKind.UNKNOWN,
            raw=raw,
            display_name=raw.get(KEY_DISPLAY_NAME),
        )

    return Item(kind=ItemKind.UNKNOWN, raw=raw)


@dataclass
class IconState:
    """getIconState 결과 전체.

    관측된 형식: 최상위 리스트의 첫 원소가 독(buttonBar), 나머지가 홈화면 페이지.
    이 가정은 `dock_first` 로 표시해 두고, 실기기 결과로 확인한다.
    """

    raw: list[Any]
    dock: list[Item]
    pages: list[list[Item]]
    dock_first: bool = True

    @classmethod
    def parse(cls, raw: list[Any]) -> "IconState":
        raw = copy.deepcopy(raw)
        if not raw:
            return cls(raw=raw, dock=[], pages=[])
        dock = [parse_item(entry) for entry in raw[0]] if isinstance(raw[0], list) else []
        pages = [
            [parse_item(entry) for entry in page] if isinstance(page, list) else []
            for page in raw[1:]
        ]
        return cls(raw=raw, dock=dock, pages=pages)

    # --------------------------------------------------------------- 집계

    def iter_items(self, *, include_folder_children: bool = True) -> Iterator[Item]:
        for item in self.dock:
            yield from _walk(item, include_folder_children)
        for page in self.pages:
            for item in page:
                yield from _walk(item, include_folder_children)

    def counts(self) -> dict[str, int]:
        tally = {kind.value: 0 for kind in ItemKind}
        for item in self.iter_items():
            tally[item.kind.value] += 1
        return tally

    def bundle_ids(self) -> set[str]:
        return {item.bundle_id for item in self.iter_items() if item.bundle_id}

    def describe(self) -> str:
        """로그와 프로브 출력용 요약. 원본 전체를 로그에 쏟지 않기 위한 것이다."""
        tally = self.counts()
        lines = [
            tr("페이지 {pages}개, 독 {dock}칸").format(pages=len(self.pages), dock=len(self.dock)),
            tr("앱 {apps}개 · 폴더 {folders}개 · 빈칸 {empty}개 · 알 수 없는 항목 {unknown}개").format(
                apps=tally["app"], folders=tally["folder"], empty=tally["empty"], unknown=tally["unknown"]
            ),
        ]
        widgets = [item for item in self.iter_items() if item.kind is ItemKind.WIDGET]
        if widgets:
            lines.append(tr("Widgets: {blocks} positions, {members} including stack members").format(
                blocks=len(widgets), members=sum(widget_member_count(item.raw) for item in widgets)
            ))
        offloaded = sum(1 for i in self.iter_items() if i.kind is ItemKind.APP and not i.installed)
        clips = sum(1 for i in self.iter_items() if i.is_web_clip)
        if offloaded or clips:
            lines.append(tr("(그 중 오프로드된 앱 {offloaded}개 · 웹 클립 {clips}개)").format(
                offloaded=offloaded, clips=clips
            ))
        if self.dock:
            lines.append(tr("  독: {items}").format(items=", ".join(item.label for item in self.dock)))
        for index, page in enumerate(self.pages, start=1):
            labels = [item.label for item in page]
            preview = ", ".join(labels[:8])
            if len(labels) > 8:
                preview += tr(", … (총 {count}칸)").format(count=len(labels))
            lines.append(tr("  {index}페이지 ({count}칸): {preview}").format(
                index=index, count=len(page), preview=preview
            ))
        return "\n".join(lines)

    def unknown_samples(self, limit: int = 5) -> list[Any]:
        """알 수 없는 항목의 원본 표본. 형식 해석을 고치는 근거가 된다."""
        samples: list[Any] = []
        for item in self.iter_items():
            if item.kind is ItemKind.UNKNOWN and len(samples) < limit:
                samples.append(item.raw)
        return samples


def _walk(item: Item, include_children: bool) -> Iterator[Item]:
    yield item
    if include_children and item.kind is ItemKind.FOLDER:
        for page in item.children:
            for child in page:
                yield from _walk(child, include_children)


def deep_equal(left: Any, right: Any) -> bool:
    """두 iconState 가 같은지 비교한다.

    항등 왕복 시험(REQ-003)과 적용 후 대조(REQ-015)의 판정 기준이다.
    """
    return _normalize(left) == _normalize(right)


def _normalize(value: Any) -> Any:
    """비교를 방해하는 비본질적 차이를 제거한다.

    iconModDate 같은 시각 필드는 기기가 갱신하므로, 이 값이 다르다는 이유로
    '적용 실패'를 보고하면 항상 실패하게 된다.
    """
    volatile = {"iconModDate", "iconModificationDate"}
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in sorted(value.items()) if k not in volatile}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, bytes):
        return ("__plist_bytes__", value.hex())
    return value


def diff_summary(before: Any, after: Any) -> list[str]:
    """무엇이 달라졌는지 사람이 읽을 수 있게 요약한다. 적용 결과 대조용."""
    left, right = IconState.parse(before), IconState.parse(after)
    notes: list[str] = []

    if len(left.pages) != len(right.pages):
        notes.append(tr("페이지 수: {before} → {after}").format(before=len(left.pages), after=len(right.pages)))
    if len(left.dock) != len(right.dock):
        notes.append(tr("독 항목 수: {before} → {after}").format(before=len(left.dock), after=len(right.dock)))

    gone = left.bundle_ids() - right.bundle_ids()
    added = right.bundle_ids() - left.bundle_ids()
    if gone:
        notes.append(tr("사라진 앱 {count}개: {items}").format(count=len(gone), items=", ".join(sorted(gone)[:10])))
    if added:
        notes.append(tr("새로 나타난 앱 {count}개: {items}").format(count=len(added), items=", ".join(sorted(added)[:10])))

    left_counts, right_counts = left.counts(), right.counts()
    if left_counts["unknown"] != right_counts["unknown"]:
        notes.append(
            tr("알 수 없는 항목 수: {before} → {after}").format(
                before=left_counts["unknown"], after=right_counts["unknown"]
            )
        )

    if not notes:
        notes.append(tr("구조적 차이 없음"))
    return notes


def value_diff(before: Any, after: Any, limit: int = 20) -> list[str]:
    """두 구조의 차이를 '경로: 이전 -> 이후' 형태로 정확히 짚는다.

    diff_summary() 가 '무엇이 달라졌나'를 사람 말로 요약한다면, 이쪽은 '어디가'를 가리킨다.
    백업 검증이나 왕복 시험이 실패했을 때 메시지 한 줄만 남으면 원인을 추측할 수밖에 없다.
    추측은 이 프로젝트에서 가장 위험한 행동이다 — 사용자의 홈화면이 걸려 있기 때문이다.
    """
    out: list[str] = []

    def walk(a: Any, b: Any, path: str) -> None:
        if len(out) >= limit:
            return
        if type(a) is not type(b):
            out.append(tr("{path}: 타입 {before} -> {after}").format(
                path=path, before=type(a).__name__, after=type(b).__name__
            ))
            return
        if isinstance(a, dict):
            for key in sorted(set(a) | set(b), key=str):
                if key not in a:
                    out.append(tr("{path}.{key}: (없음) -> {after!r}").format(path=path, key=key, after=b[key]))
                elif key not in b:
                    out.append(tr("{path}.{key}: {before!r} -> (없음)").format(path=path, key=key, before=a[key]))
                else:
                    walk(a[key], b[key], f"{path}.{key}")
        elif isinstance(a, list):
            if len(a) != len(b):
                out.append(tr("{path}: 항목 수 {before} -> {after}").format(path=path, before=len(a), after=len(b)))
                return
            for index, (left, right) in enumerate(zip(a, b)):
                walk(left, right, f"{path}[{index}]")
        elif a != b:
            out.append(f"{path}: {a!r} -> {b!r}")

    walk(before, after, "$")
    return out


@dataclass
class WriteComparison:
    """쓰기 전후 비교 결과.

    '같다/다르다'로는 부족하다. 실기기에서 확인된 바로는, 잃는 것과 늘어나는 것은
    성격이 전혀 다르기 때문이다:

      손실·이동 : 사용자가 만든 배치가 훼손된 것. 쓰기 기능을 만들면 안 된다.
      추가       : 홈화면에 없던 앱을 iOS 가 도로 붙인 것. 눈에 보이고 되돌릴 수 있다.

    이 둘을 뭉뚱그리면 안전한 기기를 위험하다고 판정하거나, 그 반대가 된다.
    """

    lost: list[str]
    added: list[str]
    moved: list[str]
    changed: list[str] = field(default_factory=list)

    @property
    def safe(self) -> bool:
        """사용자의 배치가 보존되었는가. 추가는 여기에 포함하지 않는다."""
        return not self.lost and not self.moved and not self.changed

    @property
    def identical(self) -> bool:
        return self.safe and not self.added


def _position_map(state: list[Any]) -> dict[str, tuple]:
    """항목마다 '어디에 있는가'를 기록한다. 이동을 잡아내려면 위치가 필요하다.

    같은 식별자가 두 번 나오면 뒤에 #2 를 붙인다 — 덮어쓰면 중복이 조용히 사라진다.
    """
    positions: dict[str, tuple] = {}
    seen: dict[str, int] = {}

    def key_for(raw: Any) -> str:
        if isinstance(raw, dict):
            kind = parse_item(raw).kind
            identifier = raw.get(KEY_DISPLAY_ID) or raw.get(KEY_BUNDLE_ID)
            if identifier and kind in (ItemKind.APP, ItemKind.WIDGET):
                return f"{kind.value}:{identifier}"
            if kind is ItemKind.FOLDER:
                return f"folder:{raw.get(KEY_DISPLAY_NAME)}"
        # A display-length truncation can hide changes beyond the first 120 chars.
        # Hash the full payload; the UI receives a short stable identifier.
        payload = plistlib.dumps(raw, fmt=plistlib.FMT_BINARY, sort_keys=True)
        return "raw:" + hashlib.sha256(payload).hexdigest()[:24]

    def walk(items: list[Any], prefix: tuple) -> None:
        for index, raw in enumerate(items):
            key = key_for(raw)
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 1:
                key = f"{key}#{seen[key]}"
            positions[key] = prefix + (index,)
            if isinstance(raw, dict) and parse_item(raw).kind is ItemKind.FOLDER:
                for page_index, page in enumerate(raw.get(KEY_ICON_LISTS) or []):
                    if isinstance(page, list):
                        walk(page, prefix + (index, page_index))

    for list_index, entries in enumerate(state):
        if isinstance(entries, list):
            walk(entries, (list_index,))
    return positions


def describe_position(position: tuple) -> str:
    """위치를 사용자가 홈화면에서 찾을 수 있는 말로 옮긴다."""
    if not position:
        return "?"
    head, slot = position[0], position[1]
    where = (
        tr("독 {n}번째").format(n=slot + 1)
        if head == 0
        else tr("{page}페이지 {n}번째").format(page=head, n=slot + 1)
    )
    return where + (tr(" 폴더 안") if len(position) > 2 else "")


def compare_after_write(before: list[Any], after: list[Any]) -> WriteComparison:
    """쓰기 전후를 항목 단위로 대조한다 (REQ-003 · REQ-015 판정)."""
    left, right = _position_map(before), _position_map(after)
    lost = [f"{key} ({describe_position(left[key])})" for key in left if key not in right]
    added = [f"{key} ({describe_position(right[key])})" for key in right if key not in left]
    moved = [
        f"{key}: {describe_position(left[key])} -> {describe_position(right[key])}"
        for key in left
        if key in right and left[key] != right[key]
    ]
    def at(state: list[Any], position: tuple) -> Any:
        raw = state[position[0]][position[1]]
        for offset in range(2, len(position), 2):
            raw = raw[KEY_ICON_LISTS][position[offset]][position[offset + 1]]
        if isinstance(raw, dict) and parse_item(raw).kind is ItemKind.FOLDER:
            # Children are compared independently; folder metadata still matters.
            return {key: value for key, value in raw.items() if key != KEY_ICON_LISTS}
        return raw

    changed = [key for key in left if key in right
               and not deep_equal(at(before, left[key]), at(after, right[key]))]
    return WriteComparison(lost=sorted(lost), added=sorted(added), moved=sorted(moved),
                           changed=sorted(changed))
