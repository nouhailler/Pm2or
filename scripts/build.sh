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
PYTHONPATH=src .venv/bin/mypy src/pm2
mkdir -p build
uv export --frozen --no-dev --no-emit-project --format requirements-txt \
    --output-file build/runtime-requirements.txt >/dev/null
.venv/bin/pip-audit --requirement build/runtime-requirements.txt --no-deps --disable-pip
.venv/bin/cyclonedx-py environment --pyproject pyproject.toml --output-reproducible \
    --of JSON -o build/sbom.cdx.json .venv
.venv/bin/pyinstaller --noconfirm pm2-desktop.spec
bundle_data="$(mktemp -d)"
PM2_DATA_DIR="$bundle_data" dist/pm2-desktop/pm2-desktop --headless-check

echo "Paquet créé dans dist/pm2-desktop"
