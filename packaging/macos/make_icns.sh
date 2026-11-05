#!/usr/bin/env bash
# Genera efpd/resources/icon.icns a partir de icon.png (sólo macOS: sips + iconutil).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/efpd/resources/icon.png"
SET="$ROOT/dist/icon.iconset"
rm -rf "$SET"; mkdir -p "$SET"
for s in 16 32 128 256 512; do
  sips -z $s $s "$SRC" --out "$SET/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2))
  sips -z $d $d "$SRC" --out "$SET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$SET" -o "$ROOT/efpd/resources/icon.icns"
echo "icon.icns OK"
