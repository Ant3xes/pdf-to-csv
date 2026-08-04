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
# Longest-first prefixes for abbreviated / punctuated month names (Youtrust, etc.).
FRENCH_MONTH_PREFIXES = (
    ("janvier", "01"),
    ("janv", "01"),
    ("fevrier", "02"),
    ("fevr", "02"),
    ("fev", "02"),
    ("mars", "03"),
    ("avril", "04"),
    ("avr", "04"),
    ("mai", "05"),
    ("juin", "06"),
    ("juillet", "07"),
    ("juil", "07"),
    ("aout", "08"),
    ("aou", "08"),
    ("septembre", "09"),
    ("sept", "09"),
    ("sep", "09"),
    ("octobre", "10"),
    ("oct", "10"),
    ("novembre", "11"),
    ("nov", "11"),
    ("decembre", "12"),
    ("dec", "12"),
)

GENERIC_DATE_FORMATS = [
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%d.%m.%Y",
    "%d.%m.%y",
]

_AMOUNT_NUM = r"(-?\d[\d\s]*(?:[,.]\d{2}))"
_DATE_NUM = r"(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})"

# Strong labeled date anchors (preferred over bare "le …").
_GENERIC_DATE_STRONG = (
    rf"Date\s+de\s+la\s+facture\s*{_DATE_NUM}",
    rf"Date\s+de\s+facturation\s*:?\s*{_DATE_NUM}",
    rf"Date\s+d['’]édition\s*:?\s*{_DATE_NUM}",
    rf"Date\s+d['’]edition\s*:?\s*{_DATE_NUM}",
    rf"Date\s+facture\s*\*?\s*:?\s*{_DATE_NUM}",
    rf"Date\s+d['’]émission\s*:?\s*{_DATE_NUM}",
    rf"Date\s+d['’]emission\s*:?\s*{_DATE_NUM}",
    rf"Date\s*:?\s*{_DATE_NUM}",
    rf"Facture\s+N[°o]\s*[\w./\-]*\s+du\s+{_DATE_NUM}",
    rf"N[°o]\s+\d+\s+du\s+{_DATE_NUM}",
)

_GENERIC_DATE_WEAK = (
    rf",\s*le\s+{_DATE_NUM}",
    rf"(?<![A-Za-z])le\s+{_DATE_NUM}",
)

_GENERIC_DATE_MONTH_FIRST = (
    r"Date\s+de\s+la\s+facture\s+"
    r"([A-Za-zÀ-ÿ]{3,10})[\s.\u2014\u2013\u00ad\-—]*\s*(\d{1,2})\s*,\s*(\d{4})"
)

_DATE_NEGATIVE_FOLDED = re.compile(
    r"(?:echeanc|payable|au\s+plus\s+tard|periode|"
    r"avant\s+le|expedition|livraison|reference|"
    r"prochaine\s+date|expire)",
)

_GENERIC_AMOUNT_LABELS = (
    rf"Total\s+T\.?\s*T\.?\s*C\.?(?:\s+(?:en\s+)?(?:€|EURO|EUR))?[\s:]*{_AMOUNT_NUM}",
    rf"Montant\s+de\s+la\s+facture\s*{_AMOUNT_NUM}",
    rf"Net\s+TTC\s+[àa]\s+{_AMOUNT_NUM}",
    rf"Net\s+[àa]\s+payer\s*:?\s*{_AMOUNT_NUM}",
    rf"NET\s+A\s+PAYER\s*:?\s*{_AMOUNT_NUM}",
    rf"Total\s+[àa]\s+payer\s*{_AMOUNT_NUM}",
    rf"Montant\s+TTC\s*:?\s*{_AMOUNT_NUM}",
    rf"Montant\s*:?\s*{_AMOUNT_NUM}\s*(?:EUR|€)",
)


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
    if match:
        day, month_name, year = match.groups()
        month = _month_from_french_name(month_name)
        if month is None:
            return None
        return f"{int(day):02d}/{month}/{year}"
    # Month-first abbreviated (ex. Youtrust: "juil—. 19, 2026")
    match = re.fullmatch(
        r"\s*([A-Za-z]+)[\s.\-]*\s*(\d{1,2})\s*,\s*(\d{4})\s*",
        normalized,
    )
    if not match:
        return None
    month_name, day, year = match.groups()
    month = _month_from_french_name(month_name)
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


def _ascii_fold(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _month_from_french_name(name: str) -> str | None:
    folded = _ascii_fold(name).strip(".-—–\u00ad ")
    for prefix, month in FRENCH_MONTH_PREFIXES:
        if folded.startswith(prefix):
            return month
    return None


def _context_window(text: str, start: int, end: int, radius: int = 40) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def _has_negative_date_context(window: str) -> bool:
    return bool(_DATE_NEGATIVE_FOLDED.search(_ascii_fold(window)))


def _unique_or_none(values: list[str]) -> str | None:
    unique = list(dict.fromkeys(values))
    if len(unique) == 1:
        return unique[0]
    return None


def _collect_dated_matches(text: str, patterns: tuple[str, ...]) -> list[str]:
    candidates: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            window = _context_window(text, match.start(), match.end())
            if _has_negative_date_context(window):
                continue
            normalized = _normalize_date(match.group(1), GENERIC_DATE_FORMATS)
            if normalized:
                candidates.append(normalized)
    return candidates


def _generic_date(text: str) -> str | None:
    strong = _collect_dated_matches(text, _GENERIC_DATE_STRONG)
    month_first = re.search(_GENERIC_DATE_MONTH_FIRST, text, flags=re.IGNORECASE)
    if month_first:
        month = _month_from_french_name(month_first.group(1))
        if month:
            day, year = month_first.group(2), month_first.group(3)
            strong.append(f"{int(day):02d}/{month}/{year}")
    strong_pick = _unique_or_none(strong)
    if strong_pick is not None or strong:
        # Unique strong → use it; multiple distinct strong → empty (prudent).
        return strong_pick
    return _unique_or_none(_collect_dated_matches(text, _GENERIC_DATE_WEAK))


def _generic_amount(text: str) -> str | None:
    candidates: list[str] = []
    for pattern in _GENERIC_AMOUNT_LABELS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            label_prefix = text[max(0, match.start() - 30) : match.start()]
            if re.search(r"(?:H\.?\s*T\.?|TVA|T\.V\.A)\s*$", label_prefix, re.I):
                continue
            if re.search(r"Total\s+H\.?\s*T\.?\s*$", label_prefix, re.I):
                continue
            raw = match.group(1)
            sep = "," if "," in raw else "."
            normalized = _normalize_amount(raw, sep)
            if normalized:
                candidates.append(normalized)
    return _unique_or_none(candidates)


def _apply_generic_fallback(text: str) -> tuple[str | None, str | None]:
    """Filet déterministe : date + montant TTC, jamais d'Émetteur."""
    return _generic_date(text), _generic_amount(text)


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
        else:
            date, montant = _apply_generic_fallback(source.text)

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
