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
# pdf2image exige pdfinfo (nombre de pages) + pdftoppm (rasterisation).
copy_binary pdfinfo
copy_binary pdftoppm

cp "$BREW_PREFIX/share/tessdata/fra.traineddata" "$TESSDATA/fra.traineddata"

# Resolve a Mach-O load path to an absolute dylib on disk (empty if system/unknown).
resolve_dylib() {
  local binary="$1"
  local lib="$2"
  local base binary_dir candidate rpath

  case "$lib" in
    /usr/lib/*|/System/*)
      return 0
      ;;
    "$BREW_PREFIX"/*)
      if [[ -f "$lib" ]]; then
        printf '%s\n' "$lib"
      fi
      return 0
      ;;
    @rpath/*)
      base="${lib#@rpath/}"
      binary_dir="$(cd "$(dirname "$binary")" && pwd)"
      # bash 3.2: pas de process substitution — capturer puis itérer.
      local rpaths
      rpaths="$(
        otool -l "$binary" | awk '
          /cmd LC_RPATH/ { want=1; next }
          want && /path / {
            sub(/^[[:space:]]*path[[:space:]]+/, "")
            sub(/[[:space:]]*\(offset.*$/, "")
            print
            want=0
          }
        '
      )"
      while IFS= read -r rpath; do
        [[ -n "$rpath" ]] || continue
        case "$rpath" in
          @loader_path/*)
            candidate="$binary_dir/${rpath#@loader_path/}/$base"
            ;;
          @executable_path/*)
            candidate="$binary_dir/${rpath#@executable_path/}/$base"
            ;;
          /*)
            candidate="$rpath/$base"
            ;;
          *)
            continue
            ;;
        esac
        if [[ -f "$candidate" ]]; then
          printf '%s\n' "$candidate"
          return 0
        fi
      done <<EOF
$rpaths
EOF
      if [[ -f "$BREW_PREFIX/lib/$base" ]]; then
        printf '%s\n' "$BREW_PREFIX/lib/$base"
      fi
      return 0
      ;;
    @loader_path/*)
      binary_dir="$(cd "$(dirname "$binary")" && pwd)"
      candidate="$binary_dir/${lib#@loader_path/}"
      if [[ -f "$candidate" ]]; then
        printf '%s\n' "$candidate"
      fi
      return 0
      ;;
  esac
}

# Recursively copy Homebrew / @rpath dylibs (bash 3.2 compatible).
copy_linked_libs() {
  local binary="$1"
  local lib resolved base dest

  otool -L "$binary" | tail -n +2 | awk '{print $1}' | while read -r lib; do
    resolved="$(resolve_dylib "$binary" "$lib")"
    [[ -n "${resolved:-}" ]] || continue
    base="$(basename "$resolved")"
    dest="$LIB/$base"
    if [[ ! -f "$dest" ]]; then
      cp "$resolved" "$dest"
      copy_linked_libs "$dest"
    fi
    install_name_tool -change "$lib" "@executable_path/../lib/$base" "$binary" 2>/dev/null || true
  done
}

for binary in "$BIN"/*; do
  copy_linked_libs "$binary"
done

# Second pass: rewrite load commands once every dylib is present
# (pipe subshell may skip -change when the dest was already copied).
rewrite_load_commands() {
  local binary="$1"
  local lib resolved base

  otool -L "$binary" | tail -n +2 | awk '{print $1}' | while read -r lib; do
    case "$lib" in
      @executable_path/*|/usr/lib/*|/System/*)
        continue
        ;;
    esac
    resolved="$(resolve_dylib "$binary" "$lib")"
    if [[ -z "${resolved:-}" ]]; then
      # Already-vendored @rpath that resolve_dylib can't see from vendor tree.
      base="$(basename "$lib")"
      if [[ -f "$LIB/$base" ]]; then
        install_name_tool -change "$lib" "@executable_path/../lib/$base" "$binary" 2>/dev/null || true
      fi
      continue
    fi
    base="$(basename "$resolved")"
    if [[ -f "$LIB/$base" ]]; then
      install_name_tool -change "$lib" "@executable_path/../lib/$base" "$binary" 2>/dev/null || true
    fi
  done
}

for binary in "$BIN"/* "$LIB"/*; do
  [[ -f "$binary" ]] || continue
  rewrite_load_commands "$binary"
done

# install_name_tool invalide la signature → re-signature ad-hoc obligatoire (sinon SIGKILL).
for binary in "$BIN"/* "$LIB"/*; do
  [[ -f "$binary" ]] || continue
  codesign --force --sign - "$binary" >/dev/null 2>&1 || true
done

LIBHEIF_PREFIX="$(brew --prefix libheif 2>/dev/null || true)"
if [[ -n "$LIBHEIF_PREFIX" && -d "$LIBHEIF_PREFIX/lib" ]]; then
  for dylib in "$LIBHEIF_PREFIX/lib/"*.dylib; do
    [[ -f "$dylib" ]] || continue
    cp "$dylib" "$LIB/"
    codesign --force --sign - "$LIB/$(basename "$dylib")" >/dev/null 2>&1 || true
  done
fi

# Smoke test: les binaires Poppler doivent démarrer hors de Homebrew.
if ! "$BIN/pdfinfo" -v >/dev/null 2>&1; then
  echo "Échec: pdfinfo vendored ne démarre pas (dylibs manquantes ?)." >&2
  "$BIN/pdfinfo" -v || true
  exit 1
fi
if ! "$BIN/pdftoppm" -v >/dev/null 2>&1; then
  echo "Échec: pdftoppm vendored ne démarre pas (dylibs manquantes ?)." >&2
  "$BIN/pdftoppm" -v || true
  exit 1
fi

echo "Binaires OCR préparés dans $VENDOR"
