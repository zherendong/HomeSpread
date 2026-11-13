#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
umask 077
if [[ ! -x .venv/bin/python ]]; then
  echo "请先双击 install_macos.command 安装依赖。"; exit 1
fi
export PYTHONPATH="$PWD/src"
exec .venv/bin/python -m ipsm.app "$@"
