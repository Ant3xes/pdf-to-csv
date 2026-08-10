#!/usr/bin/env bash
# Copie tesseract / pdftoppm + dylibs Homebrew dans packaging/vendor pour le bundle .app.
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

# Recursively copy Homebrew dylibs referenced by a binary (bash 3.2 compatible).
copy_linked_libs() {
  local binary="$1"
  local lib base dest

  otool -L "$binary" | tail -n +2 | awk '{print $1}' | while read -r lib; do
    case "$lib" in
      "$BREW_PREFIX"/*)
        base="$(basename "$lib")"
        dest="$LIB/$base"
        if [[ ! -f "$dest" ]]; then
          cp "$lib" "$dest"
          copy_linked_libs "$dest"
        fi
        install_name_tool -change "$lib" "@executable_path/../lib/$base" "$binary" 2>/dev/null || true
        ;;
    esac
  done
}

for binary in "$BIN"/*; do
  copy_linked_libs "$binary"
done

# Re-run install_name_tool on binaries after all libs are present
# (pipe subshell may miss some changes on first pass for already-copied libs).
for binary in "$BIN"/* "$LIB"/*; do
  [[ -f "$binary" ]] || continue
  otool -L "$binary" | tail -n +2 | awk '{print $1}' | while read -r lib; do
    case "$lib" in
      "$BREW_PREFIX"/*)
        base="$(basename "$lib")"
        if [[ -f "$LIB/$base" ]]; then
          install_name_tool -change "$lib" "@executable_path/../lib/$base" "$binary" 2>/dev/null || true
        fi
        ;;
    esac
  done
done

LIBHEIF_PREFIX="$(brew --prefix libheif 2>/dev/null || true)"
if [[ -n "$LIBHEIF_PREFIX" && -d "$LIBHEIF_PREFIX/lib" ]]; then
  for dylib in "$LIBHEIF_PREFIX/lib/"*.dylib; do
    [[ -f "$dylib" ]] || continue
    cp "$dylib" "$LIB/"
  done
fi

echo "Binaires OCR préparés dans $VENDOR"
