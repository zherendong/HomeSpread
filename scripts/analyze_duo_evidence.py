"""Analyze one saved evidence bundle without importing device code."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import plistlib

from ipsm.evidence import EvidenceBundle
from ipsm.safeio import atomic_private_write
from research.duo_evidence_analysis import analyze_observations, render_analysis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只分析本地 Duo 证据包；不访问手机，不生成写入载荷。")
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="新的 .json 或 .txt 报告，父目录须已存在")
    args = parser.parse_args(argv)
    if args.output.suffix.lower() not in (".json", ".txt"):
        parser.error("报告必须使用 .json 或 .txt 后缀")
    if args.output.exists() or args.output.is_symlink() or not args.output.parent.is_dir():
        parser.error("输出已存在或父目录无效；禁止覆盖文件")
    try:
        evidence = EvidenceBundle.load(args.evidence)
        if not evidence.collection_succeeded or evidence.source != "usb_readonly":
            raise ValueError("需要已完成的 USB 只读证据包；本工具不会补采")
        binary = lambda value: plistlib.dumps(value, fmt=plistlib.FMT_BINARY, sort_keys=True)
        if any(binary(evidence.data(before)) != binary(evidence.data(after)) for before, after in (
            ("layout_v2_before", "layout_v2_after"), ("identity_before", "identity_after"),
        )):
            raise ValueError("前后观测不一致，停止分析")
        report = analyze_observations(evidence.data("layout_v2_before"), format3=evidence.data("layout_v3"),
                                      apps_user=evidence.data("apps_user"), apps_system=evidence.data("apps_system"))
        # Preserve source dates without claiming that analysis refreshes evidence.
        report["observation_started_at"] = evidence.record["started_at"]
        report["observation_finished_at"] = evidence.record["finished_at"]
        content = (json.dumps(report, ensure_ascii=False, indent=2) + "\n" if args.output.suffix.lower() == ".json"
                   else f"观测时间（UTC）：{report['observation_started_at']} 至 {report['observation_finished_at']}\n\n"
                   + render_analysis(report)).encode("utf-8")
        atomic_private_write(args.output, content)
        if args.output.read_bytes() != content:
            raise OSError("报告读回校验失败")
        print(json.dumps({"saved": str(args.output), "device_requests": 0, "can_write": False}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "stopped", "error_type": type(exc).__name__, "device_requests": 0,
                          "can_write": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
