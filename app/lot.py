from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from app.corrections import corriger_ligne
from app.extraction import (
    extract_document_text,
    is_supported_document,
    supported_document_formats_label,
)
from app.models import STATUT_OK, TYPE_AVOIR, TYPE_FACTURE, LigneFacture, Template
from app.normalisation import apply_generic_fallback, ascii_fold
from app.templates_loader import apply_template, load_templates, matching_templates

if TYPE_CHECKING:
    from app.diagnostics import DiagnosticJournal

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


def _template_detection_label(matches: list[Template]) -> str:
    if len(matches) == 0:
        return "aucun Template"
    if len(matches) == 1:
        return f"Template={matches[0].issuer}"
    issuers = ", ".join(t.issuer for t in matches)
    return f"Détection ambiguë ({issuers})"


def _raisons_diagnostic(
    *,
    from_ocr: bool,
    match_count: int,
    ligne: LigneFacture,
) -> list[str]:
    if ligne.statut == STATUT_OK:
        return []
    reasons: list[str] = []
    if match_count == 0:
        reasons.append("aucun Template")
    elif match_count > 1:
        reasons.append("Détection ambiguë")
    if from_ocr:
        reasons.append("OCR")
    if not ligne.emetteur:
        reasons.append("émetteur manquant")
    if not ligne.date:
        reasons.append("date manquante ou invalide")
    if not ligne.montant_ht:
        reasons.append("montant HT manquant ou invalide")
    return reasons or ["À vérifier"]


def _record_ligne(
    journal: DiagnosticJournal,
    *,
    ligne: LigneFacture,
    from_ocr: bool,
    matches: list[Template],
) -> None:
    montant = ligne.montant_ht.format_fr() if ligne.montant_ht else ""
    raisons = _raisons_diagnostic(
        from_ocr=from_ocr, match_count=len(matches), ligne=ligne
    )
    journal.record(
        f"fichier={ligne.fichier} "
        f"source={'OCR' if from_ocr else 'natif'} "
        f"detection={_template_detection_label(matches)} "
        f"type={ligne.type_document} "
        f"emetteur={ligne.emetteur or ''} "
        f"date={ligne.date or ''} "
        f"montant_ht={montant} "
        f"statut={ligne.statut} "
        f"raisons={';'.join(raisons) if raisons else 'OK'}"
    )


def process_lot(
    document_paths: list[Path | str],
    templates_dir: Path | str,
    journal: DiagnosticJournal | None = None,
) -> list[LigneFacture]:
    templates = load_templates(Path(templates_dir))
    lignes: list[LigneFacture] = []

    for document_path in document_paths:
        path = Path(document_path)
        source = extract_document_text(path)
        matches = matching_templates(source.text, templates)
        type_document = _classify_document(source.text, path.name)

        if len(matches) == 1:
            ligne = apply_template(
                source.text,
                matches[0],
                fichier=path.name,
                from_ocr=source.from_ocr,
                type_document=type_document,
            )
        else:
            ligne = apply_generic_fallback(
                source.text,
                fichier=path.name,
                type_document=type_document,
            )
        lignes.append(ligne)
        if journal is not None:
            _record_ligne(
                journal,
                ligne=ligne,
                from_ocr=source.from_ocr,
                matches=matches,
            )

    return lignes
