"""Local draft/evidence inspection. A report never grants device write access."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import plistlib
from typing import Any

from .draft_rules import analyze_layout, plan_swap
from .drafts import OfflineDraft
from .evidence import EvidenceBundle
from .i18n import tr
from .safeio import atomic_private_write
from .write_policy import write_block_reason

REPORT_FORMAT = "ipsm.preflight-report"
REPORT_SUFFIX = ".hspreflight"
MAX_REPORT_BYTES = 16 * 1024 * 1024


def _binary(value: Any) -> bytes:
    return plistlib.dumps(value, fmt=plistlib.FMT_BINARY, sort_keys=True)


def _stamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Missing timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _visible_aliases(raw: list[Any]) -> list[set[str]]:
    aliases: list[set[str]] = []
    def walk(pages: list[Any]) -> None:
        for page in pages:
            for item in page:
                if isinstance(item, dict):
                    if any(key in item for key in ("widgetIdentifier", "elements", "gridSize", "webClipURL")):
                        continue
                    if item.get("listType") == "folder":
                        walk(item["iconLists"])
                    else:
                        names = {item[key] for key in ("displayIdentifier", "bundleIdentifier")
                                 if isinstance(item.get(key), str) and item[key]}
                        if names:
                            aliases.append(names)
                elif isinstance(item, str) and item:
                    aliases.append({item})
    walk(raw)
    return aliases


def evidence_source_label(source: str) -> str:
    return {"imported_backup": tr("Imported local backup"),
            "usb_readonly": tr("USB read-only collection"),
            "synthetic": tr("Synthetic test data")}[source]


def build_preflight_report(draft: OfflineDraft, evidence: EvidenceBundle | None = None,
                           *, now: datetime | None = None, max_age_seconds: int = 300) -> dict[str, Any]:
    """Inspect exported information without querying a phone or constructing a send.

    Fresh receipts and matching exported data are partial checks only. Unknown
    system state and the unchanged production capability policy remain blockers.
    Imported evidence is integrity-checked data, not cryptographic attestation.
    """
    if not isinstance(draft, OfflineDraft):
        raise ValueError("Expected an offline draft")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 3600:
        raise ValueError("Invalid freshness interval")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must include a timezone")
    now = now.astimezone(timezone.utc)
    origin, current, operations = draft.origin, draft.current_state, draft.operations
    # Independently replay the active history, never trust a UI verification flag.
    replay = origin
    for op in operations:
        replay = plan_swap(replay, op.page, op.index_a, op.index_b)
    if _binary(replay) != _binary(current):
        raise ValueError("Draft state does not match its operation history")
    analysis = analyze_layout(current)
    evidence = evidence or EvidenceBundle.from_backup(origin)
    # Revalidate even an in-memory instance against the persistent record schema.
    evidence = EvidenceBundle.from_record(evidence.to_dict())
    receipts = evidence.receipts
    record = evidence.to_dict()
    checks: list[dict[str, str]] = []

    def add(code: str, status: str, title: str, detail: str) -> None:
        checks.append({"code": code, "status": status, "title": title, "detail": detail})

    def observed(part: str) -> bool:
        return receipts.get(part, {}).get("status") == "observed"

    add("draft_integrity", "pass", tr("Draft integrity"),
        tr("The operation history replays exactly; unchanged layout fields are preserved."))
    changes = [{"page": change.page, "index": change.index,
                "before": change.before_label, "after": change.after_label} for change in draft.diff()]
    add("draft_changes", "pass" if changes else "blocked", tr("Draft changes"),
        tr("The draft contains {n} changed positions.").format(n=len(changes)) if changes
        else tr("The draft has no changes to inspect."))
    add("evidence_source", "pass" if evidence.source == "usb_readonly" else "blocked", tr("Evidence source"),
        tr("The package records USB read-only collection; its hashes are not device authentication.")
        if evidence.source == "usb_readonly" else
        tr("This package comes from a local backup or simulation and is not a current phone observation."))
    collection_failed = bool(record.get("close_error_code")) or any(
        receipt.get("status") == "failed" for receipt in receipts.values())
    add("collection_completion", "failed" if collection_failed else ("pass" if evidence.collection_succeeded else "missing"),
        tr("Read-only collection completion"),
        tr("Collection or connection cleanup failed. The package is incomplete even if some observations succeeded.") if collection_failed else
        (tr("Requested observations completed. This does not establish coverage of hidden system state.") if evidence.collection_succeeded else
         tr("Not all requested device observations were collected.")))

    before = evidence.data("layout_v2_before")
    after = evidence.data("layout_v2_after")
    baseline_ok = observed("layout_v2_before") and _binary(before) == _binary(origin)
    add("baseline", "pass" if baseline_ok else ("failed" if observed("layout_v2_before") else "missing"),
        tr("Draft baseline"), tr("The exported layout matches the draft baseline.") if baseline_ok
        else tr("A matching original layout observation is missing or differs from this draft."))
    stable = observed("layout_v2_before") and observed("layout_v2_after")
    stable_ok = stable and _binary(before) == _binary(after)
    add("snapshot_stability", "pass" if stable_ok else ("failed" if stable else "missing"),
        tr("Collection stability"), tr("The two exported layout reads match; this does not provide an atomic device snapshot.") if stable_ok
        else tr("Matching before-and-after device layout reads are missing or the layout changed during collection."))

    identity_before, identity_after = evidence.data("identity_before"), evidence.data("identity_after")
    identity_present = observed("identity_before") and observed("identity_after")
    identity_ok = identity_present and _binary(identity_before) == _binary(identity_after)
    add("device_identity", "pass" if identity_ok else ("failed" if identity_present else "missing"),
        tr("Device and OS identity"), tr("The recorded device fingerprint, model and OS build match across collection.") if identity_ok
        else tr("Stable device identity and the exact OS build have not been established."))

    freshness, freshness_detail = "missing", tr("There is no recent USB collection receipt. Importing a backup does not refresh its device state.")
    if evidence.source == "usb_readonly":
        try:
            started, finished = _stamp(record.get("started_at")), _stamp(record.get("finished_at"))
            age = (now - finished).total_seconds()
            if finished < started or age < -5 or (started - now).total_seconds() > 5:
                freshness, freshness_detail = "failed", tr("Collection timestamps are inconsistent or in the future.")
            elif age > max_age_seconds or (now - started).total_seconds() > max_age_seconds:
                freshness, freshness_detail = "failed", tr("The collection receipt is too old; a future write would require a new read.")
            else:
                freshness, freshness_detail = "pass", tr("The receipt is within {seconds} seconds; a future send still requires an immediate re-read.").format(seconds=max_age_seconds)
        except (ValueError, TypeError):
            freshness, freshness_detail = "failed", tr("Collection timestamps are missing or invalid.")
    add("freshness", freshness, tr("Receipt age"), freshness_detail)

    inventories: dict[str, dict] = {}
    inventory_success = True
    placeholders = True
    for part, kind in (("apps_user", "User"), ("apps_system", "System")):
        receipt = receipts.get(part, {})
        options = receipt.get("options") or {}
        data = evidence.data(part)
        valid = observed(part) and isinstance(data, dict) and options.get("application_type") == kind
        inventory_success &= valid
        placeholders &= valid and options.get("show_placeholders") is True
        if valid:
            inventories[part] = data
        status = "pass" if valid else ("failed" if receipt.get("status") == "failed" or observed(part) else "missing")
        add(part, status, tr("User application query") if kind == "User" else tr("System application query"),
            tr("The query completed with {n} entries. This does not establish complete App Library coverage.").format(n=len(data)) if valid
            else tr("The application query failed, was not collected, or has incompatible scope. An empty result is not substituted."))
    overlap = set(inventories.get("apps_user", {})) & set(inventories.get("apps_system", {}))
    add("inventory_consistency", "failed" if overlap else ("pass" if inventory_success else "missing"),
        tr("Inventory consistency"), tr("The User and System queries contain conflicting identities.") if overlap else
        (tr("The two query result sets do not overlap.") if inventory_success else tr("Both application query results are required for comparison.")))
    known_ids = set(inventories.get("apps_user", {})) | set(inventories.get("apps_system", {}))
    missing_visible = sum(not (names & known_ids) for names in _visible_aliases(origin))
    add("visible_inventory_coverage", "missing" if not inventory_success else ("failed" if missing_visible else "pass"),
        tr("Visible application coverage"),
        tr("The inventory is missing {n} app occurrences from the draft baseline.").format(n=missing_visible) if inventory_success and missing_visible else
        (tr("The baseline's visible apps are represented in the queries; hidden content may still be missing.") if inventory_success else
         tr("Both application query results are needed to check visible app coverage.")))
    add("placeholder_coverage", "pass" if placeholders else "missing", tr("Offloaded application placeholders"),
        tr("Both queries explicitly requested placeholders; this is request scope, not proof that every hidden entry was exported.") if placeholders
        else tr("Placeholder-inclusive User and System queries have not both been established."))

    metrics = evidence.data("metrics")
    keys = {"homeScreenIconColumns": 4, "homeScreenIconRows": 6,
            "homeScreenIconDockMaxCount": 4, "homeScreenIconFolderColumns": 3,
            "homeScreenIconFolderRows": 3}
    grid_ok = observed("metrics") and isinstance(metrics, dict) and all(
        type(metrics.get(key)) in (int, float) and metrics[key] == value for key, value in keys.items())
    add("grid_profile", "pass" if grid_ok else ("failed" if observed("metrics") else "missing"),
        tr("Logical grid profile"), tr("The reported grid agrees with the draft rules; modeled placement is not a screenshot coordinate proof.") if grid_ok
        else tr("The device grid is missing or does not match the supported offline draft profile."))
    add("layout_v3", "pass" if observed("layout_v3") else "missing", tr("Additional layout reference"),
        tr("An additional layout-format observation is present; no completeness is inferred from it.") if observed("layout_v3")
        else tr("No additional layout-format observation is available."))

    for code, title, detail in (
        ("geometry", tr("Real positions and gaps"), tr("Exported item order cannot prove preservation of native gaps or folded/unfolded positions.")),
        ("hidden_pages", tr("Hidden page visibility"), tr("Hidden page and Focus visibility have not been independently verified.")),
        ("widget_settings", tr("Widget and stack configuration"), tr("Retaining widget dictionaries does not prove that iOS will preserve their configuration or selected members.")),
        ("hidden_webclips", tr("Hidden web clips and App Library exclusions"), tr("A complete exclusion list cannot be inferred from the layout and application queries alone.")),
    ):
        add(code, "unknown", title, detail)
    recorded_identity = identity_after if isinstance(identity_after, dict) else identity_before
    model = recorded_identity.get("product_type") if isinstance(recorded_identity, dict) else None
    policy = write_block_reason(current, product_type=model)
    add("write_policy", "blocked", tr("Device write permission"), policy or
        tr("This preflight tool never authorizes a device write, even when local checks pass."))
    add("wire_protocol", "unknown", tr("Write protocol and encoding"),
        tr("The target OS request format, encoding and failure behavior have not been validated on the device."))
    return {"format": REPORT_FORMAT, "schema_version": 1, "status": "blocked", "can_write": False,
            "created_at": now.isoformat(), "evidence_source": evidence.source,
            "device": ({key: recorded_identity[key] for key in ("product_type", "ios_version", "build_version")}
                       if isinstance(recorded_identity, dict) else None),
            "baseline_sha256": sha256(_binary(origin)).hexdigest(),
            "draft_sha256": sha256(_binary(current)).hexdigest(),
            "counts": analysis["counts"], "changes": changes, "checks": checks,
            "blockers": [check["code"] for check in checks if check["status"] != "pass"],
            "device_requests": 0}


def render_preflight_report(report: dict[str, Any]) -> str:
    statuses = {"pass": tr("Checked locally"), "missing": tr("Missing evidence"),
                "failed": tr("Check failed"), "blocked": tr("Blocked"), "unknown": tr("Unverified")}
    lines = [tr("Draft preflight — device writing remains disabled"), "",
             tr("This report uses local draft and evidence files only. It does not collect device data or grant write permission."), "",
             tr("Evidence: {source}").format(source=evidence_source_label(report["evidence_source"])),
             tr("Report created at {time} (UTC).").format(time=report["created_at"]), "",
             tr("Draft differences: {n}").format(n=len(report["changes"]))]
    if report.get("device"):
        device = report["device"]
        lines.insert(5, tr("Recorded device: {model}, iOS {version} [{build}].").format(
            model=device["product_type"], version=device["ios_version"], build=device["build_version"]))
    else:
        lines.insert(5, tr("Device model and OS build have not been collected."))
    for change in report["changes"]:
        lines.append(tr("Page {page}, item {item}: {before} → {after}").format(
            page=change["page"], item=change["index"] + 1, before=change["before"], after=change["after"]))
    lines.append("")
    for check in report["checks"]:
        lines.extend([f"[{statuses[check['status']]}] {check['title']}", check["detail"], ""])
    lines.append(tr("The report may contain app names and layout information. Review it before sharing."))
    return "\n".join(lines)


def save_preflight_report(path: Path, report: dict[str, Any], *, replace: bool = False) -> Path:
    path = Path(path)
    if path.suffix.lower() != REPORT_SUFFIX:
        raise ValueError(tr("Preflight reports must use the .hspreflight extension."))
    if (report.get("format") != REPORT_FORMAT or report.get("can_write") is not False
            or report.get("status") != "blocked"):
        raise ValueError(tr("This is not a blocked offline preflight report."))
    if path.is_symlink():
        raise ValueError(tr("A preflight report cannot be saved through a symbolic link."))
    if path.exists() and replace:
        try:
            with path.open("rb") as handle:
                previous = handle.read(MAX_REPORT_BYTES + 1)
            if len(previous) > MAX_REPORT_BYTES:
                raise ValueError("Too large")
            old = json.loads(previous)
            if (not isinstance(old, dict) or old.get("format") != REPORT_FORMAT
                    or type(old.get("schema_version")) is not int or old["schema_version"] != 1
                    or old.get("can_write") is not False or old.get("status") != "blocked"):
                raise ValueError("Different file format")
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ValueError(tr("Cannot replace a file that is not an offline preflight report.")) from exc
    data = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError(tr("The preflight report exceeds the 16 MiB file limit."))
    atomic_private_write(path, data, replace=replace)
    if path.read_bytes() != data:
        raise OSError(tr("The saved preflight report did not match when read back."))
    return path


def main(argv: list[str] | None = None) -> int:
    import argparse
    from . import i18n
    parser = argparse.ArgumentParser(description="离线草稿预检，不连接手机、不启用写入。")
    parser.add_argument("--draft", required=True, type=Path, help="本地 .hsdraft 草稿")
    parser.add_argument("--evidence", type=Path, help="可选的本地 .hsevidence 证据包")
    parser.add_argument("--output", type=Path, help="新建 .hspreflight 报告，不覆盖已有文件")
    parser.add_argument("--json", action="store_true", help="在终端输出结构化报告")
    args = parser.parse_args(argv)
    i18n.start("zh_CN")
    try:
        draft = OfflineDraft.load(args.draft)
        evidence = EvidenceBundle.load(args.evidence) if args.evidence else None
        report = build_preflight_report(draft, evidence)
        if args.output:
            save_preflight_report(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render_preflight_report(report))
        return 3  # Report generated, but writing remains blocked. Never a readiness exit code.
    except (ValueError, OSError, TypeError) as exc:
        print(tr("Cannot generate the preflight report: {why}").format(why=exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
