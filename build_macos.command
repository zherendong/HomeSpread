#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
umask 077
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m pip check
.venv/bin/python scripts/prepare_macos.py
export PYINSTALLER_CONFIG_DIR="$PWD/build/pyinstaller-cache"
.venv/bin/python -m PyInstaller --noconfirm --clean HomeSpread-macos.spec
/usr/bin/codesign --verify --deep --strict dist/HomeSpread.app
echo "已生成 dist/HomeSpread.app。可在 Finder 中双击打开。"
