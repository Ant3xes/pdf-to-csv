from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from decimal import Decimal

from app.amounts import MontantHt
from app.models import STATUT_A_VERIFIER, LigneFacture

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

# Séparateurs de milliers : point/espace (EU) ou virgule/espace (US).
_AMOUNT_NUM = r"(-?\d[\d.\s]*,\d{2}|-?\d[\d,\s]*\.\d{2})"
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
    rf"Total\s+H\.?\s*T\.?(?:\s+(?:en\s+)?(?:€|EURO|EUR))?[\s:]*{_AMOUNT_NUM}",
    rf"Net\s+H\.?\s*T\.?\s*{_AMOUNT_NUM}",
    rf"Montant\s+H\.?\s*T\.?\s*:?\s*{_AMOUNT_NUM}",
)


def normalize_date(raw: str, date_formats: list[str]) -> str | None:
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


def ascii_fold(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _month_from_french_name(name: str) -> str | None:
    folded = ascii_fold(name).strip(".-—–\u00ad ")
    for prefix, month in FRENCH_MONTH_PREFIXES:
        if folded.startswith(prefix):
            return month
    return None


def _context_window(text: str, start: int, end: int, radius: int = 40) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def _has_negative_date_context(window: str) -> bool:
    return bool(_DATE_NEGATIVE_FOLDED.search(ascii_fold(window)))


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
            normalized = normalize_date(match.group(1), GENERIC_DATE_FORMATS)
            if normalized:
                candidates.append(normalized)
    return candidates


def generic_date(text: str) -> str | None:
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


def generic_amount(text: str) -> MontantHt | None:
    candidates: list[MontantHt] = []
    for pattern in _GENERIC_AMOUNT_LABELS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            label_prefix = text[max(0, match.start() - 30) : match.start()]
            if re.search(r"(?:T\.?\s*T\.?\s*C\.?|TVA|T\.V\.A)\s*$", label_prefix, re.I):
                continue
            if re.search(r"Total\s+T\.?\s*T\.?\s*C\.?\s*$", label_prefix, re.I):
                continue
            raw = match.group(1)
            sep = "," if "," in raw else "."
            normalized = MontantHt.from_raw(raw, sep)
            if normalized:
                candidates.append(normalized)
    return _unique_montant_or_none(candidates)


def _unique_montant_or_none(values: list[MontantHt]) -> MontantHt | None:
    unique: list[MontantHt] = []
    seen: set[Decimal] = set()
    for value in values:
        if value.value in seen:
            continue
        seen.add(value.value)
        unique.append(value)
    if len(unique) == 1:
        return unique[0]
    return None


def apply_generic_fallback(
    text: str,
    *,
    fichier: str,
    type_document: str,
) -> LigneFacture:
    """Filet déterministe : date + montant HT, jamais d'Émetteur."""
    return LigneFacture(
        fichier=fichier,
        emetteur=None,
        date=generic_date(text),
        montant_ht=generic_amount(text),
        statut=STATUT_A_VERIFIER,
        type_document=type_document,
    )
