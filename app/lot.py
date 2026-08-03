from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pdfplumber
import yaml

from app.models import LigneFacture

STATUT_OK = "OK"
STATUT_A_VERIFIER = "A_VERIFIER"


def _extract_text(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


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
    return None


def _normalize_amount(raw: str, decimal_separator: str) -> str | None:
    cleaned = raw.strip().replace(" ", "")
    if decimal_separator == ",":
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
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

    emetteur = template.get("issuer")
    raw_date = _extract_field(text, fields["date"]) if "date" in fields else None
    raw_amount = _extract_field(text, fields["amount"]) if "amount" in fields else None

    date = _normalize_date(raw_date, date_formats) if raw_date else None
    montant = _normalize_amount(raw_amount, decimal_separator) if raw_amount else None
    return emetteur, date, montant


def process_lot(
    pdf_paths: list[Path | str],
    templates_dir: Path | str,
) -> list[LigneFacture]:
    templates = _load_templates(Path(templates_dir))
    lignes: list[LigneFacture] = []

    for pdf_path in pdf_paths:
        path = Path(pdf_path)
        text = _extract_text(path)
        matches = _matching_templates(text, templates)

        emetteur = date = montant = None
        statut = STATUT_A_VERIFIER

        if len(matches) == 1:
            emetteur, date, montant = _apply_template(text, matches[0])
            if emetteur and date and montant:
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
