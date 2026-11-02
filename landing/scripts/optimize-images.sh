#!/usr/bin/env bash
# Convertit les captures PNG produites par capture_screens.py en WebP 800 et 1500 px.
# Usage : landing/scripts/optimize-images.sh <dossier-des-captures>
set -euo pipefail
target="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/src/assets/img"
for file in "$1"/*.png; do
    name="$(basename "$file" .png)"
    cwebp -quiet -q 82 -m 6 "$file" -o "$target/$name-1500.webp"
    cwebp -quiet -q 78 -m 6 -resize 800 0 "$file" -o "$target/$name-800.webp"
done
