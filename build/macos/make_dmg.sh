#!/usr/bin/env bash
# Wrap the built app bundle in a .dmg with an Applications shortcut.
#
#   build/macos/make_dmg.sh
#
# Signing and notarisation run only when their secrets are present:
#   MACOS_SIGN_IDENTITY                              "Developer ID Application: ..."
#   APPLE_ID, APPLE_TEAM_ID, APPLE_APP_PASSWORD      for notarytool
# Without them the .dmg is unsigned; docs/INSTALL.md explains how to open it.
set -euo pipefail

NAME="REDCap Uploader"
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
ARCH=$(uname -m)
APP="dist/${NAME}.app"
STAGE="build/out/dmg"
DMG="dist/REDCap-Uploader-${VERSION}-macOS-${ARCH}.dmg"

test -d "$APP" || { echo "missing $APP; run PyInstaller first" >&2; exit 1; }
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

if [ -n "${MACOS_SIGN_IDENTITY:-}" ]; then
  codesign --deep --force --options runtime --timestamp --sign "$MACOS_SIGN_IDENTITY" "$STAGE/${NAME}.app"
  codesign --verify --deep --strict "$STAGE/${NAME}.app"
else
  echo "MACOS_SIGN_IDENTITY not set: the app is not signed"
fi

rm -f "$DMG"
hdiutil create -volname "$NAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG"

if [ -n "${MACOS_SIGN_IDENTITY:-}" ] && [ -n "${APPLE_ID:-}" ] && [ -n "${APPLE_TEAM_ID:-}" ] && [ -n "${APPLE_APP_PASSWORD:-}" ]; then
  codesign --force --timestamp --sign "$MACOS_SIGN_IDENTITY" "$DMG"
  xcrun notarytool submit "$DMG" --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_PASSWORD" --wait
  xcrun stapler staple "$DMG"
else
  echo "Notarisation secrets not set: the .dmg is not notarised"
fi

echo "$DMG"
