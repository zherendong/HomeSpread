"""Pure analysis of exported observations; no payload, device or file operations.

The compact format-3 projection is a hypothesis tested against each input, not a
decoder or a claim about physical screen coordinates. Outputs contain only fixed
labels, counts and booleans, never app names, identifiers or source dictionaries.
"""
from __future__ import annotations

from collections import Counter
import plistlib
from typing import Any

from ipsm.draft_rules import analyze_layout


def _binary(value: Any) -> bytes:
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY, sort_keys=True)


def _text(value: Any) -> bool:
    return type(value) is str and bool(value)


def _kind(item: Any) -> str:
    if item is False:
        return "false"
    if type(item) is not dict:
        return "other"
    if item.get("listType") == "folder":
        return "folder"
    if any(key in item for key in ("elements", "widgetIdentifier", "gridSize")):
        return "widget"
    if (any(key in item for key in ("listType", "iconLists", "elementType", "webClipURL",
                                    "webClipIdentifier", "isWebClip", "isWebApp"))
            or item.get("iconType") not in (None, "app", "application")):
        return "other"
    return "app" if any(_text(item.get(k)) for k in ("displayIdentifier", "bundleIdentifier")) else "other"


def _apps(raw: list) -> list[dict]:
    result = []
    for page in raw:
        for item in page:
            if _kind(item) == "folder":
                result.extend(_apps(item["iconLists"]))
            elif _kind(item) == "app":
                result.append(item)
    return result


def _format3(raw: list, reference: Any) -> dict:
    shaped = (type(reference) is list and bool(reference)
              and all(type(page) is list and all(type(row) is list for row in page)
                      for page in reference))
    result = {"present": reference is not None, "row_shape_recognized": shaped,
              "compact_projection_matches": False, "top_level_apps_exact_order": False,
              "geometry_verified": False, "false_means_empty": False}
    if not shaped:
        return result
    cells = [cell for page in reference for row in page for cell in row]
    kinds = Counter(_kind(cell) for cell in cells)
    expected, replaced, padding = [], 0, 0
    for page in raw:
        flat = [item if _kind(item) == "app" else False for item in page]
        replaced += sum(item is False for item in flat)
        pad = (-len(flat)) % 4
        padding += pad
        flat += [False] * pad
        expected.append([flat[i:i + 4] for i in range(0, len(flat), 4)])
    same_apps = len(raw) == len(reference) and all(
        _binary([x for x in page if _kind(x) == "app"]) ==
        _binary([x for row in rows for x in row if _kind(x) == "app"])
        for page, rows in zip(raw, reference))
    projection_matches = _binary(reference) == _binary(expected)
    result.update(
        container_count=len(reference), row_count=sum(map(len, reference)),
        cell_count=len(cells), cell_kinds={key: kinds[key] for key in ("app", "folder", "widget", "false", "other")},
        all_rows_four_cells=all(len(row) == 4 for page in reference for row in page),
        compact_projection_matches=projection_matches, top_level_apps_exact_order=same_apps,
        # These counts explain False only when the ENTIRE projection matches.
        explained_non_app_cells=replaced if projection_matches else None,
        explained_padding_cells=padding if projection_matches else None,
    )
    return result


def _inventory(entries: Any, visible: set[str], expected_type: str) -> dict:
    if entries is None:
        return {"status": "missing"}
    if type(entries) is not dict:
        raise ValueError("Invalid application inventory")
    for ident, item in entries.items():
        if type(ident) is not str or not ident or type(item) is not dict:
            raise ValueError("Invalid application inventory")
        if "CFBundleIdentifier" in item and item["CFBundleIdentifier"] != ident:
            raise ValueError("Conflicting application identifier")
        if "ApplicationType" in item and item["ApplicationType"] != expected_type:
            raise ValueError("Conflicting application type")
        if "IsDemotedApp" in item and type(item["IsDemotedApp"]) is not bool:
            raise ValueError("Invalid placeholder flag")
        if "SBAppTags" in item and (type(item["SBAppTags"]) is not list
                                    or any(type(tag) is not str for tag in item["SBAppTags"])):
            raise ValueError("Invalid application tags")
    matched = set(entries) & visible
    unmatched = set(entries) - visible
    hidden = {key for key, item in entries.items() if "hidden" in item.get("SBAppTags", [])}
    tags_absent = {key for key, item in entries.items() if "SBAppTags" not in item}
    demoted = {key for key, item in entries.items() if item.get("IsDemotedApp") is True}
    return {"status": "observed", "entries": len(entries),
            "matched_visible_alias": len(matched), "not_matched_visible_alias": len(unmatched),
            "hidden_tag_present": len(hidden), "tags_absent": len(tags_absent),
            "unmatched_hidden": len(unmatched & hidden),
            "unmatched_tags_absent": len(unmatched & tags_absent),
            "unmatched_explicit_tags_without_hidden": len(unmatched - hidden - tags_absent),
            "offloaded": len(demoted), "offloaded_matched": len(demoted & matched),
            "offloaded_unmatched": len(demoted & unmatched),
            "placeholder_flag_absent": sum("IsDemotedApp" not in item for item in entries.values())}


def _widgets(raw: list) -> list[dict]:
    result = []
    for page_index, page in enumerate(raw):
        for item_index, item in enumerate(page):
            if _kind(item) != "widget":
                continue
            members = item.get("elements")
            selected = item.get("userSelectedElementIdentifier")
            unique = item.get("uniqueIdentifier")
            stack = members is not None
            if stack:
                alias = "not_applicable_stack"
            elif not _text(selected):
                alias = "selected_identifier_missing"
            elif _text(unique):
                alias = "already_equal" if unique == selected else "conflicting_identifiers"
            elif "uniqueIdentifier" in item:
                alias = "invalid_unique_identifier"
            else:
                alias = "source_field_available_unverified"
            result.append({"page": page_index, "item": item_index,
                           "kind": "stack" if stack else "standalone", "size": item["gridSize"],
                           "members": len(members) if stack else 1,
                           "selected_identifier_present": _text(selected),
                           "unique_identifier_present": _text(unique),
                           "selected_member_matches": sum(m.get("uniqueIdentifier") == selected for m in members)
                           if stack and _text(selected) else 0,
                           "standalone_alias_assessment": alias,
                           "configuration_verified": False})
    return result


def analyze_observations(raw: Any, *, format3: Any = None,
                         apps_user: Any = None, apps_system: Any = None) -> dict:
    """Summarize validated format-2 observations without constructing a write.

    None means unobserved; an empty successful inventory is not complete. The
    supported input model is the same bounded 4x6 offline-draft model. Even exact
    reference matches never establish geometry, hidden-state or write safety.
    """
    layout = analyze_layout(raw)
    apps = _apps(raw)
    aliases = [{item[k] for k in ("displayIdentifier", "bundleIdentifier") if _text(item.get(k))}
               for item in apps]
    visible = set().union(*aliases) if aliases else set()
    user = _inventory(apps_user, visible, "User")
    system = _inventory(apps_system, visible, "System")
    complete_queries = apps_user is not None and apps_system is not None
    known = set(apps_user or {}) | set(apps_system or {})
    unmatched_occurrences = sum(not (names & known) for names in aliases)
    ambiguous_occurrences = sum(len(names & known) > 1 for names in aliases)
    overlap = len(set(apps_user or {}) & set(apps_system or {}))
    return {"format": "ipsm.offline-evidence-analysis", "schema_version": 1,
            "can_write": False, "device_requests": 0, "payload_generated": False,
            "counts": layout["counts"], "home_pages": layout["home_page_count"],
            "top_level_apps": sum(_kind(item) == "app" for page in raw for item in page),
            "folder_app_occurrences": sum(len(_apps(item["iconLists"])) for page in raw for item in page
                                           if _kind(item) == "folder"),
            "format3": _format3(raw, format3),
            "inventory": {"user": user, "system": system,
                          "visible_coverage": ("missing" if not complete_queries else
                                               "failed" if unmatched_occurrences or ambiguous_occurrences or overlap else "pass"),
                          "unmatched_visible_occurrences": unmatched_occurrences if complete_queries else None,
                          "ambiguous_visible_occurrences": ambiguous_occurrences if complete_queries else None,
                          "query_overlap": overlap if complete_queries else None,
                          "exclusion_list_complete": False},
            "widgets": _widgets(raw),
            "unverified": ["physical_geometry", "hidden_pages", "widget_configuration",
                           "hidden_webclips", "exclusion_semantics", "wire_protocol"]}


def render_analysis(report: dict) -> str:
    """Chinese summary of the fixed-schema aggregate report."""
    counts, ref, inventory = report["counts"], report["format3"], report["inventory"]
    yes_no = lambda value: "是" if value else "否"
    alias_labels = {"not_applicable_stack": "堆叠不适用独立组件规则",
                    "selected_identifier_missing": "缺少选中标识，不能推导别名",
                    "already_equal": "两个标识已相同，语义仍未验证",
                    "conflicting_identifiers": "已有标识冲突，不得覆盖",
                    "invalid_unique_identifier": "已有唯一标识格式无效",
                    "source_field_available_unverified": "源字段可用，别名语义未验证"}
    lines = ["Duo 本地证据分析（不授权写入）", "",
             f"桌面 App {counts['apps']}；逻辑页 {report['home_pages']}；文件夹 {counts['folders']}；"
             f"组件位置 {counts['widget_blocks']}，成员 {counts['widget_members']}。",
             f"顶层普通 App {report['top_level_apps']}；文件夹内 App {report['folder_app_occurrences']}。", ""]
    if ref["row_shape_recognized"]:
        kinds = ref["cell_kinds"]
        lines += [f"格式 3：普通 App {kinds['app']}，文件夹 {kinds['folder']}，小组件 {kinds['widget']}，"
                  f"False 单元 {kinds['false']}，其它 {kinds['other']}。",
                  f"顶层 App 的逐页顺序及完整内容一致：{yes_no(ref['top_level_apps_exact_order'])}。"]
        if ref["compact_projection_matches"]:
            lines += ["本样本精确符合以下投影：每个顶层项目占一格，普通 App 保留，其他项目替为 False，"
                      "尾部补至四格倍数，再每四格分行。",
                      f"False 中 {ref['explained_non_app_cells']} 格对应非 App 项目，"
                      f"{ref['explained_padding_cells']} 格为该投影的尾部填充。",
                      "这是当前导出之间的关系，不是物理坐标，也不表示组件只占一格。"]
        else:
            lines.append("本样本不符合上述压缩投影，不能用该规则解释它。")
    else:
        lines.append("缺少可识别的格式 3 行结构；不推导坐标。")
    lines += ["", "安装清单（未匹配桌面不等于应写入 ignored）："]
    for key, label in (("user", "用户"), ("system", "系统")):
        item = inventory[key]
        if item["status"] == "missing":
            lines.append(f"{label}清单：未观测。")
            continue
        lines += [f"{label}条目 {item['entries']}；匹配桌面 {item['matched_visible_alias']}；"
                  f"未匹配 {item['not_matched_visible_alias']}；卸载占位 {item['offloaded']}"
                  f"（桌面 {item['offloaded_matched']} / 未匹配 {item['offloaded_unmatched']}）。",
                  f"未匹配项：带 hidden 标签 {item['unmatched_hidden']}，标签字段缺失 "
                  f"{item['unmatched_tags_absent']}，明确返回标签但不含 hidden "
                  f"{item['unmatched_explicit_tags_without_hidden']}。"]
    lines += ["缺失标签不等于非隐藏；系统条目不能全部当作可见 App。", "", "小组件标识："]
    for widget in report["widgets"]:
        kind = "堆叠" if widget["kind"] == "stack" else "独立组件"
        lines.append(f"第 {widget['page']} 页，第 {widget['item'] + 1} 项：{kind}，"
                     f"成员 {widget['members']}，选中标识存在：{yes_no(widget['selected_identifier_present'])}，"
                     f"唯一标识存在：{yes_no(widget['unique_identifier_present'])}；"
                     f"{alias_labels[widget['standalone_alias_assessment']]}。")
        if widget["kind"] == "stack":
            lines.append(f"堆叠选中标识命中 {widget['selected_member_matches']} 个成员。")
    lines += ["标识字段存在不证明组件配置可保持；本工具没有添加、替换或发送任何字段。", "",
              "后续需独立核对实际位置与空隙、隐藏页、组件设置及资源库排除语义。",
              "本报告仅分析保存文件；不证明手机当前状态，不生成写入载荷，不连接手机。"]
    return "\n".join(lines) + "\n"
