#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Tento build script je iba pre macOS."
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_NAME="M4A Transkriptor"
APP_BUNDLE_ID="com.simongodarsky.m4atranskriptor"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build"
STAGE_DIR="$ROOT_DIR/.dmg-stage"
DMG_PATH="$DIST_DIR/M4A-Transkriptor.dmg"
PY_BIN="${PY_BIN:-python3}"

echo "Použitý Python: $PY_BIN"
"$PY_BIN" -m pip install --upgrade pip
"$PY_BIN" -m pip install -r requirements.txt
"$PY_BIN" -m pip install pyinstaller

rm -rf "$BUILD_DIR" "$DIST_DIR" "$STAGE_DIR"

"$PY_BIN" -m PyInstaller \
  --noconfirm \
  --windowed \
  --clean \
  --osx-bundle-identifier "$APP_BUNDLE_ID" \
  --collect-data whisper \
  --collect-submodules whisper \
  --collect-data pyannote.audio \
  --collect-data pyannote.core \
  --collect-data pyannote.database \
  --collect-data pyannote.pipeline \
  --collect-submodules pyannote.audio \
  --exclude-module mlx \
  --exclude-module mlx_whisper \
  --exclude-module mlx.core \
  --exclude-module mlx.nn \
  --exclude-module mlx.optimizers \
  --name "$APP_NAME" \
  transcript.py

mkdir -p "$STAGE_DIR"
cp -R "$DIST_DIR/$APP_NAME.app" "$STAGE_DIR/"
ln -s /Applications "$STAGE_DIR/Applications"

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$STAGE_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

rm -rf "$STAGE_DIR"

echo "Hotovo: $DMG_PATH"
