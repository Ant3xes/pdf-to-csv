#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${1:-${VERSION:-dev}}"
DIST="$ROOT/dist"
APP_NAME="Convertisseur Factures"
APP_BUNDLE="$DIST/${APP_NAME}.app"
DMG_NAME="ConvertisseurFactures-${VERSION}.dmg"
DMG_PATH="$DIST/$DMG_NAME"

cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "Créez d'abord l'environnement virtuel (.venv)." >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install -q -r requirements.txt -r requirements-build.txt

bash "$ROOT/scripts/stage-vendor.sh"

pyinstaller --noconfirm --clean "$ROOT/packaging/ConvertisseurFactures.spec"

if [[ -n "${APPLE_SIGNING_IDENTITY:-}" ]]; then
  codesign --force --deep --options runtime \
    --sign "$APPLE_SIGNING_IDENTITY" \
    "$APP_BUNDLE"
  echo "Application signée avec $APPLE_SIGNING_IDENTITY"
else
  echo "Signature ignorée (app non signée — l'utilisateur ouvre via clic droit → Ouvrir)." >&2
fi

if [[ -n "${APPLE_NOTARIZE_KEYCHAIN_PROFILE:-}" ]]; then
  ditto -c -k --keepParent "$APP_BUNDLE" "$DIST/notarize.zip"
  xcrun notarytool submit "$DIST/notarize.zip" \
    --keychain-profile "$APPLE_NOTARIZE_KEYCHAIN_PROFILE" \
    --wait
  xcrun stapler staple "$APP_BUNDLE"
  rm -f "$DIST/notarize.zip"
  echo "Application notarisée."
else
  echo "Notarisation ignorée (optionnelle)." >&2
fi

rm -f "$DMG_PATH"
hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$APP_BUNDLE" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "Release prête : $DMG_PATH"
echo "Publiez sur GitHub Releases avec un tag v${VERSION#v}."
