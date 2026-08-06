from __future__ import annotations

import re
from pathlib import Path

from app.corrections import corriger_ligne
from app.extraction import (
    extract_document_text,
    is_supported_document,
    supported_document_formats_label,
)
from app.models import TYPE_AVOIR, TYPE_FACTURE, LigneFacture
from app.normalisation import apply_generic_fallback, ascii_fold
from app.templates_loader import apply_template, load_templates, matching_templates

# Réexport du contrat public historique (tests / web).
__all__ = [
    "corriger_ligne",
    "is_supported_document",
    "process_lot",
    "supported_document_formats_label",
]

# Marqueurs documentaires uniquement — pas le verbe « avoir » ni les CGV
# (« ni à un avoir ni… », « reconnaît avoir connaissance… »).
_AVOIR_MARKERS_TEXT = (
    r"(?m)^AVOIR\b",
    r"\bAVOIR\s+du\b",
    r"\bAVOIR\s+n[°o]\b",
    r"\bvotre\s+avoir\b",
    r"note\s+de\s+cr[eé]dit",
    r"r[eé]capitulatif\s+de\s+votre\s+avoir",
    r"(?m)^CREDIT\b",
)
_AVOIR_MARKERS_FILENAME = (r"\bavoir\b",)


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _classify_document(text: str, filename: str) -> str:
    """FACTURE ou AVOIR. En cas de doute → FACTURE (sauf AVOIR dans le titre / nom)."""
    if _matches_any(ascii_fold(filename), _AVOIR_MARKERS_FILENAME):
        return TYPE_AVOIR
    if _matches_any(text, _AVOIR_MARKERS_TEXT):
        return TYPE_AVOIR
    return TYPE_FACTURE


def process_lot(
    document_paths: list[Path | str],
    templates_dir: Path | str,
) -> list[LigneFacture]:
    templates = load_templates(Path(templates_dir))
    lignes: list[LigneFacture] = []

    for document_path in document_paths:
        path = Path(document_path)
        source = extract_document_text(path)
        matches = matching_templates(source.text, templates)
        type_document = _classify_document(source.text, path.name)

        if len(matches) == 1:
            lignes.append(
                apply_template(
                    source.text,
                    matches[0],
                    fichier=path.name,
                    from_ocr=source.from_ocr,
                    type_document=type_document,
                )
            )
        else:
            lignes.append(
                apply_generic_fallback(
                    source.text,
                    fichier=path.name,
                    type_document=type_document,
                )
            )

    return lignes
