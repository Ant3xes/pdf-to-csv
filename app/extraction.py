from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover - HEIC tests skip if missing
    pillow_heif = None

from app.runtime_paths import get_poppler_path

SUPPORTED_DOCUMENT_SUFFIXES = frozenset({".pdf", ".jpg", ".jpeg", ".png", ".heic"})

# Below this, native text is treated as empty/insufficient → OCR fallback.
MIN_NATIVE_CHARS = 50
# Page image covering at least this fraction of the page → scanned page.
FULL_PAGE_IMAGE_RATIO = 0.9
OCR_DPI = 200
OCR_LANG = "fra"


@dataclass(frozen=True)
class SourceText:
    text: str
    from_ocr: bool


def is_supported_document(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES


def supported_document_formats_label() -> str:
    return ", ".join(sorted(SUPPORTED_DOCUMENT_SUFFIXES))


def _page_max_image_ratio(page) -> float:
    area = page.width * page.height
    if area <= 0:
        return 0.0
    max_ratio = 0.0
    for image in page.images:
        width = image.get("width", abs(image["x1"] - image["x0"]))
        height = image.get("height", abs(image["y1"] - image["y0"]))
        max_ratio = max(max_ratio, (width * height) / area)
    return max_ratio


def _is_scanned_pdf(pdf) -> bool:
    if not pdf.pages:
        return False
    return all(
        _page_max_image_ratio(page) >= FULL_PAGE_IMAGE_RATIO for page in pdf.pages
    )


def _extract_native_text(pdf) -> str:
    return "\n".join((page.extract_text() or "") for page in pdf.pages)


def _extract_ocr_text(pdf_path: Path) -> str:
    convert_kwargs: dict = {"dpi": OCR_DPI}
    poppler_path = get_poppler_path()
    if poppler_path:
        convert_kwargs["poppler_path"] = poppler_path
    images = convert_from_path(pdf_path, **convert_kwargs)
    return "\n".join(
        pytesseract.image_to_string(image, lang=OCR_LANG) for image in images
    )


def _extract_ocr_from_image(image: Image.Image) -> str:
    return pytesseract.image_to_string(image, lang=OCR_LANG)


def _extract_text_from_image(image_path: Path) -> SourceText:
    with Image.open(image_path) as image:
        text = _extract_ocr_from_image(image.convert("RGB"))
    return SourceText(text=text, from_ocr=True)


def _extract_text_from_pdf(pdf_path: Path) -> SourceText:
    with pdfplumber.open(pdf_path) as pdf:
        native = _extract_native_text(pdf)
        scanned = _is_scanned_pdf(pdf)

    if len(native.strip()) >= MIN_NATIVE_CHARS:
        # Full-page image PDFs often carry an OCR text layer already; treat
        # that source as OCR so statut stays A_VERIFIER (CONTEXT rule 6).
        return SourceText(text=native, from_ocr=scanned)

    return SourceText(text=_extract_ocr_text(pdf_path), from_ocr=True)


def extract_document_text(document_path: Path) -> SourceText:
    suffix = document_path.suffix.lower()
    if suffix == ".pdf":
        return _extract_text_from_pdf(document_path)
    if suffix in SUPPORTED_DOCUMENT_SUFFIXES - {".pdf"}:
        if suffix == ".heic" and pillow_heif is None:
            raise RuntimeError(
                "Le support HEIC nécessite le paquet pillow-heif. "
                "Installez-le via pip install pillow-heif."
            )
        return _extract_text_from_image(document_path)
    raise ValueError(
        f"Format non supporté pour «{document_path.name}». "
        f"Formats acceptés : {supported_document_formats_label()}."
    )
