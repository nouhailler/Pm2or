#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e '.[dev]'
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/pytest
.venv/bin/ruff check src tests
PYTHONPATH=src .venv/bin/mypy src/pm2/domain src/pm2/application src/pm2/methodology
.venv/bin/pyinstaller --noconfirm pm2-desktop.spec

echo "Paquet créé dans dist/pm2-desktop"
