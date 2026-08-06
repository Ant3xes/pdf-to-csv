from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pytesseract

VENDOR_BIN = Path("vendor") / "bin"
VENDOR_ROOT = Path("vendor")


@dataclass(frozen=True)
class RuntimePaths:
    tesseract_cmd: str | None
    poppler_path: str | None
    tessdata_prefix: str | None


_poppler_path: str | None = None


def is_packaged() -> bool:
    return bool(getattr(sys, "frozen", False))


def _bundle_root(*, bundle_root: Path | None, packaged: bool | None) -> Path | None:
    if bundle_root is not None:
        return bundle_root
    if packaged if packaged is not None else is_packaged():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return None


def resolve_runtime_paths(
    *,
    bundle_root: Path | None = None,
    packaged: bool | None = None,
) -> RuntimePaths:
    root = _bundle_root(bundle_root=bundle_root, packaged=packaged)
    if root is None:
        return RuntimePaths(None, None, None)

    bin_dir = root / VENDOR_BIN
    tessdata_dir = root / VENDOR_ROOT / "tessdata"
    return RuntimePaths(
        tesseract_cmd=str(bin_dir / "tesseract"),
        poppler_path=str(bin_dir),
        tessdata_prefix=str(tessdata_dir),
    )


def get_poppler_path() -> str | None:
    return _poppler_path


def reset_runtime_paths() -> None:
    global _poppler_path

    _poppler_path = None
    pytesseract.pytesseract.tesseract_cmd = "tesseract"
    os.environ.pop("TESSDATA_PREFIX", None)


def configure_runtime_paths(
    paths: RuntimePaths | None = None,
    *,
    bundle_root: Path | None = None,
    packaged: bool | None = None,
) -> RuntimePaths:
    global _poppler_path

    resolved = paths or resolve_runtime_paths(bundle_root=bundle_root, packaged=packaged)

    if resolved.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = resolved.tesseract_cmd
    if resolved.tessdata_prefix:
        os.environ["TESSDATA_PREFIX"] = resolved.tessdata_prefix
    else:
        os.environ.pop("TESSDATA_PREFIX", None)

    _poppler_path = resolved.poppler_path
    return resolved
