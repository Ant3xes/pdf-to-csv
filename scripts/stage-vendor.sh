#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/packaging/vendor"
BIN="$VENDOR/bin"
TESSDATA="$VENDOR/tessdata"
LIB="$VENDOR/lib"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew est requis pour préparer les binaires OCR embarqués." >&2
  exit 1
fi

BREW_PREFIX="${HOMEBREW_PREFIX:-$(brew --prefix)}"

rm -rf "$VENDOR"
mkdir -p "$BIN" "$TESSDATA" "$LIB"

copy_binary() {
  local name="$1"
  cp "$BREW_PREFIX/bin/$name" "$BIN/$name"
  chmod +x "$BIN/$name"
}

copy_binary tesseract
copy_binary pdftoppm

cp "$BREW_PREFIX/share/tessdata/fra.traineddata" "$TESSDATA/fra.traineddata"

declare -A SEEN_LIBS=()

patch_binary() {
  local binary="$1"
  local lib dest base

  while read -r lib; do
    case "$lib" in
      "$BREW_PREFIX"/*)
        base="$(basename "$lib")"
        dest="$LIB/$base"
        if [[ -z "${SEEN_LIBS[$dest]:-}" ]]; then
          cp "$lib" "$dest"
          SEEN_LIBS[$dest]=1
          patch_binary "$dest"
        fi
        install_name_tool -change "$lib" "@executable_path/../lib/$base" "$binary"
        ;;
    esac
  done < <(otool -L "$binary" | tail -n +2 | awk '{print $1}')
}

for binary in "$BIN"/*; do
  patch_binary "$binary"
done

LIBHEIF_PREFIX="$(brew --prefix libheif 2>/dev/null || true)"
if [[ -n "$LIBHEIF_PREFIX" && -d "$LIBHEIF_PREFIX/lib" ]]; then
  cp "$LIBHEIF_PREFIX/lib/"*.dylib "$LIB/" 2>/dev/null || true
fi

echo "Binaires OCR préparés dans $VENDOR"
