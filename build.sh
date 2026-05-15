#!/usr/bin/env bash
# Build PyInstaller de CABReplay (Windows / Git Bash / MSYS).
# Usage : ./build.sh

set -euo pipefail

cd "$(dirname "$0")"

PY="${PY:-py}"
DIST="dist/CABReplay"

echo ">>> Nettoyage build/ et $DIST"
rm -rf build "$DIST"

if [ ! -f assets/icon.ico ] || [ "$(stat -c %s assets/icon.ico 2>/dev/null || echo 0)" -lt 1000 ]; then
    echo ">>> (Re)génération de l'icône"
    "$PY" tools/make_icon.py
fi

echo ">>> PyInstaller"
"$PY" -m PyInstaller --noconfirm CABReplay.spec

echo ">>> Copie datas/ (si présent)"
if [ -d datas ]; then
    mkdir -p "$DIST/datas"
    cp -r datas/* "$DIST/datas/" || true
fi

echo ">>> Copie config.json (si présent)"
[ -f config.json ] && cp config.json "$DIST/config.json"

echo ""
echo "OK -> $DIST/CABReplay.exe"
