from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber
import pytesseract
import yaml
from pdf2image import convert_from_path

from app.models import LigneFacture

STATUT_OK = "OK"
STATUT_A_VERIFIER = "A_VERIFIER"

# Below this, native text is treated as empty/insufficient → OCR fallback.
MIN_NATIVE_CHARS = 50
# Page image covering at least this fraction of the page → scanned page.
FULL_PAGE_IMAGE_RATIO = 0.9
OCR_DPI = 200
OCR_LANG = "fra"
FRENCH_MONTHS = {
    "janvier": "01",
    "fevrier": "02",
    "mars": "03",
    "avril": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07",
    "aout": "08",
    "septembre": "09",
    "octobre": "10",
    "novembre": "11",
    "decembre": "12",
}


@dataclass(frozen=True)
class SourceText:
    text: str
    from_ocr: bool


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
    images = convert_from_path(pdf_path, dpi=OCR_DPI)
    return "\n".join(
        pytesseract.image_to_string(image, lang=OCR_LANG) for image in images
    )


def _extract_text(pdf_path: Path) -> SourceText:
    with pdfplumber.open(pdf_path) as pdf:
        native = _extract_native_text(pdf)
        scanned = _is_scanned_pdf(pdf)

    if len(native.strip()) >= MIN_NATIVE_CHARS:
        # Full-page image PDFs often carry an OCR text layer already; treat
        # that source as OCR so statut stays A_VERIFIER (CONTEXT rule 6).
        return SourceText(text=native, from_ocr=scanned)

    return SourceText(text=_extract_ocr_text(pdf_path), from_ocr=True)


def _load_templates(templates_dir: Path) -> list[dict]:
    templates: list[dict] = []
    for path in sorted(templates_dir.glob("*.yml")) + sorted(
        templates_dir.glob("*.yaml")
    ):
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if data:
            templates.append(data)
    return templates


def _keywords_match(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return all(keyword.lower() in lower for keyword in keywords)


def _matching_templates(text: str, templates: list[dict]) -> list[dict]:
    return [t for t in templates if _keywords_match(text, t.get("keywords") or [])]


def _normalize_date(raw: str, date_formats: list[str]) -> str | None:
    for fmt in date_formats:
        try:
            return datetime.strptime(raw, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    normalized = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode(
        "ascii"
    )
    match = re.fullmatch(r"\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*", normalized)
    if not match:
        return None
    day, month_name, year = match.groups()
    month = FRENCH_MONTHS.get(month_name.lower())
    if month is None:
        return None
    return f"{int(day):02d}/{month}/{year}"


def _normalize_amount(
    raw: str, decimal_separator: str, amount_sign: str | None = None
) -> str | None:
    cleaned = raw.strip().replace(" ", "")
    if decimal_separator == ",":
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if amount_sign == "negative" and value > 0:
        value = -value
    return f"{value:.2f}".replace(".", ",")


def _extract_field(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1) if match.lastindex else match.group(0)


def _apply_template(text: str, template: dict) -> tuple[str | None, str | None, str | None]:
    options = template.get("options") or {}
    fields = template.get("fields") or {}
    date_formats = options.get("date_formats") or ["%d/%m/%Y", "%d/%m/%y"]
    decimal_separator = options.get("decimal_separator") or ","
    amount_sign = options.get("amount_sign")

    emetteur = template.get("issuer")
    raw_date = _extract_field(text, fields["date"]) if "date" in fields else None
    raw_amount = _extract_field(text, fields["amount"]) if "amount" in fields else None

    date = _normalize_date(raw_date, date_formats) if raw_date else None
    montant = (
        _normalize_amount(raw_amount, decimal_separator, amount_sign)
        if raw_amount
        else None
    )
    return emetteur, date, montant


def process_lot(
    pdf_paths: list[Path | str],
    templates_dir: Path | str,
) -> list[LigneFacture]:
    templates = _load_templates(Path(templates_dir))
    lignes: list[LigneFacture] = []

    for pdf_path in pdf_paths:
        path = Path(pdf_path)
        source = _extract_text(path)
        matches = _matching_templates(source.text, templates)

        emetteur = date = montant = None
        statut = STATUT_A_VERIFIER

        if len(matches) == 1:
            emetteur, date, montant = _apply_template(source.text, matches[0])
            if emetteur and date and montant and not source.from_ocr:
                statut = STATUT_OK

        lignes.append(
            LigneFacture(
                fichier=path.name,
                emetteur=emetteur,
                date=date,
                montant_ttc=montant,
                statut=statut,
            )
        )

    return lignes


_UNSET: Any = object()


def corriger_ligne(
    ligne: LigneFacture,
    *,
    emetteur: str | None = _UNSET,
    date: str | None = _UNSET,
    montant_ttc: str | None = _UNSET,
) -> LigneFacture:
    """Correction manuelle éphémère : nouvelle ligne, templates intacts."""
    updates: dict[str, str | None] = {}
    if emetteur is not _UNSET:
        updates["emetteur"] = emetteur
    if date is not _UNSET:
        updates["date"] = date
    if montant_ttc is not _UNSET:
        updates["montant_ttc"] = montant_ttc
    return replace(ligne, **updates)
