"""Explicit evidence commands. Default/help/import never contact a phone.

USB collection is a separate opt-in CLI path, not connected to the app UI. It
requires acknowledgement of the exact data categories before device imports.
This module has no device write command or roundtrip flag.
"""
from __future__ import annotations

import argparse
import asyncio
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import plistlib

from . import i18n
from .evidence import EvidenceBundle, EvidenceError, MAX_FILE_BYTES, collect_evidence

SCOPE_ACK = "device-layout-installed-apps"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="生成只读证据包：仅整理观测，不启用任何手机写入。",
        epilog=("真机采集范围：机型、iOS/构建号、设备标识摘要、两次布局、网格，"
                "User/System 应用标识与名称、卸载占位标记，以及可选格式 3 布局。"
                "不请求照片、通讯录、聊天、壁纸、图标或应用内容；不保存配对凭据。"
                "SDK 连接时会读取系统元数据，证据包仅保留声明字段。"),
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--from-backup", type=Path, help="只读取本地原始 .plist，缺失信息明确标记")
    modes.add_argument("--collect-usb", action="store_true", help="明确发起已信任 USB 设备的只读采集")
    parser.add_argument("--scope-ack", help=f"真机采集必须填写 {SCOPE_ACK}，表示已了解上述范围")
    parser.add_argument("--output", type=Path, required=True, help="新建 .hsevidence 文件；不覆盖已有文件")
    parser.add_argument("--timeout", type=float, default=10.0, help="每项只读请求的秒数上限，默认 10，最高 60")
    parser.add_argument("--skip-format3", action="store_true", help="不查询格式 3，将其标为未采集")
    args = parser.parse_args(argv)
    if args.collect_usb and args.scope_ack != SCOPE_ACK:
        parser.error(f"真机采集未获得范围确认：必须显式提供 --scope-ack {SCOPE_ACK}")
    if args.from_backup and (args.scope_ack or args.skip_format3):
        parser.error("本地备份导入不使用真机范围确认或格式 3 查询选项")
    if args.output.suffix.lower() != ".hsevidence":
        parser.error("输出必须使用 .hsevidence 扩展名")
    if args.output.exists() or args.output.is_symlink():
        parser.error("输出文件已存在，请选择新的文件名")
    if not args.output.parent.is_dir():
        parser.error("输出目录不存在，请先选择已有目录")
    if not 0 < args.timeout <= 60:
        parser.error("每项超时必须大于 0 且不超过 60 秒")
    if os.name == "posix":
        os.umask(0o077)
    i18n.start("zh_CN")
    # Dependencies may include device identifiers in diagnostics. Evidence has
    # stable failure codes; don't create unrelated logs or export SDK internals.
    previous_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        if args.from_backup:
            if args.from_backup.suffix.lower() != ".plist":
                raise EvidenceError("invalid_backup", "输入必须是原始 .plist 备份，不能是草稿文件。")
            with args.from_backup.open("rb") as handle:
                payload = handle.read(MAX_FILE_BYTES + 1)
            if len(payload) > MAX_FILE_BYTES:
                raise EvidenceError("evidence_too_large", "原始备份超过 64 MiB。")
            bundle = EvidenceBundle.from_backup(plistlib.loads(payload), sha256(payload).hexdigest())
        else:
            # Lazy by design: no SDK import, USB enumeration or trust access can
            # happen before both explicit command and scope acknowledgement.
            from .device import ReadOnlyEvidenceAdapter

            bundle = asyncio.run(collect_evidence(ReadOnlyEvidenceAdapter(), source="usb_readonly",
                                                  timeout=args.timeout, include_layout_v3=not args.skip_format3))
        saved = bundle.save(args.output)
        failures = {part: receipt["error_code"] for part, receipt in bundle.receipts.items()
                    if receipt["status"] == "failed"}
        print(json.dumps({"output": str(saved), "source": bundle.source,
                          "collection_succeeded": bundle.collection_succeeded,
                          "can_write": False, "failures": failures,
                          "close_error_code": bundle.record["close_error_code"]}, ensure_ascii=False))
        return 2 if failures or bundle.record["close_error_code"] else 0
    except (EvidenceError, OSError, ValueError, TypeError, OverflowError, RecursionError) as exc:
        print(json.dumps({"status": "stopped", "reason": str(exc), "can_write": False}, ensure_ascii=False))
        return 2
    finally:
        logging.disable(previous_disable)


if __name__ == "__main__":
    raise SystemExit(main())
