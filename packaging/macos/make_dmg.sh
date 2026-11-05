#!/usr/bin/env bash
# Crea la imagen de disco .dmg de macOS a partir de la .app generada por PyInstaller.
# Uso: packaging/macos/make_dmg.sh <version> <arquitectura>
set -euo pipefail
VERSION="$1"; ARCH="$2"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/dist/Electronic Front Panel Designer.app"
STAGE="$ROOT/dist/dmg"
OUT="$ROOT/dist/FrontPanelDesigner-$VERSION-macOS-$ARCH.dmg"
rm -rf "$STAGE" "$OUT"
mkdir -p "$STAGE/Ejemplos"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp "$ROOT"/ejemplos/*.efpd "$STAGE/Ejemplos/"
cp "$ROOT/LICENSE" "$STAGE/LICENSE.txt"
cp "$ROOT/packaging/macos/LEEME - Read me.txt" "$STAGE/"
hdiutil create -volname "Front Panel Designer $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$OUT"
echo "$OUT"
