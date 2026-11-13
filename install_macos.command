#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
umask 077
if [[ "$(uname -s)" != Darwin ]]; then
  echo "此安装脚本适用于 macOS。"; exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
  HOMESPREAD_PYTHON="${HOMESPREAD_PYTHON:-python3.12}"
  "$HOMESPREAD_PYTHON" -m venv .venv
fi
.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 12), "锁定的 macOS 环境需要 Python 3.12"'
.venv/bin/python -m pip install 'pip==26.3'
.venv/bin/python -m pip install -r requirements-macos.lock
.venv/bin/python -m pip check
echo "安装完成。双击 run_macos.command 启动中文版。"
