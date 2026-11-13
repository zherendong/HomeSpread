"""편집 가능한 홈화면 문서 — 원본 dict 를 옮겨 다니게 한다.

`iconstate.py` 가 '읽기 위한 뷰'라면 이 모듈은 '고치기 위한 문서'다. 둘을 나눈 이유는
setIconState 가 전체 덮어쓰기이기 때문이다.

핵심 설계는 한 줄로 요약된다:

    **우리는 항목을 만들지 않는다. 원본 dict 를 다른 리스트로 옮길 뿐이다.**

편집이란 곧 원본 객체의 자리바꿈이고, 내보내기는 그 객체들을 다시 중첩 리스트로 담는
일이다. 그래서 우리가 해석하지 못한 키(위젯, 새 iOS 기능, 우리가 모르는 무엇이든)는
해석할 필요조차 없이 그대로 실려 나간다 — REQ-017 은 '잊지 않고 챙기는 규율'이 아니라
자료 구조가 보장하는 성질이 된다.

이 성질은 검증 가능하다: 아무것도 편집하지 않은 문서를 내보내면 읽어들인 원본과
**완전히 같아야 한다**. `verify_identity()` 가 그것을 확인하고, 테스트가 실기기 덤프로
그것을 고정한다.
"""

from __future__ import annotations

import copy
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional, Sequence

from .i18n import defer, tr
from .iconstate import (
    KEY_BUNDLE_ID,
    KEY_DISPLAY_ID,
    KEY_DISPLAY_NAME,
    KEY_ICON_LISTS,
    KEY_LIST_TYPE,
    KEY_WEB_CLIP_URL,
    LIST_TYPE_FOLDER,
    ItemKind,
    parse_item,
    widget_label,
    widget_member_count,
    widget_span,
)

# 기기에서 읽은 그리드 수치가 없을 때 쓰는 값. iPhone 14 (iOS 26.1) 실측치다.
# 기기가 메트릭을 주면 언제나 그쪽을 따른다 — 화면 크기별로 행 수가 다르기 때문이다.
DEFAULT_METRICS = {
    "homeScreenIconColumns": 4,
    "homeScreenIconRows": 6,
    "homeScreenIconDockMaxCount": 4,
    "homeScreenIconFolderColumns": 3,
    "homeScreenIconFolderRows": 3,
    "homeScreenIconMaxPages": 15,
    "homeScreenIconFolderMaxPages": 15,
}


class LayoutError(Exception):
    """편집 규칙 위반. 메시지는 사용자에게 그대로 보여줄 수 있어야 한다."""


def _display(name: Optional[str]) -> Optional[str]:
    """화면에 쓸 이름으로 다듬는다. **원본은 건드리지 않는다.**

    iOS 가 주는 한글 이름은 자모가 분리된 형태(NFD)로 오기도 한다 — '11번가'의 '번'이
    ㅂ+ㅓ+ㄴ 세 글자로 온다. Windows 에서는 이것이 깨져 보이거나 자모가 흩어져 보인다.
    합친 형태(NFC)로 바꿔 표시하되, 기기에 다시 쓸 raw 는 원본 그대로 둔다. 표시용
    정규화가 원본에 새어 들어가면 항등 왕복이 깨지기 때문이다.

    이름 안의 붙임 공백(U+00A0)도 보통 공백으로 바꾼다. 'App Store' 가 한 덩어리로
    보이는 것은 iPhone 화면에서나 의미가 있고, 목록에서는 검색을 방해한다.
    """
    if not name:
        return name
    cleaned = unicodedata.normalize("NFC", name)
    return cleaned.replace("\u00a0", " ").replace("\u200e", "")


@dataclass
class Grid:
    """그리드 수치. 기기가 알려준 값을 담는 그릇이며, 없으면 기본값을 쓴다."""

    columns: int = 4
    rows: int = 6
    dock_capacity: int = 4
    folder_columns: int = 3
    folder_rows: int = 3
    max_pages: int = 15
    folder_max_pages: int = 15

    @property
    def page_capacity(self) -> int:
        return self.columns * self.rows

    @property
    def folder_page_capacity(self) -> int:
        return self.folder_columns * self.folder_rows

    @classmethod
    def from_metrics(cls, metrics: Optional[dict[str, Any]]) -> "Grid":
        source = {**DEFAULT_METRICS, **(metrics or {})}

        def as_int(key: str, fallback: int) -> int:
            try:
                value = int(float(source[key]))
            except (KeyError, TypeError, ValueError):
                return fallback
            # 0 이나 음수가 오면 기기가 이상한 값을 준 것이다. 0 을 그대로 쓰면
            # 모든 페이지가 '가득 참'이 되어 편집이 통째로 막힌다.
            return value if value > 0 else fallback

        return cls(
            columns=as_int("homeScreenIconColumns", 4),
            rows=as_int("homeScreenIconRows", 6),
            dock_capacity=as_int("homeScreenIconDockMaxCount", 4),
            folder_columns=as_int("homeScreenIconFolderColumns", 3),
            folder_rows=as_int("homeScreenIconFolderRows", 3),
            max_pages=as_int("homeScreenIconMaxPages", 15),
            folder_max_pages=as_int("homeScreenIconFolderMaxPages", 15),
        )


# --------------------------------------------------------------------- 노드


@dataclass(eq=False)  # 동등성은 '같은 객체인가'로 판단한다. 같은 앱이 두 번 있어도 다른 노드다.
class Node:
    """홈화면 항목 하나. `raw` 가 정본이고 나머지는 화면에 그리기 위한 해석이다."""

    raw: Any
    kind: ItemKind
    uid: str
    identifier: Optional[str] = None
    display_name: Optional[str] = None
    pages: list["Container"] = field(default_factory=list)  # 폴더일 때만
    renamed_to: Optional[str] = None  # 사용자가 바꾼 묶음 이름

    @property
    def is_folder(self) -> bool:
        return self.kind is ItemKind.FOLDER

    @property
    def is_widget(self) -> bool:
        return self.kind is ItemKind.WIDGET

    @property
    def widget_span(self) -> Optional[tuple[int, int]]:
        return widget_span(self.raw) if self.is_widget else None

    @property
    def widget_member_count(self) -> int:
        return widget_member_count(self.raw) if self.is_widget else 0

    @property
    def widget_label(self) -> str:
        return widget_label(self.raw) if self.is_widget else ""

    @property
    def label(self) -> str:
        if self.is_widget:
            return self.widget_label
        return self.renamed_to or self.display_name or self.identifier or {
            ItemKind.EMPTY: tr("(빈칸)"),
            ItemKind.UNKNOWN: tr("(알 수 없는 항목)"),
        }.get(self.kind, tr("(이름 없음)"))

    @property
    def movable(self) -> bool:
        """알 수 없는 항목은 움직이지 않는다 — 어떤 제약이 걸려 있는지 모르기 때문이다."""
        return self.kind in (ItemKind.APP, ItemKind.FOLDER)

    @property
    def installed(self) -> bool:
        return isinstance(self.raw, dict) and KEY_BUNDLE_ID in self.raw

    @property
    def is_web_clip(self) -> bool:
        return isinstance(self.raw, dict) and KEY_WEB_CLIP_URL in self.raw

    def child_count(self) -> int:
        return sum(len(page.items) for page in self.pages)

    def to_raw(self) -> Any:
        """원본으로 되돌린다.

        폴더가 아니면 읽어들인 객체를 **그대로** 돌려준다. 복사도 재구성도 하지 않는다.
        폴더는 자식 배치가 바뀌었을 수 있으므로 iconLists 만 새로 만들고, 나머지 키는
        원본에서 그대로 가져온다 — 폴더 dict 에 우리가 모르는 키가 있어도 살아남는다.
        """
        if not self.is_folder:
            return self.raw
        rebuilt = dict(self.raw)
        rebuilt[KEY_ICON_LISTS] = [
            [child.to_raw() for child in page.items] for page in self.pages
        ]
        if self.renamed_to is not None:
            # 이름만 갈아 끼운다. 이름을 바꿨다고 해서 폴더의 다른 키까지 우리가
            # 다시 지어낼 이유는 없다 — 모르는 키는 위 dict(self.raw) 로 그대로 실린다.
            rebuilt[KEY_DISPLAY_NAME] = self.renamed_to
        return rebuilt


@dataclass(eq=False)
class Container:
    """항목이 담기는 자리 — 독 하나, 홈화면 페이지 하나, 폴더 페이지 하나.

    셋을 한 타입으로 묶은 이유는 드래그가 이 셋 사이를 자유롭게 오가기 때문이다.
    담는 규칙(용량, 무엇을 받을 수 있는가)만 kind 로 갈린다.
    """

    uid: str
    kind: str  # "dock" | "page" | "folder"
    items: list[Node] = field(default_factory=list)
    capacity: int = 24
    owner: Optional[Node] = None  # 폴더 페이지일 때 그 폴더 노드

    @property
    def full(self) -> bool:
        return len(self.items) >= self.capacity

    @property
    def accepts_folder(self) -> bool:
        """폴더 안에 폴더를 넣을 수 없다 — iOS 가 중첩 폴더를 지원하지 않는다."""
        return self.kind != "folder"


# ----------------------------------------------------------------- 명령(취소 단위)


@dataclass
class Command:
    """되돌릴 수 있는 편집 하나. 드래그 1회 = 명령 1개 = 취소 1회 (REQ-014)."""

    label: str

    def apply(self, doc: "LayoutDocument") -> None:  # pragma: no cover - 인터페이스
        raise NotImplementedError

    def revert(self, doc: "LayoutDocument") -> None:  # pragma: no cover - 인터페이스
        raise NotImplementedError


def _drop_emptied(
    doc: "LayoutDocument", emptied: tuple[str, int, "Node"]
) -> tuple[str, int, "Node"]:
    """마지막 하나가 빠져 빈 묶음이 된 것을 치운다. 치운 자리를 되돌려준다.

    자리는 **지금** 다시 찾는다. 항목을 끼워 넣느라 번째가 밀렸을 수 있고, 되돌렸다
    다시 실행할 때도 같은 자리를 다시 계산해야 맞는다.
    """
    holder_uid, _, folder = emptied
    holder = doc.container(holder_uid)
    index = next(i for i, item in enumerate(holder.items) if item is folder)
    holder.items.pop(index)
    return (holder_uid, index, folder)


def _put_back_emptied(doc: "LayoutDocument", emptied: tuple[str, int, "Node"]) -> None:
    holder_uid, index, folder = emptied
    doc.container(holder_uid).items.insert(index, folder)


#: 페이지 한 장이 없어질 자리. (묶음 노드 또는 None=홈화면, 몇 번째, 그 페이지)
Pruned = tuple[Optional["Node"], int, "Container"]


def _pages_of(doc: "LayoutDocument", holder: Optional["Node"]) -> list["Container"]:
    """페이지 무리 하나. 묶음이면 그 안의 페이지들, None 이면 홈화면 페이지들."""
    return doc.pages if holder is None else holder.pages


def _drop_pages(doc: "LayoutDocument", pruned: list[Pruned]) -> list[Pruned]:
    """다 빈 페이지들을 치운다. 치운 자리를 기록해 돌려준다.

    항목을 다 옮긴 **뒤**에 불러야 한다. 먼저 치우면 출발 자리를 uid 로 찾을 수 없다 —
    무리에서 떨어져 나간 페이지는 어디에도 없다.

    자리는 **지금** 다시 찾는다. 되돌렸다 다시 실행할 때 번째가 달라져 있을 수 있다.
    치울 수 없는 것(이미 없거나, 무리의 마지막 한 장)은 -1 로 적어 자리만 지킨다 —
    목록의 길이가 달라지면 되돌리기가 어긋난다.
    """
    done: list[Pruned] = []
    for holder, _index, page in pruned:
        pages = _pages_of(doc, holder)
        index = next((i for i, other in enumerate(pages) if other is page), None)
        if index is None or len(pages) <= 1:
            done.append((holder, -1, page))
            continue
        pages.pop(index)
        done.append((holder, index, page))
    return done


def _put_back_pages(doc: "LayoutDocument", pruned: list[Pruned]) -> None:
    for holder, index, page in reversed(pruned):
        if index < 0:
            continue
        _pages_of(doc, holder).insert(index, page)


@dataclass
class MoveCommand(Command):
    """항목 하나를 옮긴다. 드래그 한 번에 딸려 오는 곁가지도 여기에 함께 담는다.

    곁가지를 따로 명령으로 두면 취소를 두 번 눌러야 하고, 그 사이에 드러나는 중간
    상태(페이지만 늘었다든지, 빈 묶음만 남았다든지)는 사용자가 만든 적 없는 모양이다.
    드래그 1회 = 취소 1회 (REQ-014).
    """

    src_uid: str
    src_index: int
    dst_uid: str
    dst_index: int
    grew: Optional[tuple["Node", "Container"]] = None  # 꽉 차서 새로 편 묶음 페이지
    emptied: Optional[tuple[str, int, "Node"]] = None  # 마지막 하나가 빠져 없어질 묶음
    pruned: list[Pruned] = field(default_factory=list)  # 다 비어 없어질 페이지들

    def apply(self, doc: "LayoutDocument") -> None:
        if self.grew is not None:
            folder, page = self.grew
            if page not in folder.pages:
                folder.pages.append(page)
        node = doc.container(self.src_uid).items.pop(self.src_index)
        doc.container(self.dst_uid).items.insert(self.dst_index, node)
        # 묶음을 먼저 치운다. 그 묶음이 놓여 있던 페이지가 그것 때문에 비는 경우가
        # 있어서, 페이지 치우기는 반드시 그 뒤여야 한다.
        if self.emptied is not None:
            self.emptied = _drop_emptied(doc, self.emptied)
        if self.pruned:
            self.pruned = _drop_pages(doc, self.pruned)

    def revert(self, doc: "LayoutDocument") -> None:
        if self.pruned:
            _put_back_pages(doc, self.pruned)
        if self.emptied is not None:
            _put_back_emptied(doc, self.emptied)
        node = doc.container(self.dst_uid).items.pop(self.dst_index)
        doc.container(self.src_uid).items.insert(self.src_index, node)
        if self.grew is not None:
            folder, page = self.grew
            if page in folder.pages:
                folder.pages.remove(page)


@dataclass
class SpillCommand(Command):
    """꽉 찬 페이지에 끼워 넣고, 넘치는 것을 뒤 페이지로 민다.

    iPhone 에서 하던 그대로다 — 꽉 찬 페이지의 가운데에 앱을 놓으면 뒤가 한 칸씩
    밀리고, 페이지 끝을 넘은 마지막 앱이 다음 페이지 맨 앞으로 넘어간다. 홈화면이든
    묶음 안이든 미는 방식은 같아서, `holder` 하나로 어느 무리인지만 가린다.

    한 번에 여러 페이지가 바뀌므로 '무엇을 몇 번째로'가 아니라 **페이지 내용을
    통째로** 갈아 끼운다. 되돌릴 때도 통째로 되돌리니, 몇 개가 밀렸는지 다시 세지
    않아도 정확히 제자리가 된다. 드래그 1회 = 취소 1회 (REQ-014).
    """

    holder: Optional["Node"]  # 묶음 노드. None 이면 홈화면 페이지들
    pages_before: list["Container"]
    items_before: list[list["Node"]]
    pages_after: list["Container"]
    items_after: list[list["Node"]]
    src_uid: Optional[str] = None  # 이 무리 밖에서 왔다면 그 출발 자리
    src_index: int = 0
    src_node: Optional["Node"] = None
    emptied: Optional[tuple[str, int, "Node"]] = None
    pruned: list[Pruned] = field(default_factory=list)  # 떠나온 쪽의 빈 페이지들

    def _install(
        self, doc: "LayoutDocument", pages: list["Container"], items: list[list["Node"]]
    ) -> None:
        if self.holder is None:
            doc.pages = list(pages)
        else:
            self.holder.pages = list(pages)
        for page, content in zip(pages, items):
            page.items = list(content)

    def apply(self, doc: "LayoutDocument") -> None:
        if self.src_uid is not None:
            doc.container(self.src_uid).items.pop(self.src_index)
        self._install(doc, self.pages_after, self.items_after)
        if self.emptied is not None:
            self.emptied = _drop_emptied(doc, self.emptied)
        if self.pruned:
            self.pruned = _drop_pages(doc, self.pruned)

    def revert(self, doc: "LayoutDocument") -> None:
        if self.pruned:
            _put_back_pages(doc, self.pruned)
        if self.emptied is not None:
            _put_back_emptied(doc, self.emptied)
        self._install(doc, self.pages_before, self.items_before)
        if self.src_uid is not None and self.src_node is not None:
            doc.container(self.src_uid).items.insert(self.src_index, self.src_node)


@dataclass
class GroupCommand(Command):
    """여러 항목을 새 묶음(폴더) 하나로 모은다.

    되돌리기가 정확해야 하므로, 각 항목이 **원래 어느 자리 몇 번째였는지**를 통째로
    들고 있는다. 폴더 노드는 `group()` 이 한 번만 만들어 여기 담아 두고, 실행·되돌리기가
    같은 객체를 다시 쓴다 — 되돌렸다 다시 실행할 때마다 새 폴더가 생기면 uid 가 달라져
    변경 목록이 매번 '새 묶음'을 다시 보고하게 된다.
    """

    folder: Node
    members: list[tuple[str, int, str]]  # (원래 자리 uid, 그 자리에서의 번째, 노드 uid)
    dst_uid: str
    dst_index: int

    def apply(self, doc: "LayoutDocument") -> None:
        nodes = {uid: doc.node(uid) for _, _, uid in self.members}
        # 뒤에서부터 빼낸다. 앞에서 빼면 뒤 항목의 번째가 밀려 엉뚱한 것을 집는다.
        for container_uid, index, _uid in sorted(self.members, key=lambda m: -m[1]):
            doc.container(container_uid).items.pop(index)
        cursor = 0
        for page in self.folder.pages:
            take = self.members[cursor : cursor + page.capacity]
            page.items = [nodes[uid] for _, _, uid in take]
            cursor += len(take)
        doc.container(self.dst_uid).items.insert(self.dst_index, self.folder)

    def revert(self, doc: "LayoutDocument") -> None:
        destination = doc.container(self.dst_uid)
        for index, item in enumerate(destination.items):
            if item is self.folder:
                destination.items.pop(index)
                break
        # 비우기 **전에** 붙잡아 둔다 — 비운 뒤에는 찾을 곳이 없다.
        nodes = {uid: self._find(uid) for _, _, uid in self.members}
        for page in self.folder.pages:
            page.items = []
        # 앞에서부터 되돌린다. 빼낼 때와 반대 순서라야 번째가 맞는다.
        for container_uid, index, uid in sorted(self.members, key=lambda m: m[1]):
            doc.container(container_uid).items.insert(index, nodes[uid])

    def _find(self, uid: str) -> Node:
        for page in self.folder.pages:
            for node in page.items:
                if node.uid == uid:
                    return node
        raise LayoutError(tr("묶음 안에서 항목을 찾을 수 없습니다 ({uid}).").format(uid=uid))


@dataclass
class RenameFolderCommand(Command):
    node_uid: str
    before: Optional[str]
    after: str

    def apply(self, doc: "LayoutDocument") -> None:
        doc.node(self.node_uid).renamed_to = self.after

    def revert(self, doc: "LayoutDocument") -> None:
        doc.node(self.node_uid).renamed_to = self.before


@dataclass
class ReorderPagesCommand(Command):
    from_index: int
    to_index: int

    def apply(self, doc: "LayoutDocument") -> None:
        doc.pages.insert(self.to_index, doc.pages.pop(self.from_index))

    def revert(self, doc: "LayoutDocument") -> None:
        doc.pages.insert(self.from_index, doc.pages.pop(self.to_index))


@dataclass
class AddPageCommand(Command):
    index: int
    container: Container

    def apply(self, doc: "LayoutDocument") -> None:
        doc.pages.insert(self.index, self.container)

    def revert(self, doc: "LayoutDocument") -> None:
        doc.pages.pop(self.index)


@dataclass
class RemovePageCommand(Command):
    index: int
    container: Container

    def apply(self, doc: "LayoutDocument") -> None:
        doc.pages.pop(self.index)

    def revert(self, doc: "LayoutDocument") -> None:
        doc.pages.insert(self.index, self.container)


# ------------------------------------------------------------------- 문서


class LayoutDocument:
    """편집 중인 홈화면 하나. 원본 상태와 편집 이력을 함께 들고 있다."""

    def __init__(self, origin: list[Any], grid: Grid) -> None:
        self.origin = copy.deepcopy(origin)  # 되돌릴 기준. 절대 건드리지 않는다.
        self.grid = grid
        self.dock = Container(uid="dock", kind="dock", items=[], capacity=grid.dock_capacity)
        self.pages: list[Container] = []
        self._uid_counter = 0
        self._undo: list[Command] = []
        self._redo: list[Command] = []
        self._build(origin)
        kinds = {node.kind for container in self.containers() for node in container.items}
        self._readonly_key: Optional[str] = None
        if not origin or not all(isinstance(page, list) for page in origin):
            self._readonly_key = defer("This layout has an unsupported structure. Preview only; editing is disabled.")
        elif ItemKind.WIDGET in kinds:
            self._readonly_key = defer("This layout contains widgets. Preview only; editing is disabled.")
        elif ItemKind.UNKNOWN in kinds or ItemKind.EMPTY in kinds:
            self._readonly_key = defer("This layout contains unknown items or empty placeholders. Preview only; editing is disabled.")
        elif any(len(container.items) > container.capacity for container in self.containers()):
            self._readonly_key = defer("The layout exceeds the reported grid capacity. Preview only; editing is disabled.")
        # 편집 전의 배치를 그대로 떠 둔다. 변경 목록은 이것과의 대조로만 만들어진다 —
        # 명령 이력을 되짚어 계산하면 취소·재실행이 섞였을 때 어긋난다.
        self._origin_snapshot = self._snapshot()
        self._origin_order: dict[str, list[tuple[str, int]]] = {
            container.uid: [(node.uid, index) for index, node in enumerate(container.items)]
            for container in self.containers()
        }
        self._origin_page_order = [page.uid for page in self.pages]
        # 없어진 묶음은 어디에서도 찾을 수 없다. 변경 목록에서 이름을 대려면
        # 원본에 있던 묶음의 이름을 지금 적어 둬야 한다.
        self._origin_folders = {
            node.uid: node.label
            for container in self.containers()
            for node in container.items
            if node.is_folder
        }

    # ------------------------------------------------------------- 만들기

    @property
    def readonly_reason(self) -> Optional[str]:
        """An origin-based restriction, unaffected by a caller changing its nodes."""
        return tr(self._readonly_key) if self._readonly_key else None

    def _ensure_editable(self) -> None:
        if self.readonly_reason:
            raise LayoutError(self.readonly_reason)

    @classmethod
    def from_state(
        cls, state: list[Any], metrics: Optional[dict[str, Any]] = None
    ) -> "LayoutDocument":
        return cls(state, Grid.from_metrics(metrics))

    def _next_uid(self, prefix: str) -> str:
        self._uid_counter += 1
        return f"{prefix}{self._uid_counter}"

    def _build(self, state: list[Any]) -> None:
        """원본 중첩 리스트를 노드/컨테이너 트리로 편다.

        `state[0]` 이 독, 나머지가 홈화면 페이지라는 관측을 따른다. 리스트가 아닌 원소가
        섞여 있으면 (본 적은 없지만) 빈 컨테이너로 두어 내보낼 때 원형이 유지되게 한다.
        """
        for index, entries in enumerate(state):
            rows = entries if isinstance(entries, list) else []
            if index == 0:
                self.dock.items = [self._make_node(raw) for raw in rows]
                continue
            page = Container(
                uid=self._next_uid("page"),
                kind="page",
                items=[self._make_node(raw) for raw in rows],
                capacity=self.grid.page_capacity,
            )
            self.pages.append(page)

    def _make_node(self, raw: Any) -> Node:
        item = parse_item(raw)
        name = item.display_name or (raw.get(KEY_DISPLAY_NAME) if isinstance(raw, dict) else None)
        node = Node(
            raw=raw,
            kind=item.kind,
            uid=self._next_uid("n"),
            identifier=item.bundle_id
            or (raw.get(KEY_DISPLAY_ID) if isinstance(raw, dict) else None),
            display_name=_display(name),
        )
        if item.kind is ItemKind.FOLDER and isinstance(raw, dict):
            for entries in raw.get(KEY_ICON_LISTS, []):
                node.pages.append(
                    Container(
                        uid=self._next_uid("f"),
                        kind="folder",
                        items=[
                            self._make_node(child)
                            for child in (entries if isinstance(entries, list) else [])
                        ],
                        capacity=self.grid.folder_page_capacity,
                        owner=node,
                    )
                )
        return node

    # ------------------------------------------------------------- 찾기

    def containers(self) -> Iterator[Container]:
        yield self.dock
        for page in self.pages:
            yield page
            for node in page.items:
                yield from node.pages
        for node in self.dock.items:
            yield from node.pages

    def container(self, uid: str) -> Container:
        for container in self.containers():
            if container.uid == uid:
                return container
        raise LayoutError(tr("자리를 찾을 수 없습니다 ({uid}).").format(uid=uid))

    def node(self, uid: str) -> Node:
        for container in self.containers():
            for item in container.items:
                if item.uid == uid:
                    return item
        raise LayoutError(tr("항목을 찾을 수 없습니다 ({uid}).").format(uid=uid))

    def locate(self, node_uid: str) -> tuple[Container, int]:
        for container in self.containers():
            for index, item in enumerate(container.items):
                if item.uid == node_uid:
                    return container, index
        raise LayoutError(tr("항목을 찾을 수 없습니다."))

    # ------------------------------------------------------------- 편집

    def can_move(
        self, node_uid: str, dst_uid: str, dst_index: Optional[int] = None
    ) -> Optional[str]:
        """옮길 수 없으면 그 이유를 사용자 언어로 돌려준다. 옮길 수 있으면 None.

        UI 는 드래그 도중에 이것을 물어 커서 모양과 안내 문구를 정한다. 규칙을 UI 와
        모델 양쪽에 적으면 반드시 어긋나므로, 판단은 여기 한 곳에만 둔다.
        """
        if self.readonly_reason:
            return self.readonly_reason
        node = self.node(node_uid)
        source, _ = self.locate(node_uid)
        destination = self.container(dst_uid)

        if not node.movable:
            return tr("이 항목은 우리가 해석하지 못한 것이라, 안전을 위해 옮기지 않습니다.")
        if node.is_folder and not destination.accepts_folder:
            return tr("폴더 안에 폴더를 넣을 수 없습니다.")
        if destination.owner is node:
            return tr("폴더를 자기 자신 안에 넣을 수 없습니다.")
        if destination is not source and destination.full:
            # 같은 묶음 안에서 페이지를 옮기는 것은 개수를 늘리지 않는다. 꽉 찬
            # 묶음이라도 1페이지와 2페이지 사이에서 자리를 바꿀 수 있어야 한다.
            if destination.kind == "folder" and source.owner is destination.owner:
                return None
            # 묶음은 iPhone 에서처럼 페이지를 더 편다. 페이지 하나가 찼다는 것은
            # 묶음이 찼다는 뜻이 아니다.
            if destination.kind == "folder" and self._folder_room(destination) is not None:
                return None
            # 홈 페이지도 **자리를 겨누면** 밀어낸다. 묶음에서 하던 것과 같다 —
            # 뒤가 한 칸씩 밀리고 넘친 마지막 항목이 다음 페이지 맨 앞으로 간다.
            # 겨눈 자리가 없으면(끝에 붙이기) 밀 이유가 없으므로 그대로 거절한다.
            # `dst_index` 를 모르고 물으면(None) 보수적으로 거절한다 — 화면이
            # 자리를 정하기 전의 물음에 '된다'고 답하면 안 되는 것이 되어 있다.
            if (
                destination.kind == "page"
                and dst_index is not None
                and dst_index < len(destination.items)
                and self._spill_room(destination)
            ):
                return None
            # 조각을 이어 붙이지 않고 문장마다 통째로 둔다. "독이" + "가득 찼습니다"
            # 식으로 나누면 조사가 붙은 조각이 열쇠가 되어 다른 말로 옮길 수 없다.
            if destination.kind == "folder":
                limit = self.grid.folder_page_capacity * self.grid.folder_max_pages
                return tr("이 묶음이 가득 찼습니다 (최대 {n}개).").format(n=limit)
            if destination.kind == "dock":
                return tr("독이 가득 찼습니다 (최대 {n}칸).").format(n=destination.capacity)
            return tr("이 페이지가 가득 찼습니다 (최대 {n}칸).").format(n=destination.capacity)
        return None

    def _page_family(
        self, page: "Container"
    ) -> Optional[tuple[Optional["Node"], list["Container"], int, int, str]]:
        """이 페이지가 속한 무리와 그 무리의 규칙.

        (묶음 노드 또는 None=홈화면, 페이지 목록, 한 장의 칸 수, 최대 장수, uid 앞글자).
        독은 무리가 아니다 — 페이지가 한 장뿐이라 밀어낼 곳이 없다.
        """
        if page.kind == "folder":
            folder = page.owner
            if folder is None:
                return None
            return (
                folder,
                folder.pages,
                self.grid.folder_page_capacity,
                self.grid.folder_max_pages,
                "f",
            )
        if page.kind == "page":
            return (None, self.pages, self.grid.page_capacity, self.grid.max_pages, "p")
        return None

    def _spill_room(self, page: "Container") -> bool:
        """이 페이지에서 넘친 것을 받아 줄 자리가 뒤에 있는가.

        판정만 한다 — 계획을 세우지 않는 이유는 드래그가 움직이는 내내 이 물음이
        오기 때문이다. 여기서 새 페이지를 지어내면 쓰지도 않을 uid 가 쌓인다.
        """
        family = self._page_family(page)
        if family is None:
            return False
        _holder, pages, _capacity, max_pages, _prefix = family
        index = next((i for i, other in enumerate(pages) if other is page), None)
        if index is None:
            return False
        if any(not other.full for other in pages[index + 1 :]):
            return True
        return len(pages) < max_pages  # 뒤가 다 찼으면 한 장 더 편다

    def _folder_room(self, page: "Container") -> Optional["Container"]:
        """이 묶음 페이지가 찼을 때 대신 받을 자리. 없으면 None.

        이미 있는 빈자리가 먼저다. 없으면 새 페이지를 하나 만들어 돌려준다 —
        아직 묶음에 붙이지는 않는다. 붙이는 일은 명령이 해야 되돌릴 수 있다.
        """
        folder = page.owner
        if folder is None:
            return None
        for other in folder.pages:
            if not other.full:
                return other
        if len(folder.pages) >= self.grid.folder_max_pages:
            return None
        return Container(
            uid=self._next_uid("f"),
            kind="folder",
            items=[],
            capacity=self.grid.folder_page_capacity,
            owner=folder,
        )

    def _plan_spill(
        self, node: "Node", source: "Container", page: "Container", index: int
    ) -> Optional[tuple[Optional["Node"], list["Container"], list[list["Node"]]]]:
        """`page` 의 `index` 자리에 끼우고 넘치는 것을 뒤 페이지로 민 결과.

        돌려주는 것은 (무리, 페이지 목록, 페이지별 내용)이며 **아직 반영하지
        않는다** — 반영은 명령이 해야 되돌릴 수 있다. 밀어낼 자리가 없으면 None.

        홈화면과 묶음을 가리지 않는다. 칸 수와 최대 장수만 무리에서 가져오고,
        미는 방식은 하나다 — 두 벌로 적으면 언젠가 한쪽만 고치게 된다.
        """
        family = self._page_family(page)
        if family is None:
            return None
        folder, pages_now, capacity, max_pages, prefix = family
        pages = list(pages_now)
        items = {p.uid: list(p.items) for p in pages}

        # 같은 무리 안에서 온 것은 먼저 빼야 한다. 빼지 않고 끼우면 그 잠깐 동안
        # 항목이 두 곳에 있는 셈이 되어, 밀려나는 개수가 하나씩 어긋난다.
        if source.uid in items:
            items[source.uid].remove(node)
        target = pages.index(page)
        room = items[page.uid]
        room.insert(max(0, min(index, len(room))), node)

        cursor = target
        while len(items[pages[cursor].uid]) > pages[cursor].capacity:
            overflow = items[pages[cursor].uid].pop()
            if cursor + 1 >= len(pages):
                if len(pages) >= max_pages:
                    return None  # 더 펼 수 없다 — 밀어낼 곳이 없다
                pages.append(
                    Container(
                        uid=self._next_uid(prefix),
                        kind=page.kind,
                        items=[],
                        capacity=capacity,
                        owner=folder,
                    )
                )
                items[pages[-1].uid] = []
            cursor += 1
            # 밀려난 것은 다음 페이지의 **맨 앞**이다. iPhone 에서 보는 순서가 그렇다.
            items[pages[cursor].uid].insert(0, overflow)

        # 텅 빈 페이지는 남기지 않는다. 마지막 하나가 페이지를 건너 옮겨 가면 그
        # 페이지가 통째로 비는데, 그것을 그대로 기기에 보내면 iOS 가 지우면서
        # 뒤가 밀린다 — 빈 묶음 때와 같은 일이다.
        kept = [p for p in pages if items[p.uid]] or pages[:1]
        return folder, kept, [items[p.uid] for p in kept]

    def move(self, node_uid: str, dst_uid: str, dst_index: int) -> None:
        """항목을 옮긴다. 실패하면 아무것도 바꾸지 않고 LayoutError 를 던진다."""
        reason = self.can_move(node_uid, dst_uid, dst_index)
        if reason:
            raise LayoutError(reason)

        node = self.node(node_uid)
        source, src_index = self.locate(node_uid)
        destination = self.container(dst_uid)

        # 마지막 하나를 꺼내면 빈 묶음만 남는다. iPhone 도, 기기에 쓸 때의 iOS 도
        # 그것을 지운다 — 우리가 먼저 지워야 보낸 것과 되읽은 것이 어긋나지 않는다.
        # (목적지를 어느 페이지로 바꾸든 묶음은 그대로이므로 여기서 먼저 정한다.)
        emptied = None
        owner = source.owner
        if owner is not None and owner.child_count() == 1 and destination.owner is not owner:
            holder, holder_index = self.locate(owner.uid)
            emptied = (holder.uid, holder_index, owner)

        # 다 빈 페이지는 홈화면이든 묶음 안이든 남기지 않는다. 빈 채로 실어 보내면
        # iOS 가 지우면서 뒤가 한 칸씩 밀리고, 우리 검증기는 그것을 손실·오이동으로
        # 읽는다. 묶음이 통째로 없어지는 경우(emptied)는 페이지째 함께 사라진다.
        pruned_src: list[Pruned] = []
        if emptied is None and destination is not source and len(source.items) == 1:
            if source.kind == "folder" and owner is not None:
                page_index = next(i for i, page in enumerate(owner.pages) if page is source)
                pruned_src.append((owner, page_index, source))
            elif source.kind == "page":
                page_index = next(i for i, page in enumerate(self.pages) if page is source)
                pruned_src.append((None, page_index, source))

        # 묶음이 통째로 없어지면 그 묶음만 놓여 있던 홈 페이지도 함께 빈다.
        pruned_emptied: list[Pruned] = []
        if emptied is not None:
            holder = self.container(emptied[0])
            if holder.kind == "page" and len(holder.items) == 1 and destination is not holder:
                index = next(i for i, page in enumerate(self.pages) if page is holder)
                pruned_emptied.append((None, index, holder))

        # 꽉 찬 페이지의 **자리를 겨눠** 놓았으면 iPhone 처럼 밀어낸다. 홈화면도
        # 묶음 안도 같다. 끝에 붙이려는 것(자리 없이 뒤를 겨눔)은 밀 이유가 없으므로
        # 밀지 않는다 — 밀어내면 겨누지도 않은 항목이 페이지를 넘는다.
        if (
            destination is not source
            and destination.kind in ("folder", "page")
            and destination.full
            and dst_index < len(destination.items)
        ):
            plan = self._plan_spill(node, source, destination, dst_index)
            if plan is None:
                raise LayoutError(
                    tr("이 묶음이 가득 차서 밀어낼 자리가 없습니다.")
                    if destination.kind == "folder"
                    else tr("홈화면이 가득 차서 밀어낼 자리가 없습니다.")
                )
            holder_node, pages_after, items_after = plan
            family_pages = _pages_of(self, holder_node)
            # 무리 밖에서 왔으면 명령이 출발 자리에서 빼야 한다. 무리 안에서 왔으면
            # 계획이 이미 뺀 뒤이고, 빈 페이지도 계획이 이미 치웠다.
            outside = all(page is not source for page in family_pages)
            self._run(
                SpillCommand(
                    label=tr("{name} 이동").format(name=node.label),
                    holder=holder_node,
                    pages_before=list(family_pages),
                    items_before=[list(page.items) for page in family_pages],
                    pages_after=pages_after,
                    items_after=items_after,
                    src_uid=source.uid if outside else None,
                    src_index=src_index if outside else 0,
                    src_node=node if outside else None,
                    emptied=emptied,
                    pruned=(pruned_src if outside else []) + pruned_emptied,
                )
            )
            return

        # 묶음 페이지가 찼으면 옆 페이지로, 그것도 없으면 새 페이지를 펴서 받는다.
        # can_move 가 이미 '받을 수 있다'고 답한 뒤이므로 자리는 반드시 있다.
        grew = None
        if destination is not source and destination.full and destination.kind == "folder":
            spill = self._folder_room(destination)
            if spill is not None:
                if spill not in destination.owner.pages:
                    grew = (destination.owner, spill)
                destination = spill
                dst_index = len(destination.items)

        # 같은 자리로의 드래그는 명령으로 남기지 않는다. 취소 이력이 '아무 일도 없었던
        # 취소'로 채워지면 실행 취소가 쓸모없어진다.
        bounded = max(0, min(dst_index, len(destination.items)))
        if destination is source and bounded in (src_index, src_index + 1):
            return
        if destination is source and bounded > src_index:
            bounded -= 1  # 꺼낸 자리만큼 앞으로 당겨진다

        self._run(
            MoveCommand(
                label=tr("{name} 이동").format(name=node.label),
                src_uid=source.uid,
                src_index=src_index,
                dst_uid=destination.uid,
                dst_index=bounded,
                grew=grew,
                emptied=emptied,
                pruned=pruned_src + pruned_emptied,
            )
        )

    # ------------------------------------------------------------- 묶기

    def _positions(self) -> dict[str, tuple[int, int, str]]:
        """모든 항목의 (자리 순서, 그 자리에서의 번째, 자리 uid).

        '자리 순서'는 `containers()` 가 도는 순서다. 사용자가 고른 순서가 아니라
        **화면에 보이는 순서**로 묶어야, 묶고 나서 폴더를 열었을 때 왜 이 순서인지
        설명할 필요가 없다.
        """
        return {
            node.uid: (order, index, container.uid)
            for order, container in enumerate(self.containers())
            for index, node in enumerate(container.items)
        }

    def can_group(self, node_uids: "Sequence[str]") -> Optional[str]:
        """묶을 수 없으면 그 이유를 사용자 언어로. 묶을 수 있으면 None."""
        if self.readonly_reason:
            return self.readonly_reason
        unique = list(dict.fromkeys(node_uids))
        if len(unique) < 2:
            return tr("묶으려면 항목을 두 개 이상 골라야 합니다.")

        limit = self.grid.folder_page_capacity * self.grid.folder_max_pages
        if len(unique) > limit:
            return tr("묶음 하나에는 최대 {limit}개까지 들어갑니다 ({picked}개를 고르셨습니다).").format(
                limit=limit, picked=len(unique)
            )

        try:
            for uid in unique:
                node = self.node(uid)
                container, _ = self.locate(uid)
                if not node.movable:
                    return tr(
                        "“{name}”은(는) 우리가 해석하지 못한 항목이라,"
                        " 안전을 위해 묶지 않습니다."
                    ).format(name=node.label)
                if node.is_folder:
                    # iOS 는 폴더 안의 폴더를 지원하지 않는다. 묶음끼리 합치려면
                    # 안의 앱을 옮기는 것이지 묶음을 넣는 것이 아니다.
                    return tr(
                        "“{name}”은(는) 이미 묶음입니다. 묶음끼리는 묶을 수 없습니다."
                    ).format(name=node.label)
                if container.kind == "folder":
                    return tr(
                        "“{name}”은(는) 이미 묶음 안에 있습니다."
                        " 먼저 묶음 밖으로 꺼내 주세요."
                    ).format(name=node.label)
        except LayoutError as exc:
            return str(exc)
        return None

    def suggest_group_name(self, node_uids: "Sequence[str]") -> str:
        """새 묶음의 기본 이름.

        iOS 는 앱 분류를 알기 때문에 '생산성' 같은 이름을 스스로 붙인다. 우리는 그
        분류를 모른다. 아는 척해서 엉뚱한 이름을 붙이느니 **첫 앱의 이름**을 내놓고
        사용자가 고치게 한다 — 무엇을 묶었는지가 이름에 그대로 보인다.
        """
        try:
            ordered = self._ordered(node_uids)
        except LayoutError:
            return tr("새 묶음")
        return self.node(ordered[0]).label if ordered else tr("새 묶음")

    def _ordered(self, node_uids: "Sequence[str]") -> list[str]:
        positions = self._positions()
        unique = list(dict.fromkeys(node_uids))
        for uid in unique:
            if uid not in positions:
                raise LayoutError(tr("항목을 찾을 수 없습니다."))
        return sorted(unique, key=lambda uid: positions[uid][:2])

    def group(self, node_uids: "Sequence[str]", name: str) -> str:
        """고른 항목들을 새 묶음으로 만든다. 새 폴더 노드의 uid 를 돌려준다.

        묶음은 **첫 항목이 있던 자리**에 놓인다. 사용자가 마지막에 고른 자리도,
        아무 빈 칸도 아니다 — 눈으로 좇을 수 있는 자리는 그것뿐이다.
        """
        reason = self.can_group(node_uids)
        if reason:
            raise LayoutError(reason)

        ordered = self._ordered(node_uids)
        positions = self._positions()
        members = [(positions[uid][2], positions[uid][1], uid) for uid in ordered]

        label = _display(name.strip()) or tr("새 묶음")
        raw: dict[str, Any] = {
            KEY_DISPLAY_NAME: label,
            KEY_LIST_TYPE: LIST_TYPE_FOLDER,
            KEY_ICON_LISTS: [],
        }
        folder = Node(
            raw=raw,
            kind=ItemKind.FOLDER,
            uid=self._next_uid("n"),
            display_name=label,
        )
        per = self.grid.folder_page_capacity
        for _ in range(0, len(ordered), per):
            folder.pages.append(
                Container(
                    uid=self._next_uid("f"),
                    kind="folder",
                    items=[],
                    capacity=per,
                    owner=folder,
                )
            )

        dst_uid = members[0][0]
        anchor_index = members[0][1]
        # 앞에 있던 것들을 먼저 빼내므로 자리가 당겨진다. 첫 항목보다 앞에 있는
        # 선택 항목은 없지만(정렬해서 골랐다), 규칙을 식에 남겨 둔다.
        shift = sum(1 for c, i, _ in members if c == dst_uid and i < anchor_index)
        self._run(
            GroupCommand(
                label=tr("묶음 “{name}” 만들기 ({n}개)").format(name=label, n=len(ordered)),
                folder=folder,
                members=members,
                dst_uid=dst_uid,
                dst_index=anchor_index - shift,
            )
        )
        return folder.uid

    def can_rename(self, node_uid: str, name: str) -> Optional[str]:
        if self.readonly_reason:
            return self.readonly_reason
        try:
            node = self.node(node_uid)
        except LayoutError as exc:
            return str(exc)
        if not node.is_folder:
            return tr("묶음의 이름만 바꿀 수 있습니다.")
        cleaned = name.strip()
        if not cleaned:
            return tr("이름을 비워 둘 수 없습니다.")
        if len(cleaned) > 64:
            return tr("이름이 너무 깁니다 (64자까지).")
        return None

    def rename_folder(self, node_uid: str, name: str) -> None:
        reason = self.can_rename(node_uid, name)
        if reason:
            raise LayoutError(reason)
        node = self.node(node_uid)
        cleaned = _display(name.strip()) or name.strip()
        if cleaned == node.label:
            return  # 같은 이름은 편집이 아니다. 취소 이력을 늘리지 않는다.
        self._run(
            RenameFolderCommand(
                label=tr("묶음 이름 “{before}” → “{after}”").format(before=node.label, after=cleaned),
                node_uid=node_uid,
                before=node.renamed_to,
                after=cleaned,
            )
        )

    def original_name(self, node_uid: str) -> Optional[str]:
        """이름을 바꾸기 전의 이름. 변경 목록에서 무엇이 무엇으로 바뀌었는지 쓰려고."""
        node = self.node(node_uid)
        return node.display_name

    def reorder_pages(self, from_index: int, to_index: int) -> None:
        self._ensure_editable()
        if not (0 <= from_index < len(self.pages)) or not (0 <= to_index < len(self.pages)):
            raise LayoutError(tr("페이지 번호가 범위를 벗어났습니다."))
        if from_index == to_index:
            return
        self._run(
            ReorderPagesCommand(
                label=tr("{n}페이지를 {to}번째로 이동").format(n=from_index + 1, to=to_index + 1),
                from_index=from_index,
                to_index=to_index,
            )
        )

    def add_page(self) -> None:
        self._ensure_editable()
        if len(self.pages) >= self.grid.max_pages:
            raise LayoutError(
                tr("페이지는 최대 {n}개까지입니다.").format(n=self.grid.max_pages)
            )
        container = Container(
            uid=self._next_uid("page"),
            kind="page",
            items=[],
            capacity=self.grid.page_capacity,
        )
        self._run(
            AddPageCommand(
                label=tr("{n}페이지 추가").format(n=len(self.pages) + 1),
                index=len(self.pages),
                container=container,
            )
        )

    def remove_page(self, index: int) -> None:
        self._ensure_editable()
        if not (0 <= index < len(self.pages)):
            raise LayoutError(tr("페이지 번호가 범위를 벗어났습니다."))
        if self.pages[index].items:
            raise LayoutError(tr("비어 있는 페이지만 지울 수 있습니다. 먼저 항목을 옮겨 주세요."))
        if len(self.pages) <= 1:
            raise LayoutError(tr("페이지를 모두 지울 수는 없습니다."))
        self._run(
            RemovePageCommand(
                label=tr("{n}페이지 삭제").format(n=index + 1),
                index=index,
                container=self.pages[index],
            )
        )

    # ------------------------------------------------------------- 취소/재실행

    def _run(self, command: Command) -> None:
        self._ensure_editable()
        command.apply(self)
        self._undo.append(command)
        self._redo.clear()  # 새 편집을 하면 되돌렸던 미래는 사라진다

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo_label(self) -> Optional[str]:
        return self._undo[-1].label if self._undo else None

    def redo_label(self) -> Optional[str]:
        return self._redo[-1].label if self._redo else None

    def undo(self) -> None:
        self._ensure_editable()
        if not self._undo:
            return
        command = self._undo.pop()
        command.revert(self)
        self._redo.append(command)

    def redo(self) -> None:
        self._ensure_editable()
        if not self._redo:
            return
        command = self._redo.pop()
        command.apply(self)
        self._undo.append(command)

    # ------------------------------------------------------------- 내보내기

    def to_state(self) -> list[Any]:
        if self.readonly_reason:
            # A preview is a view over the original, never a reconstructed payload.
            return copy.deepcopy(self.origin)
        return [[node.to_raw() for node in self.dock.items]] + [
            [node.to_raw() for node in page.items] for page in self.pages
        ]

    def verify_identity(self) -> bool:
        """편집이 없을 때 내보낸 결과가 원본과 완전히 같은지 확인한다.

        이 성질이 깨졌다면 우리 문서 모델 자체가 무언가를 잃고 있다는 뜻이고, 그 상태로
        기기에 쓰면 사용자의 홈화면에서 그것이 사라진다. 적용 직전에 한 번 더 확인한다.
        """
        probe = LayoutDocument(self.origin, self.grid)
        return probe.to_state() == self.origin

    # ------------------------------------------------------------- 변경 요약

    def _snapshot(self) -> dict[str, tuple[str, int]]:
        """모든 노드의 '어느 자리에 몇 번째'를 담는다. 자리는 컨테이너 uid 로 기록한다.

        페이지 번호가 아니라 컨테이너 uid 를 쓰는 이유는, 페이지 순서를 바꿔도 그 안의
        항목이 '옮겨졌다'고 보고되지 않게 하기 위해서다. 페이지가 움직인 것이지 앱이
        움직인 것이 아니다.
        """
        return {
            node.uid: (container.uid, index)
            for container in self.containers()
            for index, node in enumerate(container.items)
        }

    def container_label(self, uid: str, *, at_origin: bool = False) -> str:
        """자리를 사용자가 iPhone 에서 찾아갈 수 있는 말로 옮긴다."""
        if uid == "dock":
            return tr("독")
        order = self._origin_page_order if at_origin else [page.uid for page in self.pages]
        if uid in order:
            return tr("{n}페이지").format(n=order.index(uid) + 1)
        for container in self.containers():
            if container.uid == uid and container.owner is not None:
                page_index = container.owner.pages.index(container)
                return tr("폴더 “{name}” {n}페이지").format(
                    name=container.owner.label, n=page_index + 1
                )
        return tr("(사라진 페이지)")

    def describe_position(self, place: tuple[str, int], *, at_origin: bool = False) -> str:
        uid, index = place
        return tr("{where} {n}번째").format(
            where=self.container_label(uid, at_origin=at_origin), n=index + 1
        )

    @property
    def dirty(self) -> bool:
        """기기에 반영되지 않은 변경이 있는가 (REQ-016).

        편집 횟수가 아니라 **결과**로 판단한다. 옮겼다가 제자리로 되돌려 놓았다면 아무
        변경도 없는 것이고, 그때 '미적용 변경 있음'이라고 경고하면 사용자는 자기가 무엇을
        놓쳤는지 찾느라 헤매게 된다.
        """
        return bool(self.changes())

    def changes(self) -> list[str]:
        """적용 전에 보여줄 변경 목록 (REQ-015 · REQ-016).

        여기서 가장 중요한 것은 **말하지 않는 것**이다. 아이콘 하나를 앞으로 당기면 뒤의
        스물세 개가 한 칸씩 밀린다. 그것을 전부 '이동'이라 부르면 목록이 화면을 뒤덮고,
        정작 사용자가 한 일이 그 안에 묻힌다. 그래서 밀려난 것은 변경이 아니라 결과로
        본다 — 같은 자리에 남았고 서로의 순서도 그대로라면, 그것은 움직인 것이 아니다.

        판단 기준은 두 가지뿐이다.
          1. 다른 자리로 갔는가
          2. 같은 자리에 남았지만 이웃과의 앞뒤가 바뀌었는가
        """
        notes: list[str] = []
        current = self._snapshot()
        nodes = {node.uid: node for c in self.containers() for node in c.items}
        order = [page.uid for page in self.pages]

        # 페이지 자체의 이동은 항목 이동으로 보이면 읽을 수 없다. 먼저, 따로 말한다.
        if order != self._origin_page_order:
            before = {uid: index for index, uid in enumerate(self._origin_page_order)}
            moved = [
                tr("{n}페이지 → {to}번째").format(n=before[uid] + 1, to=index + 1)
                for index, uid in enumerate(order)
                if uid in before and before[uid] != index
            ]
            if moved:
                notes.append(tr("페이지 순서: {list}").format(list=", ".join(moved)))
            for index, uid in enumerate(order):
                if uid not in before:
                    notes.append(tr("{n}페이지 추가").format(n=index + 1))
            for uid, index in before.items():
                if uid not in order:
                    notes.append(tr("{n}페이지 삭제").format(n=index + 1))

        # 새로 만든 묶음. 그 안에 든 앱은 아래에서 하나씩 '이동'으로 세지 않는다 —
        # 열 개를 묶었으면 열 줄이 아니라 한 줄이라야 사용자가 자기가 한 일을 알아본다.
        new_folders = [
            node
            for node in nodes.values()
            if node.is_folder and node.uid not in self._origin_snapshot
        ]
        inside_new = {page.uid for folder in new_folders for page in folder.pages}
        for folder in new_folders:
            members = [child.label for page in folder.pages for child in page.items]
            shown = ", ".join(members[:4])
            if len(members) > 4:
                shown += tr(" 외 {n}개").format(n=len(members) - 4)
            notes.append(
                tr("새 묶음 “{name}” 만듦 ({n}개: {members})").format(
                    name=folder.label, n=len(members), members=shown
                )
            )

        # 비어서 없어진 묶음. 이것을 말하지 않으면, 뒤따라 한 칸씩 밀린 항목들만
        # 잔뜩 보이고 정작 그 원인이 목록에 없다.
        for uid, name in self._origin_folders.items():
            if uid not in nodes:
                where = self.describe_position(self._origin_snapshot[uid], at_origin=True)
                notes.append(tr("빈 묶음 “{name}” 없어짐 ({where})").format(name=name, where=where))

        # 이름을 바꾼 묶음. 아무것도 움직이지 않으므로 여기서 말하지 않으면
        # `dirty` 가 거짓이 되고, 적용 단추가 계속 잠겨 있게 된다.
        for node in nodes.values():
            if node.renamed_to is None or node.uid not in self._origin_snapshot:
                continue
            notes.append(
                tr("묶음 이름: “{before}” → “{after}”").format(
                    before=node.display_name or "", after=node.renamed_to
                )
            )

        # 1. 자리를 옮긴 항목
        relocated: set[str] = set()
        for uid, (container_uid, index) in current.items():
            origin = self._origin_snapshot.get(uid)
            if origin is None or origin[0] == container_uid:
                continue
            relocated.add(uid)
            if container_uid in inside_new:
                continue  # 새 묶음 줄에서 이미 말했다
            notes.append(
                f"{nodes[uid].label}: {self.describe_position(origin, at_origin=True)}"
                f" → {self.describe_position((container_uid, index))}"
            )

        # 2. 같은 자리에 남았지만 이웃과의 앞뒤가 바뀐 항목
        for container in self.containers():
            stayed = [
                node.uid
                for node in container.items
                if self._origin_snapshot.get(node.uid, (None,))[0] == container.uid
            ]
            was = [uid for uid, _ in self._origin_order.get(container.uid, []) if uid in set(stayed)]
            for uid in _reordered(was, stayed):
                origin = self._origin_snapshot[uid]
                notes.append(
                    tr("{name}: {where} 안에서 {before}번째 → {after}번째").format(
                        name=nodes[uid].label,
                        where=self.container_label(container.uid),
                        before=origin[1] + 1,
                        after=current[uid][1] + 1,
                    )
                )

        return notes

    def placed_identifiers(self) -> set[str]:
        """홈화면 어딘가에 놓여 있는 항목의 식별자 전부 (폴더 안까지).

        번들 ID 와 표시 식별자를 **둘 다** 담는다. 오프로드된 앱에는 번들 ID 가 없고,
        설치 목록 쪽은 번들 ID 로만 말하기 때문이다. 한쪽만 보면 이미 홈화면에 있는
        앱을 '없다'고 판정해, 사용자에게 거짓 경고를 하게 된다.
        """
        found: set[str] = set()
        for container in self.containers():
            for node in container.items:
                if node.kind is not ItemKind.APP:
                    continue
                if node.identifier:
                    found.add(str(node.identifier))
                if isinstance(node.raw, dict):
                    bundle_id = node.raw.get(KEY_BUNDLE_ID)
                    if bundle_id:
                        found.add(str(bundle_id))
        return found

    def unplaced_apps(self, installed: dict[str, str]) -> list[tuple[str, str]]:
        """설치돼 있지만 홈화면에는 없는 앱 — 쓰기를 하면 iOS 가 끝에 되붙일 것들.

        이름순으로 돌려준다. 사용자가 이 목록에서 찾는 것은 특정 앱이지 개수가 아니다.
        """
        placed = self.placed_identifiers()
        return sorted(
            ((bundle_id, name) for bundle_id, name in installed.items() if bundle_id not in placed),
            key=lambda pair: pair[1].lower(),
        )

    def empty_pages(self) -> list[int]:
        """비어 있는 페이지 번호(1부터). iOS 가 빈 페이지를 어떻게 다루는지는 미검증이다."""
        return [index for index, page in enumerate(self.pages, start=1) if not page.items]

    def summary(self) -> str:
        apps = folders = unknown = widgets = members = 0
        for container in self.containers():
            for node in container.items:
                if node.is_folder:
                    folders += 1
                elif node.kind is ItemKind.APP:
                    apps += 1
                elif node.is_widget:
                    widgets += 1
                    members += node.widget_member_count
                elif node.kind is ItemKind.UNKNOWN:
                    unknown += 1
        parts = [
            tr("페이지 {n}개").format(n=len(self.pages)),
            tr("앱 {n}개").format(n=apps),
            tr("폴더 {n}개").format(n=folders),
        ]
        if widgets:
            parts.append(tr("Widgets: {blocks} positions, {members} including stack members").format(
                blocks=widgets, members=members
            ))
        if unknown:
            parts.append(tr("알 수 없는 항목 {n}개").format(n=unknown))
        return " · ".join(parts)


def _reordered(before: list[str], after: list[str]) -> list[str]:
    """두 순서를 견주어, 순서를 실제로 바꾼 최소 항목만 골라낸다.

    가장 긴 공통 부분수열(LCS)에 남는 것은 '가만히 있었는데 남이 비켜서 번호만 바뀐'
    항목이다. 거기서 빠진 것만이 사용자가 실제로 옮긴 것이다.
    """
    if before == after:
        return []
    rows = len(before)
    cols = len(after)
    table = [[0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(rows - 1, -1, -1):
        for j in range(cols - 1, -1, -1):
            table[i][j] = (
                table[i + 1][j + 1] + 1
                if before[i] == after[j]
                else max(table[i + 1][j], table[i][j + 1])
            )
    common: set[str] = set()
    i = j = 0
    while i < rows and j < cols:
        if before[i] == after[j]:
            common.add(before[i])
            i += 1
            j += 1
        elif table[i + 1][j] >= table[i][j + 1]:
            i += 1
        else:
            j += 1
    return [uid for uid in after if uid not in common]
