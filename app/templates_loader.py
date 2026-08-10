from __future__ import annotations

import re
from pathlib import Path

import yaml

from app.models import STATUT_A_VERIFIER, STATUT_OK, TYPE_AVOIR, LigneFacture, Template
from app.amounts import MontantHt
from app.normalisation import normalize_date


def load_templates(templates_dir: Path) -> list[Template]:
    templates: list[Template] = []
    for path in sorted(templates_dir.glob("*.yml")) + sorted(
        templates_dir.glob("*.yaml")
    ):
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if data:
            templates.append(Template.from_mapping(data))
    return templates


def _keywords_match(text: str, keywords: tuple[str, ...]) -> bool:
    lower = text.lower()
    return all(keyword.lower() in lower for keyword in keywords)


def matching_templates(text: str, templates: list[Template]) -> list[Template]:
    return [t for t in templates if _keywords_match(text, t.keywords)]


def _extract_field(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1) if match.lastindex else match.group(0)


def apply_template(
    text: str,
    template: Template,
    *,
    fichier: str,
    from_ocr: bool,
    type_document: str,
) -> LigneFacture:
    raw_date = (
        _extract_field(text, template.date_pattern) if template.date_pattern else None
    )
    raw_amount = (
        _extract_field(text, template.amount_pattern)
        if template.amount_pattern
        else None
    )

    date = (
        normalize_date(raw_date, list(template.date_formats)) if raw_date else None
    )
    amount_sign = template.amount_sign if type_document == TYPE_AVOIR else None
    # amount_sign YAML ne s'applique qu'aux Avoirs — une Facture reste positive.
    montant = (
        MontantHt.from_raw(raw_amount, template.decimal_separator, amount_sign)
        if raw_amount
        else None
    )
    emetteur = template.issuer
    # OCR → À vérifier systématique (prudence CONTEXT.md), même si date/montant OK.
    statut = (
        STATUT_OK
        if emetteur and date and montant and not from_ocr
        else STATUT_A_VERIFIER
    )
    return LigneFacture(
        fichier=fichier,
        emetteur=emetteur,
        date=date,
        montant_ht=montant,
        statut=statut,
        type_document=type_document,
    )
