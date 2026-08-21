# 계약: layout-model

**소유자:** homescreen-model-analyst
**구현:** `src/ipsm/iconstate.py` (해석), `src/ipsm/layout.py` (편집 문서)
**상태:** 실기기 309개 항목으로 확인됨

홈화면 하나를 프로그램 안에서 무엇으로 볼 것인가. 다른 모든 계약이 이 위에 선다.

## 두 겹으로 나눈 이유

| 겹 | 파일 | 무엇을 아는가 |
|----|------|--------------|
| 해석 | `iconstate.py` | plist 를 읽어 종류를 붙인다. **편집하지 않는다** |
| 편집 | `layout.py` | 페이지·자리·이동·취소를 안다. plist 모양은 `raw` 로만 들고 있다 |

해석 층을 편집 층과 섞지 않는 이유는 **원본 보존** 때문이다. 편집 층의 `Node.raw` 는
기기에서 온 dict 그 자체이고, `to_raw()` 는 폴더가 아닌 한 그것을 손대지 않고 돌려준다.
우리가 이해한 필드만으로 항목을 다시 지어내면, 이해하지 못한 필드는 그 순간 사라진다.

## 정체성

**항목의 정체성 키는 `displayIdentifier` 다.** `bundleIdentifier` 가 아니다.

> 2026-08-19 정정. 실기기 첫 덤프에서 79개(26%)가 Unknown 으로 분류됐다. 오프로드된
> 앱에는 번들 ID 가 없고 `displayIdentifier` 만 있다. 번들 ID 로 정체성을 잡으면
> 오프로드된 앱은 전부 "알 수 없는 항목"이 되어 움직일 수 없게 된다.

`placed_identifiers()` 는 두 값을 **모두** 담는다. 설치 목록(`list_installed_apps`)은
번들 ID 로만 말하므로, 한쪽만 보면 "설치됐는데 홈화면에 없다"는 거짓 경고를 하게 된다.

## 종류 (ItemKind)

| 종류 | 판정 | 움직일 수 있는가 |
|------|------|-----------------|
| `APP` | `displayIdentifier` 가 있고 폴더가 아니다 | 예 |
| `FOLDER` | `listType == "folder"` | 예 (폴더 안으로는 못 들어간다) |
| `WEB_CLIP` | 식별자가 웹 클립 꼴 | 예 (아이콘 PNG 는 없다) |
| `UNKNOWN` | 위 어느 것도 아니다 (위젯 등) | **아니오** |

**모르는 것은 움직이지 않는다.** 위치를 바꾸려면 그 항목이 무엇인지 알아야 하는데,
모르는 것을 옮기다 잃으면 되돌릴 수 있어도 사용자는 이미 놀란 뒤다. 대신 자리는 그대로
지키고 `raw` 를 그대로 다시 쓴다.

## 자리 (Container)

```python
@dataclass
class Grid:
    columns, rows, dock_capacity, folder_columns, folder_rows, max_pages
    page_capacity() -> int
    folder_page_capacity() -> int
    from_metrics(metrics) -> Grid       # 기기가 준 값 우선, 없으면 iPhone 기본값
```

- `state[0]` 은 **독**, `state[1:]` 이 페이지다. 이 순서를 바꾸지 않는다.
- 폴더는 `iconLists` 안에 다시 페이지를 가진다. `containers()` 는 독 → 페이지 →
  폴더 페이지 순으로 전부 훑는다.

## 편집 문서 (LayoutDocument)

```python
LayoutDocument(origin: list, grid: Grid)
    .origin              # 되돌릴 기준. 절대 건드리지 않는다
    .can_move(node_uid, dst_uid, dst_index=None) -> str | None   # 못 옮기면 '이유'
    .move(node_uid, dst_uid, dst_index)
    .can_group(node_uids) -> str | None           # 못 묶으면 이유
    .group(node_uids, name) -> str                # 새 폴더 노드의 uid
    .suggest_group_name(node_uids) -> str         # 기본 이름 (첫 항목의 이름)
    .can_rename(node_uid, name) -> str | None
    .rename_folder(node_uid, name)
    .add_page() / .remove_page(i) / .reorder_pages(a, b)
    .undo() / .redo() / .can_undo / .can_redo
    .to_state() -> list          # 기기에 쓸 plist
    .verify_identity() -> bool   # 편집이 없으면 to_state() == origin 인가
    .changes() -> list[str]      # 사용자에게 보여줄 변경 목록
    .placed_identifiers() -> set[str]
    .unplaced_apps(installed) -> list[tuple[str, str]]
```

### 지키기로 한 것

- **`can_move` 가 유일한 판정자다.** 화면은 스스로 판단하지 않고 여기에 묻는다.
  두 곳에서 판단하면 "되는 것처럼 보였는데 안 되는" 화면이 생긴다.
- 거절 이유는 **사용자에게 그대로 보여줄 수 있는 한 문장**이어야 한다. 화면이 문구를
  다시 짓지 않는다.
- 변경 목록은 **원본 스냅숏과의 대조**로만 만든다. 명령 이력을 되짚어 계산하면
  취소·재실행이 섞였을 때 어긋난다.
- 페이지를 옮긴 것은 **한 줄**로 보고한다. 그 안의 앱까지 세면 목록이 수십 줄로 불어나
  사용자가 적용 전에 읽지 않게 된다.
- `verify_identity()` 가 거짓이면 **쓰기를 막는다.** 경고만 하고 버튼을 살려 두면,
  경고를 닫은 사용자에게는 아무 일도 없었던 것과 같다.
- 새 폴더의 raw 는 `displayName` · `listType` · `iconLists` **세 키만** 만든다. 기기의
  폴더 26개가 전부 이 모양이므로, 더 지어낼 것도 빠뜨릴 것도 없다.
- 이름 바꾸기는 `Node.renamed_to` 에만 적는다. `raw` 는 끝까지 원본이고, `to_raw()` 가
  내보낼 때 `displayName` 한 키만 갈아 끼운다 — 모르는 키는 그대로 실린다 (REQ-017).
- 묶기는 고른 **순서가 아니라 화면에 보이는 순서**로 담고, 새 묶음은 첫 항목이 있던
  자리에 놓는다. 눈으로 좇을 수 있는 자리는 그것뿐이다.
- 묶음 페이지가 찼다는 것은 묶음이 찼다는 뜻이 아니다. 빈자리가 있는 페이지가 먼저이고,
  없으면 `folder_max_pages` 까지 새 페이지를 편다. 판정은 `can_move` 한 곳에만 둔다 —
  UI 가 따로 세면 반드시 어긋난다.
- 꽉 찬 페이지의 **자리를 겨눈** 놓기(`dst_index < len(items)`)는 밀어내기다. 뒤가
  한 칸씩 밀리고 넘친 것이 다음 페이지 **맨 앞**으로 간다. 끝을 겨눈 놓기는 밀지 않는다.
  **홈화면과 묶음 안이 같은 규칙을 쓴다** — `_plan_spill` 한 벌이 둘 다 처리하고,
  다른 것은 `_page_family` 가 알려주는 칸 수·최대 장수뿐이다. 두 벌로 적으면 언젠가
  한쪽만 고치게 된다.
- `can_move` 는 **겨눈 자리까지 받는다.** `dst_index` 를 모르고 물으면(None) 꽉 찬
  페이지를 그대로 거절한다 — 자리를 정하기 전의 물음에 '된다'고 답하면, 화면이
  실제로 놓을 때 안 되는 것이 되어 있다. 화면은 `_resolve_target` 에서 계산한 자리를
  반드시 함께 넘긴다.
- 같은 묶음 안에서의 이동은 개수를 늘리지 않으므로 **가득 참으로 막지 않는다.** 막으면
  꽉 찬 묶음의 1·2페이지 사이에서 자리를 바꿀 수 없다.
- 페이지가 다 비면 **그 페이지를 지운다.** 홈화면도 묶음 안도 같다 (무리의 마지막
  한 장은 비어도 남긴다 — 페이지가 없는 홈화면·묶음은 없다). 묶음이 통째로 없어져
  그 묶음만 놓여 있던 홈 페이지가 비는 경우도 함께 치운다.
- 마지막 항목이 빠지면 **그 묶음을 우리가 지운다.** 빈 묶음을 보내면 iOS 가 지우고
  뒤따르던 항목이 전부 밀려, 검증기가 손실·오이동으로 읽는다 (2026-08-20 실기기 확인).
- 페이지가 펴지는 것도 묶음이 없어지는 것도 **같은 `MoveCommand` 안**에 담는다. 따로
  두면 취소를 두 번 눌러야 하고, 그 사이 상태는 사용자가 만든 적 없는 모양이다 (REQ-014).
- 이름만 바꾼 편집도 `changes()` 에 한 줄로 나온다. 아무것도 움직이지 않았다고 해서
  `dirty` 가 거짓이 되면 적용 단추가 잠긴 채로 남는다.

## 확인된 것

- 309개 항목 항등 왕복 통과 (REQ-003) — 손실·이동 0
- `tests/test_core.py` 71개 통과 (기기 없이) — 묶기·이름 바꾸기·페이지 증감·밀어내기 포함
- 홈 페이지 밀어내기와 빈 홈 페이지 치우기는 `[미검증]` (실기기 쓰기 필요)
