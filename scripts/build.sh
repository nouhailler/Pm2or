#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv est requis pour construire un environnement reproductible." >&2
    exit 1
fi
uv sync --frozen --extra dev
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/pytest --cov=pm2 --cov-report=term-missing
.venv/bin/ruff check src tests scripts migrations
PYTHONPATH=src .venv/bin/mypy src/pm2/domain src/pm2/application src/pm2/infrastructure src/pm2/methodology
.venv/bin/pyinstaller --noconfirm pm2-desktop.spec

echo "Paquet créé dans dist/pm2-desktop"
